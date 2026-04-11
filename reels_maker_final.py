from __future__ import annotations

import base64
import os
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

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


def _gradient_bg(top=(10, 16, 28), bottom=(18, 28, 46)):
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
        "Ultra-realistic editorial news photography, authentic camera look, natural daylight or bright overcast lighting, "
        "not CGI, not illustration, not poster, no text, no watermark, no collage, no UI, "
        "premium Reuters/Bloomberg magazine aesthetic, vertical 9:16 composition, "
        "keep upper 35 percent visually clean and simple for headline overlay, avoid clutter behind text."
    )
    if key == "oil":
        return [
            f"Bright documentary-style photo of a large oil tanker moving through open water in daytime, clean sky, realistic reflections, premium macro-news energy background. {common}",
            f"Photorealistic editorial image of global energy shipping, tanker deck and sea under soft daylight, high-end financial magazine look, believable human-shot photo. {common}",
            f"Realistic daylight photo of an oil tanker near a strategic strait, premium business-news style, open composition, not dark. {common}",
        ]
    if key == "fx":
        return [
            f"Bright editorial finance photo of a modern foreign exchange desk, soft daylight through windows, polished screens glow, realistic human-shot composition with clear top area. {common}",
            f"Photorealistic macro-finance image of currency trading atmosphere, clean blue and silver palette, bright premium newsroom look, not dark. {common}",
            f"Business-news style photo of a bright FX trading environment, modern glass office, believable depth of field, clean composition. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Bright luxury trading desk photo with crypto-market mood, daylight reflections, premium editorial look, restrained bitcoin cue, stylish and realistic, top area clear. {common}",
            f"Photorealistic business-magazine image of a modern digital asset trading setup in daylight, clean glass reflections, believable and premium. {common}",
            f"Human-shot editorial photo of a bright modern market workstation with crypto sentiment, realistic lighting, not flashy, open top area. {common}",
        ]
    if key == "rates":
        return [
            f"Bright editorial photo of a central-bank or institutional finance setting, premium macro-news style, clean architecture, open upper frame for text. {common}",
            f"Photorealistic daylight image of a policy-driven financial newsroom environment, elegant and realistic, calm but important mood. {common}",
            f"Business magazine photo evoking interest-rate and macro direction, bright neutral palette, high-end editorial realism. {common}",
        ]
    if key == "geopolitics":
        return [
            f"Bright but serious documentary-style image of strategic shipping waters in daytime, subtle geopolitical tension, premium world-news editorial photography, upper area clean. {common}",
            f"Photorealistic world-news background with cargo route and distant patrol presence under bright sky, realistic, restrained, business-news look. {common}",
            f"Editorial geopolitical market image with bright sea, strategic shipping mood and clean composition, realistic human-shot feel. {common}",
        ]
    if key == "gold":
        return [
            f"Bright premium finance photo with safe-haven gold mood, elegant metallic reflections, clean editorial business-magazine aesthetic, no text. {common}",
            f"Photorealistic macro-market image evoking gold demand, bright high-end desk reflections, realistic and luxurious without looking fake. {common}",
            f"Business-news style photo with premium gold-toned market atmosphere, bright and polished, clear upper space. {common}",
        ]
    return [
        f"Bright premium financial-news background, realistic editorial photography, modern market atmosphere, clean daylight, upper area simple for text overlay. {common}",
        f"Photorealistic business-magazine image of global market mood, bright polished finance aesthetic, believable human-shot composition. {common}",
        f"Editorial macro market background with bright blue city and finance mood, realistic, premium, not dark, open top area. {common}",
    ]


