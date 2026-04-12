from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1350
BG_COLOR = (0, 0, 0)
TEXT_COLOR = (244, 246, 248)
SUB_TEXT_COLOR = (134, 140, 152)
BAR_BG = (45, 51, 70)

ACCENT_NEWS = (226, 232, 242)
ACCENT_POLY = (247, 175, 74)
ACCENT_MARKET = (88, 202, 182)

UP_COLOR = (83, 214, 150)
DOWN_COLOR = (255, 118, 118)
FLAT_COLOR = (160, 166, 178)

FONT_DIR = "fonts"


def _font_path(bold: bool = True) -> str:
    return os.path.join(FONT_DIR, "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf")


def get_font(size: int, bold: bool = True):
    try:
        return ImageFont.truetype(_font_path(bold), size)
    except Exception:
        return ImageFont.load_default()


def now_kst_text() -> str:
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    return now.strftime("%Y.%m.%d %H:%M KST")


def _safe_score(v) -> int:
    try:
        v = int(round(float(v)))
    except Exception:
        v = 0
    return max(0, min(100, v))


def _text_width(draw, text, font) -> int:
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0]


def _trim_text(draw, text, font, max_width: int) -> str:
    text = str(text).strip()
    if _text_width(draw, text, font) <= max_width:
        return text
    s = text
    while len(s) > 1:
        s = s[:-1].rstrip()
        cand = s + "…"
        if _text_width(draw, cand, font) <= max_width:
            return cand
    return "…"


def _draw_bar(draw, x: int, y: int, width: int, height: int, score: int, fill_color) -> None:
    radius = height // 2
    draw.rounded_rectangle((x, y, x + width, y + height), radius=radius, fill=BAR_BG)
    fill_w = int(width * (_safe_score(score) / 100))
    if fill_w > 0:
        draw.rounded_rectangle((x, y, x + fill_w, y + height), radius=radius, fill=fill_color)


def _page_style(page_type: str) -> Dict[str, object]:
    if page_type == "news":
        return {"title": "뉴스", "subtitle": "지난 구간 핵심 이슈", "accent": ACCENT_NEWS, "footer": "NEWS"}
    if page_type == "poly":
        return {"title": "폴리마켓", "subtitle": "베팅이 몰린 흐름", "accent": ACCENT_POLY, "footer": "POLYMARKET"}
    return {"title": "시장 반응", "subtitle": "가격이 먼저 움직인 구간", "accent": ACCENT_MARKET, "footer": "MARKET"}


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _translate_poly_label(text: str) -> str:
    t = _normalize_ws(text)
    low = t.lower()
    if "us" in low and "iran" in low and ("meet" in low or "talk" in low):
        return "미국-이란 회담 변수"
    if any(x in low for x in ["military action", "strike", "attack"]):
        return "군사 행동 가능성"
    if any(x in low for x in ["ceasefire", "framework", "deal", "truce", "hopes for a", "fra"]):
        return "휴전 기대 확대"
    if any(x in low for x in ["oil", "wti", "crude", "brent"]):
        return "유가 상단 도전"
    if any(x in low for x in ["bitcoin", "btc"]):
        return "비트코인 상단 테스트"
    if "gold" in low:
        return "금 선호 확대"
    if "trump" in low:
        return "트럼프 변수 확대"
    if any(x in low for x in ["fed", "rate", "cpi", "inflation"]):
        return "금리 방향 베팅"
    if low.startswith("will ") or low.startswith("who will"):
        return "해외 베팅 이슈"
    return t


def _translate_news_label(text: str) -> str:
    t = _normalize_ws(text)
    low = t.lower()
    if any(x in low for x in ["fra", "ceasefire", "deal", "framework", "truce", "hopes for a"]):
        return "휴전 기대 확대"
    if any(x in low for x in ["tariff", "trump"]):
        return "트럼프 변수 확대"
    if any(x in low for x in ["dollar", "usd", "fx", "won"]):
        return "달러 강세 유지"
    if any(x in low for x in ["bitcoin", "btc"]):
        return "비트코인 강세 유지"
    if any(x in low for x in ["oil", "wti", "crude", "brent"]):
        return "유가 상방 압력"
    if any(x in low for x in ["rate", "fed", "cpi", "yield"]):
        return "금리 완화 기대"
    return t


def _translate_label(page_type: str, text: str) -> str:
    if page_type == "poly":
        return _translate_poly_label(text)
    if page_type == "news":
        return _translate_news_label(text)
    return _normalize_ws(text)


