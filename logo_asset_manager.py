from __future__ import annotations

import os
from typing import Dict

from PIL import Image, ImageDraw, ImageFont

ASSET_DIR = os.path.join("assets", "logos")
SYMBOL_DIR = os.path.join("assets", "symbols")

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


def load_symbol_icon(name: str, size: int = 92) -> Image.Image:
    key = str(name or "").lower().strip()
    file_map = {
        "us": "us.png",
        "btc": "btc.png",
        "etf": "etf.png",
        "ai": "ai.png",
        "rates": "rates.png",
    }
    filename = file_map.get(key, "")
    path = os.path.join(SYMBOL_DIR, filename) if filename else ""
    if path and os.path.exists(path):
        img = Image.open(path).convert("RGBA")
        return img.resize((size, size), Image.LANCZOS)

    # Fallback icon badge
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    fill = (22, 26, 33, 235)
    if key == "btc":
        fill = (88, 60, 20, 235)
    elif key == "us":
        fill = (16, 34, 64, 235)
    elif key == "ai":
        fill = (20, 58, 52, 235)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=20, fill=fill, outline=(90, 98, 112, 255), width=2)
    txt_map = {"us": "US", "btc": "BTC", "etf": "ETF", "ai": "AI", "rates": "RATE"}
    txt = txt_map.get(key, key[:4].upper() or "N/A")
    font = _font(max(16, size // 4))
    tw = d.textbbox((0, 0), txt, font=font)[2]
    th = d.textbbox((0, 0), txt, font=font)[3]
    d.text(((size - tw) // 2, (size - th) // 2), txt, fill=(240, 244, 248, 255), font=font)
    return img


def build_fallback_asset_background(style: str, symbol: str, width: int, height: int) -> Image.Image:
    style = str(style or "").lower().strip()
    base = Image.new("RGB", (width, height), (10, 12, 16))
    d = ImageDraw.Draw(base)

    palette = {
        "btc": ((40, 28, 12), (20, 14, 8)),
        "ai": ((10, 32, 28), (8, 18, 18)),
        "etf": ((14, 24, 40), (10, 16, 28)),
        "rates": ((24, 24, 28), (14, 14, 18)),
        "us": ((16, 20, 34), (10, 14, 22)),
    }
    top, bottom = palette.get(style, ((18, 20, 24), (10, 12, 16)))
    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        d.line([(0, y), (width, y)], fill=(r, g, b))

    # subtle chart-like lines to avoid empty template feel
    line_color = (84, 96, 116)
    for i in range(6):
        y = int(height * (0.22 + i * 0.11))
        d.line([(0, y), (width, y)], fill=line_color, width=1)

    logo = load_logo(symbol, min(220, width // 4))
    sym = load_symbol_icon(style if style in ("btc", "ai", "etf", "rates", "us") else "us", min(140, width // 6))
    base.paste(logo, (width - logo.width - 44, 38), logo)
    base.paste(sym, (44, 40), sym)

    # fake chart stroke
    points = [
        (int(width * 0.08), int(height * 0.72)),
        (int(width * 0.24), int(height * 0.66)),
        (int(width * 0.42), int(height * 0.69)),
        (int(width * 0.58), int(height * 0.57)),
        (int(width * 0.78), int(height * 0.61)),
        (int(width * 0.92), int(height * 0.50)),
    ]
    d.line(points, fill=(112, 220, 160), width=5)
    for x, y in points:
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(112, 220, 160))
    return base
