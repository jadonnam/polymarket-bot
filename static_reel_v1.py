from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

try:
    from moviepy.editor import ImageClip
except Exception:
    from moviepy import ImageClip

W, H = 1080, 1920
LOGO_DIR = os.path.join("assets", "company_logos")
PHOTO_DIR = os.path.join("assets", "company_photos")

COMPANY_PRESET: Dict[str, Dict[str, object]] = {
    "NVDA": {
        "name_kr": "엔비디아",
        "name_en": "NVIDIA",
        "logo_files": ["nvidia.png", "nvda.png"],
        "photo_files": ["nvidia.jpg", "nvda.jpg", "jensen_huang.jpg", "datacenter.jpg", "gpu.jpg"],
        "logo_urls": [
            "https://upload.wikimedia.org/wikipedia/commons/2/21/Nvidia_logo.svg",
            "https://upload.wikimedia.org/wikipedia/commons/a/a4/NVIDIA_logo.svg",
        ],
        "photo_urls": [
            "https://upload.wikimedia.org/wikipedia/commons/2/21/Nvidia_logo.svg.png",
            "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1600&q=80",
            "https://images.unsplash.com/photo-1581092160607-ee22621dd758?auto=format&fit=crop&w=1600&q=80",
        ],
    },
    "TSLA": {
        "name_kr": "테슬라",
        "name_en": "TESLA",
        "logo_files": ["tesla.png", "tsla.png"],
        "photo_files": ["tesla.jpg", "factory.jpg", "ev.jpg"],
        "logo_urls": ["https://upload.wikimedia.org/wikipedia/commons/b/bd/Tesla_Motors.svg"],
        "photo_urls": [
            "https://images.unsplash.com/photo-1619767886558-efdc7df33bc4?auto=format&fit=crop&w=1600&q=80",
            "https://images.unsplash.com/photo-1492144534655-ae79c964c9d7?auto=format&fit=crop&w=1600&q=80",
        ],
    },
    "AAPL": {
        "name_kr": "애플",
        "name_en": "APPLE",
        "logo_files": ["apple.png", "aapl.png"],
        "photo_files": ["apple.jpg", "iphone.jpg", "apple_store.jpg"],
        "logo_urls": ["https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg"],
        "photo_urls": [
            "https://images.unsplash.com/photo-1592286927505-1def25115558?auto=format&fit=crop&w=1600&q=80",
            "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=1600&q=80",
        ],
    },
    "MSFT": {
        "name_kr": "마이크로소프트",
        "name_en": "MICROSOFT",
        "logo_files": ["microsoft.png", "msft.png"],
        "photo_files": ["microsoft.jpg", "office.jpg"],
        "logo_urls": ["https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg"],
        "photo_urls": [
            "https://images.unsplash.com/photo-1497215728101-856f4ea42174?auto=format&fit=crop&w=1600&q=80",
            "https://images.unsplash.com/photo-1552664730-d307ca884978?auto=format&fit=crop&w=1600&q=80",
        ],
    },
}


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _base() -> Image.Image:
    return Image.new("RGB", (W, H), (6, 8, 10))


def _fetch_image(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return Image.open(BytesIO(r.content))
    except Exception:
        return None


def _find_local_image(base_dir: str, candidates: List[str]) -> Optional[Image.Image]:
    for name in candidates:
        path = os.path.join(base_dir, name)
        if os.path.exists(path):
            try:
                return Image.open(path)
            except Exception:
                continue
    return None


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    src = img.convert("RGB")
    ratio = max(w / max(1, src.width), h / max(1, src.height))
    nw, nh = int(src.width * ratio), int(src.height * ratio)
    r = src.resize((nw, nh), Image.LANCZOS)
    l = max(0, (nw - w) // 2)
    t = max(0, (nh - h) // 2)
    return r.crop((l, t, l + w, t + h))


def _contain_rgba(img: Image.Image, max_size: int = 560) -> Image.Image:
    rgba = img.convert("RGBA")
    ratio = min(max_size / max(1, rgba.width), max_size / max(1, rgba.height))
    nw, nh = max(1, int(rgba.width * ratio)), max(1, int(rgba.height * ratio))
    return rgba.resize((nw, nh), Image.LANCZOS)


def _company_data(ticker: str) -> Dict[str, object]:
    t = ticker.upper().strip()
    return COMPANY_PRESET.get(t, {
        "name_kr": t,
        "name_en": t,
        "logo_files": [f"{t.lower()}.png", f"{t.lower()}.webp"],
        "photo_files": [f"{t.lower()}.jpg", f"{t.lower()}.png"],
        "logo_urls": [],
        "photo_urls": [],
    })


def _load_company_photo(data: Dict[str, object]) -> Optional[Image.Image]:
    local = _find_local_image(PHOTO_DIR, [str(x) for x in data.get("photo_files", [])])
    if local is not None:
        return local
    for url in data.get("photo_urls", []) or []:
        img = _fetch_image(str(url))
        if img is not None:
            return img
    return None


def _load_company_logo(data: Dict[str, object]) -> Optional[Image.Image]:
    local = _find_local_image(LOGO_DIR, [str(x) for x in data.get("logo_files", [])])
    if local is not None:
        return local
    for url in data.get("logo_urls", []) or []:
        img = _fetch_image(str(url))
        if img is not None:
            return img
    return None


def _poster_stock_study() -> Image.Image:
    ticker = "NVDA"
    data = _company_data(ticker)
    bg_raw = _load_company_photo(data)
    img = _cover(bg_raw, W, H) if bg_raw is not None else _base()
    img = Image.blend(img, _base(), alpha=0.28)
    d = ImageDraw.Draw(img)

    # readability overlays
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rectangle((0, 0, W, 320), fill=(0, 0, 0, 112))
    od.rectangle((0, 1360, W, H), fill=(0, 0, 0, 138))
    img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(img)

    d.text((66, 78), "매일 미국 주식 1종목", fill=(247, 249, 251), font=_font(82, True))
    d.text((66, 170), "공부하기", fill=(247, 249, 251), font=_font(82, True))

    logo_raw = _load_company_logo(data)
    if logo_raw is not None:
        logo = _contain_rgba(logo_raw, 560)
    else:
        # still avoid placeholder box; use clean text only fallback
        logo = None
    if logo is not None:
        img.paste(logo, ((W - logo.width) // 2, 520), logo)

    company_kr = str(data.get("name_kr", "엔비디아"))
    company_en = str(data.get("name_en", "NVIDIA"))
    d.text((80, 1488), "#1", fill=(245, 248, 251), font=_font(88, True))
    d.text((80, 1596), company_kr, fill=(245, 248, 251), font=_font(96, True))
    d.text((80, 1716), company_en, fill=(214, 221, 230), font=_font(62, True))
    d.text((72, 1842), "JADONNAM", fill=(166, 176, 190), font=_font(30, False))
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

    poster = _poster_stock_study() if fmt == "stock_study" else _poster_ranking()
    poster.save(poster_path, quality=95)

    clip = ImageClip(poster_path)
    if hasattr(clip, "with_duration"):
        clip = clip.with_duration(duration_sec)
    else:
        clip = clip.set_duration(duration_sec)
    clip.write_videofile(reel_path, fps=30, codec="libx264", audio=False, logger=None)

    return {"poster_path": poster_path, "reel_path": reel_path}
