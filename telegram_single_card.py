"""
단일 카드뉴스(1장) → 텔레그램 저장 채널 전송.

- 뉴스는 news.py의 trusted / market impact / low-quality 필터를 재사용해 '팩트 게이트'에 가깝게 선별
- 이미지는 Pillow로 합성(배경 사진 + 하단 그라데이션 + 헤드라인). media_group 미사용.
"""
from __future__ import annotations

import io
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

import news as news_module

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFilter = None  # type: ignore
    ImageFont = None  # type: ignore

W, H = 1080, 1350
PAD_X = 56
BOTTOM_ZONE = 620
# NewsAPI urlToImage는 기사와 안 맞는 경우가 많아 기본은 끔(그라데이션 배경)
TELEGRAM_CARD_USE_NEWS_IMAGE = (os.getenv("TELEGRAM_CARD_USE_NEWS_IMAGE") or "false").lower() == "true"
_CARD_TMPL = (os.getenv("CARD_TEMPLATE") or "photo").strip().lower()
CARD_TEMPLATE = _CARD_TMPL if _CARD_TMPL in ("photo", "badge", "quote") else "photo"


def _font_candidates() -> List[str]:
    env = (os.getenv("CARD_FONT_PATH") or "").strip()
    out: List[str] = []
    if env:
        out.append(env)
    out.extend(
        [
            r"C:\Windows\Fonts\malgunbd.ttf",
            r"C:\Windows\Fonts\malgun.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    return out


def _load_font(size: int) -> Any:
    for path in _font_candidates():
        if not path or not os.path.isfile(path):
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _has_cjk(s: str) -> bool:
    return bool(re.search(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]", s))


def _clamp_title(title: str, max_len: int = 140) -> str:
    t = re.sub(r"\s+", " ", (title or "").strip())
    return t[:max_len] + ("…" if len(t) > max_len else "")


def _subtitle_from_article(article: Dict[str, Any]) -> str:
    desc = (article.get("description") or article.get("content") or "").strip()
    desc = re.sub(r"\s+", " ", desc)
    if len(desc) > 280:
        return desc[:277] + "…"
    return desc


def _article_image_url(article: Dict[str, Any]) -> str:
    u = str(article.get("urlToImage") or "").strip()
    if u.lower().startswith("http"):
        return u
    return ""


def _fallbacks_dir() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "assets", "fallbacks"))


def _pick_fallback_background_path(article: Dict[str, Any]) -> Optional[str]:
    """BoA/삼성형 레퍼런스용 스톡 배경 — 키워드별 assets/fallbacks/*.jpg"""
    root = _fallbacks_dir()
    title = news_module.clean_spaces(article.get("title", "") or "").lower()
    desc = news_module.clean_spaces(
        article.get("description", "") or article.get("content", "") or ""
    ).lower()
    blob = f"{title} {desc}"

    rules: List[Tuple[Tuple[str, ...], str]] = [
        (
            ("iran", "israel", "war", "attack", "missile", "ceasefire", "military"),
            "market_01.jpg",
        ),
        (
            (
                "semiconductor",
                "chip",
                "nvidia",
                "data center",
                "ai ",
                "삼성",
                "samsung",
                "calbee",
                "packaging",
            ),
            "market_02.jpg",
        ),
        (("oil", "crude", "wti", "brent", "gold", "silver", "commodit"), "market_03.jpg"),
        (("japan", "korea", "china", "yuan", "yen", "asia", "tokyo"), "market_04.jpg"),
        (("fed", "inflation", "cpi", "tariff", "rate cut", "treasury", "dollar"), "market_05.jpg"),
    ]
    for keys, fname in rules:
        if any(k in blob for k in keys):
            p = os.path.join(root, fname)
            if os.path.isfile(p):
                return p
    default = os.path.join(root, "default_market.jpg")
    return default if os.path.isfile(default) else None


def _open_fallback_cover(path: str, tw: int, th: int) -> Optional[Image.Image]:
    if Image is None:
        return None
    try:
        raw = Image.open(path).convert("RGB")
        return _cover_background(raw, tw, th)
    except Exception as e:
        print(f"[telegram_single_card] fallback bg open failed {path!r}: {repr(e)}")
        return None


def _apply_photo_bottom_gradient(img: Image.Image) -> None:
    """전면 사진 위 하단만 눌러 제목 대비(레퍼런스 BoA/삼성형)."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    y0 = int(img.height * 0.46)
    for y in range(y0, img.height):
        t = (y - y0) / max(img.height - y0 - 1, 1)
        alpha = int(25 + 215 * (t**0.92))
        d.line([(0, y), (img.width, y)], fill=(0, 0, 0, min(alpha, 238)))
    img.alpha_composite(overlay)


def _download_image(url: str, timeout: int = 12) -> Optional[Image.Image]:
    if not url or Image is None:
        return None
    try:
        r = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; jadonnam-card/1.0)"},
        )
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception as e:
        print(f"[telegram_single_card] bg download failed: {repr(e)}")
        return None


def _cover_background(img: Image.Image, tw: int, th: int) -> Image.Image:
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _solid_background(tw: int, th: int) -> Image.Image:
    """무이미지일 때 쓰는 배경 — 거의 순흑 대신 뉴스레터형 슬레이트 그라데이션."""
    base = Image.new("RGB", (tw, th))
    g = ImageDraw.Draw(base)
    for y in range(th):
        t = y / max(th - 1, 1)
        r = int(32 - t * 18)
        gg = int(36 - t * 20)
        b = int(58 - t * 32)
        g.line([(0, y), (tw, y)], fill=(max(r, 12), max(gg, 14), max(b, 22)))
    return base


def _apply_bottom_gradient(base: Image.Image) -> None:
    """하단만 살짝 눌러 가독성 확보(이전보다 약하게 — 전체가 보라·검정으로 묻히지 않게)."""
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    y0 = base.height - BOTTOM_ZONE
    for y in range(y0, base.height):
        t = (y - y0) / max(BOTTOM_ZONE - 1, 1)
        alpha = int(12 + 100 * (t**1.08))
        d.line([(0, y), (base.width, y)], fill=(0, 0, 0, min(alpha, 155)))
    base.alpha_composite(overlay)


def _draw_text_outlined(
    draw: Any,
    xy: Tuple[int, int],
    text: str,
    font: Any,
    fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
    outline: Tuple[int, int, int, int] = (0, 0, 0, 230),
) -> None:
    x, y = xy
    for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
        draw.text((x + ox, y + oy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


def _wrap_lines(draw: Any, text: str, font: Any, max_width: int) -> List[str]:
    lines: List[str] = []
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        words = paragraph.split()
        cur: List[str] = []
        for w in words:
            trial = " ".join(cur + [w]) if cur else w
            if draw.textlength(trial, font=font) <= max_width:
                cur.append(w)
                continue
            if cur:
                lines.append(" ".join(cur))
            # 긴 단어: 글자 단위로 잘라 넣기
            if draw.textlength(w, font=font) > max_width:
                buf = ""
                for ch in w:
                    t2 = buf + ch
                    if draw.textlength(t2, font=font) <= max_width:
                        buf = t2
                    else:
                        if buf:
                            lines.append(buf)
                        buf = ch
                cur = [buf] if buf else []
            else:
                cur = [w]
        if cur:
            lines.append(" ".join(cur))
    return lines[:9]


def _relaxed_body_passes(article: Dict[str, Any]) -> bool:
    """Strict `is_low_quality_text`는 본문 40자 미만을 배제 — 짧은 통신 요약도 카드로 쓸 수 있게 완화."""
    title = news_module.clean_spaces(article.get("title", "") or "")
    desc = news_module.clean_spaces(article.get("description", "") or article.get("content", "") or "")
    text = f"{title} {desc}".lower()
    if len(title) < 18:
        return False
    if len(desc) < 28 and len(title) < 72:
        return False
    for p in news_module.LOW_QUALITY_PATTERNS:
        if p in text:
            return False
    return True


def best_single_card_candidate_relaxed(
    articles: List[Dict[str, Any]],
) -> Tuple[int, Optional[Dict[str, Any]]]:
    best_s = -1
    best_a: Optional[Dict[str, Any]] = None
    for a in articles or []:
        if not news_module.trusted_article(a):
            continue
        if not news_module.has_market_impact(a):
            continue
        if news_module.is_press_release_wire(a):
            continue
        if not _relaxed_body_passes(a):
            continue
        url = str(a.get("url") or "").strip()
        if not url.lower().startswith("https://"):
            continue
        title = news_module.clean_spaces(a.get("title", ""))
        if len(title) < 18:
            continue
        s = news_module.score_article(a)
        if s > best_s:
            best_s = s
            best_a = a
    if best_a is None:
        return -1, None
    return best_s, best_a


def best_single_card_candidate(
    articles: List[Dict[str, Any]],
) -> Tuple[int, Optional[Dict[str, Any]]]:
    """
    pick_article_for_single_card와 동일한 팩트 게이트·점수 기준으로
    (최고 점수, 해당 기사)를 반환. 후보가 없으면 (-1, None).
    """
    best_s = -1
    best_a: Optional[Dict[str, Any]] = None
    for a in articles or []:
        if not news_module.trusted_article(a):
            continue
        if not news_module.has_market_impact(a):
            continue
        if news_module.is_press_release_wire(a):
            continue
        if news_module.is_low_quality_text(a):
            continue
        url = str(a.get("url") or "").strip()
        if not url.lower().startswith("https://"):
            continue
        title = news_module.clean_spaces(a.get("title", ""))
        if len(title) < 18:
            continue
        s = news_module.score_article(a)
        if s > best_s:
            best_s = s
            best_a = a
    if best_a is None:
        return -1, None
    return best_s, best_a


def pick_article_for_single_card(articles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    팩트 게이트(확실한 기준):
    - news.trusted_article (도메인/통신사 화이트리스트)
    - 시장 연관(has_market_impact / has_high_impact는 fetch 단계에서 이미 적용됐을 수 있음 — 재확인)
    - 저품질/라이브블로그 등 제외
    - 원문 URL 필수(https)
    - 점수: news.score_article 기준 상위 1건
    """
    _s, a = best_single_card_candidate(articles)
    return a


def _headline_split_photo(title: str, subtitle: str) -> Tuple[str, str]:
    """BoA/삼성형: 첫 줄 강조 + 둘째 줄 설명."""
    title = (title or "").strip()
    subtitle = (subtitle or "").strip()
    if " due to " in title and len(title) > 56:
        a, b = title.split(" due to ", 1)
        a, b = a.strip(), b.strip()
        if len(a) >= 18:
            rest = b.strip()
            if not rest.lower().startswith(("the ", "a ", "an ")):
                rest = "Due to " + rest
            line1 = a.strip() + " —"
            line2 = (rest + (" " + subtitle if subtitle else "")).strip()
            return line1, line2[:400]
    if ";" in title and len(title) > 72:
        a, b = title.split(";", 1)
        a, b = a.strip(), b.strip()
        if len(a) >= 20:
            line1 = a + ";"
            line2 = (b + (" " + subtitle if subtitle else "")).strip()
            return line1, line2[:380]
    if "," in title and len(title.split(",", 1)[0]) < 96:
        a, b = title.split(",", 1)
        line1 = a.strip() + ","
        line2 = (b.strip() + (" " + subtitle if subtitle else "")).strip()
        return line1, line2[:320]
    if len(title) <= 58:
        return title, subtitle
    cut = title[:58].rfind(" ")
    if cut < 12:
        cut = 58
    return title[:cut].strip(), (title[cut:].strip() + (" " + subtitle if subtitle else ""))[:320]


def _ticker_from_title(title: str) -> str:
    m = re.findall(r"\b[A-Z]{2,6}\b", title or "")
    if m:
        return m[0]
    w = re.sub(r"[^A-Za-z0-9\s]", "", title or "").split()
    if w:
        return (w[0].upper()[:6] or "NEWS")
    return "NEWS"


def _tech_datacenter_background(tw: int, th: int) -> Image.Image:
    """IREN 레퍼런스용 쿨톤 그라데이션(사진 대체)."""
    base = Image.new("RGB", (tw, th))
    g = ImageDraw.Draw(base)
    for y in range(th):
        t = y / max(th - 1, 1)
        r = int(10 + t * 28)
        gg = int(14 + t * 42)
        b = int(40 + t * 90)
        g.line([(0, y), (tw, y)], fill=(r, gg, b))
    return base


def _render_template_photo(article: Dict[str, Any], out_path: str) -> str:
    """
    BoA / 삼성형 레퍼런스: 전면 사진 + 하단 그라데이션 + 좌측 큰 제목(패널 박스 없음).
    - TELEGRAM_CARD_USE_NEWS_IMAGE=true 이고 urlToImage 유효 시 기사 이미지
    - 아니면 assets/fallbacks 키워드 스톡 → 최후 solid
    """
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")

    title = _clamp_title(article.get("title", "") or "")
    subtitle = _subtitle_from_article(article)
    source = news_module.article_source_name(article)

    bg_url = _article_image_url(article)
    base: Optional[Image.Image] = None
    bg_mode = "solid"

    if TELEGRAM_CARD_USE_NEWS_IMAGE and bg_url:
        bg = _download_image(bg_url)
        if bg is not None:
            if ImageFilter is not None:
                try:
                    bg = bg.filter(ImageFilter.GaussianBlur(radius=1.2))
                except Exception:
                    pass
            base = _cover_background(bg, W, H)
            bg_mode = "article_image"
            print(f"[telegram_single_card] bg_mode=article_image url={bg_url[:72]}…")

    if base is None:
        fp = _pick_fallback_background_path(article)
        if fp:
            base = _open_fallback_cover(fp, W, H)
            if base is not None:
                bg_mode = f"fallback:{os.path.basename(fp)}"
                print(f"[telegram_single_card] bg_mode={bg_mode}")
        if base is None:
            if bg_url and not TELEGRAM_CARD_USE_NEWS_IMAGE:
                print(
                    "[telegram_single_card] bg_mode=solid "
                    "(no fallback file — TELEGRAM_CARD_USE_NEWS_IMAGE=false)"
                )
            else:
                print("[telegram_single_card] bg_mode=solid (no usable image)")
            base = _solid_background(W, H)
            bg_mode = "solid"

    rgba = base.convert("RGBA")
    _apply_photo_bottom_gradient(rgba)
    draw = ImageDraw.Draw(rgba)

    top_left = (os.getenv("CARD_TOP_LEFT_LABEL") or "").strip()
    brand = (os.getenv("CARD_BRAND_LABEL") or "").strip()
    if top_left:
        f_tl = _load_font(22)
        _draw_text_outlined(
            draw,
            (PAD_X, 40),
            top_left,
            f_tl,
            fill=(252, 252, 255, 255),
            outline=(6, 8, 18, 200),
        )
    elif brand:
        f_tl = _load_font(22)
        _draw_text_outlined(
            draw,
            (PAD_X, 40),
            brand,
            f_tl,
            fill=(252, 252, 255, 255),
            outline=(6, 8, 18, 200),
        )

    max_text_w = W - 2 * PAD_X
    line1, line2 = _headline_split_photo(title, subtitle)
    combined = len(line1) + len(line2)
    if combined > 260:
        h1s, h2s, m1, m2 = 38, 28, 3, 7
    elif combined > 190:
        h1s, h2s, m1, m2 = 44, 32, 2, 6
    elif combined > 130:
        h1s, h2s, m1, m2 = 52, 34, 2, 5
    else:
        h1s, h2s, m1, m2 = 60, 38, 2, 4

    f_h1 = _load_font(h1s)
    f_h2 = _load_font(h2s)
    h1_lines = _wrap_lines(draw, line1, f_h1, max_text_w)[:m1]
    if not h1_lines and line1:
        h1_lines = [line1[:100]]
    h2_lines = _wrap_lines(draw, line2, f_h2, max_text_w)[:m2] if line2 else []

    body_chk = line1 + line2
    if _has_cjk(body_chk) and not os.getenv("CARD_FONT_PATH"):
        print(
            "[telegram_single_card] CJK 문자 포함 — Railway/Linux에서는 CARD_FONT_PATH(NotoSansKR 등) 설정 권장"
        )

    lh1 = max(int(h1s * 1.12), 28)
    lh2 = max(int(h2s * 1.12), 24)
    f_src = _load_font(21)
    src_line = source if source else "AP / Reuters 등"
    src_h = int(lh2 * 0.85)
    gap = 18
    block_h = len(h1_lines) * lh1 + len(h2_lines) * lh2 + gap + src_h
    top_pad = 108 if (top_left or brand) else 72
    y_text_top = max(top_pad, H - int(H * 0.44) - block_h // 4, H - block_h - 50)
    y_text_top = min(y_text_top, H - block_h - 28)

    y = y_text_top
    for ln in h1_lines:
        _draw_text_outlined(
            draw,
            (PAD_X, y),
            ln,
            f_h1,
            fill=(255, 255, 255, 255),
            outline=(4, 6, 14, 235),
        )
        y += lh1
    for ln in h2_lines:
        _draw_text_outlined(
            draw,
            (PAD_X, y),
            ln,
            f_h2,
            fill=(245, 248, 255, 255),
            outline=(4, 6, 14, 210),
        )
        y += lh2

    y += gap // 2
    _draw_text_outlined(
        draw,
        (PAD_X, min(y, H - 44)),
        src_line,
        f_src,
        fill=(210, 218, 232, 255),
        outline=(2, 4, 10, 200),
    )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rgba.convert("RGB").save(out_path, "JPEG", quality=93, optimize=True)
    print(f"[telegram_single_card] wrote {out_path} ({bg_mode})")
    return out_path


def _render_template_badge(article: Dict[str, Any], out_path: str) -> str:
    """IREN형: 쿨톤 배경 + 중앙 그린 배지(티커) + 하단 제목 스택."""
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")
    title = _clamp_title(article.get("title", "") or "")
    subtitle = _subtitle_from_article(article)
    source = news_module.article_source_name(article)

    base = _tech_datacenter_background(W, H).convert("RGBA")
    _apply_bottom_gradient(base)
    draw = ImageDraw.Draw(base)

    cx, cy = W // 2, int(H * 0.34)
    skew = 20
    poly = [
        (cx - 175 + skew, cy - 52),
        (cx + 155 + skew, cy - 66),
        (cx + 175 - skew, cy + 58),
        (cx - 155 - skew, cy + 64),
    ]
    draw.polygon(poly, fill=(46, 220, 113, 255))

    tick = _ticker_from_title(title)
    f_tick = _load_font(54)
    tw = draw.textlength(tick, font=f_tick)
    tx = int(cx - tw / 2 + 6)
    ty = int(cy - 32)
    draw.text((tx, ty), tick, font=f_tick, fill=(10, 14, 18))

    max_text_w = W - 2 * PAD_X
    stack = title
    if subtitle:
        stack = title + "\n" + subtitle
    f_body = _load_font(40)
    lines = _wrap_lines(draw, stack, f_body, max_text_w)[:5]
    y0 = H - 340
    for i, ln in enumerate(lines):
        _draw_text_outlined(draw, (PAD_X, y0 + i * int(40 * 1.22)), ln, f_body)

    f_src = _load_font(22)
    _draw_text_outlined(
        draw,
        (PAD_X, H - 52),
        f"출처: {source}" if source else "출처: 확인",
        f_src,
        fill=(210, 218, 228, 255),
    )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=92, optimize=True)
    print(f"[telegram_single_card] wrote {out_path} (badge)")
    return out_path


def _render_template_quote(article: Dict[str, Any], out_path: str) -> str:
    """HipHub형: 웜톤 배경 + 인용 박스 + 하단 대제목."""
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")
    title = _clamp_title(article.get("title", "") or "")
    subtitle = _subtitle_from_article(article)
    source = news_module.article_source_name(article)

    base = Image.new("RGB", (W, H))
    g = ImageDraw.Draw(base)
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(38 + t * 95)
        gg = int(16 + t * 38)
        b = int(20 + t * 32)
        g.line([(0, y), (W, y)], fill=(r, gg, b))
    base = base.convert("RGBA")
    _apply_bottom_gradient(base)
    draw = ImageDraw.Draw(base)

    brand = (os.getenv("CARD_BRAND_LABEL") or "ISSUE").strip()
    f_sm = _load_font(28)
    twb = draw.textlength(brand, font=f_sm)
    _draw_text_outlined(draw, (int((W - twb) / 2), 42), brand, f_sm)

    quote_txt = (subtitle or title)[:260]
    f_q = _load_font(26)
    q_lines = _wrap_lines(draw, quote_txt, f_q, W - 2 * PAD_X - 48)[:3]
    bx0, by0 = PAD_X - 6, int(H * 0.28)
    box_h = 28 + len(q_lines) * 32 + 24
    bx1, by1 = W - PAD_X + 6, by0 + box_h
    draw.rectangle([bx0, by0, bx1, by1], fill=(255, 255, 255, 248))
    try:
        draw.rectangle([bx0, by0, bx1, by1], outline=(0, 0, 0, 255), width=3)
    except TypeError:
        draw.rectangle([bx0, by0, bx1, by1], outline=(0, 0, 0, 255))

    yq = by0 + 18
    for ql in q_lines:
        draw.text((bx0 + 22, yq), ql, font=f_q, fill=(14, 14, 18))
        yq += 32

    f_big = _load_font(48)
    max_text_w = W - 2 * PAD_X
    hlines = _wrap_lines(draw, title, f_big, max_text_w)[:3]
    yb = H - 300
    for hl in hlines:
        _draw_text_outlined(draw, (PAD_X, yb), hl, f_big)
        yb += int(48 * 1.18)

    f_src = _load_font(22)
    _draw_text_outlined(
        draw,
        (PAD_X, H - 52),
        f"출처: {source}" if source else "출처: 확인",
        f_src,
        fill=(220, 226, 234, 255),
    )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=92, optimize=True)
    print(f"[telegram_single_card] wrote {out_path} (quote)")
    return out_path


