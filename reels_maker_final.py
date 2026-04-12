from __future__ import annotations

import base64
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

try:
    from moviepy.editor import AudioClip, AudioFileClip, ImageClip, concatenate_videoclips
except Exception:
    from moviepy import AudioClip, AudioFileClip, ImageClip, concatenate_videoclips

W, H = 1080, 1920
BASE_DIR = os.path.dirname(__file__)
FONT_DIR = os.path.join(BASE_DIR, "fonts")
ASSETS_AUDIO = os.path.join(BASE_DIR, "assets", "audio", "bg.mp3")
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


def _cover_crop(img: Image.Image, target_w: int = W, target_h: int = H) -> Image.Image:
    img = img.convert("RGB")
    src_w, src_h = img.size
    ratio = max(target_w / src_w, target_h / src_h)
    new_size = (max(1, int(src_w * ratio)), max(1, int(src_h * ratio)))
    img = img.resize(new_size, Image.LANCZOS)
    left = max(0, (img.width - target_w) // 2)
    top = max(0, (img.height - target_h) // 2)
    return img.crop((left, top, left + target_w, top + target_h))


def _wrap_text(draw, text, font, max_width, max_lines=2):
    text = str(text or "").strip()
    if not text:
        return [""]

    words = text.split()
    if len(words) == 1 and len(text) > 12:
        # Korean-ish fallback by char chunks
        chars = list(text)
        lines, cur = [], chars[0]
        for ch in chars[1:]:
            test = cur + ch
            if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
                cur = test
            else:
                lines.append(cur)
                cur = ch
                if len(lines) == max_lines - 1:
                    break
        if len(lines) < max_lines and cur:
            lines.append(cur)
        return lines[:max_lines]

    lines, cur = [], words[0]
    for w in words[1:]:
        test = cur + " " + w
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            cur = test
        else:
            lines.append(cur)
            cur = w
            if len(lines) == max_lines - 1:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    return lines[:max_lines]


def _topic_keyword(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ["유가", "oil", "wti", "crude", "brent", "호르무즈", "hormuz", "opec", "석유"]):
        return "oil"
    if any(k in t for k in ["환율", "달러", "usd", "fx", "won", "dollar", "원화", "외환"]):
        return "fx"
    if any(k in t for k in ["비트", "bitcoin", "btc", "crypto", "eth", "이더", "가상자산"]):
        return "bitcoin"
    if any(k in t for k in ["금리", "fed", "cpi", "inflation", "yield", "연준", "물가", "채권"]):
        return "rates"
    if any(k in t for k in ["중동", "전쟁", "휴전", "war", "iran", "israel", "attack", "missile", "공습", "이란", "이스라엘"]):
        return "geopolitics"
    return "market"


def _topic_prompt_variants(hook_text: str):
    key = _topic_keyword(hook_text)
    common = (
        "Editorial news photography, photorealistic, realistic lighting, no text, no watermark, no ui, "
        "clean upper half for headline, sharp subject, premium news magazine style, visible subject, readable background."
    )
    if key == "oil":
        return [
            f"Large oil tanker near a brightly lit refinery at blue hour, clear industrial lights, visible ship details, dramatic but readable scene. {common}",
            f"Oil tanker on calm water with refinery lights in the background, bright blue evening sky, realistic editorial photo. {common}",
        ]
    if key == "fx":
        return [
            f"Modern trading desk with currency screens, blue ambient light, bright readable details, premium finance editorial photo. {common}",
            f"Financial district skyline and currency screens, modern blue tone, clear readable composition. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Modern crypto trading setup with bright monitor glow, realistic desk and chart screens, premium editorial photo. {common}",
            f"Bitcoin trading environment, clean cinematic blue light, readable subject, realistic photo. {common}",
        ]
    if key == "rates":
        return [
            f"Central bank style building at dusk with bright sky and architectural lighting, realistic editorial photograph. {common}",
            f"Financial institution exterior at evening blue hour, visible building details, premium news photo. {common}",
        ]
    return [
        f"Global market news visual, premium editorial photography, bright blue hour lighting, readable subject and background. {common}",
        f"World economy news mood, modern realistic photo, clean composition, blue and white tones, visible subject. {common}",
    ]


def _generate_openai_bg(prompt_variants, out_path: str) -> bool:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except Exception:
        return False
    for prompt in prompt_variants:
        for model, size in [("gpt-image-1", "1024x1536"), ("dall-e-3", "1024x1792")]:
            try:
                result = client.images.generate(model=model, prompt=prompt, size=size)
                data = result.data[0]
                if getattr(data, "b64_json", None):
                    raw = base64.b64decode(data.b64_json)
                elif getattr(data, "url", None):
                    raw = requests.get(data.url, timeout=60).content
                else:
                    continue
                img = Image.open(BytesIO(raw)).convert("RGB")
                img = _cover_crop(img)
                img = ImageEnhance.Brightness(img).enhance(1.22)
                img = ImageEnhance.Contrast(img).enhance(1.06)
                img.save(out_path, quality=95)
                return True
            except Exception:
                continue
    return False


def _draw_topic_fallback(hook_text: str, out_path: str) -> None:
    img = Image.new("RGB", (W, H), (18, 28, 44))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, H), fill=(22, 38, 66))
    draw.ellipse((-120, 780, 620, 1500), fill=(50, 90, 140))
    draw.ellipse((520, 620, 1260, 1440), fill=(240, 162, 72))
    img = img.filter(ImageFilter.GaussianBlur(22))
    img = ImageEnhance.Brightness(img).enhance(1.08)
    img.save(out_path, quality=95)


