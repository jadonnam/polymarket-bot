
from __future__ import annotations

import base64
import os
import re
from io import BytesIO
from pathlib import Path
from typing import List, Optional

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


def _gradient_bg(top=(10, 12, 20), bottom=(18, 24, 38)):
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


def _contains(text: str, words: List[str]) -> bool:
    t = (text or "").lower()
    return any(w in t for w in words)


def _topic_keyword(text: str) -> str:
    t = (text or "").lower()
    if _contains(t, ["유가", "oil", "wti", "crude", "brent", "호르무즈", "hormuz", "opec", "석유"]):
        return "oil"
    if _contains(t, ["환율", "달러", "usd", "fx", "won", "dollar", "원화", "외환"]):
        return "fx"
    if _contains(t, ["비트", "bitcoin", "btc", "crypto", "eth", "이더", "가상자산"]):
        return "bitcoin"
    if _contains(t, ["금리", "fed", "cpi", "inflation", "yield", "연준", "물가", "채권"]):
        return "rates"
    if _contains(t, ["중동", "전쟁", "휴전", "war", "iran", "israel", "attack", "missile", "공습", "이란", "이스라엘"]):
        return "geopolitics"
    if _contains(t, ["금", "gold", "safe haven", "안전자산"]):
        return "gold"
    return "market"


def _topic_prompt_variants(hook_text: str):
    key = _topic_keyword(hook_text)
    common = (
        "Photorealistic editorial news photography, realistic human-shot feeling, "
        "not CGI, not illustration, no text, no watermark, no UI. Vertical 9:16 composition. "
        "Top area kept relatively simple for headline placement. Premium financial magazine aesthetic."
    )
    if key == "oil":
        return [
            f"Large oil tanker at blue hour near a refinery, realistic photography, warm lights on the horizon, premium editorial composition, slightly brighter exposure, moody but readable. {common}",
            f"Realistic oil refinery by the sea at dusk, industrial lights reflecting on water, premium Reuters style photo, not too dark, strong clean composition. {common}",
            f"Wide angle photo from the front of an oil tanker moving through calm sea at dusk, distant refinery lights, luxury editorial news look, brighter shadows. {common}",
        ]
    if key == "fx":
        return [
            f"Realistic currency trading desk with USD/KRW screens, bright monitor glow, clean premium office environment, editorial finance photography. {common}",
            f"Modern financial trading room with exchange rate screens, realistic, crisp light, premium Bloomberg style photo, readable top area. {common}",
            f"Close-up of global currency market screens in a bright but serious finance office, realistic and premium. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Modern crypto trading desk with multiple monitors, realistic finance photo, blue glow, bright enough to read over, premium editorial aesthetic. {common}",
            f"Premium realistic photo of bitcoin trading setup in a clean modern office, balanced lighting, no cyberpunk exaggeration. {common}",
            f"Financial newsroom style photo showing crypto market screens and analysts, realistic, brighter exposure, polished. {common}",
        ]
    if key == "rates":
        return [
            f"Central bank building exterior at dusk, realistic photography, clean serious atmosphere, balanced brighter exposure, premium editorial look. {common}",
            f"Government finance institution under clear evening sky, realistic, clean architectural shot, readable darker lower half. {common}",
            f"Premium macroeconomic editorial photo with central bank setting, modern and realistic, not too dark. {common}",
        ]
    if key == "geopolitics":
        return [
            f"Strategic shipping route at dusk with cargo vessel and distant lights, realistic geopolitics photo, premium editorial style, balanced exposure. {common}",
            f"Realistic nightfall sea-lane with industrial glow in the distance, geopolitical tension, but bright enough for headline readability. {common}",
            f"Editorial news photo of sea route, tanker foreground and distant orange industrial lights, cinematic but not overly dark. {common}",
        ]
    if key == "gold":
        return [
            f"Premium editorial photograph of gold bars under clean directional light, realistic, balanced exposure, luxury finance magazine mood. {common}",
            f"Realistic finance photo of gold in a secure vault, premium clean composition, brighter highlights and readable contrast. {common}",
        ]
    return [
        f"Modern financial district at blue hour, realistic editorial photo, premium magazine quality, balanced exposure and clean top area. {common}",
        f"Premium finance newsroom visual with city lights and market atmosphere, realistic, brighter shadows, editorial composition. {common}",
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
                # brighten slightly
                img = ImageEnhance.Brightness(img).enhance(1.10)
                img = ImageEnhance.Contrast(img).enhance(1.08)
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
        "oil": ((15, 24, 36), (255, 146, 60)),
        "fx": ((18, 30, 58), (80, 168, 255)),
        "bitcoin": ((16, 20, 42), (82, 122, 255)),
        "rates": ((16, 22, 34), (120, 180, 210)),
        "geopolitics": ((22, 20, 30), (255, 120, 76)),
        "gold": ((30, 24, 12), (220, 178, 72)),
        "market": ((16, 20, 32), (86, 160, 255)),
    }
    c1, c2 = palettes.get(key, palettes["market"])
    img = _gradient_bg((12, 14, 24), (18, 24, 38)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-100, 520, 820, 1350), fill=(*c2, 80))
    gd.ellipse((480, 800, 1380, 1750), fill=(*c1, 60))
    img = Image.alpha_composite(img, glow)
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    img.convert("RGB").save(out_path, quality=95)


