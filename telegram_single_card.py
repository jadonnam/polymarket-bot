"""
단일 카드뉴스(1장) → 텔레그램 저장 채널 전송.

- 뉴스는 news.py의 trusted / market impact / low-quality 필터를 재사용해 '팩트 게이트'에 가깝게 선별
- 이미지는 Pillow로 합성(배경 사진 + 하단 그라데이션 + 헤드라인). media_group 미사용.
"""
from __future__ import annotations

import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

import news as news_module
from card_backgrounds import build_card_background

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFilter = None  # type: ignore
    ImageFont = None  # type: ignore

W, H = 1080, 1350
PAD_X = 48
BOTTOM_ZONE = 620
# BoA/삼성형 레퍼런스 (1080×1350) — 가독·임팩트 우선 (기본값 상향)
BOA_H1_PX = 94
BOA_H2_PX = 56
BOA_BOTTOM_MARGIN = 52
BOA_GRADIENT_START = 0.34
CARD_IMPACT_STYLE = (os.getenv("CARD_IMPACT_STYLE") or "true").lower() == "true"
CARD_PHOTO_SHOW_SOURCE = (os.getenv("CARD_PHOTO_SHOW_SOURCE") or "false").lower() == "true"
# NewsAPI urlToImage — 차트·무관 썸네일이 많아 기본 off. photo(BoA형)는 env와 무관하게 항상 폴백만.
TELEGRAM_CARD_USE_NEWS_IMAGE = (os.getenv("TELEGRAM_CARD_USE_NEWS_IMAGE") or "false").lower() == "true"
_CARD_TMPL = (os.getenv("CARD_TEMPLATE") or "photo").strip().lower()
CARD_TEMPLATE = _CARD_TMPL if _CARD_TMPL in ("photo", "badge", "quote") else "photo"

_discovered_cjk_font: Optional[str] = None


def _openai_headline_enabled() -> bool:
    raw = (os.getenv("CARD_HEADLINE_OPENAI") or "auto").strip().lower()
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if raw in ("false", "0", "no", "off"):
        return False
    if raw in ("true", "1", "yes", "on"):
        return bool(key)
    return bool(key)


def _try_openai_korean_card_lines(article: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    """OPENAI_API_KEY + CARD_HEADLINE_OPENAI 시 카드용 한국어 2줄(JSON). 실패 시 None."""
    if not _openai_headline_enabled():
        return None
    try:
        from openai import OpenAI
    except Exception as e:
        print(f"[card_ko] openai import failed: {repr(e)}")
        return None
    title = news_module.clean_spaces(article.get("title", "") or "")
    desc = news_module.clean_spaces(
        article.get("description", "") or article.get("content", "") or ""
    )[:900]
    if len(title) < 10:
        return None
    model = (os.getenv("OPENAI_HEADLINE_MODEL") or "gpt-4o-mini").strip()
    client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())
    sys = (
        "You write Korean headlines for a 1080x1350 Instagram financial news card (BoA/broker style). "
        "Pick scroll-stopping MAINSTREAM market stories: KOSPI/KOSDAQ records (e.g. 8100), "
        "Buffett/Berkshire buys, mega-cap surges, war/geopolitics, Fed/CPI, oil, big scandals. "
        "MANDATORY: only mainstream hooks — KOSPI record, Buffett buy, war/geopolitics, mega-cap shock, "
        "Fed/CPI surprise, oil/gold spike, major scandal. "
        "NEVER: crypto exchange products, pope/religion, AI ethics, product launches, Kraken vault. "
        "Tone: punchy Korean brokerage card — vivid but factual. No emoji. No fake facts. "
        'Output JSON only: {"line1":"...","line2":"...","emphasis":["..."]}. '
        "line1 = hook (한글, max ~26 chars). Lead with the surprise number/event. Comma at end when natural. "
        "line2 = why it matters now (한글, max ~52 chars). "
        "emphasis = 1–3 exact substrings from line1 to highlight in color (digits, 코스피, 돌파, 신고가…). "
        "Spell 코스피 never 코스파. Keep tickers in Latin when natural (NVDA, Fed)."
    )
    user = f"TITLE:\n{title}\n\nLEAD:\n{desc}\n"
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.22,
            max_tokens=240,
        )
        raw_j = (r.choices[0].message.content or "").strip()
        d = json.loads(raw_j)
    except Exception as e:
        print(f"[card_ko] openai request/json failed: {repr(e)}")
        return None
    l1 = (d.get("line1") or "").strip()
    l2 = (d.get("line2") or "").strip()
    emph_raw = d.get("emphasis")
    emphasis: List[str] = []
    if isinstance(emph_raw, list):
        emphasis = [str(x).strip() for x in emph_raw if str(x).strip()]
    elif isinstance(emph_raw, str) and emph_raw.strip():
        emphasis = [emph_raw.strip()]
    if len(l1) < 6:
        return None
    print("[card_ko] openai korean headline ok")
    article["_ko_emphasis"] = [e[:40] for e in emphasis[:4] if e in l1 or e in l2]
    return l1[:110], l2[:240]


