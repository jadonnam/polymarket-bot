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


def _gradient_bg(top=(30, 64, 118), bottom=(8, 14, 24)):
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
        "Ultra-realistic editorial news photography, authentic human-shot photo, premium Reuters/Bloomberg magazine aesthetic, "
        "bright natural daylight or soft bright overcast lighting, not CGI, not illustration, not poster, no text, no watermark, no UI, "
        "vertical 9:16 composition, keep the top 45 percent visually simple and uncluttered for headline overlay, realistic depth and believable details."
    )
    if key == "oil":
        return [
            f"Bright documentary-style photo of a large oil tanker moving through open water in daytime, clean sky, realistic reflections, premium macro-news energy image, upper area visually clean. {common}",
            f"Photorealistic editorial image of global energy shipping in daylight, tanker deck and sea under bright sun, premium financial magazine look, believable human-shot composition. {common}",
            f"Realistic daylight photo of an oil tanker near a strategic strait, bright open composition, premium business-news style, not dark or moody. {common}",
        ]
    if key == "fx":
        return [
            f"Bright editorial finance photo of a modern foreign exchange desk, soft daylight through windows, polished screens glow, realistic human-shot composition with clean upper area. {common}",
            f"Photorealistic macro-finance image of currency trading atmosphere, bright blue and silver palette, premium newsroom look, open top area, not dark. {common}",
            f"Business-news style photo of a bright FX trading environment, modern glass office, believable depth of field, clean composition. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Bright luxury trading desk photo with crypto-market mood, daylight reflections, premium editorial look, restrained bitcoin cue, stylish and realistic, upper area clean. {common}",
            f"Photorealistic business-magazine image of a modern digital asset trading setup in daylight, clean glass reflections, believable and premium, not neon-heavy. {common}",
            f"Human-shot editorial photo of a bright modern market workstation with crypto sentiment, realistic lighting, premium and minimal, open upper area. {common}",
        ]
    if key == "rates":
        return [
            f"Bright editorial photo of a central-bank or institutional finance setting, premium macro-news style, clean architecture, upper frame open for text. {common}",
            f"Photorealistic daylight image of a policy-driven financial newsroom environment, elegant and realistic, important but not gloomy mood. {common}",
            f"Business-magazine photo evoking interest-rate and macro direction, bright neutral palette, high-end editorial realism. {common}",
        ]
    if key == "geopolitics":
        return [
            f"Bright documentary-style image of strategic shipping waters in daytime, subtle geopolitical tension, premium world-news editorial photography, visually clean upper area. {common}",
            f"Photorealistic world-news background with cargo route and distant patrol presence under bright sky, realistic and restrained, premium business-news look. {common}",
            f"Editorial geopolitical market image with bright sea, strategic shipping mood and clean composition, realistic human-shot feel, not dark. {common}",
        ]
    if key == "gold":
        return [
            f"Bright premium finance photo with safe-haven gold mood, elegant metallic reflections, clean editorial business-magazine aesthetic, open top area. {common}",
            f"Photorealistic macro-market image evoking gold demand, bright high-end desk reflections, realistic and luxurious without looking fake. {common}",
            f"Business-news style photo with premium gold-toned market atmosphere, bright and polished, simple upper composition. {common}",
        ]
    return [
        f"Bright premium financial-news background, realistic editorial photography, modern market atmosphere, daylight clean composition, upper area simple for headline overlay. {common}",
        f"Photorealistic business-magazine image of global market mood, bright polished finance aesthetic, believable human-shot composition, no clutter at the top. {common}",
        f"Editorial macro market background with bright blue city and finance mood, realistic, premium, not dark, open top area. {common}",
    ]


