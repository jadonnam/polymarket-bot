import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG_TOP = (8, 12, 22)
BG_BOTTOM = (18, 24, 38)
PANEL = (18, 24, 36, 160)
TEXT = (246, 247, 250)
SUB = (155, 163, 175)
EMPTY = (52, 58, 72)

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
ICON_MAP = {
    "뉴스": os.path.join(ASSET_DIR, "icon_news.png"),
    "폴리마켓": os.path.join(ASSET_DIR, "icon_poly.png"),
    "시장 반응": os.path.join(ASSET_DIR, "icon_market.png"),
}

def _font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

FONT_HEADER = _font(60, True)
FONT_SUB = _font(25, False)
FONT_NUM = _font(34, True)
FONT_ITEM = _font(44, True)
FONT_PERCENT = _font(36, True)

def _bg():
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        r = y / max(H - 1, 1)
        rr = int(BG_TOP[0] * (1 - r) + BG_BOTTOM[0] * r)
        gg = int(BG_TOP[1] * (1 - r) + BG_BOTTOM[1] * r)
        bb = int(BG_TOP[2] * (1 - r) + BG_BOTTOM[2] * r)
        d.line([(0, y), (W, y)], fill=(rr, gg, bb))
    return img.convert("RGBA")

def _rounded(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

def _icon(img, kind):
    path = ICON_MAP.get(kind)
    if path and os.path.exists(path):
        icon = Image.open(path).convert("RGBA").resize((66, 66))
        img.alpha_composite(icon, (58, 58))

def _trim_kor(text, limit=16):
    t = str(text).strip()
    if len(t) <= limit:
        return t
    return t[:limit].rstrip() + "…"

def _palette(score):
    if score >= 80:
        return (255, 84, 84)
    if score >= 60:
        return (255, 160, 48)
    if score >= 40:
        return (255, 214, 70)
    return (174, 180, 190)

def _draw_gradient_bar(draw, x, y, width, height, score):
    score = max(0, min(100, int(score)))
    filled = int(width * score / 100)
    _rounded(draw, (x, y, x + width, y + height), 14, EMPTY)
    if filled <= 0:
        return
    base = _palette(score)
    for i in range(filled):
        ratio = i / max(filled, 1)
        r = min(255, int(base[0] * (0.84 + ratio * 0.20)))
        g = min(255, int(base[1] * (0.80 + ratio * 0.22)))
        b = min(255, int(base[2] * (0.80 + ratio * 0.08)))
        draw.line([(x + i, y), (x + i, y + height)], fill=(r, g, b), width=1)

def _visible_items(items):
    visible = []
    for item in items:
        title = str(item.get("title", "")).strip()
        score = int(item.get("score", 0))
        if not title:
            continue
        visible.append({"title": title, "score": score})
    return visible[:5]

def create_rank_card(kind, items, out_path):
    items = _visible_items(items)
    img = _bg()
    draw = ImageDraw.Draw(img)

    _icon(img, kind)
    draw.text((140, 58), kind, font=FONT_HEADER, fill=TEXT)
    draw.text((140, 118), "오늘 핵심 순위", font=FONT_SUB, fill=SUB)

    if not items:
        items = [{"title": "데이터 수집 중", "score": 0}]

    count = len(items)
    header_bottom = 190
    bottom_margin = 90
    usable_h = H - header_bottom - bottom_margin
    row_gap = int(usable_h / max(count, 1))
    row_gap = max(180, min(255, row_gap))

    panel_x1, panel_x2 = 44, W - 44
    num_x = 84
    title_x = 150
    bar_x = 150
    bar_w = 700
    bar_h = 28

    for idx, item in enumerate(items):
        y = header_bottom + idx * row_gap + 10
        panel_y1 = y - 22
        panel_y2 = y + 126
        _rounded(draw, (panel_x1, panel_y1, panel_x2, panel_y2), 28, PANEL)

        title = _trim_kor(item["title"], 15)
        score = item["score"]

        draw.text((num_x, y), f"{idx+1}.", font=FONT_NUM, fill=SUB)
        draw.text((title_x, y), title, font=FONT_ITEM, fill=TEXT)

        bar_y = y + 72
        _draw_gradient_bar(draw, bar_x, bar_y, bar_w, bar_h, score)
        draw.text((bar_x + bar_w + 26, bar_y - 6), f"{score}%", font=FONT_PERCENT, fill=_palette(score))

    img.convert("RGB").save(out_path, quality=96)
    return out_path

def _merge_market(news_items, poly_items):
    merged = {}
    for source in [news_items, poly_items]:
        for item in source:
            title = str(item.get("title", "")).strip()
            score = int(item.get("score", 0))
            if not title:
                continue
            if title in merged:
                merged[title] = max(merged[title], score)
            else:
                merged[title] = score
    items = [{"title": k, "score": v} for k, v in merged.items()]
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:5]

def create_rank_set(news_items, poly_items, out_dir="output_rank"):
    os.makedirs(out_dir, exist_ok=True)
    news_path = os.path.join(out_dir, "rank_news.png")
    poly_path = os.path.join(out_dir, "rank_polymarket.png")
    market_path = os.path.join(out_dir, "rank_market.png")
    create_rank_card("뉴스", news_items, news_path)
    create_rank_card("폴리마켓", poly_items, poly_path)
    create_rank_card("시장 반응", _merge_market(news_items, poly_items), market_path)
    return [news_path, poly_path, market_path]