def _face_prompt_variants():
    common = (
        "Ultra-realistic editorial portrait photography, believable human skin, no text, no watermark, no collage, premium magazine look, vertical 9:16."
    )
    return [
        f"Confident stylish young man in a luxury car during daytime, subtle reaction expression, modern lifestyle editorial photo, premium and realistic. {common}",
        f"Photorealistic editorial portrait of a successful young man reacting to market news while seated in a premium car, bright daylight, clean composition. {common}",
        f"Bright luxury lifestyle photo of a focused young man in a car interior, premium modern editorial aesthetic, realistic and clean. {common}",
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


def _analyze_brightness(img: Image.Image) -> float:
    gray = ImageOps.grayscale(img).resize((64, 64), Image.LANCZOS)
    arr = np.asarray(gray, dtype=np.float32)
    return float(arr.mean())


def _brighten_image(img: Image.Image) -> Image.Image:
    b = _analyze_brightness(img)
    if b < 70:
        img = ImageEnhance.Brightness(img).enhance(1.75)
        img = ImageEnhance.Contrast(img).enhance(1.08)
    elif b < 95:
        img = ImageEnhance.Brightness(img).enhance(1.45)
    elif b < 120:
        img = ImageEnhance.Brightness(img).enhance(1.20)
    return img


def _tone_finish(img: Image.Image, top_clear: bool = False) -> Image.Image:
    img = _brighten_image(img)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    if top_clear:
        od.rectangle((0, 0, W, 760), fill=(8, 10, 18, 40))
        od.rectangle((0, 1200, W, H), fill=(0, 0, 0, 28))
    else:
        od.rectangle((0, 0, W, H), fill=(0, 0, 0, 18))
    out = Image.alpha_composite(img.convert("RGBA"), overlay)
    return out.convert("RGB")


def _generate_openai_bg(prompt_variants, out_path: str, model_env: str) -> bool:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return False
    try:
        from openai import OpenAI
    except Exception:
        return False

    sizes = ["1024x1536", "1536x1024", "1024x1024"]
    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        print(f"[이미지 클라이언트 실패] {repr(e)}")
        return False

    for prompt in prompt_variants:
        for size in sizes:
            try:
                result = client.images.generate(
                    model=os.getenv(model_env, "gpt-image-1"),
                    prompt=prompt,
                    size=size,
                )
                data = result.data[0]
                if getattr(data, "b64_json", None):
                    raw = base64.b64decode(data.b64_json)
                elif getattr(data, "url", None):
                    raw = requests.get(data.url, timeout=60).content
                else:
                    continue
                img = Image.open(BytesIO(raw)).convert("RGB")
                img = _cover_crop(img)
                img = _tone_finish(img, top_clear=True)
                img.save(out_path, quality=95)
                print(f"[이미지 생성 성공] size={size}")
                return True
            except Exception as e:
                print(f"[이미지 재시도] size={size} err={repr(e)}")
                continue
    return False


def _draw_topic_fallback(hook_text: str, out_path: str) -> None:
    key = _topic_keyword(hook_text)
    palettes = {
        "oil": ((95, 143, 198), (242, 185, 84)),
        "fx": ((102, 166, 226), (212, 224, 242)),
        "bitcoin": ((255, 196, 95), (112, 152, 222)),
        "rates": ((160, 193, 242), (88, 202, 182)),
        "geopolitics": ((118, 160, 214), (247, 175, 74)),
        "gold": ((214, 187, 108), (246, 224, 166)),
        "market": ((102, 170, 222), (88, 202, 182)),
    }
    c1, c2 = palettes.get(key, palettes["market"])
    img = _gradient_bg((18, 32, 52), (60, 96, 146)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-160, -220, 640, 540), fill=(*c1, 90))
    gd.ellipse((560, 180, 1320, 1040), fill=(*c2, 70))
    gd.rectangle((0, 0, W, 700), fill=(255, 255, 255, 10))
    gd.rectangle((0, 1460, W, H), fill=(0, 0, 0, 15))
    img = Image.alpha_composite(img, glow)
    img = _tone_finish(img.convert("RGB"), top_clear=True)
    img.save(out_path, quality=95)


