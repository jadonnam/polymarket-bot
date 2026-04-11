from __future__ import annotations

import base64
import math
import os
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

try:
    from moviepy.editor import AudioClip, ImageClip, concatenate_videoclips
except Exception:
    from moviepy import AudioClip, ImageClip, concatenate_videoclips

W, H = 1080, 1920
BASE_DIR = os.path.dirname(__file__)
FONT_DIR = os.path.join(BASE_DIR, "fonts")
BOLD_PATH = os.path.join(FONT_DIR, "Pretendard-Bold.ttf")
REG_PATH = os.path.join(FONT_DIR, "Pretendard-Regular.ttf")


def _font(size: int, bold: bool = True):
    path = BOLD_PATH if bold else REG_PATH
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _safe_duration(clip, duration: float):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip.set_duration(duration)


def _set_audio(clip, audio):
    if hasattr(clip, "with_audio"):
        return clip.with_audio(audio)
    return clip.set_audio(audio)


def _gradient_bg(top=(7, 10, 19), bottom=(12, 18, 34)):
    img = Image.new("RGB", (W, H), top)
    px = img.load()
    for y in range(H):
        t = y / max(1, H - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def _wrap(draw, text, font, max_width):
    words = str(text).split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        test = current + " " + word
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:3]


def _topic_keyword(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["유가", "oil", "wti", "crude", "brent", "호르무즈", "hormuz"]):
        return "oil"
    if any(k in t for k in ["환율", "달러", "usd", "fx"]):
        return "fx"
    if any(k in t for k in ["비트", "bitcoin", "btc"]):
        return "bitcoin"
    if any(k in t for k in ["금리", "fed", "cpi", "inflation", "yield"]):
        return "rates"
    if any(k in t for k in ["중동", "전쟁", "휴전", "war", "iran", "israel"]):
        return "geopolitics"
    return "market"


def _topic_prompt(hook_text: str) -> str:
    key = _topic_keyword(hook_text)
    if key == "oil":
        scene = "A photorealistic night view of a large oil tanker moving through a narrow strait, tense industrial lights, dark blue sea, premium finance-news style, no text"
    elif key == "fx":
        scene = "A photorealistic macro-finance scene with glowing dollar and won exchange board reflections in a dark trading room, premium editorial style, no text"
    elif key == "bitcoin":
        scene = "A photorealistic dark trading desk with a large bitcoin coin and chart glow, dramatic but realistic finance media look, no text"
    elif key == "rates":
        scene = "A photorealistic central-bank style briefing room with rate chart glow and tense macro mood, premium editorial style, no text"
    elif key == "geopolitics":
        scene = "A photorealistic dark geopolitical tension scene with cargo ships and distant orange crisis glow, premium news-magazine style, no text"
    else:
        scene = "A photorealistic premium financial-news background, dark market screens, subtle chart lights, serious editorial mood, no text"
    return (
        f"{scene}. Vertical 9:16 composition. Leave the center-left area readable for Korean headline overlay. "
        "No watermark, no UI, no poster typography, no collage, no split screen."
    )


def _generate_openai_intro_bg(hook_text: str, out_path: str) -> bool:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return False
    try:
        from openai import OpenAI
    except Exception:
        return False
    try:
        client = OpenAI(api_key=api_key)
        result = client.images.generate(
            model=os.getenv("INTRO_IMAGE_MODEL", "gpt-image-1"),
            prompt=_topic_prompt(hook_text),
            size="1024x1536",
        )
        data = result.data[0]
        if getattr(data, "b64_json", None):
            raw = base64.b64decode(data.b64_json)
        elif getattr(data, "url", None):
            raw = requests.get(data.url, timeout=60).content
        else:
            return False
        img = Image.open(BytesIO(raw)).convert("RGB")
        img = img.resize((W, H), Image.LANCZOS)
        img.save(out_path, quality=95)
        return True
    except Exception as e:
        print(f"[인트로 이미지 생성 실패] {repr(e)}")
        return False


