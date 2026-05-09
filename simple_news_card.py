from __future__ import annotations

import os
from io import BytesIO
from typing import List, Optional

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


def _fetch(url: str) -> Optional[Image.Image]:
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


def _cover_variant(img: Image.Image, variant: int) -> Image.Image:
    src = img.convert("RGB")
    scale = max(W / max(1, src.width), H / max(1, src.height))
    nw, nh = int(src.width * scale), int(src.height * scale)
    resized = src.resize((nw, nh), _RESAMPLE)
    max_x = max(0, nw - W)
    anchors = [0.10, 0.35, 0.50, 0.65, 0.85]
    x = int(max_x * anchors[(variant - 1) % len(anchors)])
    y = max(0, (nh - H) // 2)
    return resized.crop((x, y, x + W, y + H))


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


def _resolve_background(
    *,
    card_index: int,
    image_path: str,
    image_url: str,
    image_prompt: str,
) -> Image.Image:
    ensure_fallback_assets()

    bg: Optional[Image.Image] = None
    chosen = "fallback"
    detail_path = ""
    path_exists = False

    # 1) OpenAI (optional)
    openai_out = os.path.join("output_cards", f"bg_{card_index:02d}.jpg")
    prompt_use = (image_prompt or "").strip()
    if (os.getenv("ENABLE_OPENAI_CARD_IMAGE") or "false").lower() == "true" and prompt_use:
        oimg, _attempted = try_openai_card_background(
            prompt_use,
            openai_out,
            log_env=(card_index == 1),
        )
        if oimg is not None:
            bg = oimg
            chosen = "openai"
            detail_path = openai_out
            path_exists = os.path.exists(detail_path)

    # 2) Local path
    if bg is None and image_path:
        path_exists = os.path.exists(image_path)
        bg = _load_file(image_path) if path_exists else None
        if bg is not None:
            chosen = "local"
            detail_path = image_path

    # 3) URL
    if bg is None and image_url:
        detail_path = image_url
        path_exists = True
        try:
            bg = _fetch(image_url)
            if bg is not None:
                log_pil_open(bg, "url fetch")
        except Exception as e:
            print(f"[card_image] url fetch error: {repr(e)}")
            bg = None
        if bg is not None:
            chosen = "url"

    # 4) default_market.jpg (required fallback, never solid black)
    if bg is None:
        detail_path = DEFAULT_MARKET_JPG
        path_exists = os.path.exists(detail_path)
        bg = _load_file(DEFAULT_MARKET_JPG)
        if bg is not None:
            chosen = "fallback"

    # 5) market_NN.jpg
    if bg is None:
        detail_path = market_fallback_path(card_index)
        path_exists = os.path.exists(detail_path)
        bg = _load_file(detail_path)
        if bg is not None:
            chosen = "fallback"

    # 6) regenerate assets and retry (must not return empty)
    if bg is None:
        ensure_fallback_assets()
        bg = _load_file(DEFAULT_MARKET_JPG) or _load_file(market_fallback_path(card_index))
        detail_path = DEFAULT_MARKET_JPG
        path_exists = os.path.exists(detail_path)
        chosen = "fallback"

    if bg is None:
        raise RuntimeError("card background resolution failed after fallbacks")

    log_card_image(chosen, detail_path, path_exists if chosen != "url" else True, True)
    log_pil_open(bg, "background final")
    return bg


def render_simple_news_card(
    image_path: str = "",
    image_url: str = "",
    image_prompt: str = "",
    title: str = "",
    tag: str = "MARKET",
    source_label: str = "JADONNAM",
    out_path: str = "output_cardnews/card_01.jpg",
    crop_variant: int = 1,
    card_index: int = 1,
) -> str:
    bg = _resolve_background(
        card_index=card_index,
        image_path=image_path or "",
        image_url=image_url or "",
        image_prompt=image_prompt or "",
    )
    img = _cover_variant(bg, crop_variant)
    print(f"[card_image] after cover crop width={img.width} height={img.height}")

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
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
    image_prompts: Optional[List[str]] = None,
    image_path: str = "",
) -> List[str]:
    ensure_fallback_assets()
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs("output_cards", exist_ok=True)
    prompts = image_prompts or []
    out: List[str] = []
    for i in range(5):
        idx = i + 1
        out_path = os.path.join(out_dir, f"card_{idx:02d}.jpg")
        title = titles[i] if i < len(titles) else f"핵심 이슈 {idx}"
        tag = tags[i] if i < len(tags) else "MARKET"
        prompt = prompts[i] if i < len(prompts) else ""
        out.append(
            render_simple_news_card(
                image_path=image_path,
                image_url=image_url,
                image_prompt=prompt,
                title=title,
                tag=tag,
                source_label=source_label,
                out_path=out_path,
                crop_variant=idx,
                card_index=idx,
            )
        )
    return out
