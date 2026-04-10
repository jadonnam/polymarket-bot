import os
import math
from typing import List, Dict, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1080, 1350
OUT_DEFAULT = "output_rank"

BG_TOP = (5, 8, 16)
BG_MID = (10, 16, 29)
BG_BOTTOM = (18, 25, 40)
CARD_BG = (14, 20, 34, 230)
CARD_BG_2 = (18, 24, 38, 240)
CARD_BORDER = (42, 55, 79, 255)
TEXT_MAIN = (245, 248, 255)
TEXT_SUB = (147, 161, 188)
TEXT_FAINT = (102, 118, 144)
LINE_SOFT = (43, 59, 84)
WHITE = (255, 255, 255)

ACCENTS = {
    "뉴스": (78, 168, 255),
    "폴리마켓": (255, 163, 72),
    "시장 반응": (86, 223, 160),
}

SUBTITLES = {
    "뉴스": "최근 이슈 강도 기준 TOP 5",
    "폴리마켓": "베팅 자금 + 확률 반응 TOP 5",
    "시장 반응": "실제 자산 민감도 기준 TOP 5",
}


def _font_candidates(bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    return [
        os.path.join(os.path.dirname(__file__), "fonts", name),
        os.path.join(os.path.dirname(__file__), name),
        os.path.join("fonts", name),
        name,
        "/mnt/data/Pretendard-Bold.ttf" if bold else "/mnt/data/Pretendard-Regular.ttf",
    ]


def _font(size: int, bold: bool = True):
    for path in _font_candidates(bold):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    try:
        fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(fallback, size)
    except Exception:
        return ImageFont.load_default()


def _background() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_TOP)
    px = img.load()
    for y in range(H):
        r = y / max(1, H - 1)
        if r < 0.55:
            rr = r / 0.55
            color = (
                int(BG_TOP[0] * (1 - rr) + BG_MID[0] * rr),
                int(BG_TOP[1] * (1 - rr) + BG_MID[1] * rr),
                int(BG_TOP[2] * (1 - rr) + BG_MID[2] * rr),
            )
        else:
            rr = (r - 0.55) / 0.45
            color = (
                int(BG_MID[0] * (1 - rr) + BG_BOTTOM[0] * rr),
                int(BG_MID[1] * (1 - rr) + BG_BOTTOM[1] * rr),
                int(BG_MID[2] * (1 - rr) + BG_BOTTOM[2] * rr),
            )
        for x in range(W):
            px[x, y] = color

    rgba = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    for i in range(8):
        alpha = max(12, 34 - i * 3)
        d.ellipse(
            (
                700 - i * 28,
                -140 - i * 18,
                1250 + i * 24,
                430 + i * 18,
            ),
            outline=(255, 255, 255, alpha),
            width=2,
        )

    for i in range(150):
        a = int(115 * (1 - i / 150))
        d.line([(0, i), (W, i)], fill=(0, 0, 0, a))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((700, 50, 1180, 530), fill=(66, 108, 255, 44))
    gd.ellipse((760, 660, 1160, 1060), fill=(41, 209, 152, 30))
    glow = glow.filter(ImageFilter.GaussianBlur(45))

    rgba = Image.alpha_composite(rgba, glow)
    rgba = Image.alpha_composite(rgba, overlay)
    return rgba.convert("RGB")


def _score_color(score: int):
    if score >= 85:
        return (255, 92, 92)
    if score >= 72:
        return (255, 171, 79)
    if score >= 58:
        return (255, 211, 99)
    return (100, 214, 255)


def _fit_single_line(draw, text: str, max_width: int, start: int, minimum: int, bold: bool = True):
    for size in range(start, minimum - 1, -2):
        font = _font(size, bold=bold)
        box = draw.textbbox((0, 0), text, font=font)
        if (box[2] - box[0]) <= max_width:
            return font
    return _font(minimum, bold=bold)


def _wrap_text(draw, text: str, font, max_width: int, max_lines: int = 2):
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        box = draw.textbbox((0, 0), candidate, font=font)
        if (box[2] - box[0]) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if current:
        lines.append(current)
    lines = lines[:max_lines]
    if len(lines) == max_lines and len(words) > len(" ".join(lines).split()):
        last = lines[-1]
        if len(last) >= 2:
            lines[-1] = last[:-1].rstrip() + "…"
    return lines


def _normalize_items(items: Optional[List[Dict]], limit: int = 5):
    out = []
    for raw in items or []:
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        try:
            score = int(round(float(raw.get("score", 0))))
        except Exception:
            score = 0
        score = max(0, min(100, score))
        meta = str(raw.get("meta", "")).strip()
        out.append({"title": title, "score": score, "meta": meta})
    return out[:limit]


