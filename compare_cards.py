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
    img = Image.new("RGB", (W, H), (10, 11, 15))
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = int(14 + 18 * (y / H))
        d.line([(0, y), (W, y)], fill=(v, v, v + 2))
    return img


def build_compare_cards(
    left: Dict[str, str],
    right: Dict[str, str],
    metrics: List[Dict[str, str]],
    out_dir: str = "output_planned",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    l_name = str(left.get("name", "NVIDIA"))
    l_sym = str(left.get("symbol", "NVDA"))
    r_name = str(right.get("name", "AMD"))
    r_sym = str(right.get("symbol", "AMD"))

    out: List[str] = []
    for i in range(3):
        img = _base()
        d = ImageDraw.Draw(img)
        d.text((40, 34), "COMPARE CARD", fill=(174, 182, 194), font=_font(24, False))
        d.text((40, 72), f"{l_name[:10]} vs {r_name[:10]}", fill=(240, 244, 248), font=_font(42, True))
        ll = load_logo(l_sym, 130)
        rr = load_logo(r_sym, 130)
        img.paste(ll, (118, 180), ll)
        img.paste(rr, (830, 180), rr)
        d.text((100, 330), l_name[:12], fill=(230, 236, 242), font=_font(34, True))
        d.text((804, 330), r_name[:12], fill=(230, 236, 242), font=_font(34, True))
        d.text((505, 252), "VS", fill=(245, 248, 251), font=_font(48, True))
        d.line([(540, 390), (540, 1210)], fill=(62, 70, 84), width=2)

        start = i * 3
        chunk = metrics[start:start + 3]
        y = 470
        for m in chunk:
            label = str(m.get("label", "지표"))[:12]
            lv = str(m.get("left", "-"))[:12]
            rv = str(m.get("right", "-"))[:12]
            d.text((60, y), lv, fill=(97, 214, 126), font=_font(40, True))
            d.text((438, y), label, fill=(208, 216, 226), font=_font(30, True))
            d.text((604, y), rv, fill=(255, 104, 104), font=_font(40, True))
            y += 220

        out_path = os.path.join(out_dir, f"compare_{i+1:02d}.jpg")
        img.save(out_path, quality=95)
        out.append(out_path)
    return out