def _face_prompt_variants():
    common = (
        "Ultra-realistic editorial portrait photography, believable human skin, premium magazine look, no text, no watermark, vertical 9:16, bright daylight in luxury car interior."
    )
    return [
        f"Confident stylish young man in a premium sports car during daytime, subtle reaction expression, luxury lifestyle editorial photo, bright and realistic. {common}",
        f"Photorealistic editorial portrait of a successful young man reacting to market news while seated in a luxury car, bright daylight, premium and clean composition. {common}",
        f"Bright luxury lifestyle photo of a focused young man in a premium car interior, realistic, stylish, modern magazine aesthetic. {common}",
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
        img = ImageEnhance.Brightness(img).enhance(2.0)
        img = ImageEnhance.Contrast(img).enhance(1.10)
        img = ImageEnhance.Color(img).enhance(1.06)
    elif b < 95:
        img = ImageEnhance.Brightness(img).enhance(1.55)
        img = ImageEnhance.Contrast(img).enhance(1.05)
    elif b < 120:
        img = ImageEnhance.Brightness(img).enhance(1.22)
    return img


def _tone_finish(img: Image.Image, top_clear: bool = False) -> Image.Image:
    img = _brighten_image(img)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    if top_clear:
        # make headline zone readable without making the whole frame dark
        od.rectangle((0, 0, W, 820), fill=(10, 14, 22, 34))
        od.rectangle((0, 1280, W, H), fill=(0, 0, 0, 22))
        od.ellipse((-80, -120, 520, 440), fill=(255, 255, 255, 16))
    else:
        od.rectangle((0, 0, W, H), fill=(0, 0, 0, 12))
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
        "oil": ((126, 188, 255), (255, 214, 122)),
        "fx": ((122, 188, 255), (232, 240, 255)),
        "bitcoin": ((255, 205, 120), (122, 188, 255)),
        "rates": ((174, 208, 255), (94, 220, 194)),
        "geopolitics": ((144, 190, 255), (255, 194, 118)),
        "gold": ((226, 194, 118), (255, 230, 170)),
        "market": ((122, 188, 255), (94, 220, 194)),
    }
    c1, c2 = palettes.get(key, palettes["market"])
    img = _gradient_bg((70, 128, 198), (10, 18, 30)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-160, -240, 720, 520), fill=(*c1, 88))
    gd.ellipse((500, 120, 1320, 980), fill=(*c2, 72))
    gd.rectangle((0, 0, W, 760), fill=(255, 255, 255, 12))
    img = Image.alpha_composite(img, glow)
    img = _tone_finish(img.convert("RGB"), top_clear=True)
    img.save(out_path, quality=95)


def _draw_face_fallback(out_path: str) -> None:
    img = _gradient_bg((118, 170, 230), (18, 24, 36)).convert("RGBA")
    d = ImageDraw.Draw(img)
    d.ellipse((120, 150, 980, 1020), fill=(235, 198, 170, 230))
    d.rounded_rectangle((245, 980, 850, 1820), radius=80, fill=(36, 40, 60, 250))
    d.ellipse((200, 180, 900, 760), fill=(72, 56, 44, 230))
    d.rectangle((0, 0, W, 420), fill=(255, 255, 255, 24))
    img = _tone_finish(img.convert("RGB"), top_clear=True)
    img.save(out_path, quality=95)


def _generate_openai_intro_bg(hook_text: str, out_path: str) -> bool:
    return _generate_openai_bg(_topic_prompt_variants(hook_text), out_path, "INTRO_IMAGE_MODEL")


def _generate_openai_face_bg(out_path: str) -> bool:
    return _generate_openai_bg(_face_prompt_variants(), out_path, "OUTRO_IMAGE_MODEL")


def _text_shadow(draw: ImageDraw.ImageDraw, xy, text, font, fill, shadow=(0,0,0), shadow_alpha=180, offsets=None):
    if offsets is None:
        offsets = [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, 4), (0, 6)]
    sx, sy = xy
    for ox, oy in offsets:
        draw.text((sx + ox, sy + oy), text, fill=(*shadow, shadow_alpha), font=font)
    draw.text(xy, text, fill=fill, font=font)


def _draw_text_panel(img: Image.Image, top: int, bottom: int) -> Image.Image:
    panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel)
    pd.rounded_rectangle((70, top, W - 70, bottom), radius=48, fill=(6, 10, 18, 112))
    panel = panel.filter(ImageFilter.GaussianBlur(12))
    return Image.alpha_composite(img.convert("RGBA"), panel)


