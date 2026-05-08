from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1080, 1350
FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
BOLD_PATH = os.path.join(FONT_DIR, "Pretendard-Bold.ttf")
REG_PATH = os.path.join(FONT_DIR, "Pretendard-Regular.ttf")


def _font(size: int, bold: bool = True):
    path = BOLD_PATH if bold else REG_PATH
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _cover_crop(img: Image.Image, target_w: int = W, target_h: int = H) -> Image.Image:
    img = img.convert("RGB")
    ratio = max(target_w / max(1, img.width), target_h / max(1, img.height))
    nw = max(1, int(img.width * ratio))
    nh = max(1, int(img.height * ratio))
    resized = img.resize((nw, nh), Image.LANCZOS)
    left = max(0, (nw - target_w) // 2)
    top = max(0, (nh - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _download_news_photo(url: str, out_path: str) -> Optional[str]:
    if not url:
        return None
    try:
        res = requests.get(url, timeout=20)
        res.raise_for_status()
        img = Image.open(BytesIO(res.content)).convert("RGB")
        img = _cover_crop(img)
        img = ImageEnhance.Contrast(img).enhance(1.07)
        img = ImageEnhance.Sharpness(img).enhance(1.06)
        img.save(out_path, quality=95)
        return out_path
    except Exception:
        return None


def _editorial_fallback(seed: str, out_path: str) -> str:
    # Keep fallback looking like finance editorial tone.
    s = sum(ord(c) for c in str(seed or "")) % 50
    top = (20 + s // 4, 29 + s // 5, 41 + s // 7)
    bottom = (40 + s // 3, 58 + s // 4, 84 + s // 6)
    img = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(1, H - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    img.save(out_path, quality=95)
    return out_path


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> List[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), cand, font=font)[2] <= max_width:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:max_lines]


def _draw_slide(base: Image.Image, title: str, body: str, source: str, page_no: int, out_path: str) -> str:
    img = base.copy().convert("RGB")

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, 430), fill=(0, 0, 0, 48))
    od.rectangle((0, 860, W, H), fill=(0, 0, 0, 132))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    brand_font = _font(21, False)
    title_font = _font(64, True)
    body_font = _font(44, True)
    meta_font = _font(24, False)

    draw.text((42, 44), "JADONNAM ECONOMY", fill=(214, 220, 228), font=brand_font)
    draw.text((42, 86), f"{source} · CARD {page_no}/5", fill=(188, 197, 208), font=meta_font)

    t_lines = _wrap(draw, title, title_font, 980, 2)
    y = 925
    for ln in t_lines:
        draw.text((42, y), ln, fill=(246, 248, 250), font=title_font)
        y += 74

    b_lines = _wrap(draw, body, body_font, 980, 3)
    y += 14
    for ln in b_lines:
        draw.text((42, y), ln, fill=(232, 236, 242), font=body_font)
        y += 56

    img.save(out_path, quality=95)
    return out_path


def render_card_news_v2(story: Dict[str, Any], out_dir: str = "output_rank/card_news_v2") -> List[str]:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    image_url = str(story.get("image_url", ""))
    source = str(story.get("source", "Finance Desk"))[:36]
    slides = story.get("slides", []) or []

    base_path = os.path.join(out_dir, "_base.jpg")
    downloaded = _download_news_photo(image_url, base_path)
    if not downloaded:
        downloaded = _editorial_fallback(story.get("topic", "market"), base_path)
    base = Image.open(downloaded).convert("RGB").resize((W, H), Image.LANCZOS)

    paths: List[str] = []
    for idx, slide in enumerate(slides[:5], start=1):
        path = os.path.join(out_dir, f"card_{idx}.jpg")
        _draw_slide(
            base=base,
            title=str(slide.get("title", "")),
            body=str(slide.get("body", "")),
            source=source,
            page_no=idx,
            out_path=path,
        )
        paths.append(path)

    while len(paths) < 5:
        idx = len(paths) + 1
        path = os.path.join(out_dir, f"card_{idx}.jpg")
        _draw_slide(base, "시장 핵심", "핵심 업데이트 확인", source, idx, path)
        paths.append(path)
    return paths[:5]