def _smart_break(text: str, max_chars=12):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return [""]
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if not cur:
            cur = w
            continue
        if len(cur.replace(" ", "")) + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    # fallback for no-space long Korean
    if len(lines) == 1 and len(lines[0].replace(" ", "")) > max_chars + 2:
        raw = lines[0].replace(" ", "")
        cut = min(max_chars, len(raw))
        return [raw[:cut], raw[cut:cut + max_chars]]
    return lines[:3]


def _draw_headline_with_shadow(draw, lines, font, start_y, fill=(245, 247, 250)):
    y = start_y
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        w = box[2] - box[0]
        x = (W - w) // 2
        for ox, oy in [(-4, 4), (4, 4), (0, 6)]:
            draw.text((x + ox, y + oy), line, fill=(0, 0, 0, 180), font=font)
        draw.text((x, y), line, fill=fill, font=font)
        y += int(font.size * 1.08)
    return y


def _intro_copy(hook_text: str) -> str:
    t = hook_text or ""
    if _contains(t, ["유가", "oil", "wti", "crude", "brent"]):
        return "지금 유가 변수\n다시 크게 움직인다"
    if _contains(t, ["환율", "달러", "usd", "fx"]):
        return "지금 환율\n다시 흔들리기 시작했다"
    if _contains(t, ["비트", "bitcoin", "btc", "crypto"]):
        return "지금 코인 쪽으로\n돈이 다시 몰린다"
    if _contains(t, ["금리", "fed", "cpi", "yield"]):
        return "지금 금리 해석이\n다시 바뀌는 중이다"
    return "지금 돈 흐름\n먼저 움직인 곳"

def _outro_copy() -> str:
    return "저장해두면\n다음 흐름 비교가 쉬워진다"


def _intro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, int(H * 0.60)), fill=(0, 0, 0, 80))
    od.rectangle((0, int(H * 0.60), W, H), fill=(0, 0, 0, 34))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    title_font = _font(96, True)
    sub_font = _font(36, False)
    brand_font = _font(24, False)

    draw.text((60, 58), "JADONNAM", fill=(184, 190, 200), font=brand_font)
    lines = _smart_break(text, max_chars=10)
    end_y = _draw_headline_with_shadow(draw, lines, title_font, 500)
    box = draw.textbbox((0, 0), subtitle, font=sub_font)
    sw = box[2] - box[0]
    draw.text(((W - sw) // 2, end_y + 22), subtitle, fill=(168, 172, 180), font=sub_font)
    img.save(out_path, quality=95)


def _outro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, int(H * 0.45), W, H), fill=(0, 0, 0, 110))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    title_font = _font(84, True)
    sub_font = _font(34, False)
    brand_font = _font(24, False)

    draw.text((60, 58), "JADONNAM", fill=(184, 190, 200), font=brand_font)
    lines = _smart_break(text, max_chars=10)
    end_y = _draw_headline_with_shadow(draw, lines, title_font, 1180)
    box = draw.textbbox((0, 0), subtitle, font=sub_font)
    sw = box[2] - box[0]
    draw.text(((W - sw) // 2, end_y + 28), subtitle, fill=(175, 178, 186), font=sub_font)
    img.save(out_path, quality=95)


def _fit_card_no_zoom(src_path: str, out_path: str) -> str:
    card = Image.open(src_path).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))
    max_w, max_h = 1080, 1700
    ratio = min(max_w / card.width, max_h / card.height)
    new_w = int(card.width * ratio)
    new_h = int(card.height * ratio)
    card = card.resize((new_w, new_h), Image.LANCZOS)

    shadow = Image.new("RGBA", (new_w + 40, new_h + 40), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((16, 16, new_w + 24, new_h + 24), radius=30, fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))

    card_x = (W - new_w) // 2
    card_y = (H - new_h) // 2
    canvas.paste(shadow, (card_x - 20, card_y - 20), shadow)

    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, new_w, new_h), radius=24, fill=255)
    canvas.paste(card, (card_x, card_y), mask)
    canvas.save(out_path, quality=95)
    return out_path


def _prep(path: str, duration: float, zoom: float = 0.015):
    clip = ImageClip(path)
    clip = _safe_duration(clip, duration)
    # subtle zoom
    if hasattr(clip, "resize"):
        clip = clip.resize(lambda t: 1 + zoom * (t / max(duration, 0.01)))
    elif hasattr(clip, "resized"):
        clip = clip.resized(lambda t: 1 + zoom * (t / max(duration, 0.01)))
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
    top_labels: Optional[List[str]] = None,
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

    _intro_image(_intro_copy(hook_text), "오늘 돈 흐름 정리", intro, bg_path=intro_bg)
    _outro_image(_outro_copy(), "팔로우하면 다음 흐름도 바로 본다", outro, bg_path=intro_bg)

    _fit_card_no_zoom(news_path, news_frame)
    _fit_card_no_zoom(poly_path, poly_frame)
    _fit_card_no_zoom(market_path, market_frame)

    clips = [
        _prep(intro, 2.4, zoom=0.030),
        _prep(news_frame, 3.0, zoom=0.010),
        _prep(poly_frame, 3.0, zoom=0.010),
        _prep(market_frame, 3.0, zoom=0.010),
        _prep(outro, 2.1, zoom=0.022),
    ]
    final = concatenate_videoclips(clips, method="compose")
    audio = _build_audio(final.duration)
    final = _set_audio(final, audio)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return out_path
