from __future__ import annotations

import os
from io import BytesIO
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _cover(img: Image.Image, w: int = W, h: int = H) -> Image.Image:
    src = img.convert("RGB")
    ratio = max(w / max(1, src.width), h / max(1, src.height))
    nw, nh = int(src.width * ratio), int(src.height * ratio)
    r = src.resize((nw, nh), Image.LANCZOS)
    l = max(0, (nw - w) // 2)
    t = max(0, (nh - h) // 2)
    return r.crop((l, t, l + w, t + h))


def _fetch_image(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        return Image.open(BytesIO(res.content)).convert("RGB")
    except Exception:
        return None


def render_news_template(
    headline: str,
    image_url: str,
    source_text: str,
    out_path: str = "output_cardnews/news.jpg",
) -> str:
    bg = _fetch_image(image_url)
    if bg is None:
        bg = Image.new("RGB", (W, H), (8, 10, 14))
    img = _cover(bg)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, 140), fill=(0, 0, 0, 70))
    od.rectangle((0, H - 360, W, H), fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(img)
    d.text((40, 44), "NEWS BRIEF CARD", fill=(206, 212, 222), font=_font(22, False))
    d.text((40, 86), str(source_text)[:36], fill=(176, 184, 196), font=_font(20, False))
    d.rounded_rectangle((40, H - 300, 52, H - 92), radius=6, fill=(245, 247, 250))
    d.text((78, H - 292), str(headline)[:28], fill=(246, 248, 251), font=_font(64, True))
    d.text((40, 1302), "JADONNAM", fill=(166, 176, 190), font=_font(28, False))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)
    return out_path
