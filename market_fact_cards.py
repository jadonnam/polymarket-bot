from __future__ import annotations

import os
from io import BytesIO
from typing import Dict, List, Optional

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from logo_asset_manager import load_logo

W, H = 1080, 1350


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _download_image(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return Image.open(BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def _cover(img: Image.Image, w: int = W, h: int = H) -> Image.Image:
    ratio = max(w / max(1, img.width), h / max(1, img.height))
    nw, nh = int(img.width * ratio), int(img.height * ratio)
    r = img.resize((nw, nh), Image.LANCZOS)
    l = (nw - w) // 2
    t = (nh - h) // 2
    return r.crop((l, t, l + w, t + h))


def _base_bg(topic: str) -> Image.Image:
    img = Image.new("RGB", (W, H), (7, 9, 12))
    d = ImageDraw.Draw(img)
    seed = sum(ord(c) for c in topic) % 70
    for y in range(H):
        v = int(16 + seed * 0.3 + 44 * (y / H))
        d.line([(0, y), (W, y)], fill=(v // 2, v // 2, v))
    return img


def _render_card(
    title: str,
    subtitle: str,
    image_url: str,
    symbol: str,
    page_no: int,
    out_path: str,
) -> str:
    bg = _download_image(image_url)
    if bg is None:
        bg = _base_bg(title)
    bg = _cover(bg)
    bg = ImageEnhance.Contrast(bg).enhance(1.08)

    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rectangle((0, 860, W, H), fill=(0, 0, 0, 130))
    od.rectangle((0, 0, W, 150), fill=(0, 0, 0, 72))
    merged = Image.alpha_composite(bg.convert("RGBA"), ov).convert("RGB")
    d = ImageDraw.Draw(merged)
    d.text((44, 40), f"MARKET FACT CARD {page_no}/5", fill=(190, 198, 208), font=_font(22, False))
    d.text((44, 920), title[:24], fill=(245, 248, 251), font=_font(68, True))
    d.text((44, 1010), subtitle[:34], fill=(231, 236, 242), font=_font(44, True))

    logo = load_logo(symbol, 120)
    merged.paste(logo, (916, 26), logo)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    merged.save(out_path, quality=95)
    return out_path


def build_market_fact_cards(
    pack: Dict[str, object],
    out_dir: str = "output_cardnews",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    topic = str(pack.get("title", "오늘 시장 핵심"))
    symbol = str(pack.get("symbol", "N/A"))
    image_urls = [str(x) for x in (pack.get("image_urls", []) or []) if str(x).strip()]
    subtitles = [str(x) for x in (pack.get("bullets", []) or [])]
    while len(subtitles) < 5:
        subtitles.append("핵심 지표 확인")

    paths: List[str] = []
    for i in range(5):
        p = os.path.join(out_dir, f"card_{i+1:02d}.jpg")
        img_url = image_urls[i] if i < len(image_urls) else ""
        title = "오늘 시장을 흔든 이슈" if i == 0 else f"핵심 포인트 {i}"
        if i == 4:
            title = "한 줄 결론"
        paths.append(_render_card(title, subtitles[i], img_url, symbol, i + 1, p))
    return paths
