
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


def _set_pos(clip, pos):
    if hasattr(clip, "with_position"):
        return clip.with_position(pos)
    return clip.set_position(pos)


def _resize_clip(clip, width=None, height=None):
    if hasattr(clip, "resized"):
        return clip.resized(width=width, height=height)
    return clip.resize(width=width, height=height)


def _crop_clip(clip, x1=None, y1=None, x2=None, y2=None):
    if hasattr(clip, "cropped"):
        return clip.cropped(x1=x1, y1=y1, x2=x2, y2=y2)
    return clip.crop(x1=x1, y1=y1, x2=x2, y2=y2)


def _gradient_bg(top=(18, 24, 36), bottom=(44, 55, 78)):
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


def _wrap(draw, text, font, max_width, max_lines=2):
    words = str(text).replace("\n", " ").split()
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
            if len(lines) == max_lines - 1:
                break
    if len(lines) < max_lines:
        remaining = current
        if len(lines) == max_lines - 1:
            while draw.textbbox((0, 0), remaining, font=font)[2] > max_width and len(remaining) > 2:
                remaining = remaining[:-2] + "…"
        lines.append(remaining)
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
    if any(k in t for k in ["금", "gold", "safe haven", "안전자산"]):
        return "gold"
    return "market"


def _topic_prompt_variants(hook_text: str):
    key = _topic_keyword(hook_text)
    common = (
        "Photorealistic editorial news photography, realistic human-shot photo, premium financial magazine aesthetic, "
        "bright but serious lighting, high clarity, visible subject, no text, no watermark, no UI, no poster, no illustration, "
        "vertical 9:16 composition, upper third kept relatively clean for text overlay."
    )
    if key == "oil":
        return [
            f"Large oil tanker on open water at blue hour, refinery lights glowing clearly in the distance, realistic details, visible ship deck, balanced exposure. {common}",
            f"Oil refinery by the sea at dusk, orange industrial lights, visible structures and smoke, realistic documentary photo, bright enough to read details. {common}",
            f"Tanker ship passing industrial coastline at sunset, warm highlights on water, clear visible subject, Reuters style financial news photo. {common}",
        ]
    if key == "fx":
        return [
            f"Modern currency trading desk with multiple screens showing exchange-rate charts, bright realistic office lighting, crisp details, editorial finance photo. {common}",
            f"Financial monitors with USD KRW style currency charts in a clean modern trading room, readable shapes, balanced lighting, realistic photo. {common}",
            f"Macro finance newsroom with glowing currency screens, polished corporate atmosphere, brighter documentary style. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Modern crypto trading setup with bitcoin price charts on several monitors, balanced bright lighting, realistic office scene, premium editorial photo. {common}",
            f"Bitcoin themed trading desk with screens and reflections, modern finance aesthetic, bright clear subject, photorealistic. {common}",
            f"City office at dusk with crypto market monitors and subtle bitcoin motif, visible details, documentary photo. {common}",
        ]
    if key == "rates":
        return [
            f"Central bank or government finance building at early evening, clear architecture, balanced daylight and warm lights, serious editorial photography. {common}",
            f"Modern financial district building exterior with institutional atmosphere, realistic photo, bright enough to show details clearly. {common}",
            f"Economic press photo of central bank style building and city skyline at dusk, polished and clear. {common}",
        ]
    if key == "geopolitics":
        return [
            f"Strategic shipping route at dusk with visible cargo ship and distant industrial lights, geopolitical tension but clear bright details, editorial photo. {common}",
            f"Middle East energy infrastructure by the sea at twilight, visible flames and industrial coastline, clear subject, realistic documentary image. {common}",
            f"Cargo ship in a tense maritime corridor with distant orange lights, balanced exposure, realistic news photography. {common}",
        ]
    if key == "gold":
        return [
            f"Gold bars in a bright premium vault setting, polished metal reflections, realistic financial editorial photo, visible details. {common}",
            f"Close-up of gold bars under clean studio-like lighting, luxurious but realistic, no dark shadows hiding details. {common}",
            f"Safe-haven finance image with gold bars and vault shelves, polished premium documentary style. {common}",
        ]
    return [
        f"Bright premium financial newsroom with market screens and city lights, clear visible details, Reuters or Bloomberg style editorial photo. {common}",
        f"Modern global market trading floor at dusk, balanced lighting, realistic financial magazine photo, subject clearly visible. {common}",
        f"Financial district skyline with market mood, warm and blue tones, clear documentary style image. {common}",
    ]


def _cover_crop(img: Image.Image, target_w: int = W, target_h: int = H) -> Image.Image:
    img = img.convert("RGB")
    src_w, src_h = img.size
    ratio = max(target_w / src_w, target_h / src_h)
    new_size = (max(1, int(src_w * ratio)), max(1, int(src_h * ratio)))
    img = img.resize(new_size, Image.LANCZOS)
    left = max(0, (img.width - target_w) // 2)
    top = max(0, (img.height - target_h) // 2)
    return img.crop((left, top, left + target_w, top + target_h))


def _normalize_bg_image(img: Image.Image) -> Image.Image:
    img = _cover_crop(img)
    img = ImageEnhance.Brightness(img).enhance(1.35)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.05)
    return img


def _generate_openai_bg(prompt_variants, out_path: str) -> bool:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except Exception as e:
        print(f"[이미지 클라이언트 실패] {repr(e)}")
        return False

    models = [
        ("gpt-image-1", "1024x1536"),
        ("dall-e-3", "1024x1792"),
    ]

    for prompt in prompt_variants:
        for model, size in models:
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
                img = _normalize_bg_image(img)
                img.save(out_path, quality=95)
                print(f"[이미지 생성 성공] model={model}")
                return True
            except Exception as e:
                print(f"[이미지 재시도] model={model} err={repr(e)}")
                continue
    return False


def _draw_topic_fallback(hook_text: str, out_path: str) -> None:
    key = _topic_keyword(hook_text)
    palettes = {
        "oil": ((65, 86, 122), (255, 146, 62)),
        "fx": ((40, 70, 130), (120, 180, 255)),
        "bitcoin": ((35, 55, 120), (100, 185, 255)),
        "rates": ((40, 70, 100), (150, 180, 220)),
        "geopolitics": ((55, 65, 95), (255, 120, 70)),
        "gold": ((75, 66, 28), (240, 190, 70)),
        "market": ((40, 60, 100), (100, 160, 220)),
    }
    c1, c2 = palettes.get(key, palettes["market"])
    img = _gradient_bg((24, 32, 48), (62, 78, 108)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-200, 450, 680, 1200), fill=(*c2, 80))
    gd.ellipse((420, 920, 1320, 1860), fill=(*c1, 55))
    gd.ellipse((760, -120, 1260, 380), fill=(255, 255, 255, 25))
    img = Image.alpha_composite(img, glow).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(1.1)
    img.save(out_path, quality=95)