def _card_title_subtitle_from_article(article: Dict[str, Any]) -> Tuple[str, str]:
    """OpenAI 한글 라인이 있으면 우선, 없으면 영문 제목·요약."""
    ko1 = str(article.get("_ko_line1") or "").strip()
    ko2 = str(article.get("_ko_line2") or "").strip()
    if ko1:
        return _clamp_title(ko1, max_len=110), (ko2[:280] if ko2 else "")
    return _clamp_title(article.get("title", "") or ""), _subtitle_from_article(article)


def _discover_cjk_font_path() -> Optional[str]:
    """Linux(Railway) 등: apt fonts-noto-cjk 설치 경로를 glob으로 찾음."""
    global _discovered_cjk_font
    if _discovered_cjk_font is not None:
        return _discovered_cjk_font or None
    bundled_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    for name in (
        "NotoSansKR-Bold.otf",
        "NotoSansKR-Regular.otf",
        "NotoSansCJK-Bold.otf",
        "NotoSansCJK-Regular.otf",
    ):
        p = os.path.join(bundled_dir, name)
        if os.path.isfile(p):
            _discovered_cjk_font = p
            print(f"[telegram_single_card] bundled CJK font: {p}")
            return p
    import glob

    globs = [
        "/usr/share/fonts/**/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/**/NotoSansCJK-Bold.otf",
        "/usr/share/fonts/**/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/**/NotoSansCJK-Regular.otf",
        "/usr/share/fonts/**/NotoSansKR-Bold.otf",
        "/usr/share/fonts/**/NotoSansKR-Regular.otf",
        "/usr/share/fonts/**/NanumGothicBold.ttf",
        "/usr/share/fonts/**/NanumGothic.ttf",
    ]
    for pattern in globs:
        for p in sorted(glob.glob(pattern, recursive=True)):
            if os.path.isfile(p):
                _discovered_cjk_font = p
                print(f"[telegram_single_card] discovered CJK font: {p}")
                return p
    _discovered_cjk_font = ""
    return None


