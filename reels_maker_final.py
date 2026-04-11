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


def _gradient_bg(top=(8, 10, 18), bottom=(18, 22, 36)):
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
    return lines[:2]


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
    """자돈남 채널 방향: 어둡고 긴장감 있는 프리미엄 금융 분위기"""
    key = _topic_keyword(hook_text)

    common = (
        "Dark cinematic editorial photography, moody dramatic lighting, deep shadows, "
        "premium financial news atmosphere, no text, no watermark, no UI elements, "
        "vertical 9:16 composition, photorealistic, high contrast, tension and urgency, "
        "upper half clean and dark for text overlay."
    )

    if key == "oil":
        return [
            f"Dramatic night shot of a massive oil tanker cutting through dark ocean waters, orange refinery fires glowing on the horizon, deep shadows, cinematic tension. {common}",
            f"Dark aerial view of an oil refinery at night, industrial flames and smoke, dramatic orange and black palette, high stakes atmosphere. {common}",
        ]
    if key == "fx":
        return [
            f"Dark moody trading room at night, multiple screens glowing with currency charts, deep blue and amber tones, tense atmosphere, cinematic. {common}",
            f"Close-up of glowing financial screens in darkness showing dollar and won exchange rates, dramatic contrast, premium noir finance aesthetic. {common}",
        ]
    if key == "bitcoin":
        return [
            f"Dark dramatic scene of crypto trading screens glowing in a dim room, deep shadows, intense blue and white light, high tension atmosphere. {common}",
            f"Moody night cityscape with dark trading terminal screens reflecting bitcoin chart movements, cinematic financial noir. {common}",
        ]
    if key == "rates":
        return [
            f"Dark dramatic exterior of a central bank building at night, imposing architecture under stormy sky, dramatic spotlights, tension and authority. {common}",
            f"Moody government financial institution at dusk, heavy clouds, dramatic lighting, serious and weighty atmosphere. {common}",
        ]
    if key == "geopolitics":
        return [
            f"Dark aerial view of strategic shipping strait at night, distant orange glow of conflict on horizon, tense military atmosphere, cinematic. {common}",
            f"Dramatic dark ocean scene at night with cargo ships and distant warning lights, geopolitical tension, deep shadows and orange accents. {common}",
        ]
    if key == "gold":
        return [
            f"Dark vault interior with gold bars under dramatic single spotlight, deep shadows, luxury and tension combined, cinematic noir. {common}",
            f"Dramatic close-up of gold bars in darkness, single dramatic light source, rich and heavy atmosphere, financial safe haven mood. {common}",
        ]
    return [
        f"Dark premium financial trading floor at night, screens glowing with market data, deep shadows and dramatic blue light, cinematic tension. {common}",
        f"Moody dark cityscape at night from above, financial district lights, dramatic contrast, sense of global market forces at work. {common}",
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

    # gpt-image-1 먼저 시도, 실패하면 dall-e-3
    models = [
        ("gpt-image-1", "1024x1536"),
        ("dall-e-3", "1024x1792"),
    ]

    for prompt in prompt_variants:
        for model, size in models:
            try:
                result = client.images.generate(
                    model=model,
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
                img.save(out_path, quality=95)
                print(f"[이미지 생성 성공] model={model}")
                return True
            except Exception as e:
                print(f"[이미지 재시도] model={model} err={repr(e)}")
                continue
    return False


def _draw_topic_fallback(hook_text: str, out_path: str) -> None:
    """DALL-E 실패시 다크 그라디언트 폴백"""
    key = _topic_keyword(hook_text)
    palettes = {
        "oil": ((80, 40, 10), (255, 120, 30)),
        "fx": ((10, 20, 60), (30, 80, 180)),
        "bitcoin": ((10, 10, 40), (60, 60, 200)),
        "rates": ((10, 30, 50), (20, 80, 120)),
        "geopolitics": ((40, 10, 10), (180, 60, 20)),
        "gold": ((40, 30, 5), (180, 140, 20)),
        "market": ((10, 15, 30), (20, 50, 100)),
    }
    c1, c2 = palettes.get(key, palettes["market"])
    img = _gradient_bg((8, 10, 18), (20, 25, 40)).convert("RGBA")
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-160, 600, 720, 1400), fill=(*c2, 60))
    gd.ellipse((400, 800, 1300, 1800), fill=(*c1, 40))
    img = Image.alpha_composite(img, glow)
    img.convert("RGB").save(out_path, quality=95)