def _apply_top_readability(img: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # only subtle top gradient, no box
    for y in range(0, 850):
        alpha = int(max(0, 96 - y * 0.10))
        od.rectangle((0, y, W, y + 2), fill=(6, 8, 14, alpha))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _draw_centered_text(draw, text, font, y, fill=(244, 246, 248), shadow=(0,0,0,160), max_width=920, line_gap=110):
    lines = _wrap(draw, text, font, max_width, max_lines=2)
    yy = y
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        w = box[2] - box[0]
        x = (W - w) // 2
        for ox, oy in [(-3, 3), (3, 3), (0, 6)]:
            draw.text((x + ox, yy + oy), line, fill=shadow, font=font)
        draw.text((x, yy), line, fill=fill, font=font)
        yy += line_gap
    return yy


def _intro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()
    img = _apply_top_readability(img)

    draw = ImageDraw.Draw(img)
    title_font = _font(96, True)
    sub_font = _font(34, False)
    brand_font = _font(24, False)
    draw.text((42, 58), "JADONNAM", fill=(176, 182, 192), font=brand_font)

    end_y = _draw_centered_text(draw, text, title_font, 430, max_width=930, line_gap=106)
    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    sx = (W - sw) // 2
    for ox, oy in [(0,2), (2,2)]:
        draw.text((sx + ox, end_y + 16 + oy), subtitle, fill=(0, 0, 0, 110), font=sub_font)
    draw.text((sx, end_y + 16), subtitle, fill=(190, 196, 205), font=sub_font)
    img.save(out_path, quality=95)


def _outro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()
    img = _apply_top_readability(img)
    draw = ImageDraw.Draw(img)

    title_font = _font(86, True)
    sub_font = _font(32, False)
    brand_font = _font(24, False)
    draw.text((42, 58), "JADONNAM", fill=(176, 182, 192), font=brand_font)
    end_y = _draw_centered_text(draw, text, title_font, 1140, max_width=920, line_gap=96)
    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    sx = (W - sw) // 2
    draw.text((sx+2, end_y + 20+2), subtitle, fill=(0,0,0,110), font=sub_font)
    draw.text((sx, end_y + 20), subtitle, fill=(190, 196, 205), font=sub_font)
    img.save(out_path, quality=95)


def _fit_card_no_zoom(src_path: str, out_path: str) -> str:
    card = Image.open(src_path).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    max_w, max_h = 1040, 1640
    ratio = min(max_w / card.width, max_h / card.height)
    new_w = int(card.width * ratio)
    new_h = int(card.height * ratio)
    card = card.resize((new_w, new_h), Image.LANCZOS)

    shadow = Image.new("RGBA", (new_w + 36, new_h + 36), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((12, 12, new_w + 24, new_h + 24), radius=26, fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))

    x = (W - new_w) // 2
    y = (H - new_h) // 2
    canvas.paste(shadow, (x - 18, y - 18), shadow)

    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, new_w, new_h), radius=22, fill=255)
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
        bass = 0.028 * np.sin(2 * np.pi * 56 * tt) * (0.7 + 0.3 * np.sin(2 * np.pi * 0.5 * tt))
        hats = 0.014 * np.sin(2 * np.pi * 860 * tt) * (np.mod(tt, 0.5) < 0.05)
        click = 0.030 * np.sin(2 * np.pi * 1240 * tt) * (np.mod(tt, 1.0) < 0.06)
        val = np.clip(base + bass + hats + click, -0.22, 0.22)
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
        except Exception as e:
            print(f"[외부 배경음 로드 실패] {repr(e)}")
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

    seed_text = " ".join(top_labels or []) + " " + hook_text

    if not _generate_openai_bg(_topic_prompt_variants(seed_text), intro_bg):
        _draw_topic_fallback(seed_text, intro_bg)

    _intro_image(hook_text, "오늘 돈 흐름 정리", intro, bg_path=intro_bg)
    _outro_image("저장해두면 내일 비교가 쉬워진다", "팔로우하면 매일 업데이트", outro, bg_path=intro_bg)

    _fit_card_no_zoom(news_path, news_frame)
    _fit_card_no_zoom(poly_path, poly_frame)
    _fit_card_no_zoom(market_path, market_frame)

    clips = [
        _prep(intro, 2.3),
        _prep(news_frame, 3.0),
        _prep(poly_frame, 3.0),
        _prep(market_frame, 3.0),
        _prep(outro, 2.2),
    ]
    final = concatenate_videoclips(clips, method="compose")
    audio = _build_audio(final.duration)
    final = _set_audio(final, audio)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return out_path
