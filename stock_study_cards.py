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


def _base() -> Image.Image:
    img = Image.new("RGB", (W, H), (9, 11, 15))
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = int(14 + 24 * (y / H))
        d.line([(0, y), (W, y)], fill=(v, v, v + 2))
    return img


def build_stock_study_cards(
    company: Dict[str, str],
    points: List[str],
    out_dir: str = "output_planned",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    name = str(company.get("name", "NVIDIA"))
    symbol = str(company.get("symbol", "NVDA"))
    one_liner = str(company.get("one_liner", "핵심 한 줄 인사이트"))
    points = [str(x) for x in points][:4]
    while len(points) < 4:
        points.append("핵심 체크포인트")

    paths: List[str] = []
    for idx in range(5):
        img = _base()
        d = ImageDraw.Draw(img)
        d.text((40, 36), "STOCK STUDY", fill=(176, 184, 198), font=_font(24, False))
        d.text((40, 74), f"CARD {idx+1}/5", fill=(152, 160, 174), font=_font(20, False))
        logo = load_logo(symbol, 170)
        img.paste(logo, (870, 30), logo)
        d.rounded_rectangle((40, 980, 54, 1240), radius=6, fill=(244, 246, 248))

        if idx == 0:
            d.text((84, 930), name[:18], fill=(246, 248, 251), font=_font(98, True))
            d.text((84, 1046), one_liner[:28], fill=(225, 231, 239), font=_font(44, True))
        elif idx <= 3:
            d.text((84, 930), f"핵심 포인트 {idx}", fill=(246, 248, 251), font=_font(72, True))
            d.text((84, 1036), points[idx - 1][:30], fill=(227, 233, 240), font=_font(48, True))
        else:
            d.text((84, 930), "한 줄 결론", fill=(246, 248, 251), font=_font(72, True))
            d.text((84, 1036), "저장해두고 실적 시즌 전에 다시 보기", fill=(227, 233, 240), font=_font(40, True))

        out_path = os.path.join(out_dir, f"stock_study_{idx+1:02d}.jpg")
        img.save(out_path, quality=95)
        paths.append(out_path)
    return paths
