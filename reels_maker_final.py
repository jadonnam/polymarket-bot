
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


def _gradient_bg(top=(16, 28, 42), bottom=(44, 82, 140)):
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


def _wrap_kor(draw, text, font, max_width):
    text = str(text or "").replace("  ", " ").strip()
    if not text:
        return [""]
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = f"{cur} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) <= 2:
        return lines
    first = lines[0]
    second = " ".join(lines[1:])
    return [first, second]


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
        "Bright editorial financial photography, realistic, premium news magazine aesthetic, "
        "clear subject visibility, balanced exposure, no text, no watermark, no UI, vertical 9:16, "
        "human-shot photo feel, upper area left clean enough for headline."
    )
    if key == "oil":
        return [
            f"Large oil tanker at blue hour near bright refinery coastline, realistic, clear and visible ship, premium editorial energy market photo. {common}",
            f"Oil tanker moving on calm sea with refinery lights in background, bright blue evening sky, clear subject, realistic Reuters style. {common}",
        ]
    if key == "fx":
        return [
            f"Bright financial trading desk with currency screens and city lights, realistic, clean exposure, premium finance editorial photo. {common}",
            f"Modern foreign exchange trading environment with glowing USD and KRW market screens, balanced lighting, realistic. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Modern crypto trading room with visible monitors and blue light, realistic, clean exposure, premium editorial photo. {common}",
            f"Professional trader desk with bitcoin charts, bright but moody finance newsroom style, realistic. {common}",
        ]
    if key == "rates":
        return [
            f"Central bank or government finance building at dusk with balanced light, realistic, premium editorial style. {common}",
            f"Financial district building exterior at blue hour, clear details, realistic monetary policy news photo. {common}",
        ]
    return [
        f"Premium global market editorial photo at blue hour, balanced exposure, realistic finance news atmosphere. {common}",
        f"Professional economy news background image, realistic, clear subject, bright blue evening tones. {common}",
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

    models = [("gpt-image-1", "1024x1536"), ("dall-e-3", "1024x1792")]
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
                img = _cover_crop(img)
                img = ImageEnhance.Brightness(img).enhance(1.32)
                img = ImageEnhance.Contrast(img).enhance(1.08)
                img.save(out_path, quality=95)
                return True
            except Exception:
                continue
    return False


def _draw_topic_fallback(hook_text: str, out_path: str) -> None:
    img = _gradient_bg().convert("RGB")
    img.save(out_path, quality=95)


def _intro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
        img = ImageEnhance.Brightness(img).enhance(1.20)
    else:
        img = _gradient_bg()

    # subtle top darkening only
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, 720), fill=(0, 0, 0, 24))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    title_font = _font(94, True)
    sub_font = _font(34, False)
    brand_font = _font(22, False)

    draw.text((48, 58), "JADONNAM", fill=(210, 214, 224), font=brand_font)

    lines = _wrap_kor(draw, text, title_font, 910)
    y = 430
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        x = (W - w) // 2
        draw.text((x + 3, y + 4), line, fill=(0, 0, 0, 120), font=title_font)
        draw.text((x, y), line, fill=(247, 248, 250), font=title_font)
        y += 112

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    draw.text(((W - sw) // 2, y + 10), subtitle, fill=(220, 224, 230), font=sub_font)
    img.save(out_path, quality=95)


def _outro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
        img = ImageEnhance.Brightness(img).enhance(1.08)
    else:
        img = _gradient_bg()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 900, W, H), fill=(0, 0, 0, 40))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    title_font = _font(74, True)
    sub_font = _font(32, False)

    lines = _wrap_kor(draw, text, title_font, 900)
    y = 1180
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        x = (W - w) // 2
        draw.text((x + 3, y + 4), line, fill=(0, 0, 0, 110), font=title_font)
        draw.text((x, y), line, fill=(247, 248, 250), font=title_font)
        y += 90

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    draw.text(((W - sw) // 2, y + 14), subtitle, fill=(224, 228, 234), font=sub_font)
    img.save(out_path, quality=95)


def _fit_card_no_zoom(src_path: str, out_path: str) -> str:
    card = Image.open(src_path).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    max_w, max_h = 1000, 1540
    ratio = min(max_w / card.width, max_h / card.height)
    new_w = int(card.width * ratio)
    new_h = int(card.height * ratio)
    card = card.resize((new_w, new_h), Image.LANCZOS)
    card_x = (W - new_w) // 2
    card_y = (H - new_h) // 2
    canvas.paste(card, (card_x, card_y))
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

    if not _generate_openai_bg(_topic_prompt_variants(hook_text), intro_bg):
        _draw_topic_fallback(hook_text, intro_bg)

    _intro_image(hook_text, "오늘 돈 흐름 정리", intro, bg_path=intro_bg)
    _outro_image("저장해두면 다음 흐름 비교가 쉬워진다", "팔로우하면 매일 업데이트", outro, bg_path=intro_bg)

    _fit_card_no_zoom(news_path, news_frame)
    _fit_card_no_zoom(poly_path, poly_frame)
    _fit_card_no_zoom(market_path, market_frame)

    clips = [
        _prep(intro, 2.4),
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
