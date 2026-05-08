from __future__ import annotations

import os
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from logo_asset_manager import load_logo

W, H = 1080, 1350


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _bg() -> Image.Image:
    img = Image.new("RGB", (W, H), (8, 10, 14))
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = int(12 + 38 * (y / H))
        d.line([(0, y), (W, y)], fill=(v // 2, v // 2, v))
    return img


def build_rank_card_editorial(
    title: str,
    rows: List[Dict[str, object]],
    out_path: str = "output_cardnews/rank_editorial.jpg",
) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img = _bg()
    d = ImageDraw.Draw(img)
    d.text((44, 46), "JADONNAM INFO", fill=(170, 176, 188), font=_font(22, False))
    d.text((44, 92), str(title)[:28], fill=(244, 247, 250), font=_font(66, True))

    y = 250
    for i, row in enumerate(rows[:5], start=1):
        symbol = str(row.get("symbol", "N/A"))
        label = str(row.get("label", symbol))
        score = str(row.get("score", ""))
        logo = load_logo(symbol, 86)
        img.paste(logo, (44, y), logo)
        d.text((148, y + 6), f"{i}. {label[:18]}", fill=(238, 242, 246), font=_font(40, True))
        d.text((936, y + 14), score[:10], fill=(255, 189, 92), font=_font(34, True))
        d.line([(44, y + 104), (1036, y + 104)], fill=(44, 50, 62), width=1)
        y += 120

    img.save(out_path, quality=95)
    return out_path
