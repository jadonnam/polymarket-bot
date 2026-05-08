from __future__ import annotations

import os
import re
from io import BytesIO
from typing import Dict, List, Optional

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from logo_asset_manager import build_fallback_asset_background, load_logo, load_symbol_icon

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


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_w: int, max_lines: int) -> List[str]:
    words = str(text or "").split()
    if not words:
        return [""]
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), cand, font=font)[2] <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:max_lines]


def _style_key(pack: Dict[str, object]) -> str:
    title = str(pack.get("title", "")).lower()
    symbol = str(pack.get("symbol", "")).upper()
    if "btc" in title or symbol in ("BTC", "ETH"):
        return "btc"
    if any(k in title for k in ["ai", "semiconductor", "반도체"]):
        return "ai"
    if "etf" in title:
        return "etf"
    if any(k in title for k in ["금리", "cpi", "rates"]):
        return "rates"
    if any(k in title for k in ["미국", "us", "nasdaq", "s&p"]):
        return "us"
    return "bigtech"


def _accent_colors(style: str):
    if style == "btc":
        return (245, 166, 61), (255, 83, 83), (69, 210, 126)
    if style == "ai":
        return (92, 221, 202), (255, 95, 95), (89, 214, 124)
    if style == "rates":
        return (175, 182, 196), (255, 97, 97), (96, 210, 126)
    if style == "etf":
        return (109, 180, 255), (255, 96, 96), (99, 213, 128)
    return (198, 205, 215), (255, 98, 98), (94, 212, 128)


def _draw_header(draw: ImageDraw.ImageDraw, page_no: int):
    draw.text((36, 26), "JADONNAM", fill=(212, 218, 226), font=_font(22, False))
    draw.text((36, 58), f"CARD {page_no}/5", fill=(176, 184, 196), font=_font(18, False))


def _overlay_for_readability(base: Image.Image) -> Image.Image:
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rectangle((0, 0, W, 130), fill=(0, 0, 0, 58))
    d.rectangle((0, H - 440, W, H), fill=(0, 0, 0, 148))
    return Image.alpha_composite(base.convert("RGBA"), ov).convert("RGB")


def _left_vertical_line(canvas: Image.Image) -> None:
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((44, H - 338, 54, H - 84), radius=5, fill=(245, 247, 250))


def _title_block(canvas: Image.Image, title: str, subtitle: str = "") -> None:
    d = ImageDraw.Draw(canvas)
    y = H - 308
    t_lines = _wrap(d, title, _font(76, True), 960, 2)
    for ln in t_lines:
        d.text((78, y), ln, fill=(247, 249, 251), font=_font(76, True))
        y += 82
    if subtitle:
        s_lines = _wrap(d, subtitle, _font(40, True), 930, 1)
        for ln in s_lines:
            d.text((78, y + 8), ln, fill=(230, 236, 242), font=_font(40, True))


def _build_base(image_url: str, style: str, symbol: str, title_seed: str) -> Image.Image:
    bg = _download_image(image_url)
    if bg is None:
        bg = build_fallback_asset_background(style=style, symbol=symbol, width=W, height=H)
    bg = _cover(bg)
    bg = ImageEnhance.Contrast(bg).enhance(1.10)
    bg = ImageEnhance.Sharpness(bg).enhance(1.05)
    return _overlay_for_readability(bg.convert("RGB"))


def _draw_template(
    title: str,
    subtitle: str,
    image_url: str,
    symbol: str,
    page_no: int,
    out_path: str,
    style: str,
) -> str:
    canvas = _build_base(image_url, style, symbol, title)
    accent, red_c, green_c = _accent_colors(style)
    logo = load_logo(symbol, 116)
    icon = load_symbol_icon(style if style in ("btc", "etf", "ai", "rates", "us") else "us", 92)

    d = ImageDraw.Draw(canvas)
    _draw_header(d, page_no)
    _left_vertical_line(canvas)

    if page_no == 1:
        _title_block(canvas, title, subtitle)
        canvas.paste(logo, (930, 24), logo)
    elif page_no == 2:
        panel = Image.new("RGBA", (1000, 240), (0, 0, 0, 122))
        canvas.paste(panel, (40, H - 360), panel)
        _title_block(canvas, title, subtitle)
        canvas.paste(icon, (930, 24), icon)
    elif page_no == 3:
        panel = Image.new("RGBA", (W, 620), (0, 0, 0, 128))
        canvas.paste(panel, (0, 360), panel)
        d = ImageDraw.Draw(canvas)
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?%?", subtitle)
        a = nums[0] if nums else "3.2%"
        b = nums[1] if len(nums) > 1 else "1.1%"
        d.text((72, 500), a, fill=green_c if "-" not in a else red_c, font=_font(148, True))
        d.text((72, 668), b, fill=red_c if "-" in b else accent, font=_font(96, True))
        d.text((78, 834), title[:20], fill=(245, 248, 251), font=_font(52, True))
        canvas.paste(logo, (904, 470), logo)
    elif page_no == 4:
        _title_block(canvas, title, subtitle)
        d = ImageDraw.Draw(canvas)
        d.rounded_rectangle((78, H - 108, 620, H - 44), radius=14, fill=(20, 25, 31))
        d.text((102, H - 92), "시장 영향 포인트", fill=accent, font=_font(30, True))
    else:
        _title_block(canvas, title, subtitle)
        d = ImageDraw.Draw(canvas)
        d.rounded_rectangle((78, H - 106, 710, H - 34), radius=18, fill=(19, 26, 34))
        d.text((104, H - 86), "저장하고 장 시작 전에 다시 보기", fill=accent, font=_font(32, True))
        canvas.paste(icon, (934, 1002), icon)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    canvas.save(out_path, quality=95)
    return out_path


def build_market_fact_cards(
    pack: Dict[str, object],
    out_dir: str = "output_cardnews",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    symbol = str(pack.get("symbol", "N/A"))
    style = _style_key(pack)
    image_urls = [str(x) for x in (pack.get("image_urls", []) or []) if str(x).strip()]
    subtitles = [str(x) for x in (pack.get("bullets", []) or [])]
    while len(subtitles) < 5:
        subtitles.append("핵심 지표 확인")

    titles = ["오늘 핵심 이슈", "핵심 이유", "숫자/수익률", "시장 영향", "결론/저장"]
    paths: List[str] = []
    for i in range(5):
        p = os.path.join(out_dir, f"card_{i+1:02d}.jpg")
        img_url = image_urls[i] if i < len(image_urls) else ""
        subtitle = subtitles[i].replace("|", " ").strip()[:24]
        paths.append(_draw_template(titles[i], subtitle, img_url, symbol, i + 1, p, style))
    return paths