def _draw_face_fallback(out_path: str) -> None:
    img = _gradient_bg((36, 74, 126), (22, 24, 40)).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.ellipse((160, 220, 930, 1140), fill=(232, 196, 168, 220))
    d.rounded_rectangle((250, 1040, 850, 1780), radius=70, fill=(34, 36, 56, 250))
    d.ellipse((215, 280, 875, 780), fill=(58, 44, 36, 230))
    d.rectangle((0, 0, W, 360), fill=(255, 255, 255, 20))
    img = _tone_finish(img.convert("RGB"), top_clear=True)
    img.save(out_path, quality=95)


def _generate_openai_intro_bg(hook_text: str, out_path: str) -> bool:
    return _generate_openai_bg(_topic_prompt_variants(hook_text), out_path, "INTRO_IMAGE_MODEL")


def _generate_openai_face_bg(out_path: str) -> bool:
    return _generate_openai_bg(_face_prompt_variants(), out_path, "OUTRO_IMAGE_MODEL")


def _text_shadow(draw: ImageDraw.ImageDraw, xy, text, font, fill, shadow=(0,0,0), shadow_alpha=160, offsets=None):
    if offsets is None:
        offsets = [(-2, -2), (2, -2), (-2, 2), (2, 2), (0, 3)]
    sx, sy = xy
    for ox, oy in offsets:
        draw.text((sx + ox, sy + oy), text, fill=(*shadow, shadow_alpha), font=font)
    draw.text(xy, text, fill=fill, font=font)