def _draw_header(draw: ImageDraw.ImageDraw, kind: str, accent):
    brand_font = _font(28, False)
    chip_font = _font(28, True)
    title_font = _font(72, True)
    sub_font = _font(30, False)

    draw.text((60, 52), "jadonnam market board", font=brand_font, fill=TEXT_FAINT)
    chip_w = draw.textbbox((0, 0), kind, font=chip_font)[2] + 48
    draw.rounded_rectangle((60, 104, 60 + chip_w, 164), radius=20, fill=(15, 22, 37), outline=accent, width=2)
    draw.text((84, 118), kind, font=chip_font, fill=accent)

    draw.text((60, 212), kind, font=title_font, fill=TEXT_MAIN)
    draw.text((60, 292), SUBTITLES.get(kind, "핵심 순위 카드"), font=sub_font, fill=TEXT_SUB)

    draw.line((60, 345, W - 60, 345), fill=LINE_SOFT, width=2)


def _draw_rank_badge(draw, x, y, rank, accent):
    badge_fill = (18, 25, 42)
    draw.rounded_rectangle((x, y, x + 72, y + 72), radius=24, fill=badge_fill, outline=accent, width=2)
    font = _font(34, True)
    box = draw.textbbox((0, 0), str(rank), font=font)
    tw = box[2] - box[0]
    th = box[3] - box[1]
    draw.text((x + (72 - tw) / 2, y + (72 - th) / 2 - 3), str(rank), font=font, fill=TEXT_MAIN)


def _draw_card(draw, x, y, w, h, rank, title, score, accent, meta=""):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=34, fill=CARD_BG, outline=CARD_BORDER, width=2)
    draw.rounded_rectangle((x + 1, y + 1, x + w - 1, y + h - 1), radius=34, outline=(255, 255, 255, 10), width=1)
    _draw_rank_badge(draw, x + 26, y + 28, rank, accent)

    score_color = _score_color(score)
    pct_font = _font(42, True)
    pct_text = f"{score}%"
    pct_box = draw.textbbox((0, 0), pct_text, font=pct_font)
    pct_w = pct_box[2] - pct_box[0]
    draw.text((x + w - 32 - pct_w, y + 34), pct_text, font=pct_font, fill=score_color)

    title_area_x = x + 118
    title_area_w = w - 118 - 160
    dummy = Image.new("RGB", (10, 10))
    dd = ImageDraw.Draw(dummy)
    title_font = _fit_single_line(dd, title, title_area_w, 40, 28, True)
    lines = _wrap_text(dd, title, title_font, title_area_w, max_lines=2)
    line_h = title_font.size + 10
    ty = y + 28
    for line in lines:
        draw.text((title_area_x, ty), line, font=title_font, fill=TEXT_MAIN)
        ty += line_h

    if meta:
        meta_font = _font(24, False)
        meta_lines = _wrap_text(dd, meta, meta_font, w - 64, max_lines=1)
        draw.text((x + 30, y + h - 76), meta_lines[0], font=meta_font, fill=TEXT_SUB)

    bar_x = x + 30
    bar_y = y + h - 48
    bar_w = w - 60
    bar_h = 16
    draw.rounded_rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), radius=8, fill=(34, 42, 60))
    fill_w = max(12, int(bar_w * (score / 100.0))) if score > 0 else 0
    if fill_w > 0:
        draw.rounded_rectangle((bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), radius=8, fill=score_color)


def create_rank_card(kind: str, items: List[Dict], path: str):
    accent = ACCENTS.get(kind, (120, 180, 255))
    img = _background().convert("RGBA")
    draw = ImageDraw.Draw(img)
    _draw_header(draw, kind, accent)

    items = _normalize_items(items, limit=5)
    visible_count = max(1, min(5, len(items)))
    card_h = 154
    gap = 28 if visible_count >= 5 else 34
    total_h = visible_count * card_h + (visible_count - 1) * gap
    start_y = 400 if visible_count == 5 else int((H - total_h) / 2) + 40

    for idx, item in enumerate(items):
        y = start_y + idx * (card_h + gap)
        _draw_card(
            draw,
            48,
            y,
            W - 96,
            card_h,
            idx + 1,
            item["title"],
            item["score"],
            accent,
            item.get("meta", ""),
        )

    if not items:
        empty_font = _font(34, False)
        draw.text((60, 470), "표시할 데이터가 없습니다.", font=empty_font, fill=TEXT_SUB)

    footer_font = _font(24, False)
    draw.text((60, H - 58), "auto ranked by issue intensity · jadonnam", font=footer_font, fill=TEXT_FAINT)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    img.convert("RGB").save(path, quality=95)
    return path


def create_rank_set(news_items: List[Dict], poly_items: List[Dict], market_items: Optional[List[Dict]] = None, out_dir: str = OUT_DEFAULT):
    os.makedirs(out_dir, exist_ok=True)
    n = create_rank_card("뉴스", news_items, os.path.join(out_dir, "news_rank.png"))
    p = create_rank_card("폴리마켓", poly_items, os.path.join(out_dir, "poly_rank.png"))
    m = create_rank_card("시장 반응", market_items or [], os.path.join(out_dir, "market_rank.png"))
    return [n, p, m]