def _draw_topic_fallback(hook_text: str, out_path: str):
    key = _topic_keyword(hook_text)
    img = _gradient_bg((6, 9, 18), (12, 18, 34))
    draw = ImageDraw.Draw(img)
    accent = (247, 175, 74)
    secondary = (88, 202, 182)

    for r, alpha in [(420, 18), (300, 24), (180, 32)]:
        circle = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cdraw = ImageDraw.Draw(circle)
        cdraw.ellipse((W - 260 - r, 260 - r, W - 260 + r, 260 + r), fill=(accent[0], accent[1], accent[2], alpha))
        img = Image.alpha_composite(img.convert("RGBA"), circle).convert("RGB")

    draw = ImageDraw.Draw(img)
    if key == "oil":
        draw.rectangle((130, 1110, 910, 1145), fill=(27, 34, 52))
        draw.polygon([(210, 1120), (520, 980), (840, 1120)], fill=(secondary[0], secondary[1], secondary[2]))
        draw.rectangle((510, 760, 560, 1030), fill=accent)
        draw.ellipse((495, 700, 575, 780), fill=accent)
    elif key == "bitcoin":
        draw.ellipse((620, 610, 970, 960), fill=(28, 32, 46), outline=accent, width=10)
        big = _font(180, True)
        draw.text((710, 645), "₿", fill=accent, font=big)
    elif key == "fx":
        big = _font(150, True)
        draw.text((620, 720), "$", fill=accent, font=big)
        draw.text((770, 760), "₩", fill=secondary, font=big)
    elif key == "rates":
        draw.line((180, 1130, 920, 870), fill=secondary, width=14)
        draw.line((740, 900, 920, 870), fill=secondary, width=14)
        draw.line((875, 820, 920, 870), fill=secondary, width=14)
    else:
        draw.line((170, 1160, 440, 1020, 660, 1070, 930, 860), fill=accent, width=16)
        draw.ellipse((900, 830, 950, 880), fill=accent)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, H), fill=(0, 0, 0, 70))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img.save(out_path, quality=95)


