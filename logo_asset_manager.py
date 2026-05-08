from __future__ import annotations

import os
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = os.path.join("assets", "logos")

LOGO_MAP: Dict[str, str] = {
    "AAPL": "apple.png",
    "NVDA": "nvidia.png",
    "TSLA": "tesla.png",
    "MSFT": "microsoft.png",
    "GOOGL": "google.png",
    "AMZN": "amazon.png",
    "META": "meta.png",
    "BTC": "bitcoin.png",
    "ETH": "ethereum.png",
}


def _font(size: int):
    try:
        return ImageFont.truetype(os.path.join("fonts", "Pretendard-Bold.ttf"), size)
    except Exception:
        return ImageFont.load_default()


def load_logo(symbol: str, size: int = 140) -> Image.Image:
    symbol = str(symbol or "").upper().strip()
    filename = LOGO_MAP.get(symbol, "")
    path = os.path.join(ASSET_DIR, filename) if filename else ""
    if path and os.path.exists(path):
        img = Image.open(path).convert("RGBA")
        return img.resize((size, size), Image.LANCZOS)

    # Fallback badge when logo asset is missing.
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=24, fill=(26, 30, 36, 240), outline=(72, 80, 92, 255), width=2)
    txt = symbol[:4] or "N/A"
    font = _font(max(20, size // 4))
    tw = d.textbbox((0, 0), txt, font=font)[2]
    th = d.textbbox((0, 0), txt, font=font)[3]
    d.text(((size - tw) // 2, (size - th) // 2), txt, fill=(236, 240, 246, 255), font=font)
    return img