def render_single_card(article: Dict[str, Any], out_path: str) -> str:
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")
    print(f"[telegram_single_card] CARD_TEMPLATE={CARD_TEMPLATE}")
    if CARD_TEMPLATE == "badge":
        return _render_template_badge(article, out_path)
    if CARD_TEMPLATE == "quote":
        return _render_template_quote(article, out_path)
    return _render_template_photo(article, out_path)


def build_telegram_caption(article: Dict[str, Any]) -> str:
    """텔레그램 캡션(1024자). 기본 minimal — 이미지에 본문이 있으므로 제목+링크 위주."""
    title = news_module.clean_spaces(article.get("title", "") or "")
    desc = _subtitle_from_article(article)
    src = news_module.article_source_name(article)
    url = str(article.get("url") or "").strip()
    minimal = (os.getenv("TELEGRAM_CAPTION_MINIMAL") or "true").lower() == "true"
    if minimal:
        parts: List[str] = []
        if title:
            parts.append("📌 " + title[:480])
        if url:
            parts.append(f"원문: {url}")
        elif src:
            parts.append(f"출처: {src}")
        cap = "\n".join(parts).strip()
        if len(cap) > 1020:
            cap = cap[:1017] + "…"
        return cap

    parts = []
    if title:
        parts.append("📌 " + title[:420])
    if desc:
        parts.append(desc[:360])
    parts.append("")
    parts.append("—")
    parts.append("신뢰 매체·시장 연관 기사만 선별했습니다.")
    if src:
        parts.append(f"출처: {src}")
    if url:
        parts.append(f"원문: {url}")
    cap = "\n".join(parts).strip()
    if len(cap) > 1020:
        cap = cap[:1017] + "…"
    return cap