def _delta_display(delta: Optional[int]):
    if delta is None:
        return "0%", FLAT_COLOR
    try:
        d = int(delta)
    except Exception:
        d = 0
    if d > 0:
        return f"▲{abs(d)}%", UP_COLOR
    if d < 0:
        return f"▼{abs(d)}%", DOWN_COLOR
    return "0%", FLAT_COLOR


def draw_card(page_type: str, items: List[Dict], out_path: str, generated_at_text: Optional[str] = None) -> str:
    style = _page_style(page_type)
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    brand_font = get_font(22, bold=False)
    title_font = get_font(84, bold=True)
    sub_font = get_font(28, bold=False)
    item_font = get_font(48, bold=True)
    rank_font = get_font(28, bold=True)
    score_font = get_font(44, bold=True)
    meta_font = get_font(24, bold=False)
    delta_font = get_font(24, bold=True)
    foot_font = get_font(18, bold=False)

    draw.text((60, 52), "JADONNAM", fill=SUB_TEXT_COLOR, font=brand_font)
    title = style["title"]
    subtitle = style["subtitle"]
    accent = style["accent"]
    title_w = _text_width(draw, title, title_font)
    draw.text(((WIDTH - title_w) // 2, 132), title, fill=TEXT_COLOR, font=title_font)
    sub_w = _text_width(draw, subtitle, sub_font)
    draw.text(((WIDTH - sub_w) // 2, 234), subtitle, fill=SUB_TEXT_COLOR, font=sub_font)
    underline_w = 110
    draw.rounded_rectangle(((WIDTH - underline_w) // 2, 290, (WIDTH + underline_w) // 2, 298), radius=4, fill=accent)

    start_y = 360
    row_gap = 175
    label_x = 150
    bar_x = 126
    bar_w = 704
    bar_h = 18
    score_x = 1000
    meta_x = 850

    cleaned: List[Dict] = []
    seen = set()
    for i, item in enumerate(items[:10], start=1):
        raw_label = str((item or {}).get("label") or (item or {}).get("title") or f"항목 {i}").strip()
        label = _translate_label(page_type, raw_label)
        if not label or label in seen:
            continue
        seen.add(label)
        cleaned.append({
            "label": label,
            "score": _safe_score((item or {}).get("score", 0)),
            "delta": (item or {}).get("delta"),
        })
        if len(cleaned) == 5:
            break

    while len(cleaned) < 5:
        cleaned.append({"label": f"항목 {len(cleaned) + 1}", "score": 0, "delta": 0})

    for idx, item in enumerate(cleaned, start=1):
        y = start_y + (idx - 1) * row_gap
        draw.text((60, y + 10), f"{idx:02d}", fill=SUB_TEXT_COLOR, font=rank_font)
        label = _trim_text(draw, item["label"], item_font, 610)
        draw.text((label_x, y), label, fill=TEXT_COLOR, font=item_font)

        score_text = f"{item['score']}%"
        score_w = _text_width(draw, score_text, score_font)
        draw.text((score_x - score_w, y - 2), score_text, fill=accent, font=score_font)

        delta_text, delta_color = _delta_display(item.get("delta"))
        delta_w = _text_width(draw, delta_text, delta_font)
        draw.text((meta_x, y - 16), "중요도", fill=SUB_TEXT_COLOR, font=meta_font)
        draw.text((meta_x, y + 18), delta_text, fill=delta_color, font=delta_font)

        _draw_bar(draw, bar_x, y + 82, bar_w, bar_h, item["score"], accent)

    time_text = f"기준 {generated_at_text or now_kst_text()}"
    draw.text((60, HEIGHT - 72), time_text, fill=SUB_TEXT_COLOR, font=meta_font)
    footer = style["footer"]
    foot_w = _text_width(draw, footer, foot_font)
    draw.text((WIDTH - 60 - foot_w, HEIGHT - 68), footer, fill=SUB_TEXT_COLOR, font=foot_font)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)
    return out_path


def create_rank_set(news_items: List[Dict], poly_items: List[Dict], market_items: List[Dict], out_dir: str = "output_rank", generated_at_text: Optional[str] = None):
    os.makedirs(out_dir, exist_ok=True)
    p1 = os.path.join(out_dir, "rank_news.jpg")
    p2 = os.path.join(out_dir, "rank_poly.jpg")
    p3 = os.path.join(out_dir, "rank_market.jpg")
    draw_card("news", news_items, p1, generated_at_text=generated_at_text)
    draw_card("poly", poly_items, p2, generated_at_text=generated_at_text)
    draw_card("market", market_items, p3, generated_at_text=generated_at_text)
    return [p1, p2, p3]
