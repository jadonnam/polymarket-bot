from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from logo_asset_manager import load_logo, load_symbol_icon

try:
    from moviepy.editor import ImageClip
except Exception:
    from moviepy import ImageClip

W, H = 1080, 1920


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _base() -> Image.Image:
    return Image.new("RGB", (W, H), (6, 8, 10))


def _ticker_box(ticker: str, size: int = 520) -> Image.Image:
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=36, fill=(236, 240, 245), outline=(230, 234, 238), width=2)
    t = ticker[:6].upper() or "N/A"
    f = _font(max(60, size // 4), True)
    tw = d.textbbox((0, 0), t, font=f)[2]
    th = d.textbbox((0, 0), t, font=f)[3]
    d.text(((size - tw) // 2, (size - th) // 2), t, fill=(16, 20, 26), font=f)
    return img


def _poster_stock_study() -> Image.Image:
    img = _base()
    d = ImageDraw.Draw(img)
    d.text((70, 84), "매일 미국 주식 1종목", fill=(247, 249, 251), font=_font(84, True))
    d.text((70, 176), "공부하기", fill=(247, 249, 251), font=_font(84, True))

    ticker = "NVDA"
    company_kr = "엔비디아"
    logo = load_logo(ticker, 520)
    center_x = (W - logo.width) // 2
    center_y = 520
    # If logo loader returns fallback badge, keep a cleaner white ticker box.
    if logo.width < 200:
        logo = _ticker_box(ticker, 520)
        center_x = (W - logo.width) // 2
    img.paste(logo, (center_x, center_y), logo)

    d.text((80, 1480), "#1", fill=(245, 248, 251), font=_font(88, True))
    d.text((80, 1590), company_kr, fill=(245, 248, 251), font=_font(96, True))
    d.text((80, 1710), ticker, fill=(214, 221, 230), font=_font(62, True))
    d.text((72, 1842), "@jadonnam", fill=(166, 176, 190), font=_font(30, False))
    return img


def _poster_ranking() -> Image.Image:
    img = _base()
    d = ImageDraw.Draw(img)
    d.text((60, 72), "올해 반도체 기업 수익률 순위", fill=(245, 248, 251), font=_font(60, True))
    d.text((60, 154), "저장형 순위 카드", fill=(188, 197, 209), font=_font(34, False))

    rows: List[tuple[str, str, str]] = [
        ("NVDA", "NVIDIA", "+38.2%"),
        ("AVGO", "Broadcom", "+27.4%"),
        ("AMD", "AMD", "+19.5%"),
        ("TSM", "TSMC", "+14.1%"),
        ("ASML", "ASML", "+11.6%"),
    ]
    y = 320
    for idx, (sym, name, ret) in enumerate(rows, start=1):
        lg = load_logo(sym, 94)
        img.paste(lg, (72, y), lg)
        d.text((190, y + 10), f"{idx}. {name}", fill=(238, 242, 247), font=_font(46, True))
        color = (95, 214, 128) if not ret.startswith("-") else (255, 101, 101)
        d.text((832, y + 18), ret, fill=color, font=_font(40, True))
        d.line([(70, y + 116), (1010, y + 116)], fill=(42, 50, 62), width=1)
        y += 126

    icon = load_symbol_icon("etf", 120)
    img.paste(icon, (900, 76), icon)
    d.rounded_rectangle((60, 1540, 1020, 1690), radius=24, fill=(18, 24, 32))
    d.text((92, 1586), "한 장 저장하고 다음 분기 실적 시즌 전에 다시 확인", fill=(231, 237, 244), font=_font(35, True))
    d.text((60, 1780), "JADONNAM", fill=(176, 185, 198), font=_font(30, False))
    return img


def build_static_reel_v1(
    output_dir: str = "output_static_reel",
    reel_format: str = "stock_study",
    duration_sec: float = 18.0,
) -> Dict[str, str]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fmt = (reel_format or "stock_study").strip().lower()
    if fmt not in ("stock_study", "ranking"):
        fmt = "stock_study"

    poster_path = os.path.join(output_dir, "poster.jpg")
    reel_path = os.path.join(output_dir, "reel_output.mp4")

    # stock_study format is now fixed to static simple style.
    poster = _poster_stock_study() if fmt == "stock_study" else _poster_ranking()
    poster.save(poster_path, quality=95)

    clip = ImageClip(poster_path)
    if hasattr(clip, "with_duration"):
        clip = clip.with_duration(duration_sec)
    else:
        clip = clip.set_duration(duration_sec)
    clip.write_videofile(reel_path, fps=30, codec="libx264", audio=False, logger=None)

    return {"poster_path": poster_path, "reel_path": reel_path}
