"""
BoA형 카드 배경 — 차트 JPG 폴백 제거, 코드로만 생성(실사 ref는 금융 키워드만).
"""
from __future__ import annotations

import os
import random
from typing import Any, Dict, Literal, Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFilter = None  # type: ignore

BgKind = Literal["finance_ref", "geopolitical", "tech", "commodity", "asia", "neutral"]


def _blob(article: Dict[str, Any]) -> str:
    title = (article.get("title") or "").lower()
    desc = (article.get("description") or article.get("content") or "").lower()
    return f"{title} {desc}"


def classify_background(article: Dict[str, Any]) -> BgKind:
    b = _blob(article)
    bank = (
        "bank of america",
        "bofa",
        "jpmorgan",
        "goldman",
        "금융",
        "은행",
        "반도체",
        "semiconductor",
        "nvidia",
        "materials stock",
        "소재",
    )
    if any(k in b for k in bank):
        return "finance_ref"
    geo = (
        "iran",
        "iraq",
        "israel",
        "ukraine",
        "russia",
        "war",
        "attack",
        "missile",
        "military",
        "airstrike",
        "ceasefire",
        "민병대",
        "기소",
    )
    if any(k in b for k in geo):
        return "geopolitical"
    if any(k in b for k in ("oil", "crude", "wti", "brent", "gold", "opec", "유가")):
        return "commodity"
    if any(k in b for k in ("fed", "cpi", "inflation", "tariff", "treasury", "rate cut")):
        return "commodity"
    if any(k in b for k in ("chip", "ai ", "data center", "samsung", "삼성", "nvidia")):
        return "tech"
    if any(k in b for k in ("japan", "korea", "china", "yuan", "yen", "asia", "won", "krw")):
        return "asia"
    return "neutral"


def _ref_photo_bank_path() -> Optional[str]:
    root = os.path.dirname(__file__)
    p = os.path.join(root, "assets", "card_references", "ref_photo_bank.png")
    return p if os.path.isfile(p) else None


def _cover(img: "Image.Image", tw: int, th: int) -> "Image.Image":
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    return img.crop((left, top, left + tw, top + th))


def _gradient_base(tw: int, th: int, top: Tuple[int, int, int], bottom: Tuple[int, int, int]) -> "Image.Image":
    base = Image.new("RGB", (tw, th))
    d = ImageDraw.Draw(base)
    for y in range(th):
        t = y / max(th - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        d.line([(0, y), (tw, y)], fill=(r, g, b))
    return base


def _soft_shapes(d: "ImageDraw.ImageDraw", tw: int, th: int, seed: int) -> None:
    rng = random.Random(seed)
    for _ in range(8):
        x0 = rng.randint(-tw // 4, tw)
        y0 = rng.randint(th // 5, th)
        x1 = x0 + rng.randint(tw // 6, tw // 2)
        y1 = y0 + rng.randint(40, 220)
        fill = (rng.randint(20, 60), rng.randint(25, 70), rng.randint(40, 90), rng.randint(18, 45))
        d.ellipse([x0, y0, x1, y1], fill=fill)


def _skyline_silhouette(base: "Image.Image", tw: int, th: int, base_y: int, color: Tuple[int, int, int]) -> None:
    d = ImageDraw.Draw(base)
    blocks = [
        (0, tw // 5, base_y - 80),
        (tw // 6, tw // 3, base_y - 140),
        (tw // 3, tw // 2, base_y - 200),
        (tw // 2, tw * 2 // 3, base_y - 120),
        (tw * 2 // 3, tw - tw // 8, base_y - 260),
        (tw - tw // 4, tw, base_y - 100),
    ]
    for x0, x1, top in blocks:
        d.rectangle([x0, top, x1, base_y], fill=color)


def generate_geopolitical(tw: int, th: int, seed: int = 7) -> "Image.Image":
    base = _gradient_base(tw, th, (28, 42, 78), (12, 14, 22))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    _soft_shapes(d, tw, th, seed)
    for y in range(int(th * 0.55), th):
        t = (y - th * 0.55) / (th * 0.45)
        d.line([(0, y), (tw, y)], fill=(180, 90, 40, int(12 + 35 * t)))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    _skyline_silhouette(base, tw, th, th - 90, (18, 20, 28))
    if ImageFilter:
        base = base.filter(ImageFilter.GaussianBlur(radius=0.6))
    return base


def generate_tech(tw: int, th: int, seed: int = 3) -> "Image.Image":
    base = _gradient_base(tw, th, (18, 32, 68), (8, 12, 28))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    _soft_shapes(d, tw, th, seed + 11)
    d.rectangle([0, int(th * 0.62), tw, th], fill=(0, 180, 220, 28))
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    _skyline_silhouette(base, tw, th, th - 70, (14, 18, 32))
    return base


def generate_commodity(tw: int, th: int, seed: int = 5) -> "Image.Image":
    base = _gradient_base(tw, th, (42, 28, 18), (14, 12, 16))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    _soft_shapes(d, tw, th, seed + 21)
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    _skyline_silhouette(base, tw, th, th - 80, (22, 18, 16))
    return base


def generate_asia(tw: int, th: int, seed: int = 9) -> "Image.Image":
    base = _gradient_base(tw, th, (52, 78, 118), (16, 22, 36))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    _soft_shapes(d, tw, th, seed + 31)
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    _skyline_silhouette(base, tw, th, th - 85, (20, 26, 38))
    return base


def generate_neutral(tw: int, th: int, seed: int = 1) -> "Image.Image":
    base = _gradient_base(tw, th, (72, 118, 168), (22, 28, 42))
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    _soft_shapes(d, tw, th, seed + 41)
    base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    _skyline_silhouette(base, tw, th, th - 75, (24, 30, 44))
    return base


def build_card_background(
    article: Dict[str, Any], tw: int = 1080, th: int = 1350
) -> Tuple["Image.Image", str]:
    """차트 JPG 미사용. (RGB 이미지, bg_mode 라벨)"""
    if Image is None:
        raise RuntimeError("Pillow required")
    kind = classify_background(article)
    if kind == "finance_ref":
        ref = _ref_photo_bank_path()
        if ref:
            raw = Image.open(ref).convert("RGB")
            return _cover(raw, tw, th), "ref_photo_bank"
    seed = abs(hash(_blob(article))) % 10000
    gens = {
        "geopolitical": generate_geopolitical,
        "tech": generate_tech,
        "commodity": generate_commodity,
        "asia": generate_asia,
        "neutral": generate_neutral,
        "finance_ref": generate_neutral,
    }
    gen = gens.get(kind, generate_neutral)
    return gen(tw, th, seed), f"generated:{kind}"