def _intro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()
    img = _tone_finish(img, top_clear=True)
    img = _draw_text_panel(img, 430, 1040).convert("RGB")
    draw = ImageDraw.Draw(img)

    title_font = _font(104, True)
    sub_font = _font(38, False)
    brand_font = _font(26, True)

    draw.text((62, 52), "JADONNAM", fill=(236, 240, 246), font=brand_font)

    lines = _wrap(draw, text, title_font, 820)
    y = 560
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        _text_shadow(draw, ((W - w) // 2, y), line, title_font, (250, 252, 255), shadow_alpha=210)
        y += 116

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    _text_shadow(draw, ((W - sw) // 2, y + 4), subtitle, sub_font, (235, 239, 245), shadow_alpha=180)
    draw.rounded_rectangle((420, y + 78, 660, y + 88), radius=4, fill=(247, 175, 74))
    img.save(out_path, quality=95)


def _outro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg((92, 146, 216), (18, 24, 36))
    img = _tone_finish(img, top_clear=True)
    img = _draw_text_panel(img, 1040, 1640).convert("RGB")
    draw = ImageDraw.Draw(img)

    title_font = _font(86, True)
    sub_font = _font(34, False)

    lines = _wrap(draw, text, title_font, 860)
    y = 1140
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        _text_shadow(draw, ((W - w) // 2, y), line, title_font, (248, 249, 251), shadow_alpha=190)
        y += 100

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    _text_shadow(draw, ((W - sw) // 2, y + 20), subtitle, sub_font, (232, 236, 242), shadow_alpha=170)
    draw.rounded_rectangle((430, y + 80, 650, y + 88), radius=4, fill=(88, 202, 182))
    img.save(out_path, quality=95)


def _crop_card_core(card: Image.Image) -> Image.Image:
    # remove duplicated header/footer zones from the 1080x1350 feed card for reel display
    left, top, right, bottom = 60, 330, 1020, 1220
    if card.width < right or card.height < bottom:
        return card
    return card.crop((left, top, right, bottom))


def _fit_card_on_canvas(src_path: str, out_path: str, section_label: str) -> str:
    card = Image.open(src_path).convert("RGB")
    card = _crop_card_core(card)
    canvas = Image.new("RGB", (W, H), (0, 0, 0))

    # single small section label only
    cd = ImageDraw.Draw(canvas)
    label_font = _font(32, True)
    sub_font = _font(22, False)
    label_w = cd.textbbox((0, 0), section_label, font=label_font)[2]
    cd.text(((W - label_w) // 2, 120), section_label, fill=(245, 246, 248), font=label_font)
    sub = "핵심 흐름"
    sub_w = cd.textbbox((0, 0), sub, font=sub_font)[2]
    cd.text(((W - sub_w) // 2, 168), sub, fill=(152, 158, 170), font=sub_font)
    cd.rounded_rectangle((460, 208, 620, 216), radius=4, fill=(245, 246, 248))

    max_w, max_h = 930, 980
    ratio = min(max_w / card.width, max_h / card.height)
    card = card.resize((int(card.width * ratio), int(card.height * ratio)), Image.LANCZOS)

    shadow = Image.new("RGBA", (card.width + 60, card.height + 60), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.rounded_rectangle((24, 24, card.width + 36, card.height + 36), radius=42, fill=(0, 0, 0, 190))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))

    card_x = (W - card.width) // 2
    card_y = 320

    canvas.paste(shadow, (card_x - 30, card_y - 30), shadow)

    rounded = Image.new("RGBA", card.size, (0, 0, 0, 0))
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width, card.height), radius=34, fill=255)
    rounded.paste(card, (0, 0))
    canvas.paste(rounded, (card_x, card_y), mask)
    canvas.save(out_path, quality=95)
    return out_path


def _zoom_variant(src_path: str, out_path: str, scale: float = 1.05):
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
    news_zoom = "output_rank/_reel_news_zoom.jpg"
    poly_frame = "output_rank/_reel_poly_frame.jpg"
    poly_zoom = "output_rank/_reel_poly_zoom.jpg"
    market_frame = "output_rank/_reel_market_frame.jpg"
    market_zoom = "output_rank/_reel_market_zoom.jpg"
    outro = "output_rank/_reel_outro.jpg"
    outro_zoom = "output_rank/_reel_outro_zoom.jpg"

    if not _generate_openai_intro_bg(hook_text, intro_bg):
        _draw_topic_fallback(hook_text, intro_bg)

    if not _generate_openai_face_bg(outro_bg):
        _draw_face_fallback(outro_bg)

    _intro_image(hook_text, "오늘 돈 흐름만 빠르게 정리", intro, bg_path=intro_bg)
    _zoom_variant(intro, intro_zoom, 1.05)

    _fit_card_on_canvas(news_path, news_frame, "뉴스")
    _fit_card_on_canvas(poly_path, poly_frame, "폴리마켓")
    _fit_card_on_canvas(market_path, market_frame, "시장 반응")
    _zoom_variant(news_frame, news_zoom, 1.03)
    _zoom_variant(poly_frame, poly_zoom, 1.03)
    _zoom_variant(market_frame, market_zoom, 1.03)

    _outro_image("이 흐름은 저장해둬야 된다", "다음 업로드랑 비교하면 더 빨리 보입니다", outro, bg_path=outro_bg)
    _zoom_variant(outro, outro_zoom, 1.04)

    clips = [
        _prep(intro, 0.8),
        _prep(intro_zoom, 1.0),
        _prep(news_frame, 1.3),
        _prep(news_zoom, 1.1),
        _prep(poly_frame, 1.3),
        _prep(poly_zoom, 1.1),
        _prep(market_frame, 1.3),
        _prep(market_zoom, 1.1),
        _prep(outro, 0.8),
        _prep(outro_zoom, 1.0),
    ]
    final = concatenate_videoclips(clips, method="compose")
    audio = _build_audio(final.duration)
    final = _set_audio(final, audio)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return out_path
