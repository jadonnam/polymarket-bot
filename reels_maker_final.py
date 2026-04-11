
from __future__ import annotations

import base64
import math
import os
from io import BytesIO
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

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
        "Ultra-realistic editorial news photography, authentic camera look, natural lighting, "
        "not CGI, not illustration, not poster, no text, no watermark, no collage, no UI, "
        "no infographic, no fake screenshots, premium Reuters/Bloomberg magazine aesthetic, "
        "clean composition for vertical 9:16, center-left and upper-center readable for Korean headline overlay."
    )
    if key == "oil":
        return [
            f"Night photograph of a massive oil tanker moving through a narrow strategic strait, subtle industrial lights, dark blue sea, tense global energy atmosphere. {common}",
            f"Realistic documentary-style photo of an offshore oil terminal and tanker at dusk, moody sky, restrained orange reflections on water, serious macro-news tone. {common}",
            f"Photorealistic crude oil transport scene at night, large tanker, open water, distant port lights, high-end financial media style. {common}",
        ]
    if key == "fx":
        return [
            f"Photorealistic macro-finance newsroom photo with out-of-focus currency board lights, dollar and won mood, dark trading room reflections, human-shot editorial realism. {common}",
            f"Realistic trading desk photo with foreign exchange monitors glowing softly in a dark room, no readable UI, serious financial tension, shallow depth of field. {common}",
            f"Documentary-style photograph of a finance workstation at night, currency-market atmosphere, blue and amber highlights, premium editorial realism. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Photorealistic crypto trading desk at night, multiple monitors casting realistic glow, premium editorial finance photo, restrained bitcoin visual cue, not flashy. {common}",
            f"Dark realistic photograph of a professional market desk with crypto sentiment, moody screen reflections, cinematic but believable newsroom tone. {common}",
            f"Human-shot editorial photo of a digital asset trading environment, low-key lighting, serious financial atmosphere, realistic camera grain. {common}",
        ]
    if key == "rates":
        return [
            f"Editorial macro-finance photograph of a central-bank style briefing room and bond-market mood, serious institutional atmosphere, realistic lighting, no text. {common}",
            f"Realistic photo of a policy-news environment, rate-sensitive market atmosphere, dark blue and neutral lighting, premium financial magazine look. {common}",
            f"Photorealistic economist workstation and macro charts glow in a dim room, restrained and believable, human-shot editorial composition. {common}",
        ]
    if key == "geopolitics":
        return [
            f"Realistic documentary-style night photo of geopolitical tension near a shipping route, distant orange glow on horizon, sea and industrial silhouettes, serious global-news tone. {common}",
            f"Photorealistic editorial image of dark military-geopolitical tension over strategic waters, no visible combat, restrained crisis atmosphere, premium magazine realism. {common}",
            f"Human-shot news-style photo of cargo ships and distant crisis glow at night, dramatic but believable, geopolitical market tension. {common}",
        ]
    if key == "gold":
        return [
            f"Photorealistic safe-haven market image, close-up of gold-toned reflections on a dark trading desk, premium editorial look, no text. {common}",
            f"Realistic macro-finance photo with gold market atmosphere, restrained metallic highlights, dark premium magazine aesthetic. {common}",
            f"Human-shot financial editorial image evoking safe-haven demand, luxurious but realistic tone, no artificial CGI look. {common}",
        ]
    return [
        f"Photorealistic premium financial-news background, dark market atmosphere, soft screen reflections, serious editorial realism, believable human-shot composition. {common}",
        f"Editorial finance magazine style photo with moody market screens and subtle city-night reflections, realistic and restrained. {common}",
        f"Documentary-style macro market image, dark blue financial mood, premium newsroom photography, no text or UI. {common}",
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


def _tone_finish(img: Image.Image) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, img.width, img.height), fill=(8, 12, 18, 24))
    vignette = Image.new("L", img.size, 0)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse((-180, -80, img.width + 180, img.height + 260), fill=180)
    vignette = ImageOps.invert(vignette).filter(ImageFilter.GaussianBlur(120))
    dark = Image.new("RGBA", img.size, (0, 0, 0, 70))
    dark.putalpha(vignette)
    out = Image.alpha_composite(img.convert("RGBA"), overlay)
    out = Image.alpha_composite(out, dark)
    return out.convert("RGB")


