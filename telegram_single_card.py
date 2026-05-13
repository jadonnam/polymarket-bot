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
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore

W, H = 1080, 1350
PAD_X = 56
BOTTOM_ZONE = 520


def _font_candidates() -> List[str]:
    env = (os.getenv("CARD_FONT_PATH") or "").strip()
    out: List[str] = []
    if env:
        out.append(env)
    out.extend(
        [
            r"C:\Windows\Fonts\malgunbd.ttf",
            r"C:\Windows\Fonts\malgun.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
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
    if len(desc) > 160:
        return desc[:157] + "…"
    return desc


def _article_image_url(article: Dict[str, Any]) -> str:
    u = str(article.get("urlToImage") or "").strip()
    if u.lower().startswith("http"):
        return u
    return ""


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
    base = Image.new("RGB", (tw, th), (12, 12, 18))
    g = ImageDraw.Draw(base)
    for y in range(th):
        t = y / max(th - 1, 1)
        r = int(12 + t * 28)
        b = int(18 + t * 40)
        g.line([(0, y), (tw, y)], fill=(r, 12, b))
    return base


def _apply_bottom_gradient(base: Image.Image) -> None:
    """In-place bottom darken for text legibility."""
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    y0 = base.height - BOTTOM_ZONE
    for y in range(y0, base.height):
        t = (y - y0) / max(BOTTOM_ZONE - 1, 1)
        alpha = int(215 * (t**1.12))
        d.line([(0, y), (base.width, y)], fill=(0, 0, 0, alpha))
    base.alpha_composite(overlay)


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


def pick_article_for_single_card(articles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    팩트 게이트(확실한 기준):
    - news.trusted_article (도메인/통신사 화이트리스트)
    - 시장 연관(has_market_impact / has_high_impact는 fetch 단계에서 이미 적용됐을 수 있음 — 재확인)
    - 저품질/라이브블로그 등 제외
    - 원문 URL 필수(https)
    - 점수: news.score_article 기준 상위 1건
    """
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for a in articles or []:
        if not news_module.trusted_article(a):
            continue
        if not news_module.has_market_impact(a):
            continue
        if news_module.is_low_quality_text(a):
            continue
        url = str(a.get("url") or "").strip()
        if not url.lower().startswith("https://"):
            continue
        title = news_module.clean_spaces(a.get("title", ""))
        if len(title) < 18:
            continue
        scored.append((news_module.score_article(a), a))
    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return None
    return scored[0][1]


def render_single_card(article: Dict[str, Any], out_path: str) -> str:
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")

    title = _clamp_title(article.get("title", "") or "")
    subtitle = _subtitle_from_article(article)
    source = news_module.article_source_name(article)

    bg_url = _article_image_url(article)
    bg = _download_image(bg_url) if bg_url else None
    if bg is not None:
        base = _cover_background(bg, W, H)
    else:
        base = _solid_background(W, H)

    base = base.convert("RGBA")
    _apply_bottom_gradient(base)
    draw = ImageDraw.Draw(base)

    brand = (os.getenv("CARD_BRAND_LABEL") or "MARKET CARD").strip()
    f_brand = _load_font(26)
    draw.text((PAD_X, 44), brand, font=f_brand, fill=(230, 230, 235, 230))

    max_text_w = W - 2 * PAD_X
    body = title if not subtitle else f"{title}\n{subtitle}"

    font_size = 52
    lines: List[str] = []
    while font_size >= 30:
        font = _load_font(font_size)
        lines = _wrap_lines(draw, body, font, max_text_w)
        est_h = len(lines) * int(font_size * 1.25)
        if est_h < BOTTOM_ZONE - 120:
            break
        font_size -= 2

    font = _load_font(font_size)
    lines = _wrap_lines(draw, body, font, max_text_w)

    if _has_cjk(body) and not os.getenv("CARD_FONT_PATH"):
        # 기본 폰트는 한글 글리프가 없을 수 있음
        print(
            "[telegram_single_card] CJK 문자 포함 — Railway/Linux에서는 CARD_FONT_PATH(NotoSansKR 등) 설정 권장"
        )

    y0 = H - BOTTOM_ZONE + 72
    y = y0
    for line in lines:
        draw.text((PAD_X, y), line, font=font, fill=(255, 255, 255, 255))
        y += int(font_size * 1.22)

    src_line = f"출처: {source}" if source else "출처: 확인됨(통신사/도메인 화이트리스트)"
    f_src = _load_font(22)
    draw.text((PAD_X, H - 52), src_line, font=f_src, fill=(190, 200, 210, 255))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    base.convert("RGB").save(out_path, "JPEG", quality=92, optimize=True)
    print(f"[telegram_single_card] wrote {out_path}")
    return out_path


def build_telegram_caption(article: Dict[str, Any]) -> str:
    src = news_module.article_source_name(article)
    url = str(article.get("url") or "").strip()
    parts = ["[팩트 게이트]", "선별: 신뢰 통신사·도메인 + 시장 연관 + 저품질 제외"]
    if src:
        parts.append(f"매체: {src}")
    if url:
        parts.append(f"원문: {url}")
    return "\n".join(parts)


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
    out_path = os.path.join(out_dir, f"telegram_single_card_{safe_key}.jpg")
    try:
        path = render_single_card(article, out_path)
        return path, article
    except Exception as e:
        print(f"[telegram_single_card] render failed: {repr(e)}")
        return None, None