def _fit_card_on_canvas(src_path: str, title: str, subtitle: str, accent: tuple[int, int, int], out_path: str) -> str:
    card = Image.open(src_path).convert("RGB")
    canvas = _gradient_bg()
    draw = ImageDraw.Draw(canvas)

    brand_font = _font(24, False)
    title_font = _font(76, True)
    sub_font = _font(34, False)

    draw.text((64, 54), "JADONNAM", fill=(145, 152, 165), font=brand_font)

    lines = _wrap(draw, title, title_font, 920)
    y = 132
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        draw.text(((W - w) // 2, y), line, fill=(244, 246, 248), font=title_font)
        y += 88

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    draw.text(((W - sw) // 2, y + 10), subtitle, fill=(145, 152, 165), font=sub_font)
    draw.rounded_rectangle((450, y + 72, 630, y + 78), radius=3, fill=accent)

    max_w, max_h = 930, 1060
    ratio = min(max_w / card.width, max_h / card.height)
    new_size = (int(card.width * ratio), int(card.height * ratio))
    card = card.resize(new_size, Image.LANCZOS)

    shadow = Image.new("RGBA", (card.width + 36, card.height + 36), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((12, 12, card.width + 24, card.height + 24), radius=36, fill=(0, 0, 0, 120))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))

    card_x = (W - card.width) // 2
    card_y = 540

    canvas.paste(shadow, (card_x - 18, card_y - 18), shadow)

    rounded = Image.new("RGBA", card.size, (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width, card.height), radius=30, fill=255)
    rounded.paste(card, (0, 0))
    canvas.paste(rounded, (card_x, card_y), mask)

    draw = ImageDraw.Draw(canvas)
    footer = "한 장씩 넘기면 흐름이 바로 보입니다"
    fw = draw.textbbox((0, 0), footer, font=sub_font)[2]
    draw.text(((W - fw) // 2, 1735), footer, fill=(132, 138, 150), font=sub_font)

    canvas.save(out_path, quality=95)
    return out_path


def _intro_outro(text: str, subtitle: str, out_path: str, accent=(247, 175, 74), bg_path: str | None = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.rectangle((0, 0, W, H), fill=(0, 0, 0, 105))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = _gradient_bg((6, 9, 18), (10, 15, 28))
    draw = ImageDraw.Draw(img)
    brand_font = _font(24, False)
    title_font = _font(88, True)
    sub_font = _font(34, False)
    badge_font = _font(28, True)

    draw.text((64, 54), "JADONNAM", fill=(145, 152, 165), font=brand_font)
    draw.rounded_rectangle((64, 134, 190, 184), radius=24, fill=(20, 28, 46))
    draw.text((95, 145), "TODAY", fill=accent, font=badge_font)

    lines = _wrap(draw, text, title_font, 920)
    y = 690
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        draw.text(((W - w) // 2, y), line, fill=(244, 246, 248), font=title_font)
        y += 100

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    draw.text(((W - sw) // 2, y + 24), subtitle, fill=(195, 199, 208), font=sub_font)
    draw.rounded_rectangle((420, y + 90, 660, y + 96), radius=3, fill=accent)
    img.save(out_path, quality=95)


def _prep(path: str, duration: float):
    clip = ImageClip(path)
    clip = _safe_duration(clip, duration)
    return clip


def _build_audio(duration: float):
    def make_frame(t):
        tt = np.asarray(t)
        base = 0.012 * np.sin(2 * np.pi * 110 * tt)
        bass = 0.035 * np.sin(2 * np.pi * 55 * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.5 * tt))
        arp = 0.02 * np.sin(2 * np.pi * 440 * tt) * (0.5 + 0.5 * np.sin(2 * np.pi * 1.8 * tt))
        sweep = 0.03 * np.sin(2 * np.pi * (180 + 80 * np.minimum(tt, 2.0)) * tt) * np.exp(-1.1 * tt)
        click_env = np.exp(-22 * np.mod(tt, 3.2))
        click = 0.05 * np.sin(2 * np.pi * 1200 * tt) * (np.mod(tt, 3.2) < 0.08) * click_env
        val = np.clip(base + bass + arp + sweep + click, -0.22, 0.22)
        if np.ndim(val) == 0:
            return [float(val), float(val)]
        return np.column_stack([val, val])

    return AudioClip(make_frame, duration=duration, fps=44100)


def build_reel(
    news_path: str = "output_rank/rank_news.jpg",
    poly_path: str = "output_rank/rank_poly.jpg",
    market_path: str = "output_rank/rank_market.jpg",
    hook_text: str = "지금 시장이 먼저 반응한 이슈",
    out_path: str = "output_rank/reel_output.mp4",
) -> str:
    Path("output_rank").mkdir(exist_ok=True)
    intro = "output_rank/_reel_intro.jpg"
    outro = "output_rank/_reel_outro.jpg"
    intro_bg = "output_rank/_reel_intro_bg.jpg"
    news_frame = "output_rank/_reel_news_frame.jpg"
    poly_frame = "output_rank/_reel_poly_frame.jpg"
    market_frame = "output_rank/_reel_market_frame.jpg"

    generated = _generate_openai_intro_bg(hook_text, intro_bg)
    if not generated:
        _draw_topic_fallback(hook_text, intro_bg)

    _intro_outro(hook_text, "오늘 돈 흐름만 빠르게 정리", intro, accent=(247, 175, 74), bg_path=intro_bg)
    _fit_card_on_canvas(news_path, "뉴스", "지난 구간 핵심 이슈", (214, 221, 232), news_frame)
    _fit_card_on_canvas(poly_path, "폴리마켓", "베팅이 몰린 흐름", (247, 175, 74), poly_frame)
    _fit_card_on_canvas(market_path, "시장 반응", "가격이 먼저 움직인 구간", (88, 202, 182), market_frame)
    _intro_outro("전체 흐름은 피드에서 확인", "저장해두면 다음 흐름과 비교하기 편합니다", outro, accent=(88, 202, 182), bg_path=intro_bg)

    clips = [
        _prep(intro, 2.2),
        _prep(news_frame, 3.2),
        _prep(poly_frame, 3.2),
        _prep(market_frame, 3.2),
        _prep(outro, 2.0),
    ]
    final = concatenate_videoclips(clips, method="compose")
    audio = _build_audio(final.duration)
    final = _set_audio(final, audio)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return out_path