def _is_valid_card_jpeg(path: Optional[str], min_bytes: int = 2800) -> bool:
    if not path or not os.path.isfile(path):
        return False
    try:
        if os.path.getsize(path) < min_bytes:
            return False
    except OSError:
        return False
    if Image is None:
        return True
    try:
        with Image.open(path) as im:
            im.load()
            w, h = im.size
        return w >= 200 and h >= 200
    except Exception:
        return False


def _render_minimal_fallback_card(article: Dict[str, Any], out_path: str) -> str:
    """고급 템플릿 실패 시에도 JPEG는 반드시 나오게 하는 최소 카드."""
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")
    title = news_module.clean_spaces(article.get("title", "") or "")[:220]
    source = news_module.article_source_name(article) or "News"
    base = _solid_background(W, H).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    y0 = int(H * 0.48)
    for y in range(y0, H):
        t = (y - y0) / max(H - y0 - 1, 1)
        alpha = int(25 + 165 * (t**1.02))
        od.line([(0, y), (W, y)], fill=(0, 0, 0, min(alpha, 210)))
    base.alpha_composite(overlay)
    draw = ImageDraw.Draw(base)
    f = _load_font(42)
    max_w = W - 2 * PAD_X
    lines = _wrap_lines(draw, title, f, max_w)[:7]
    y = H - 120 - len(lines) * int(42 * 1.2)
    y = max(PAD_X, y)
    for ln in lines:
        _draw_text_outlined(
            draw,
            (PAD_X, int(y)),
            ln,
            f,
            fill=(255, 255, 255, 255),
            outline=(6, 8, 18, 220),
        )
        y += int(42 * 1.2)
    fs = _load_font(22)
    _draw_text_outlined(
        draw,
        (PAD_X, H - 52),
        source,
        fs,
        fill=(210, 218, 232, 255),
        outline=(4, 6, 14, 200),
    )
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=88, optimize=True)
    return out_path