def _intro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()
    img = _tone_finish(img, top_clear=True)
    draw = ImageDraw.Draw(img)

    title_font = _font(94, True)
    sub_font = _font(36, False)
    kicker_font = _font(28, True)

    kicker = "지금 돈이 먼저 반응한 이슈"
    kw = draw.textbbox((0, 0), kicker, font=kicker_font)[2]
    draw.rounded_rectangle((60, 122, 60 + kw + 36, 174), radius=24, fill=(255, 255, 255, 34))
    _text_shadow(draw, (78, 133), kicker, kicker_font, (255, 222, 168), shadow_alpha=120)

    lines = _wrap(draw, text, title_font, 840)
    y = 580
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        _text_shadow(draw, ((W - w) // 2, y), line, title_font, (248, 249, 251), shadow_alpha=190)
        y += 112

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    _text_shadow(draw, ((W - sw) // 2, y + 10), subtitle, sub_font, (222, 226, 232), shadow_alpha=170)
    draw.rounded_rectangle((420, y + 80, 660, y + 88), radius=4, fill=(247, 175, 74))
    img.save(out_path, quality=95)


def _outro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg((28, 40, 62), (14, 18, 28))
    img = _tone_finish(img, top_clear=True)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 1180, W, H), fill=(0, 0, 0, 90))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    title_font = _font(88, True)
    sub_font = _font(34, False)

    lines = _wrap(draw, text, title_font, 880)
    y = 1120
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        _text_shadow(draw, ((W - w) // 2, y), line, title_font, (248, 249, 251), shadow_alpha=190)
        y += 100

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    _text_shadow(draw, ((W - sw) // 2, y + 16), subtitle, sub_font, (222, 226, 232), shadow_alpha=170)
    draw.rounded_rectangle((430, y + 74, 650, y + 82), radius=4, fill=(88, 202, 182))
    img.save(out_path, quality=95)


def _fit_card_on_canvas(src_path: str, out_path: str) -> str:
    card = Image.open(src_path).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))

    max_w, max_h = 940, 1180
    ratio = min(max_w / card.width, max_h / card.height)
    card = card.resize((int(card.width * ratio), int(card.height * ratio)), Image.LANCZOS)

    shadow = Image.new("RGBA", (card.width + 44, card.height + 44), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((18, 18, card.width + 26, card.height + 26), radius=34, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(20))

    card_x = (W - card.width) // 2
    card_y = (H - card.height) // 2

    canvas.paste(shadow, (card_x - 22, card_y - 22), shadow)

    rounded = Image.new("RGBA", card.size, (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width, card.height), radius=28, fill=255)
    rounded.paste(card, (0, 0))
    canvas.paste(rounded, (card_x, card_y), mask)
    canvas.save(out_path, quality=95)
    return out_path


def _zoom_variant(src_path: str, out_path: str, scale: float = 1.06):
    img = Image.open(src_path).convert("RGB")
    new_size = (int(W * scale), int(H * scale))
    img = img.resize(new_size, Image.LANCZOS)
    left = (img.width - W) // 2
    top = (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    img.save(out_path, quality=95)
    return out_path


def _prep(path: str, duration: float):
    clip = ImageClip(path)
    clip = _safe_duration(clip, duration)
    return clip


def _build_synth_audio(duration: float):
    def make_frame(t):
        tt = np.asarray(t)
        base = 0.01 * np.sin(2 * np.pi * 100 * tt)
        bass = 0.03 * np.sin(2 * np.pi * 58 * tt) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.5 * tt))
        hats = 0.015 * np.sin(2 * np.pi * 840 * tt) * (np.mod(tt, 0.5) < 0.04)
        click = 0.035 * np.sin(2 * np.pi * 1200 * tt) * (np.mod(tt, 1.0) < 0.06)
        val = np.clip(base + bass + hats + click, -0.24, 0.24)
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
            try:
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
                return clip
        except Exception as e:
            print(f"[외부 배경음 로드 실패] {repr(e)}")
    return _build_synth_audio(duration)


def build_reel(
    news_path: str = "output_rank/rank_news.jpg",
    poly_path: str = "output_rank/rank_poly.jpg",
    market_path: str = "output_rank/rank_market.jpg",
    hook_text: str = "지금 시장이 먼저 반응한 이슈",
    out_path: str = "output_rank/reel_output.mp4",
) -> str:
    Path("output_rank").mkdir(exist_ok=True)

    intro_bg = "output_rank/_reel_intro_bg.jpg"
    outro_bg = "output_rank/_reel_outro_bg.jpg"

    intro = "output_rank/_reel_intro.jpg"
    intro_zoom = "output_rank/_reel_intro_zoom.jpg"
    news_frame = "output_rank/_reel_news_frame.jpg"
    poly_frame = "output_rank/_reel_poly_frame.jpg"
    market_frame = "output_rank/_reel_market_frame.jpg"
    outro = "output_rank/_reel_outro.jpg"
    outro_zoom = "output_rank/_reel_outro_zoom.jpg"

    generated = _generate_openai_intro_bg(hook_text, intro_bg)
    if not generated:
        _draw_topic_fallback(hook_text, intro_bg)

    generated_face = _generate_openai_face_bg(outro_bg)
    if not generated_face:
        _draw_face_fallback(outro_bg)

    _intro_image(hook_text, "오늘 돈 흐름만 빠르게 정리", intro, bg_path=intro_bg)
    _zoom_variant(intro, intro_zoom, 1.06)

    _fit_card_on_canvas(news_path, news_frame)
    _fit_card_on_canvas(poly_path, poly_frame)
    _fit_card_on_canvas(market_path, market_frame)

    _outro_image("다음 흐름도 계속 보려면 저장", "다음 업로드와 비교하면 더 잘 보입니다", outro, bg_path=outro_bg)
    _zoom_variant(outro, outro_zoom, 1.04)

    clips = [
        _prep(intro, 0.9),
        _prep(intro_zoom, 1.1),
        _prep(news_frame, 3.0),
        _prep(poly_frame, 3.0),
        _prep(market_frame, 3.0),
        _prep(outro, 0.9),
        _prep(outro_zoom, 1.1),
    ]
    final = concatenate_videoclips(clips, method="compose")
    audio = _build_audio(final.duration)
    final = _set_audio(final, audio)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return out_path
