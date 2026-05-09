from __future__ import annotations

import os
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import requests
from PIL import Image, ImageDraw, ImageFont

from market_layout_system import (
    DEFAULT_MARKET_JPG,
    ensure_fallback_assets,
    log_card_image,
    log_pil_open,
    market_fallback_path,
    try_openai_card_background,
)

W, H = 1080, 1350
ENABLE_OPENAI_CARD_IMAGE = (os.getenv("ENABLE_OPENAI_CARD_IMAGE") or "false").lower() == "true"

try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = Image.LANCZOS


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
    r = src.resize((nw, nh), _RESAMPLE)
    l = max(0, (nw - w) // 2)
    t = max(0, (nh - h) // 2)
    return r.crop((l, t, l + w, t + h))


def _fetch_image(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }
        res = requests.get(url, timeout=25, headers=headers)
        res.raise_for_status()
        return Image.open(BytesIO(res.content)).convert("RGB")
    except Exception as e:
        print(f"[card_image] url PIL load failed: {repr(e)}")
        return None


def _load_file(path: str) -> Optional[Image.Image]:
    try:
        if not path or not os.path.exists(path):
            return None
        img = Image.open(path).convert("RGB")
        log_pil_open(img, "local file")
        return img
    except Exception as e:
        print(f"[card_image] local load error: {repr(e)}")
        return None


def _resolve_bg(
    *,
    card_index: int,
    image_url: str,
    image_prompt: str,
    openai_out_path: str,
) -> Image.Image:
    ensure_fallback_assets()
    bg: Optional[Image.Image] = None
    chosen = "fallback"
    detail_path = ""
    path_exists = False

    prompt_use = (image_prompt or "").strip()
    if ENABLE_OPENAI_CARD_IMAGE and prompt_use:
        oimg, _ = try_openai_card_background(
            prompt_use,
            openai_out_path,
            log_env=(card_index == 1),
        )
        if oimg is not None:
            bg = oimg
            chosen = "openai"
            detail_path = openai_out_path
            path_exists = os.path.exists(detail_path)

    if bg is None and image_url:
        detail_path = image_url
        path_exists = bool(image_url.strip())
        bg = _fetch_image(image_url)
        if bg is not None:
            log_pil_open(bg, "url fetch")
            chosen = "url"

    if bg is None:
        detail_path = DEFAULT_MARKET_JPG
        path_exists = os.path.exists(detail_path)
        bg = _load_file(DEFAULT_MARKET_JPG)
        if bg is not None:
            chosen = "fallback"

    if bg is None:
        detail_path = market_fallback_path(card_index)
        path_exists = os.path.exists(detail_path)
        bg = _load_file(detail_path)
        if bg is not None:
            chosen = "fallback"

    if bg is None:
        ensure_fallback_assets()
        bg = _load_file(DEFAULT_MARKET_JPG) or _load_file(market_fallback_path(card_index))
        detail_path = DEFAULT_MARKET_JPG
        path_exists = os.path.exists(detail_path)
        chosen = "fallback"

    if bg is None:
        raise RuntimeError("signature card background missing after fallbacks")

    log_card_image(chosen, detail_path, path_exists if chosen != "url" else True, True)
    log_pil_open(bg, "background final")
    return bg


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
    card_index: int = 1,
) -> str:
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    os.makedirs("output_cards", exist_ok=True)
    openai_out = os.path.join("output_cards", f"bg_{card_index:02d}.jpg")
    bg = _resolve_bg(
        card_index=card_index,
        image_url=image_url,
        image_prompt=image_prompt,
        openai_out_path=openai_out,
    )
    img = _cover(bg)
    print(f"[card_image] after cover crop width={img.width} height={img.height}")

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, 170), fill=(0, 0, 0, 78))
    od.rectangle((0, H - 440, W, H), fill=(0, 0, 0, 165))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(img)
    d.text((38, 40), brand_text, fill=(214, 220, 230), font=_font(24, False))

    tag = str(market_tag or "MARKET")[:12].upper()
    tag_w = d.textbbox((0, 0), tag, font=_font(26, True))[2] + 42
    x1 = W - 36 - tag_w
    d.rounded_rectangle((x1, 34, W - 36, 86), radius=14, fill=(18, 24, 34))
    d.text((x1 + 22, 48), tag, fill=(240, 244, 248), font=_font(26, True))

    d.rounded_rectangle((44, H - 350, 56, H - 96), radius=6, fill=(245, 247, 250))

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
                card_index=idx,
            )
        )
    return out