def _font_candidates() -> List[str]:
    env = (os.getenv("CARD_FONT_PATH") or "").strip()
    out: List[str] = []
    if env:
        out.append(env)
    discovered = _discover_cjk_font_path()
    if discovered:
        out.append(discovered)
    out.extend(
        [
            r"C:\Windows\Fonts\malgunbd.ttf",
            r"C:\Windows\Fonts\malgun.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        ]
    )
    seen: set = set()
    deduped: List[str] = []
    for p in out:
        if p and p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


_cached_font_path: Optional[str] = None


def _resolve_font_path() -> Optional[str]:
    global _cached_font_path
    if _cached_font_path:
        return _cached_font_path
    for path in _font_candidates():
        if not path or not os.path.isfile(path):
            continue
        try:
            if os.path.getsize(path) < 50_000:
                continue
        except OSError:
            continue
        try:
            ImageFont.truetype(path, size=24)
            _cached_font_path = path
            print(f"[telegram_single_card] active font: {path}")
            return path
        except Exception:
            continue
    return None


def _load_font(size: int) -> Any:
    path = _resolve_font_path()
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            pass
    if _has_cjk("가"):
        print(
            "[telegram_single_card] WARNING: CJK font missing — "
            "한글이 네모/깨질 수 있음. Railway: fonts-noto-cjk 또는 CARD_FONT_PATH"
        )
    return ImageFont.load_default()


def _load_font_bold(size: int) -> Any:
    for path in _font_candidates():
        if not path or not os.path.isfile(path):
            continue
        low = path.lower()
        if "bold" in low or "bd.ttf" in low or "bold.ttc" in low:
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return _load_font(size)


def _load_font_regular(size: int) -> Any:
    for path in _font_candidates():
        if not path or not os.path.isfile(path):
            continue
        low = path.lower()
        if "bold" in low or "bd.ttf" in low:
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return _load_font(size)


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


_DEFAULT_REJECT_IMG_SUBSTR = (
    "tradingview.com,/charts/,chart-img,cryptocompare,price-chart,"
    "chart.googleapis,ohlc,candlestick"
)


def _article_image_url_blocked(url: str) -> bool:
    """차트·위젯 썸네일은 전면 배경으로 쓰면 제목이 묻힘 — 기본 차단."""
    u = (url or "").lower().strip()
    if not u:
        return True
    extra = (os.getenv("TELEGRAM_CARD_REJECT_IMAGE_SUBSTR") or "").strip().lower()
    parts = [p.strip() for p in _DEFAULT_REJECT_IMG_SUBSTR.split(",") if p.strip()]
    if extra:
        parts.extend([p.strip() for p in extra.split(",") if p.strip()])
    return any(p and p in u for p in parts)


def _article_image_url(article: Dict[str, Any]) -> str:
    u = str(article.get("urlToImage") or "").strip()
    if not u.lower().startswith("http"):
        return ""
    if _article_image_url_blocked(u):
        print(f"[telegram_single_card] urlToImage skipped (chart/widget): {u[:100]}…")
        return ""
    return u


def _fallbacks_dir() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "assets", "fallbacks"))


def _ref_photo_bank_path() -> Optional[str]:
    p = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "assets", "card_references", "ref_photo_bank.png")
    )
    return p if os.path.isfile(p) else None


def _watermark_path() -> Optional[str]:
    env = (os.getenv("CARD_WATERMARK_PATH") or "").strip()
    if env and os.path.isfile(env):
        return env
    p = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "assets", "branding", "watermark.png")
    )
    return p if os.path.isfile(p) else None


