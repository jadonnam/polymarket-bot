from __future__ import annotations

import base64
import os
import random
from io import BytesIO
from typing import Optional, Tuple

import requests
from PIL import Image, ImageDraw

W, H = 1080, 1350
FALLBACK_DIR = os.path.join("assets", "fallbacks")
DEFAULT_MARKET_JPG = os.path.join(FALLBACK_DIR, "default_market.jpg")


def market_fallback_path(card_index: int) -> str:
    n = max(1, min(5, card_index))
    return os.path.join(FALLBACK_DIR, f"market_{n:02d}.jpg")


def _format_kb(num_bytes: int) -> str:
    kb = max(0, num_bytes) / 1024.0
    if kb >= 100:
        return f"{kb:.0f}kb"
    return f"{kb:.1f}kb"


def _draw_synthetic_market_scene(out_path: str, seed: int) -> None:
    """Non-black trading / chart mood placeholder (no empty cards)."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    rnd = random.Random(seed)
    base_h = rnd.randint(200, 255)
    img = Image.new("RGB", (W, H), (12, 18, 32))
    d = ImageDraw.Draw(img)
    # subtle grid
    for x in range(0, W, 48):
        d.line((x, 0, x, H), fill=(22, 30, 48), width=1)
    for y in range(0, H, 48):
        d.line((0, y, W, y), fill=(22, 30, 48), width=1)
    # gradient wash
    for y in range(H):
        t = y / max(1, H - 1)
        r = int(10 + t * 18)
        g = int(14 + t * 28)
        b = int(28 + t * (base_h % 80))
        d.line((0, y, W, y), fill=(r, g, b))
    # faux candlesticks
    x0 = 60
    for i in range(40):
        x = x0 + i * 24 + rnd.randint(-4, 4)
        if x > W - 40:
            break
        open_y = rnd.randint(200, H - 400)
        close_y = open_y + rnd.randint(-140, 140)
        high_y = min(open_y, close_y) - rnd.randint(10, 50)
        low_y = max(open_y, close_y) + rnd.randint(10, 50)
        up = close_y < open_y
        col = (46, 200, 120) if up else (240, 82, 82)
        d.line((x, high_y, x, low_y), fill=(180, 190, 210), width=2)
        top, bot = sorted((open_y, close_y))
        d.rectangle((x - 7, top, x + 7, bot), fill=col)
    # soft vignette
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, 120), fill=(0, 0, 0, 120))
    od.rectangle((0, H - 200, W, H), fill=(0, 0, 0, 140))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img.save(out_path, quality=92)


def ensure_fallback_assets() -> None:
    """Create fallback JPEGs if missing so we never ship solid-black placeholders."""
    os.makedirs(FALLBACK_DIR, exist_ok=True)
    targets = [DEFAULT_MARKET_JPG] + [market_fallback_path(i) for i in range(1, 6)]
    for idx, path in enumerate(targets):
        if os.path.exists(path) and os.path.getsize(path) > 1024:
            continue
        _draw_synthetic_market_scene(path, seed=9100 + idx * 173)


def _cover_to_card(img: Image.Image) -> Image.Image:
    src = img.convert("RGB")
    scale = max(W / max(1, src.width), H / max(1, src.height))
    nw, nh = int(src.width * scale), int(src.height * scale)
    try:
        resample = Image.Resampling.LANCZOS
    except AttributeError:
        resample = Image.LANCZOS  # Pillow<10
    resized = src.resize((nw, nh), resample)
    l = max(0, (nw - W) // 2)
    t = max(0, (nh - H) // 2)
    return resized.crop((l, t, l + W, t + H))


def try_openai_card_background(
    prompt: str,
    out_path: str,
    *,
    log_env: bool = False,
) -> Tuple[Optional[Image.Image], bool]:
    """
    Returns (image_or_none, attempted).
    Logs success and failure per policy.
    """
    enabled = (os.getenv("ENABLE_OPENAI_CARD_IMAGE") or "false").lower() == "true"
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if log_env:
        print(f"[openai_image] ENABLE_OPENAI_CARD_IMAGE={str(enabled).lower()} OPENAI_API_KEY exists={bool(api_key)}")

    if not enabled:
        return None, False
    if not api_key:
        if log_env:
            print("[openai_image] skip: no API key")
        return None, True
    if not prompt.strip():
        print("[openai_image] skip: empty prompt")
        return None, True

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
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
            raw = requests.get(
                str(data.url),
                timeout=40,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                    )
                },
            ).content
        if not raw:
            raise RuntimeError("OpenAI returned empty image payload")
        img = Image.open(BytesIO(raw)).convert("RGB")
        print(f"[card_image] width={img.width} height={img.height} (after PIL.Image.open, openai)")
        img = _cover_to_card(img)
        img.save(out_path, quality=95)
        print("[openai_image] generated successfully")
        print(f"[openai_image] saved={out_path}")
        sz = os.path.getsize(out_path)
        print(f"[openai_image] file_size={_format_kb(sz)}")
        return img, True
    except Exception as e:
        print(f"[openai_image] OpenAI failed: {repr(e)}")
        return None, True


def log_card_image(
    source: str,
    path: str,
    exists: bool,
    loaded: bool,
) -> None:
    print(f"[card_image] source={source}")
    print(f"[card_image] path={path}")
    print(f"[card_image] exists={exists}")
    print(f"[card_image] loaded={loaded}")


def log_pil_open(img: Optional[Image.Image], context: str) -> None:
    if img is None:
        print(f"[card_image] PIL open ({context}): no image")
        return
    print(f"[card_image] width={img.width} height={img.height} ({context})")
