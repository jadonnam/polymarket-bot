from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

SIZE = (1080, 1350)
W, H = SIZE
OUTPUT_DIR = "output"
BG_PATH = "bg.jpg"

BOLD_FONT = os.path.join("fonts", "Pretendard-Bold.ttf")
REG_FONT = os.path.join("fonts", "Pretendard-Regular.ttf")

WHITE = (255, 255, 255)
DESC = (228, 232, 238)
BRAND = (214, 218, 224)
CHIP_BG = (18, 24, 34)

TITLE_MAX_WIDTH = 560
DESC_MAX_WIDTH = 520
EYEBROW_MAX_WIDTH = 520

ACCENTS = {
    "gold": (247, 205, 70),
    "yellow": (247, 205, 70),
    "neon_gold": (255, 214, 61),
    "orange": (255, 151, 64),
    "red": (255, 92, 92),
    "hot_red": (255, 72, 72),
    "blue": (109, 181, 255),
    "electric_blue": (74, 197, 255),
    "green": (98, 226, 146),
}

SUBTONES = {
    "white": (255, 255, 255),
    "soft_blue": (224, 237, 255),
    "warm": (255, 239, 214),
}


def get_font(path, size):
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_cover(img, target_size):
    tw, th = target_size
    iw, ih = img.size

    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh))

    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def add_overlay(base):
    base = base.convert("RGBA")

    overall = Image.new("RGBA", (W, H), (0, 0, 0, 34))
    base = Image.alpha_composite(base, overall)

    grad = Image.new("L", (W, H), 0)
    grad_px = grad.load()
    safe_width = int(W * 0.58)

    for x in range(W):
        if x <= safe_width:
            alpha = int(146 * (1 - x / safe_width))
        else:
            alpha = 0
        for y in range(H):
            grad_px[x, y] = alpha

    left_dark = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    left_dark.putalpha(grad)
    base = Image.alpha_composite(base, left_dark)

    bottom = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bottom)
    bd.rectangle((0, 980, W, H), fill=(0, 0, 0, 22))
    base = Image.alpha_composite(base, bottom)

    return base.convert("RGB")


def measure_rich_text(draw, parts, font):
    total = 0
    for text, _ in parts:
        if not text:
            continue
        bbox = draw.textbbox((0, 0), text, font=font)
        total += (bbox[2] - bbox[0])
    return total


def fit_rich_font(draw, parts, font_path, start_size, min_size, max_width):
    size = start_size
    while size >= min_size:
        font = get_font(font_path, size)
        width = measure_rich_text(draw, parts, font)
        if width <= max_width:
            return font
        size -= 2
    return get_font(font_path, min_size)


def fit_plain_font(draw, text, font_path, start_size, min_size, max_width):
    size = start_size
    while size >= min_size:
        font = get_font(font_path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            return font
        size -= 2
    return get_font(font_path, min_size)


def draw_rich_text(draw, x, y, parts, font):
    cur_x = x
    for text, color in parts:
        if not text:
            continue
        draw.text((cur_x + 3, y + 3), text, font=font, fill=(0, 0, 0))
        draw.text((cur_x, y), text, font=font, fill=color)
        bbox = draw.textbbox((cur_x, y), text, font=font)
        cur_x = bbox[2]


def draw_chip(draw, x, y, text, accent_color):
    font = get_font(BOLD_FONT, 26)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x = 18
    pad_y = 10

    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + th + pad_y * 2),
        radius=20,
        fill=CHIP_BG
    )
    draw.text((x + pad_x, y + pad_y - 1), text, font=font, fill=accent_color)


def make_card(eyebrow, title1_parts, title2_parts, desc_lines, brand_text="jadonnam", topic_label="MARKET", mode="normal", accent="gold", subtone="white"):
    if not os.path.exists(BG_PATH):
        raise RuntimeError("bg.jpg 없음")

    accent_color = ACCENTS.get(accent, ACCENTS["gold"])
    main_text_color = SUBTONES.get(subtone, SUBTONES["white"])

    normalized_title1 = []
    for text, color in title1_parts:
        normalized_title1.append((text, accent_color if color != WHITE else main_text_color))

    normalized_title2 = [(text, main_text_color) for text, _ in title2_parts]

    bg = Image.open(BG_PATH).convert("RGB")
    bg = fit_cover(bg, SIZE)
    bg = add_overlay(bg)

    draw = ImageDraw.Draw(bg)

    font_brand = get_font(REG_FONT, 34)
    font_eyebrow = fit_plain_font(draw, eyebrow, BOLD_FONT, 36, 24, EYEBROW_MAX_WIDTH)
    font_title1 = fit_rich_font(draw, normalized_title1, BOLD_FONT, 88, 58, TITLE_MAX_WIDTH)
    font_title2 = fit_rich_font(draw, normalized_title2, BOLD_FONT, 86, 56, TITLE_MAX_WIDTH)

    draw.text((82, 82), brand_text, font=font_brand, fill=BRAND)
    draw_chip(draw, 82, 145, topic_label, accent_color)

    if eyebrow:
        draw.text((84, 230), eyebrow, font=font_eyebrow, fill=(0, 0, 0))
        draw.text((82, 228), eyebrow, font=font_eyebrow, fill=accent_color)

    title_y1 = 295
    title_y2 = 445

    draw_rich_text(draw, 82, title_y1, normalized_title1, font_title1)
    draw_rich_text(draw, 82, title_y2, normalized_title2, font_title2)

    desc_y = 640
    line_gap = 72

    for i, line in enumerate(desc_lines[:2]):
        font_desc = fit_plain_font(draw, line, REG_FONT, 42, 28, DESC_MAX_WIDTH)
        draw.text((84, desc_y + i * line_gap), line, font=font_desc, fill=(0, 0, 0))
        draw.text((82, desc_y + i * line_gap), line, font=font_desc, fill=DESC)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"card_{ts}.png")
    bg.save(out_path, quality=95)

    print(f"saved: {out_path}")
    return out_path