def run_telegram_single_card(
    *,
    articles: Optional[List[Dict[str, Any]]] = None,
    out_dir: str = "output_telegram_card",
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """기사 선별 → 1장 JPEG 생성 → (경로, 기사) 반환. 전송은 호출측."""
    if Image is None:
        print("[telegram_single_card] Pillow 없음 — 스킵")
        return None, None

    arts = articles
    if arts is None:
        arts = news_module.fetch_news(limit=40, hours_back=36) or []

    article = pick_article_for_single_card(arts)
    if article is None:
        _rs, relaxed = best_single_card_candidate_relaxed(arts)
        if relaxed is not None:
            article = relaxed
            print(
                "[telegram_single_card] strict gate empty — relaxed body rules pick "
                f"score={_rs}"
            )
    if article is None:
        print("[telegram_single_card] 팩트 게이트 통과 기사 없음")
        return None, None
    print(
        "[facts_gate] picked "
        f"score={news_module.score_article(article)} "
        f"source={news_module.article_source_name(article)!r}"
    )

    os.makedirs(out_dir, exist_ok=True)
    safe_key = news_module.dedup_key(article)[:40].replace(" ", "_")
    safe_key = re.sub(r"[^a-zA-Z0-9가-힣_\-]", "", safe_key) or "card"
    out_path = os.path.join(out_dir, f"telegram_single_card_{safe_key}_{CARD_TEMPLATE}.jpg")
    fb_path = os.path.join(out_dir, f"telegram_single_card_{safe_key}_fallback.jpg")
    try:
        path = render_single_card(article, out_path)
        if _is_valid_card_jpeg(path):
            return path, article
        print(f"[telegram_single_card] primary output invalid size/corrupt: {path!r}")
    except Exception as e:
        print(f"[telegram_single_card] render failed: {repr(e)}")
    try:
        path2 = _render_minimal_fallback_card(article, fb_path)
        if _is_valid_card_jpeg(path2):
            print("[telegram_single_card] minimal fallback card ok")
            return path2, article
    except Exception as e2:
        print(f"[telegram_single_card] fallback render failed: {repr(e2)}")
    return None, None