def _pick_fallback_background_path(article: Dict[str, Any]) -> Optional[str]:
    """BoA/삼성형 레퍼런스용 스톡 배경 — 키워드별 assets/fallbacks/*.jpg"""
    root = _fallbacks_dir()
    title = news_module.clean_spaces(article.get("title", "") or "").lower()
    desc = news_module.clean_spaces(
        article.get("description", "") or article.get("content", "") or ""
    ).lower()
    blob = f"{title} {desc}"

    bank_keys = (
        "bank of america",
        "bofa",
        "bank",
        "financial",
        "materials stock",
        "소재",
        "반도체",
        "semiconductor",
        "nvidia",
        "금융",
    )
    if any(k in blob for k in bank_keys):
        ref = _ref_photo_bank_path()
        if ref:
            return ref

    rules: List[Tuple[Tuple[str, ...], str]] = [
        (
            (
                "iran",
                "israel",
                "ukraine",
                "russia",
                "war",
                "attack",
                "missile",
                "ceasefire",
                "military",
                "airstrike",
            ),
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
        (
            (
                "fed",
                "inflation",
                "cpi",
                "tariff",
                "rate cut",
                "treasury",
                "dollar",
                "bitcoin",
                "btc",
                "ethereum",
                "eth",
                "crypto",
            ),
            "market_05.jpg",
        ),
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
    """하단 그라데이션 — 카드뉴스 가독용(IMPACT 시 더 진하게)."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    y0 = int(img.height * BOA_GRADIENT_START)
    span = max(img.height - y0 - 1, 1)
    power = 1.15 if CARD_IMPACT_STYLE else 1.35
    max_a = 255 if CARD_IMPACT_STYLE else 245
    for y in range(y0, img.height):
        t = (y - y0) / span
        alpha = int(12 + max_a * (t**power))
        d.line([(0, y), (img.width, y)], fill=(0, 0, 0, min(alpha, 255)))
    if CARD_IMPACT_STYLE:
        # 좌우 비네트 — 시선을 하단 헤드라인으로
        vig = Image.new("RGBA", img.size, (0, 0, 0, 0))
        vd = ImageDraw.Draw(vig)
        for x in range(img.width):
            t = min(x, img.width - 1 - x) / max(img.width * 0.22, 1)
            t = max(0.0, min(1.0, t))
            a = int(55 * (1.0 - t))
            if a > 0:
                vd.line([(x, 0), (x, img.height)], fill=(0, 0, 0, a))
        overlay = Image.alpha_composite(overlay, vig)
    img.alpha_composite(overlay)


def _topic_chip_style(topic: str) -> Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int], str]:
    t = (topic or "").strip()
    if "유가" in t or "에너지" in t:
        return (200, 55, 35, 235), (255, 255, 255, 255), "유가"
    if "연준" in t or "금리" in t or "비트" in t:
        return (28, 78, 168, 235), (255, 255, 255, 255), "연준"
    if "반도체" in t or "AI" in t:
        return (72, 52, 168, 235), (255, 255, 255, 255), "반도체"
    if "증시" in t or "코스" in t:
        return (18, 120, 95, 235), (255, 255, 255, 255), "증시"
    if "환율" in t:
        return (160, 110, 20, 235), (255, 255, 255, 255), "환율"
    if "지정학" in t or "정치" in t:
        return (120, 50, 50, 235), (255, 255, 255, 255), "이슈"
    return (40, 40, 48, 220), (255, 230, 160, 255), "시장"


def _draw_topic_chip(draw: Any, topic: str, *, x: int = PAD_X, y: int = 44) -> int:
    """상단 주제 칩 — 반환: 칩 하단 y."""
    if not CARD_IMPACT_STYLE or not topic:
        return y
    bg, fg, short = _topic_chip_style(topic)
    label = short if len(short) <= 6 else short[:6]
    f = _load_font_bold(26)
    try:
        bbox = draw.textbbox((0, 0), label, font=f)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = draw.textsize(label, font=f)  # type: ignore[attr-defined]
    pad_x, pad_y = 18, 10
    rx2 = x + tw + pad_x * 2
    ry2 = y + th + pad_y * 2
    try:
        draw.rounded_rectangle(
            [x, y, rx2, ry2], radius=14, fill=bg
        )
    except Exception:
        draw.rectangle([x, y, rx2, ry2], fill=bg)
    draw.text((x + pad_x, y + pad_y - 2), label, font=f, fill=fg)
    return ry2 + 12


def _draw_text_impact(
    draw: Any,
    xy: Tuple[int, int],
    text: str,
    font: Any,
    *,
    fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
    accent: bool = False,
) -> None:
    """굵은 그림자 + 선택 시 골드 톤 헤드라인."""
    x, y = xy
    if accent:
        fill = (255, 218, 120, 255)
    for dx, dy, a in ((0, 3, 140), (2, 2, 90), (0, 0, 255)):
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, a))
    draw.text((x, y), text, font=font, fill=fill)


_COLOR_WHITE = (255, 255, 255, 255)
_COLOR_GOLD = (255, 214, 72, 255)
_COLOR_MINT = (118, 255, 178, 255)
_COLOR_CORAL = (255, 118, 102, 255)
_COLOR_SKY = (130, 210, 255, 255)

_ACCENT_RULES: List[Tuple[re.Pattern[str], Tuple[int, int, int, int]]] = [
    (re.compile(r"\d[\d,.\d]*%?"), _COLOR_GOLD),
    (re.compile(r"코스피|코스닥|KOSPI|KOSDAQ", re.I), _COLOR_MINT),
    (re.compile(r"돌파|신고가|역대|최고|급등|상승|surge|rally|record", re.I), _COLOR_MINT),
    (re.compile(r"급락|폭락|하락|crash|slump|plunge", re.I), _COLOR_CORAL),
    (re.compile(r"비트코인|BTC|이더리움|ETH|연준|Fed|NVDA|엔비디아", re.I), _COLOR_SKY),
]


def _color_for_token(token: str, *, user_emphasis: bool = False) -> Tuple[int, int, int, int]:
    if user_emphasis:
        return _COLOR_GOLD
    for pat, col in _ACCENT_RULES:
        if pat.search(token):
            return col
    return _COLOR_WHITE


def _headline_colored_segments(
    text: str,
    *,
    emphasis_words: Optional[List[str]] = None,
) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    """한 줄을 (조각, RGBA) 리스트로 — 숫자·지수·강조어 색상."""
    if not text:
        return []
    emphasis_words = emphasis_words or []
    emph_lower = [e.lower() for e in emphasis_words if e]

    spans: List[Tuple[int, int, bool]] = []
    for ew in emphasis_words:
        if not ew:
            continue
        start = 0
        while True:
            i = text.find(ew, start)
            if i < 0:
                break
            spans.append((i, i + len(ew), True))
            start = i + len(ew)
    for pat, _ in _ACCENT_RULES:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end(), False))
    if not spans:
        return [(text, _COLOR_WHITE)]

    spans.sort(key=lambda t: t[0])
    merged: List[Tuple[int, int, bool]] = []
    for s, e, ue in spans:
        if merged and s <= merged[-1][1]:
            prev_s, prev_e, prev_ue = merged[-1]
            merged[-1] = (prev_s, max(prev_e, e), prev_ue or ue)
        else:
            merged.append((s, e, ue))

    out: List[Tuple[str, Tuple[int, int, int, int]]] = []
    pos = 0
    for s, e, ue in merged:
        if s > pos:
            out.append((text[pos:s], _COLOR_WHITE))
        chunk = text[s:e]
        out.append((chunk, _color_for_token(chunk, user_emphasis=ue)))
        pos = e
    if pos < len(text):
        out.append((text[pos:], _COLOR_WHITE))
    return out


def _draw_text_colored_line(
    draw: Any,
    xy: Tuple[int, int],
    segments: List[Tuple[str, Tuple[int, int, int, int]]],
    font: Any,
    *,
    strong_shadow: bool = True,
) -> None:
    x, y = xy
    for seg, fill in segments:
        if not seg:
            continue
        if strong_shadow:
            for dx, dy, a in ((0, 4, 150), (2, 3, 100), (0, 0, 255)):
                draw.text((x + dx, y + dy), seg, font=font, fill=(0, 0, 0, a))
        else:
            draw.text((x + 1, y + 1), seg, font=font, fill=(0, 0, 0, 72))
        draw.text((x, y), seg, font=font, fill=fill)
        x += int(draw.textlength(seg, font=font))


def _emphasis_from_article(article: Dict[str, Any]) -> List[str]:
    raw = article.get("_ko_emphasis")
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    return []


def _draw_text_photo(
    draw: Any,
    xy: Tuple[int, int],
    text: str,
    font: Any,
    fill: Tuple[int, int, int, int] = (255, 255, 255, 255),
) -> None:
    """레퍼런스: 흰 글자만, 얇은 그림자 1px (검은 외곽선 없음)."""
    x, y = xy
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 72))
    draw.text((x, y), text, font=font, fill=fill)


def _boa_photo_headline_lines(
    article: Dict[str, Any], title: str, subtitle: str
) -> Tuple[str, str]:
    ko1 = str(article.get("_ko_line1") or "").strip()
    ko2 = str(article.get("_ko_line2") or "").strip()
    if ko1:
        line1 = ko1
        if _has_cjk(line1) and not line1.endswith((",", "，", ":", "·", "—")) and len(line1) <= 36:
            line1 = line1 + ","
        return line1[:90], (ko2 or subtitle or "")[:140]
    line1, line2 = _headline_split_photo(title, subtitle)
    return line1, line2


def _composite_watermark(rgba: Image.Image) -> None:
    wp = _watermark_path()
    if not wp or Image is None:
        return
    try:
        mark = Image.open(wp).convert("RGBA")
        size = int(min(W, H) * 0.075)
        size = max(48, min(size, 88))
        mark = mark.resize((size, size), Image.Resampling.LANCZOS)
        mx = W - size - 40
        my = H - size - 36
        layer = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        layer.paste(mark, (mx, my), mark)
        rgba.alpha_composite(layer)
    except Exception as e:
        print(f"[telegram_single_card] watermark skip: {repr(e)}")


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


def _wrap_lines_cjk(draw: Any, text: str, font: Any, max_width: int) -> List[str]:
    lines: List[str] = []
    buf = ""
    for ch in text.replace("\n", " "):
        trial = buf + ch
        if draw.textlength(trial, font=font) <= max_width:
            buf = trial
            continue
        if buf:
            lines.append(buf)
        buf = ch
    if buf:
        lines.append(buf)
    return lines


def _wrap_lines(draw: Any, text: str, font: Any, max_width: int) -> List[str]:
    if _has_cjk(text):
        return _wrap_lines_cjk(draw, text, font, max_width)
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


def _single_card_max_age_hours() -> int:
    try:
        return max(12, int((os.getenv("SINGLE_CARD_MAX_ARTICLE_AGE_HOURS") or "48").strip()))
    except ValueError:
        return 48


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
    max_h = _single_card_max_age_hours()
    for a in articles or []:
        if not news_module.trusted_article(a):
            continue
        if news_module.is_sports_article(a):
            continue
        if not news_module.has_market_impact(a):
            continue
        if news_module.is_press_release_wire(a):
            continue
        if not news_module.published_recent_enough(a, hours=max_h):
            continue
        if news_module.article_url_slug_year_stale(a):
            continue
        if not _relaxed_body_passes(a):
            continue
        url = str(a.get("url") or "").strip()
        if not url.lower().startswith("https://"):
            continue
        title = news_module.clean_spaces(a.get("title", ""))
        min_len = 12 if news_module.is_viral_breaking(a) else 18
        if len(title) < min_len:
            continue
        if news_module.is_niche_crypto_product_article(a):
            continue
        if not news_module.is_mandatory_mainstream_card_topic(a):
            continue
        s = news_module.score_instagram_card_article(a)
        min_sc = news_module.instagram_card_min_score()
        if s < min_sc:
            continue
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
    max_h = _single_card_max_age_hours()
    for a in articles or []:
        if not news_module.trusted_article(a):
            continue
        if news_module.is_sports_article(a):
            continue
        if not news_module.has_market_impact(a):
            continue
        if news_module.is_press_release_wire(a):
            continue
        if news_module.is_low_quality_text(a):
            continue
        if not news_module.published_recent_enough(a, hours=max_h):
            continue
        if news_module.article_url_slug_year_stale(a):
            continue
        url = str(a.get("url") or "").strip()
        if not url.lower().startswith("https://"):
            continue
        title = news_module.clean_spaces(a.get("title", ""))
        min_len = 12 if news_module.is_viral_breaking(a) else 18
        if len(title) < min_len:
            continue
        if news_module.is_niche_crypto_product_article(a):
            continue
        if not news_module.is_mandatory_mainstream_card_topic(a):
            continue
        s = news_module.score_instagram_card_article(a)
        min_sc = news_module.instagram_card_min_score()
        if s < min_sc:
            continue
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
    - 배경: assets/fallbacks 키워드 스톡만 (urlToImage 미사용 — 차트 썸네일 방지)
    - 최후 solid
    """
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")

    title, subtitle = _card_title_subtitle_from_article(article)
    source = news_module.article_source_name(article)

    try:
        base, bg_mode = build_card_background(article, W, H)
        print(f"[telegram_single_card] bg_mode={bg_mode}")
    except Exception as e:
        print(f"[telegram_single_card] bg build failed: {repr(e)} — solid")
        base = _solid_background(W, H)
        bg_mode = "solid"

    rgba = base.convert("RGBA")
    _apply_photo_bottom_gradient(rgba)
    _composite_watermark(rgba)
    draw = ImageDraw.Draw(rgba)

    card_topic = str(article.get("_card_topic") or "").strip()
    _draw_topic_chip(draw, card_topic)
    top_left = (os.getenv("CARD_TOP_LEFT_LABEL") or "").strip()
    brand = (os.getenv("CARD_BRAND_LABEL") or "").strip()
    if top_left and not card_topic:
        f_tl = _load_font_regular(22)
        _draw_text_photo(draw, (PAD_X, 40), top_left, f_tl)
    elif brand and not card_topic:
        f_tl = _load_font_regular(22)
        _draw_text_photo(draw, (PAD_X, 40), brand, f_tl)

    max_text_w = W - 2 * PAD_X - (10 if CARD_IMPACT_STYLE else 0)
    text_x = PAD_X + (14 if CARD_IMPACT_STYLE else 0)
    line1, line2 = _boa_photo_headline_lines(article, title, subtitle)

    if len(line1) <= 16:
        h1s = BOA_H1_PX
    elif len(line1) <= 24:
        h1s = max(78, BOA_H1_PX - 6)
    else:
        h1s = max(68, BOA_H1_PX - 14)
    h2s = BOA_H2_PX if len(line2) <= 36 else max(46, BOA_H2_PX - 8)
    f_h1 = _load_font_bold(h1s)
    f_h2 = _load_font_bold(h2s) if CARD_IMPACT_STYLE else _load_font_regular(h2s)
    h1_lines = _wrap_lines(draw, line1, f_h1, max_text_w)[:2]
    if not h1_lines and line1:
        h1_lines = [line1[:100]]
    h2_lines = _wrap_lines(draw, line2, f_h2, max_text_w)[:2] if line2 else []

    body_chk = line1 + line2
    if _has_cjk(body_chk) and not _resolve_font_path():
        print(
            "[telegram_single_card] CJK headline but no CJK font — "
            "nixpacks fonts-noto-cjk 또는 assets/fonts/ 에 폰트 필요"
        )

    lh1 = max(int(h1s * 1.14), 40)
    lh2 = max(int(h2s * 1.16), 32)
    gap = 16
    block_h = len(h1_lines) * lh1 + len(h2_lines) * lh2 + gap
    if CARD_PHOTO_SHOW_SOURCE:
        block_h += 28
    y = H - BOA_BOTTOM_MARGIN - block_h

    if CARD_IMPACT_STYLE and (h1_lines or h2_lines):
        bar_h = block_h - gap + 8
        _accent = (255, 196, 64, 255)
        draw.rectangle(
            [text_x - 12, int(y) - 4, text_x - 4, int(y) + bar_h],
            fill=_accent,
        )

    emph_words = _emphasis_from_article(article)
    for ln in h1_lines:
        if CARD_IMPACT_STYLE:
            segs = _headline_colored_segments(ln, emphasis_words=emph_words)
            _draw_text_colored_line(draw, (text_x, int(y)), segs, f_h1, strong_shadow=True)
        else:
            _draw_text_photo(draw, (text_x, int(y)), ln, f_h1)
        y += lh1
    for ln in h2_lines:
        if CARD_IMPACT_STYLE:
            segs = _headline_colored_segments(ln, emphasis_words=emph_words)
            tinted = [
                (s, (220, 235, 255, 255) if col == _COLOR_WHITE else col)
                for s, col in segs
            ]
            _draw_text_colored_line(draw, (text_x, int(y)), tinted, f_h2, strong_shadow=True)
        else:
            _draw_text_photo(draw, (text_x, int(y)), ln, f_h2, fill=(248, 250, 255, 255))
        y += lh2

    if CARD_PHOTO_SHOW_SOURCE:
        f_src = _load_font_regular(20)
        src_line = source if source else ""
        if src_line:
            _draw_text_photo(
                draw,
                (PAD_X, int(y + gap)),
                src_line,
                f_src,
                fill=(200, 208, 220, 255),
            )

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rgba.convert("RGB").save(out_path, "JPEG", quality=93, optimize=True)
    print(f"[telegram_single_card] wrote {out_path} ({bg_mode})")
    return out_path


def _render_template_badge(article: Dict[str, Any], out_path: str) -> str:
    """IREN형: 쿨톤 배경 + 중앙 그린 배지(티커) + 하단 제목 스택."""
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")
    title, subtitle = _card_title_subtitle_from_article(article)
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
    title, subtitle = _card_title_subtitle_from_article(article)
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
    """단일 카드 = BoA 레퍼런스 photo 1장 고정 (1080×1350, badge/quote 미사용)."""
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")
    if CARD_TEMPLATE not in ("photo",):
        print(
            f"[telegram_single_card] CARD_TEMPLATE={CARD_TEMPLATE!r} — "
            "단일 카드는 photo(BoA 레퍼런스)만 사용"
        )
    if TELEGRAM_CARD_USE_NEWS_IMAGE:
        print(
            "[telegram_single_card] TELEGRAM_CARD_USE_NEWS_IMAGE=true — "
            "photo에서는 무시, ref_photo_bank + fallbacks만"
        )
    print("[telegram_single_card] mode=single_photo_boa")
    return _render_template_photo(article, out_path)


def build_telegram_caption(article: Dict[str, Any]) -> str:
    """텔레그램 캡션(1024자). 기본 minimal — 이미지에 본문이 있으므로 제목+링크 위주."""
    ko1 = str(article.get("_ko_line1") or "").strip()
    title = news_module.clean_spaces(
        ko1 if ko1 else (article.get("title", "") or "")
    )
    desc = _subtitle_from_article(article)
    src = news_module.article_source_name(article)
    url = str(article.get("url") or "").strip()
    minimal = (os.getenv("TELEGRAM_CAPTION_MINIMAL") or "true").lower() == "true"
    if minimal:
        parts: List[str] = []
        ko2 = str(article.get("_ko_line2") or "").strip()
        if title:
            parts.append("📌 " + title[:480])
        if ko2 and ko2 not in title:
            parts.append(ko2[:360])
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
    """1차: BoA photo와 동일 경로. 실패 시에만 단순 solid 카드."""
    if Image is None:
        raise RuntimeError("Pillow(PIL) 미설치")
    try:
        return _render_template_photo(article, out_path)
    except Exception as e:
        print(f"[telegram_single_card] photo fallback retry as solid: {repr(e)}")
    ko1 = str(article.get("_ko_line1") or "").strip()
    title = news_module.clean_spaces(
        ko1 if ko1 else (article.get("title", "") or "")
    )[:220]
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
    lead_article: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """기사 선별 → 1장 JPEG 생성 → (경로, 기사) 반환. 전송은 호출측."""
    if Image is None:
        print("[telegram_single_card] Pillow 없음 — 스킵")
        return None, None

    arts = articles
    if arts is None:
        arts = news_module.fetch_news(limit=40, hours_back=36) or []

    article = dict(lead_article) if lead_article else None
    if article is None:
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
        f"score={news_module.score_instagram_card_article(article)} "
        f"mainstream_hook=ok "
        f"source={news_module.article_source_name(article)!r}"
    )

    article = dict(article)
    if str(article.get("_ko_line1") or "").strip():
        print("[card_ko] reference_pipeline lines")
    else:
        ko_lines = _try_openai_korean_card_lines(article)
        if ko_lines:
            article["_ko_line1"], article["_ko_line2"] = ko_lines
            article.setdefault("_card_topic", "")
            if any(k in (article["_ko_line1"] + article["_ko_line2"]).lower() for k in ("코스", "kospi")):
                article["_card_topic"] = "증시"
        else:
            print("[card_ko] no korean lines — OPENAI_API_KEY 확인")

    skip_no_font = (os.getenv("TELEGRAM_SKIP_CARD_WITHOUT_FONT") or "true").lower() == "true"
    if skip_no_font and not _resolve_font_path():
        print(
            "[telegram_single_card] CJK font 없음 — 깨진 카드 대신 DESK 텍스트만 "
            "(Railway: fonts-noto-cjk 또는 assets/fonts/NanumGothicBold.ttf)"
        )
        return None, article

    os.makedirs(out_dir, exist_ok=True)
    safe_key = news_module.dedup_key(article)[:40].replace(" ", "_")
    safe_key = re.sub(r"[^a-zA-Z0-9가-힣_\-]", "", safe_key) or "card"
    out_path = os.path.join(out_dir, f"telegram_single_card_{safe_key}_photo.jpg")
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