def _draw_center_text(img, text: str, subtitle: str, y_start: int):
    draw = ImageDraw.Draw(img)
    title_font = _font(92, True)
    sub_font = _font(34, False)
    brand_font = _font(24, False)

    draw.text((46, 54), "JADONNAM", fill=(185, 190, 198), font=brand_font)

    lines = _wrap_text(draw, text, title_font, 920, max_lines=2)
    y = y_start
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        x = (W - w) // 2
        draw.text((x + 2, y + 3), line, fill=(0, 0, 0), font=title_font)
        draw.text((x, y), line, fill=(244, 246, 248), font=title_font)
        y += 102

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    sx = (W - sw) // 2
    draw.text((sx + 1, y + 8), subtitle, fill=(0, 0, 0), font=sub_font)
    draw.text((sx, y + 6), subtitle, fill=(198, 202, 210), font=sub_font)


def _intro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = Image.new("RGB", (W, H), (24, 44, 70))
    img = ImageEnhance.Brightness(img).enhance(1.14)
    img = ImageEnhance.Contrast(img).enhance(1.04)
    _draw_center_text(img, text, subtitle, 420)
    img.save(out_path, quality=95)


def _outro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = Image.new("RGB", (W, H), (24, 44, 70))
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img = ImageEnhance.Contrast(img).enhance(1.02)
    _draw_center_text(img, text, subtitle, 1180)
    img.save(out_path, quality=95)


def _fit_card_no_zoom(src_path: str, out_path: str) -> str:
    card = Image.open(src_path).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    max_w, max_h = 1000, 1660
    ratio = min(max_w / card.width, max_h / card.height)
    new_w = int(card.width * ratio)
    new_h = int(card.height * ratio)
    card = card.resize((new_w, new_h), Image.LANCZOS)
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, new_w, new_h), radius=18, fill=255)
    x = (W - new_w) // 2
    y = (H - new_h) // 2
    canvas.paste(card, (x, y), mask)
    canvas.save(out_path, quality=95)
    return out_path


def _prep(path: str, duration: float):
    clip = ImageClip(path)
    clip = _safe_duration(clip, duration)
    return clip


def _build_synth_audio(duration: float):
    def make_frame(t):
        tt = np.asarray(t)
        base = 0.01 * np.sin(2 * np.pi * 102 * tt)
        bass = 0.02 * np.sin(2 * np.pi * 56 * tt)
        val = np.clip(base + bass, -0.18, 0.18)
        if np.ndim(val) == 0:
            return [float(val), float(val)]
        return np.column_stack([val, val])
    return AudioClip(make_frame, duration=duration, fps=44100)


def _build_audio(duration: float):
    if os.path.exists(ASSETS_AUDIO):
        try:
            clip = AudioFileClip(ASSETS_AUDIO)
            if clip.duration > duration:
                return clip.subclip(0, duration)
            loops = []
            remaining = duration
            while remaining > 0:
                seg = clip.subclip(0, min(clip.duration, remaining))
                loops.append(seg)
                remaining -= seg.duration
            try:
                from moviepy.editor import concatenate_audioclips
            except Exception:
                from moviepy import concatenate_audioclips
            return concatenate_audioclips(loops)
        except Exception:
            pass
    return _build_synth_audio(duration)


def build_reel(
    news_path: str = "output_rank/rank_news.jpg",
    poly_path: str = "output_rank/rank_poly.jpg",
    market_path: str = "output_rank/rank_market.jpg",
    hook_text: str = "지금 시장이 먼저 반응한 이슈",
    out_path: str = "output_rank/reel_output.mp4",
    top_labels: Optional[list[str]] = None,
) -> str:
    Path("output_rank").mkdir(exist_ok=True)

    intro_bg = "output_rank/_reel_intro_bg.jpg"
    intro = "output_rank/_reel_intro.jpg"
    news_frame = "output_rank/_reel_news_frame.jpg"
    poly_frame = "output_rank/_reel_poly_frame.jpg"
    market_frame = "output_rank/_reel_market_frame.jpg"
    outro = "output_rank/_reel_outro.jpg"

    if not _generate_openai_bg(_topic_prompt_variants(hook_text), intro_bg):
        _draw_topic_fallback(hook_text, intro_bg)

    _intro_image(hook_text, "오늘 돈 흐름 정리", intro, bg_path=intro_bg)
    _outro_image("저장해두면 다음 흐름 비교가 쉽다", "팔로우하면 매일 업데이트", outro, bg_path=intro_bg)

    _fit_card_no_zoom(news_path, news_frame)
    _fit_card_no_zoom(poly_path, poly_frame)
    _fit_card_no_zoom(market_path, market_frame)

    clips = [
        _prep(intro, 2.5),
        _prep(news_frame, 3.0),
        _prep(poly_frame, 3.0),
        _prep(market_frame, 3.0),
        _prep(outro, 2.0),
    ]
    final = concatenate_videoclips(clips, method="compose")
    audio = _build_audio(final.duration)
    final = _set_audio(final, audio)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return out_path
