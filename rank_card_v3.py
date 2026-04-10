
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG_TOP = (10, 12, 18)
BG_BOTTOM = (22, 24, 34)
TEXT = (245, 245, 245)
SUB = (153, 153, 163)
EMPTY = (49, 49, 58)
WATER = (94, 94, 104)

ASSET_DIR = os.path.join(os.path.dirname(__file__), "assets")
ICON_MAP = {
    "NEWS": os.path.join(ASSET_DIR, "icon_news.png"),
    "POLYMARKET": os.path.join(ASSET_DIR, "icon_poly.png"),
    "MARKET": os.path.join(ASSET_DIR, "icon_market.png"),
}

def _font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

FONT_HEADER = _font(52, True)
FONT_ITEM = _font(42, True)
FONT_PERCENT = _font(32, True)
FONT_SUB = _font(24, False)
FONT_WATER = _font(24, False)

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

def _rounded(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)

def _icon(img, kind):
    path = ICON_MAP.get(kind)
    if path and os.path.exists(path):
        icon = Image.open(path).convert("RGBA").resize((62, 62))
        img.alpha_composite(icon, (56, 58))

def _trim(text, limit=16):
    t = str(text).strip()
    if len(t) <= limit:
        return t
    return t[:limit].rstrip() + "…"

def _palette(score):
    if score >= 80:
        return (255, 76, 76)
    if score >= 60:
        return (255, 158, 46)
    if score >= 40:
        return (255, 214, 64)
    return (170, 170, 170)

def _draw_gradient_bar(draw, x, y, width, height, score):
    score = max(0, min(100, int(score)))
    filled = int(width * score / 100)
    _rounded(draw, (x, y, x + width, y + height), 12, EMPTY)

    if filled <= 0:
        return

    base = _palette(score)
    for i in range(filled):
        ratio = i / max(filled, 1)
        r = min(255, int(base[0] * (0.86 + ratio * 0.22)))
        g = min(255, int(base[1] * (0.78 + ratio * 0.24)))
        b = min(255, int(base[2] * (0.78 + ratio * 0.10)))
        draw.line([(x + i, y), (x + i, y + height)], fill=(r, g, b), width=1)

def create_rank_card(kind, items, out_path, watermark="jadonnam"):
    img = _bg()
    draw = ImageDraw.Draw(img)

    _icon(img, kind)
    draw.text((136, 58), kind, font=FONT_HEADER, fill=TEXT)
    draw.text((136, 112), "TOP 5", font=FONT_SUB, fill=SUB)

    start_y = 212
    row_gap = 205
    title_x = 136
    num_x = 70
    bar_x = 136
    bar_w = 720
    bar_h = 24

    for idx in range(5):
        if idx < len(items):
            title = _trim(items[idx].get("title", f"이슈 {idx+1}"), 16)
            score = int(items[idx].get("score", 0))
        else:
            title = "-"
            score = 0

        y = start_y + idx * row_gap
        draw.text((num_x, y), f"{idx+1}.", font=FONT_ITEM, fill=TEXT)
        draw.text((title_x, y), title, font=FONT_ITEM, fill=TEXT)

        bar_y = y + 82
        _draw_gradient_bar(draw, bar_x, bar_y, bar_w, bar_h, score)
        draw.text((bar_x + bar_w + 22, bar_y - 7), f"{score}%", font=FONT_PERCENT, fill=_palette(score))

    draw.text((W - 170, H - 48), watermark, font=FONT_WATER, fill=WATER)
    img.convert("RGB").save(out_path, quality=95)
    return out_path

def _market_merge(news_items, poly_items):
    bucket = {}

    def push(label, score):
        if not label:
            return
        bucket[label] = max(bucket.get(label, 0), int(score))

    for item in news_items:
        push(item.get("title", ""), item.get("score", 0))
    for item in poly_items:
        push(item.get("title", ""), item.get("score", 0))

    items = [{"title": k, "score": v} for k, v in bucket.items()]
    items.sort(key=lambda x: x["score"], reverse=True)
    return items[:5]

def create_rank_set(news_items, poly_items, out_dir="output_rank", watermark="jadonnam"):
    os.makedirs(out_dir, exist_ok=True)

    news_path = os.path.join(out_dir, "rank_news.png")
    poly_path = os.path.join(out_dir, "rank_polymarket.png")
    market_path = os.path.join(out_dir, "rank_market.png")

    create_rank_card("NEWS", news_items, news_path, watermark=watermark)
    create_rank_card("POLYMARKET", poly_items, poly_path, watermark=watermark)
    market_items = _market_merge(news_items, poly_items)
    create_rank_card("MARKET", market_items, market_path, watermark=watermark)

    return [news_path, poly_path, market_path]
