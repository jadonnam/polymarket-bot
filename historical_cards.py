from __future__ import annotations

import os
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _canvas() -> Image.Image:
    img = Image.new("RGB", (W, H), (9, 11, 15))
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = int(12 + 22 * (y / H))
        d.line([(0, y), (W, y)], fill=(v, v, v + 3))
    return img


def build_historical_cards(
    topic: str,
    yearly_rows: List[Dict[str, str]],
    out_dir: str = "output_planned",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    yearly_rows = yearly_rows[:10]
    while len(yearly_rows) < 10:
        yearly_rows.append({"year": str(2015 + len(yearly_rows)), "value": "0.0%"})

    img = _canvas()
    d = ImageDraw.Draw(img)
    d.text((40, 34), "HISTORICAL DATA", fill=(176, 184, 196), font=_font(24, False))
    d.text((40, 76), topic[:24], fill=(245, 248, 251), font=_font(56, True))

    # simple chart area
    d.rounded_rectangle((40, 170, 1040, 710), radius=18, fill=(14, 18, 24), outline=(46, 56, 70), width=2)
    points = []
    for i, row in enumerate(yearly_rows):
        raw = str(row.get("value", "0")).replace("%", "").replace("+", "")
        try:
            v = float(raw)
        except Exception:
            v = 0.0
        x = 82 + int(i * (920 / 9))
        y = 640 - int(max(-20.0, min(40.0, v)) * 8)
        points.append((x, y))
    d.line(points, fill=(109, 198, 255), width=4)
    for x, y in points:
        d.ellipse((x - 5, y - 5, x + 5, y + 5), fill=(109, 198, 255))

    y = 770
    for row in yearly_rows:
        year = str(row.get("year", ""))[:4]
        val = str(row.get("value", "0.0%"))[:10]
        color = (96, 213, 126) if not val.startswith("-") else (255, 106, 106)
        d.text((70, y), year, fill=(213, 220, 228), font=_font(30, True))
        d.text((910, y), val, fill=color, font=_font(30, True))
        d.line([(60, y + 42), (1020, y + 42)], fill=(40, 48, 60), width=1)
        y += 52

    out_path = os.path.join(out_dir, "historical_01.jpg")
    img.save(out_path, quality=95)
    return [out_path]
