from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from logo_asset_manager import load_logo

W, H = 1080, 1350


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def render_stock_study_template(
    company_name_kr: str,
    ticker: str,
    rank_text: str = "#1",
    headline_top: str = "매일 미국 주식 1종목",
    headline_bottom: str = "공부하기",
    out_path: str = "output_cardnews/stock_study.jpg",
    logo_size: int = 420,
) -> str:
    img = Image.new("RGB", (W, H), (6, 8, 10))
    d = ImageDraw.Draw(img)

    d.text((64, 70), headline_top, fill=(247, 249, 251), font=_font(74, True))
    d.text((64, 152), headline_bottom, fill=(247, 249, 251), font=_font(74, True))

    logo = load_logo(ticker, logo_size)
    img.paste(logo, ((W - logo.width) // 2, 380), logo)

    d.text((80, 1020), rank_text, fill=(246, 248, 251), font=_font(84, True))
    d.text((80, 1120), str(company_name_kr)[:14], fill=(246, 248, 251), font=_font(94, True))
    d.text((80, 1240), str(ticker).upper()[:10], fill=(214, 221, 230), font=_font(64, True))
    d.text((72, 1302), "JADONNAM", fill=(166, 176, 190), font=_font(28, False))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)
    return out_path
