import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG = (8, 10, 18)
TEXT = (244, 246, 248)
SUB = (145, 152, 165)
ACCENT = (255, 174, 60)
BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "fonts"


def _font_candidates(name: str):
    stem = Path(name).stem
    suffix = Path(name).suffix or ".ttf"
    return [
        FONT_DIR / name,
        BASE_DIR / name,
        BASE_DIR / f"{stem}(1){suffix}",
        FONT_DIR / f"{stem}(1){suffix}",
    ]


def _font(name: str, size: int):
    for path in _font_candidates(name):
        try:
            if path.exists():
                return ImageFont.truetype(str(path), size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap(draw, text, font, width):
    text = str(text or "").strip()
    if not text:
        return [""]
    if " " in text:
        words = text.split()
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

    lines = []
    cur = ""
    for ch in text:
        test = cur + ch
        if cur and draw.textbbox((0, 0), test, font=font)[2] > width:
            lines.append(cur)
            cur = ch
            if len(lines) == 3:
                break
        else:
            cur = test
    if cur:
        rest = text[len("".join(lines)):]
        lines.append(rest[:len(cur)] if len(lines) == 3 else cur)
    return [line for line in lines if line][:4]


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
