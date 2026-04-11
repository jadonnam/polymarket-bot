import os
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG = (8, 10, 18)
TEXT = (244, 246, 248)
SUB = (145, 152, 165)
ACCENT = (255, 174, 60)
FONT_DIR = "fonts"


def _font(name: str, size: int):
    path = os.path.join(FONT_DIR, name)
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, font, width):
    words = str(text).split()
    if not words:
        return [""]
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + " " + w
        if draw.textbbox((0, 0), test, font=font)[2] <= width:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:4]


def _kst_text():
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    return now.strftime("%Y.%m.%d %H:%M KST")


def create_breaking_image(title: str, out_path: str = "output_breaking.png") -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    brand = _font("Pretendard-Regular.ttf", 22)
    big = _font("Pretendard-Bold.ttf", 98)
    body = _font("Pretendard-Bold.ttf", 74)
    small = _font("Pretendard-Regular.ttf", 28)

    draw.text((60, 58), "JADONNAM", fill=SUB, font=brand)
    draw.text((60, 180), "속보", fill=ACCENT, font=big)

    lines = _wrap(draw, title, body, 930)
    y = 420
    for line in lines:
        draw.text((60, y), line, fill=TEXT, font=body)
        y += 98

    draw.text((60, H - 92), f"기준 {_kst_text()}", fill=SUB, font=small)
    img.save(out_path, quality=95)
    return out_path