def _intro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    """인트로: 배경 이미지 + 텍스트만. 패널/줄 없음."""
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()

    # 상단 약간 어둡게만
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, H // 2), fill=(0, 0, 0, 80))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    title_font = _font(96, True)
    sub_font = _font(36, False)
    brand_font = _font(24, False)

    # 브랜드
    draw.text((60, 60), "JADONNAM", fill=(180, 185, 195), font=brand_font)

    # 메인 텍스트 (그림자만)
    lines = _wrap(draw, text, title_font, 900)
    y = 480
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        x = (W - w) // 2
        # 그림자
        for ox, oy in [(-3, 3), (3, 3), (0, 5)]:
            draw.text((x + ox, y + oy), line, fill=(0, 0, 0, 180), font=title_font)
        draw.text((x, y), line, fill=(244, 246, 248), font=title_font)
        y += 112

    # 서브텍스트
    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    draw.text(((W - sw) // 2, y + 16), subtitle, fill=(160, 165, 175), font=sub_font)

    img.save(out_path, quality=95)


def _outro_image(text: str, subtitle: str, out_path: str, bg_path: Optional[str] = None):
    """아웃트로: 인트로랑 동일 배경 재사용"""
    if bg_path and os.path.exists(bg_path):
        img = Image.open(bg_path).convert("RGB").resize((W, H), Image.LANCZOS)
    else:
        img = _gradient_bg()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, H // 2, W, H), fill=(0, 0, 0, 100))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    title_font = _font(80, True)
    sub_font = _font(32, False)
    brand_font = _font(24, False)

    draw.text((60, 60), "JADONNAM", fill=(180, 185, 195), font=brand_font)

    lines = _wrap(draw, text, title_font, 900)
    y = 1200
    for line in lines:
        w = draw.textbbox((0, 0), line, font=title_font)[2]
        x = (W - w) // 2
        for ox, oy in [(-2, 3), (2, 3), (0, 4)]:
            draw.text((x + ox, y + oy), line, fill=(0, 0, 0, 160), font=title_font)
        draw.text((x, y), line, fill=(244, 246, 248), font=title_font)
        y += 96

    sw = draw.textbbox((0, 0), subtitle, font=sub_font)[2]
    draw.text(((W - sw) // 2, y + 20), subtitle, fill=(160, 165, 175), font=sub_font)

    img.save(out_path, quality=95)


def _fit_card_no_zoom(src_path: str, out_path: str) -> str:
    """카드를 검은 배경에 letterbox로 배치. 상단 라벨 없음."""
    card = Image.open(src_path).convert("RGB")
    canvas = Image.new("RGB", (W, H), (0, 0, 0))

    # 비율 유지하면서 최대한 크게
    max_w, max_h = 1080, 1700
    ratio = min(max_w / card.width, max_h / card.height)
    new_w = int(card.width * ratio)
    new_h = int(card.height * ratio)
    card = card.resize((new_w, new_h), Image.LANCZOS)

    # 그림자
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
) -> str:
    Path("output_rank").mkdir(exist_ok=True)

    intro_bg = "output_rank/_reel_intro_bg.jpg"
    intro = "output_rank/_reel_intro.jpg"
    news_frame = "output_rank/_reel_news_frame.jpg"
    poly_frame = "output_rank/_reel_poly_frame.jpg"
    market_frame = "output_rank/_reel_market_frame.jpg"
    outro = "output_rank/_reel_outro.jpg"

    # 배경 이미지 생성 (인트로/아웃트로 공용)
    if not _generate_openai_bg(_topic_prompt_variants(hook_text), intro_bg):
        _draw_topic_fallback(hook_text, intro_bg)

    # 인트로/아웃트로 텍스트 합성
    _intro_image(hook_text, "오늘 돈 흐름 정리", intro, bg_path=intro_bg)
    _outro_image("저장해두면 나중에 비교하기 좋아", "팔로우하면 매일 업데이트", outro, bg_path=intro_bg)

    # 카드 — 줌인 없이, 라벨 없이
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
