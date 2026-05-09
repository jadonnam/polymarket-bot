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


def render_ranking_template(
    title: str,
    rows: List[Dict[str, str]],
    out_path: str = "output_cardnews/ranking.jpg",
) -> str:
    img = Image.new("RGB", (W, H), (6, 8, 10))
    d = ImageDraw.Draw(img)

    d.text((40, 42), "TOP10 RANKING", fill=(190, 198, 210), font=_font(22, False))
    d.text((40, 84), title[:26], fill=(246, 248, 251), font=_font(58, True))

    data = rows[:10]
    while len(data) < 10:
        data.append({"symbol": "QQQ", "label": f"자산 {len(data)+1}", "value": "+0.0%"})

    y = 190
    for idx, row in enumerate(data, start=1):
        logo = load_logo(str(row.get("symbol", "QQQ")), 70)
        img.paste(logo, (42, y), logo)
        d.text((126, y + 6), f"{idx:02d}", fill=(178, 186, 198), font=_font(28, True))
        d.text((188, y + 4), str(row.get("label", ""))[:18], fill=(236, 241, 246), font=_font(34, True))
        val = str(row.get("value", "0.0%"))[:10]
        color = (99, 214, 129) if not val.startswith("-") else (255, 102, 102)
        d.text((900, y + 8), val, fill=color, font=_font(30, True))
        d.line([(42, y + 84), (1038, y + 84)], fill=(40, 48, 60), width=1)
        y += 92

    d.text((40, 1302), "JADONNAM", fill=(166, 176, 190), font=_font(28, False))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)
    return out_path
