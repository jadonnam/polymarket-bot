from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

SIZE = (1080, 1350)
W, H = SIZE
OUTPUT_DIR = "output"

BOLD_FONT = os.path.join("fonts", "Pretendard-Bold.ttf")
REG_FONT = os.path.join("fonts", "Pretendard-Regular.ttf")

BG_PATH = "bg.jpg"

WHITE = (255, 255, 255)
DESC = (222, 222, 228)
BRAND = (165, 165, 172)

ALERT_RED = (255, 76, 76)
ALERT_BG = (120, 18, 18)
ALERT_DESC = (245, 230, 230)

TITLE_MAX_WIDTH = 470
DESC_MAX_WIDTH = 430


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


def add_normal_overlay(base):
    base = base.convert("RGBA")

    overall = Image.new("RGBA", (W, H), (0, 0, 0, 42))
    base = Image.alpha_composite(base, overall)

    return base.convert("RGB")


def add_alert_overlay(base):
    base = base.convert("RGBA")

    # 더 강한 붉은 톤
    overall = Image.new("RGBA", (W, H), (28, 0, 0, 120))
    base = Image.alpha_composite(base, overall)

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
        draw.text((cur_x, y), text, font=font, fill=color)
        bbox = draw.textbbox((cur_x, y), text, font=font)
        cur_x = bbox[2]


def make_card(title1_parts, title2_parts, desc_lines, brand_text="jadonnam", mode="normal"):
    if os.path.exists(BG_PATH):
        bg = Image.open(BG_PATH).convert("RGB")
        bg = fit_cover(bg, SIZE)
    else:
        bg = Image.new("RGB", SIZE, (18, 18, 22))

    if mode == "alert":
        bg = add_alert_overlay(bg)
    else:
        bg = add_normal_overlay(bg)

    draw = ImageDraw.Draw(bg)

    font_brand = get_font(REG_FONT, 34)

    # 제목 폰트
    if mode == "alert":
        font_title1 = fit_rich_font(draw, title1_parts, BOLD_FONT, 100, 72, TITLE_MAX_WIDTH)
        font_title2 = fit_rich_font(draw, title2_parts, BOLD_FONT, 96, 68, TITLE_MAX_WIDTH)
        desc_fill = ALERT_DESC
    else:
        font_title1 = fit_rich_font(draw, title1_parts, BOLD_FONT, 92, 68, TITLE_MAX_WIDTH)
        font_title2 = fit_rich_font(draw, title2_parts, BOLD_FONT, 92, 68, TITLE_MAX_WIDTH)
        desc_fill = DESC

    # 상단 브랜드만 유지
    draw.text((80, 92), brand_text, font=font_brand, fill=BRAND)

    # 제목 위치
    title_y1 = 248
    title_y2 = 360

    draw_rich_text(draw, 80, title_y1, title1_parts, font_title1)
    draw_rich_text(draw, 80, title_y2, title2_parts, font_title2)

    # 설명
    desc_y = 555
    line_gap = 64

    for i, line in enumerate(desc_lines[:2]):
        font_desc = fit_plain_font(draw, line, REG_FONT, 44, 32, DESC_MAX_WIDTH)
        draw.text((80, desc_y + i * line_gap), line, font=font_desc, fill=desc_fill)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%m%d_%H%M")
    suffix = "alert" if mode == "alert" else "normal"
    out_path = os.path.join(OUTPUT_DIR, f"card_{suffix}_{ts}.png")
    bg.save(out_path)

    print(f"saved: {out_path}")
    return out_path