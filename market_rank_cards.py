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


def _canvas():
    img = Image.new("RGB", (W, H), (8, 10, 14))
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = int(10 + 20 * (y / H))
        d.line([(0, y), (W, y)], fill=(v, v, v + 3))
    return img


def build_market_rank_cards(
    title: str,
    rows: List[Dict[str, str]],
    out_dir: str = "output_planned",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    rows = rows[:10]
    while len(rows) < 10:
        rows.append({"symbol": "QQQ", "label": f"자산 {len(rows)+1}", "return": "+0.0%"})

    pages = [rows[:5], rows[5:10]]
    out: List[str] = []
    for page_idx, page_rows in enumerate(pages, start=1):
        img = _canvas()
        d = ImageDraw.Draw(img)
        d.text((40, 34), "MARKET RANK", fill=(174, 182, 195), font=_font(24, False))
        d.text((40, 72), f"{title[:26]} · PAGE {page_idx}/2", fill=(152, 160, 172), font=_font(20, False))
        y = 190
        for i, row in enumerate(page_rows, start=1 + (page_idx - 1) * 5):
            logo = load_logo(str(row.get("symbol", "QQQ")), 86)
            img.paste(logo, (42, y), logo)
            d.text((148, y + 10), f"{i:02d} {str(row.get('label', '자산'))[:16]}", fill=(239, 243, 247), font=_font(40, True))
            ret = str(row.get("return", "0.0%"))[:10]
            color = (95, 214, 128) if not ret.startswith("-") else (255, 102, 102)
            d.text((900, y + 18), ret, fill=color, font=_font(34, True))
            d.line([(40, y + 104), (1038, y + 104)], fill=(42, 50, 62), width=1)
            y += 112
        out_path = os.path.join(out_dir, f"market_rank_{page_idx:02d}.jpg")
        img.save(out_path, quality=95)
        out.append(out_path)
    return out