def _generate_openai_intro_bg(hook_text: str, out_path: str) -> bool:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return False
    try:
        from openai import OpenAI
    except Exception:
        return False

    prompts = _topic_prompt_variants(hook_text)
    sizes = ["1024x1536", "1536x1024", "1024x1024"]

    try:
        client = OpenAI(api_key=api_key)
    except Exception as e:
        print(f"[인트로 이미지 클라이언트 실패] {repr(e)}")
        return False

    for prompt in prompts:
        for size in sizes:
            try:
                result = client.images.generate(
                    model=os.getenv("INTRO_IMAGE_MODEL", "gpt-image-1"),
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
                img = _tone_finish(img)
                img.save(out_path, quality=95)
                print(f"[인트로 이미지 생성 성공] size={size}")
                return True
            except Exception as e:
                print(f"[인트로 이미지 재시도] size={size} err={repr(e)}")
                continue
    return False


def _film_noise(size=(W, H), strength=14):
    noise = (np.random.rand(size[1], size[0], 3) * strength).astype(np.uint8)
    return Image.fromarray(noise, "RGB")


def _draw_topic_fallback(hook_text: str, out_path: str):
    """
    검은 화면 대신, 실제 사진 느낌에 가까운 편집형 배경을 강제로 생성한다.
    완전한 실사 사진은 아니어도 영상 이탈을 막는 '뉴스 매거진 배경' 성격으로 설계.
    """
    key = _topic_keyword(hook_text)
    img = _gradient_bg((8, 12, 20), (18, 28, 44)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)

    if key == "oil":
        gd.ellipse((560, 60, 1250, 720), fill=(235, 152, 60, 32))
        gd.rectangle((0, 1080, W, H), fill=(10, 36, 58, 170))
        gd.polygon([(90, 1205), (300, 1145), (760, 1145), (990, 1200), (940, 1260), (180, 1260)], fill=(20, 24, 32, 255))
        gd.rectangle((455, 980, 505, 1145), fill=(247, 175, 74, 215))
        gd.rectangle((220, 1260, 880, 1274), fill=(90, 205, 182, 180))
    elif key == "fx":
        gd.ellipse((650, 120, 1230, 680), fill=(56, 155, 255, 28))
        for i in range(6):
            x = 590 + i * 78
            gd.rounded_rectangle((x, 760, x + 46, 1180), radius=12, fill=(25, 35, 52, 220))
        gd.rectangle((120, 1180, 960, 1260), fill=(14, 18, 28, 170))
        gd.line((140, 1100, 340, 1020, 520, 1080, 760, 910, 940, 980), fill=(88, 202, 182, 240), width=10)
    elif key == "bitcoin":
        gd.ellipse((650, 250, 980, 580), fill=(247, 175, 74, 30))
        gd.ellipse((635, 560, 965, 890), fill=(28, 34, 46, 255), outline=(247, 175, 74, 240), width=12)
        try:
            big = _font(170, True)
            temp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            td = ImageDraw.Draw(temp)
            td.text((720, 600), "₿", fill=(247, 175, 74, 255), font=big)
            img = Image.alpha_composite(img, temp)
        except Exception:
            pass
        gd.rectangle((90, 1180, 980, 1260), fill=(14, 18, 28, 170))
    elif key == "rates":
        gd.ellipse((640, 180, 1140, 640), fill=(120, 170, 255, 28))
        gd.rectangle((130, 1125, 950, 1245), fill=(14, 18, 28, 180))
        gd.line((160, 1200, 330, 1105, 515, 1070, 700, 930, 930, 820), fill=(88, 202, 182, 235), width=14)
        gd.line((870, 755, 930, 820), fill=(88, 202, 182, 235), width=14)
        gd.line((850, 860, 930, 820), fill=(88, 202, 182, 235), width=14)
    elif key == "geopolitics":
        gd.ellipse((690, 120, 1230, 680), fill=(242, 111, 88, 34))
        gd.rectangle((0, 1050, W, H), fill=(16, 20, 32, 190))
        gd.polygon([(90, 1230), (210, 1090), (420, 1180), (610, 1040), (830, 1205), (1000, 1100), (1080, 1200), (1080, 1920), (0, 1920), (0, 1265)], fill=(28, 24, 36, 255))
        gd.line((120, 1265, 980, 1265), fill=(247, 175, 74, 125), width=8)
    elif key == "gold":
        gd.ellipse((620, 160, 1200, 720), fill=(247, 175, 74, 36))
        gd.rounded_rectangle((610, 860, 930, 1040), radius=30, fill=(140, 108, 40, 255))
        gd.rounded_rectangle((520, 1010, 840, 1190), radius=30, fill=(166, 126, 54, 255))
        gd.rectangle((120, 1200, 980, 1270), fill=(14, 18, 28, 180))
    else:
        gd.ellipse((700, 120, 1250, 680), fill=(88, 202, 182, 28))
        gd.rectangle((115, 1180, 980, 1260), fill=(14, 18, 28, 180))
        gd.line((130, 1200, 320, 1110, 520, 1170, 700, 970, 940, 885), fill=(247, 175, 74, 235), width=14)

    img = Image.alpha_composite(img, glow)
    noise = _film_noise((W, H), strength=12).filter(ImageFilter.GaussianBlur(0.3)).convert("RGBA")
    noise.putalpha(28)
    img = Image.alpha_composite(img, noise)

    # 상단, 하단 읽기 영역 확보
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    sd.rectangle((0, 0, W, 720), fill=(0, 0, 0, 68))
    sd.rectangle((0, 1380, W, H), fill=(0, 0, 0, 45))
    img = Image.alpha_composite(img, shade).convert("RGB")
    img = _tone_finish(img)
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


def _build_synth_audio(duration: float):
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


def _build_audio(duration: float):
    if os.path.exists(ASSETS_AUDIO):
        try:
            clip = AudioFileClip(ASSETS_AUDIO)
            if clip.duration > duration:
                return clip.subclip(0, duration)
            # 짧은 오디오면 뒤에 무음 대신 합성음을 얇게 덧댄다
            if abs(clip.duration - duration) < 0.05:
                return clip
            try:
                loops = []
                remaining = duration
                while remaining > 0:
                    seg = clip.subclip(0, min(clip.duration, remaining))
                    loops.append(seg)
                    remaining -= seg.duration
                from moviepy.editor import concatenate_audioclips
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
