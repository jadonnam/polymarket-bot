from __future__ import annotations

import os
from io import BytesIO
from typing import List, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _fetch(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        return Image.open(BytesIO(res.content)).convert("RGB")
    except Exception:
        return None


def _cover_variant(img: Image.Image, variant: int) -> Image.Image:
    src = img.convert("RGB")
    scale = max(W / max(1, src.width), H / max(1, src.height))
    nw, nh = int(src.width * scale), int(src.height * scale)
    resized = src.resize((nw, nh), Image.LANCZOS)
    max_x = max(0, nw - W)
    # allow same image repeat with different crop focus
    anchors = [0.10, 0.35, 0.50, 0.65, 0.85]
    x = int(max_x * anchors[(variant - 1) % len(anchors)])
    y = max(0, (nh - H) // 2)
    return resized.crop((x, y, x + W, y + H))


def render_simple_news_card(
    image_path: str = "",
    image_url: str = "",
    title: str = "",
    tag: str = "MARKET",
    source_label: str = "JADONNAM",
    out_path: str = "output_cardnews/card_01.jpg",
    crop_variant: int = 1,
) -> str:
    bg = None
    if image_path and os.path.exists(image_path):
        try:
            bg = Image.open(image_path).convert("RGB")
        except Exception:
            bg = None
    if bg is None:
        bg = _fetch(image_url)
    if bg is None:
        bg = Image.new("RGB", (W, H), (8, 10, 14))
    img = _cover_variant(bg, crop_variant)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # bottom 45% gradient-like blocks
    od.rectangle((0, int(H * 0.55), W, H), fill=(0, 0, 0, 155))
    od.rectangle((0, 0, W, 130), fill=(0, 0, 0, 70))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(img)
    d.text((40, 36), "JADONNAM", fill=(212, 218, 228), font=_font(22, False))

    t = str(tag or "MARKET").upper()[:12]
    tw = d.textbbox((0, 0), t, font=_font(24, True))[2]
    x1 = W - 44 - tw - 30
    d.rounded_rectangle((x1, 30, W - 44, 84), radius=14, fill=(18, 24, 34))
    d.text((x1 + 15, 46), t, fill=(242, 246, 250), font=_font(24, True))

    d.rounded_rectangle((44, H - 330, 56, H - 90), radius=6, fill=(245, 247, 250))
    text = str(title or "")[:32]
    if len(text) <= 15:
        lines = [text]
    else:
        lines = [text[:15], text[15:30]]
    y = H - 320
    for ln in lines:
        d.text((82, y), ln, fill=(247, 249, 251), font=_font(74, True))
        y += 84

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)
    return out_path


def build_simple_news_card_set(
    out_dir: str,
    image_url: str,
    titles: List[str],
    tags: List[str],
    source_label: str = "JADONNAM",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    out: List[str] = []
    for i in range(5):
        out_path = os.path.join(out_dir, f"card_{i+1:02d}.jpg")
        title = titles[i] if i < len(titles) else f"핵심 이슈 {i+1}"
        tag = tags[i] if i < len(tags) else "MARKET"
        out.append(
            render_simple_news_card(
                image_url=image_url,
                title=title,
                tag=tag,
                source_label=source_label,
                out_path=out_path,
                crop_variant=i + 1,
            )
        )
    return out
