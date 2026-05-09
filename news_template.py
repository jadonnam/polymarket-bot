from __future__ import annotations

import base64
import os
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
ENABLE_OPENAI_CARD_IMAGE = (os.getenv("ENABLE_OPENAI_CARD_IMAGE") or "false").lower() == "true"


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


def _load_openai_bg(prompt: str, out_path: str) -> Optional[Image.Image]:
    if not ENABLE_OPENAI_CARD_IMAGE:
        return None
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except Exception:
        return None

    try:
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1536",
        )
        data = result.data[0]
        raw = None
        if getattr(data, "b64_json", None):
            raw = base64.b64decode(data.b64_json)
        elif getattr(data, "url", None):
            raw = requests.get(data.url, timeout=40).content
        if not raw:
            return None
        img = _cover(Image.open(BytesIO(raw)).convert("RGB"))
        img.save(out_path, quality=95)
        return img
    except Exception:
        return None


def _fetch_image(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        return Image.open(BytesIO(res.content)).convert("RGB")
    except Exception:
        return None


def _split_two_lines(text: str, max_len: int = 15) -> Tuple[str, str]:
    t = str(text or "").strip()
    if len(t) <= max_len:
        return t, ""
    cut = t[:max_len].rstrip()
    rest = t[max_len:].lstrip()
    return cut, rest[:max_len]


def render_signature_card(
    headline: str,
    market_tag: str,
    image_url: str,
    image_prompt: str,
    out_path: str,
    brand_text: str = "JADONNAM",
) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    bg_cache_path = out_path.replace("card_", "_bg_")
    bg = _load_openai_bg(image_prompt, bg_cache_path)
    if bg is None:
        bg = _fetch_image(image_url)
    if bg is None:
        bg = Image.new("RGB", (W, H), (8, 10, 14))
    img = _cover(bg)

    # black gradient overlay (signature)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, 170), fill=(0, 0, 0, 78))
    od.rectangle((0, H - 440, W, H), fill=(0, 0, 0, 165))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(img)
    # 4) left-top small brand
    d.text((38, 40), brand_text, fill=(214, 220, 230), font=_font(24, False))

    # 3) top-right market tag box
    tag = str(market_tag or "MARKET")[:12].upper()
    tag_w = d.textbbox((0, 0), tag, font=_font(26, True))[2] + 42
    x1 = W - 36 - tag_w
    d.rounded_rectangle((x1, 34, W - 36, 86), radius=14, fill=(18, 24, 34))
    d.text((x1 + 22, 48), tag, fill=(240, 244, 248), font=_font(26, True))

    # 1) left-bottom white vertical line
    d.rounded_rectangle((44, H - 350, 56, H - 96), radius=6, fill=(245, 247, 250))

    # 2) bottom 2-line large headline
    h1, h2 = _split_two_lines(headline, 15)
    d.text((82, H - 332), h1, fill=(247, 249, 251), font=_font(78, True))
    if h2:
        d.text((82, H - 244), h2, fill=(247, 249, 251), font=_font(78, True))

    img.save(out_path, quality=95)
    return out_path


def build_jadonnam_signature_cards(
    out_dir: str,
    cards: List[Dict[str, str]],
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    out: List[str] = []
    for idx, item in enumerate(cards[:5], start=1):
        path = os.path.join(out_dir, f"card_{idx:02d}.jpg")
        out.append(
            render_signature_card(
                headline=str(item.get("headline", "")),
                market_tag=str(item.get("tag", "MARKET")),
                image_url=str(item.get("image_url", "")),
                image_prompt=str(item.get("prompt", "")),
                out_path=path,
            )
        )
    return out
