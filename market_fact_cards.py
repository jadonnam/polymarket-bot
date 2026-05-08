from __future__ import annotations

import os
from io import BytesIO
from typing import Dict, List, Optional

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from logo_asset_manager import load_logo, load_symbol_icon

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
    img = Image.new("RGB", (W, H), (10, 12, 16))
    d = ImageDraw.Draw(img)
    seed = sum(ord(c) for c in topic) % 70
    for y in range(H):
        v = int(18 + seed * 0.22 + 24 * (y / H))
        d.line([(0, y), (W, y)], fill=(v, v, v + 4))
    return img


def _fit(img: Image.Image, h: int) -> Image.Image:
    ratio = h / max(1, img.height)
    w = max(1, int(img.width * ratio))
    return img.resize((w, h), Image.LANCZOS)


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


def _draw_header(d: ImageDraw.ImageDraw, page_no: int):
    d.text((36, 24), "JADONNAM MARKET FACT", fill=(194, 201, 211), font=_font(21, False))
    d.text((36, 56), f"CARD {page_no}/5", fill=(168, 176, 188), font=_font(20, False))


def _draw_template(
    title: str,
    subtitle: str,
    image_url: str,
    symbol: str,
    page_no: int,
    out_path: str,
    style: str,
) -> str:
    bg = _download_image(image_url)
    if bg is None:
        bg = _base_bg(title)
    bg = _cover(bg)
    bg = ImageEnhance.Contrast(bg).enhance(1.10)
    bg = ImageEnhance.Sharpness(bg).enhance(1.05)
    accent, red_c, green_c = _accent_colors(style)
    logo = load_logo(symbol, 116)
    icon = load_symbol_icon(style if style in ("btc", "etf", "ai", "rates", "us") else "us", 92)

    canvas = bg.convert("RGB")
    d = ImageDraw.Draw(canvas)
    _draw_header(d, page_no)

    if page_no == 1:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle((0, 870, W, H), fill=(0, 0, 0, 142))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), ov).convert("RGB")
        d = ImageDraw.Draw(canvas)
        d.text((40, 130), "[NEW MARKET FACT TEMPLATE]", fill=(255, 205, 116), font=_font(24, True))
        t_lines = _wrap(d, title, _font(72, True), 980, 2)
        y = 910
        for ln in t_lines:
            d.text((40, y), ln, fill=(247, 249, 251), font=_font(72, True))
            y += 78
        b_lines = _wrap(d, subtitle, _font(44, True), 980, 1)
        for ln in b_lines:
            d.text((40, y + 6), ln, fill=(233, 238, 243), font=_font(44, True))
        canvas.paste(logo, (930, 24), logo)
    elif page_no == 2:
        # reason card: 3 short lines
        panel = Image.new("RGBA", (1000, 530), (0, 0, 0, 162))
        canvas.paste(panel, (40, 760), panel)
        d = ImageDraw.Draw(canvas)
        d.text((70, 790), title[:18], fill=(247, 249, 251), font=_font(58, True))
        reasons = [x.strip() for x in subtitle.split("|") if x.strip()]
        if not reasons:
            reasons = [subtitle]
        while len(reasons) < 3:
            reasons.append("핵심 지표 재점검")
        yy = 875
        for idx, line in enumerate(reasons[:3], start=1):
            d.text((78, yy), f"{idx}. {line[:22]}", fill=(232, 237, 242), font=_font(40, True))
            yy += 110
        canvas.paste(icon, (930, 790), icon)
    elif page_no == 3:
        # number dominant card
        panel = Image.new("RGBA", (W, 560), (0, 0, 0, 120))
        canvas.paste(panel, (0, 430), panel)
        d = ImageDraw.Draw(canvas)
        import re
        nums = re.findall(r"[-+]?\d+(?:\.\d+)?%?", subtitle)
        a = nums[0] if nums else "3.2%"
        b = nums[1] if len(nums) > 1 else "1.1%"
        d.text((56, 490), a, fill=green_c if "-" not in a else red_c, font=_font(132, True))
        d.text((56, 640), b, fill=red_c if "-" in b else accent, font=_font(88, True))
        d.text((56, 760), title[:20], fill=(245, 248, 251), font=_font(54, True))
        d.text((56, 834), subtitle[:28], fill=(229, 235, 241), font=_font(36, True))
        canvas.paste(logo, (904, 470), logo)
    elif page_no == 4:
        # why important card
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle((0, 820, W, H), fill=(0, 0, 0, 132))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), ov).convert("RGB")
        d = ImageDraw.Draw(canvas)
        d.text((40, 860), title[:20], fill=(246, 249, 251), font=_font(58, True))
        lines = _wrap(d, subtitle, _font(40, True), 980, 2)
        y = 942
        for ln in lines:
            d.text((40, y), ln, fill=(232, 238, 243), font=_font(40, True))
            y += 56
        d.rounded_rectangle((40, 1062, 470, 1138), radius=16, fill=(25, 30, 36))
        d.text((62, 1080), "생활/투자 영향 즉시 반영", fill=accent, font=_font(28, True))
    else:
        # conclusion + save CTA
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle((0, 940, W, H), fill=(0, 0, 0, 160))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), ov).convert("RGB")
        d = ImageDraw.Draw(canvas)
        d.text((40, 972), title[:18], fill=(247, 249, 251), font=_font(58, True))
        d.text((40, 1048), subtitle[:24], fill=(234, 239, 244), font=_font(42, True))
        d.rounded_rectangle((40, 1130, 600, 1220), radius=20, fill=(19, 26, 34))
        d.text((68, 1158), "저장하고 다음 변동과 비교", fill=accent, font=_font(34, True))
        canvas.paste(icon, (934, 1002), icon)

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    canvas.save(out_path, quality=95)
    return out_path


def build_market_fact_cards(
    pack: Dict[str, object],
    out_dir: str = "output_cardnews",
) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    topic = str(pack.get("title", "오늘 시장 핵심"))
    symbol = str(pack.get("symbol", "N/A"))
    style = _style_key(pack)
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
        subtitle = subtitles[i]
        if i == 1 and "|" not in subtitle:
            subtitle = f"{subtitle}|수급 집중 구간|변동성 체크"
        paths.append(_draw_template(title, subtitle, img_url, symbol, i + 1, p, style))
    return paths
