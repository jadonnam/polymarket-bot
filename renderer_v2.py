from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

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
ENABLE_OPENAI_IMAGE = (os.getenv("ENABLE_OPENAI_IMAGE") or "false").lower() == "true"


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
    ratio = max(target_w / max(1, img.width), target_h / max(1, img.height))
    new_w = max(1, int(img.width * ratio))
    new_h = max(1, int(img.height * ratio))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return resized.crop((left, top, left + target_w, top + target_h))


def _download_image(url: str, out_path: str) -> Optional[str]:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        _cover_crop(img).save(out_path, quality=95)
        return out_path
    except Exception:
        return None


def _draw_center_text(base: Image.Image, text: str, size: int = 84) -> Image.Image:
    img = base.copy().convert("RGB")
    draw = ImageDraw.Draw(img)
    font = _font(size, True)
    max_w = 900
    words = str(text or "").split()
    lines: List[str] = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if draw.textbbox((0, 0), cand, font=font)[2] <= max_w:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    lines = lines[:2] if lines else [""]

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 560, W, 1380), fill=(0, 0, 0, 96))
    merged = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(merged)

    y = 760
    for line in lines:
        tw = draw.textbbox((0, 0), line, font=font)[2]
        x = (W - tw) // 2
        draw.text((x + 2, y + 3), line, fill=(0, 0, 0), font=font)
        draw.text((x, y), line, fill=(245, 247, 250), font=font)
        y += size + 28
    return merged


def _draw_subline(base: Image.Image, text: str, sub: str = "") -> Image.Image:
    img = base.copy().convert("RGB")
    draw = ImageDraw.Draw(img)
    main_font = _font(70, True)
    sub_font = _font(34, False)
    draw.text((48, 72), "JADONNAM", fill=(208, 212, 220), font=_font(22, False))
    draw.text((48, 1320), str(text or ""), fill=(246, 248, 250), font=main_font)
    if sub:
        draw.text((48, 1420), str(sub), fill=(218, 222, 229), font=sub_font)
    return img


def _local_editorial_bg(text_seed: str, out_path: str) -> str:
    # Low-cost mode default: no external model call.
    seed = sum(ord(c) for c in str(text_seed or "")) % 40
    top = (12 + seed // 4, 22 + seed // 5, 34 + seed // 6)
    bottom = (28 + seed // 3, 46 + seed // 4, 66 + seed // 5)
    img = Image.new("RGB", (W, H), top)
    draw = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(1, H - 1)
        r = int(top[0] * (1 - t) + bottom[0] * t)
        g = int(top[1] * (1 - t) + bottom[1] * t)
        b = int(top[2] * (1 - t) + bottom[2] * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))
    img = ImageEnhance.Contrast(img).enhance(1.06)
    img.save(out_path, quality=95)
    return out_path


def _try_openai_bg(text_seed: str, out_path: str) -> Optional[str]:
    if not ENABLE_OPENAI_IMAGE:
        return None
    try:
        from image_generator_new import safe_generate_bg
    except Exception as e:
        print(f"[renderer_v2] OpenAI bg import skipped: {repr(e)}")
        return None
    try:
        safe_generate_bg(
            visual_topic="market_general",
            seed_text=text_seed,
            context_title=text_seed,
            output_path=out_path,
        )
        return out_path
    except Exception as e:
        print(f"[renderer_v2] OpenAI bg generation failed: {repr(e)}")
        return None


def _make_fallback_bg(text_seed: str, out_path: str) -> str:
    generated = _try_openai_bg(text_seed, out_path)
    if not generated:
        generated = _local_editorial_bg(text_seed, out_path)
    img = Image.open(out_path).convert("RGB")
    _cover_crop(ImageEnhance.Brightness(img).enhance(0.96)).save(out_path, quality=95)
    return out_path


def _prep(path: str, duration: float):
    clip = ImageClip(path)
    return _safe_duration(clip, duration)


def _build_synth_audio(duration: float):
    def make_frame(t):
        tt = np.asarray(t)
        base = 0.008 * np.sin(2 * np.pi * 104 * tt)
        bass = 0.022 * np.sin(2 * np.pi * 58 * tt) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.45 * tt))
        hat = 0.010 * np.sin(2 * np.pi * 910 * tt) * (np.mod(tt, 0.5) < 0.06)
        v = np.clip(base + bass + hat, -0.20, 0.20)
        if np.ndim(v) == 0:
            return [float(v), float(v)]
        return np.column_stack([v, v])

    return AudioClip(make_frame, duration=duration, fps=44100)


def _build_audio(duration: float):
    if os.path.exists(ASSETS_AUDIO):
        try:
            clip = AudioFileClip(ASSETS_AUDIO)
            if clip.duration > duration:
                return clip.subclip(0, duration)
        except Exception:
            pass
    return _build_synth_audio(duration)


def render_reel_story_v2(story: Dict[str, Any], out_path: str = "output_rank/reel_output_v2.mp4") -> str:
    Path("output_rank").mkdir(exist_ok=True)
    flow = story.get("flow", []) or []
    meta = story.get("meta", {}) or {}

    lead_title = str(meta.get("lead_title", "market move"))
    remote_photo = str(meta.get("lead_image_url", ""))
    raw_photo_path = "output_rank/_v2_news_photo_raw.jpg"
    base_bg_path = "output_rank/_v2_bg.jpg"

    photo_path = _download_image(remote_photo, raw_photo_path)
    if not photo_path:
        photo_path = _make_fallback_bg(lead_title, base_bg_path)

    base = Image.open(photo_path).convert("RGB").resize((W, H), Image.LANCZOS)
    clips = []
    for idx, beat in enumerate(flow):
        beat_type = str(beat.get("type", "hook"))
        text = str(beat.get("text", "")).strip()
        duration = float(beat.get("duration", 3.0))
        frame_path = f"output_rank/_v2_{idx}_{beat_type}.jpg"

        if beat_type == "hook":
            frame = _draw_center_text(base, text, size=92)
        elif beat_type == "news_photo":
            title = beat.get("title", lead_title)
            subtitle = beat.get("subtitle", "")
            frame = _draw_subline(base, str(title), str(subtitle))
        elif beat_type == "number_reaction":
            frame = _draw_subline(base, text, str(beat.get("subtext", "")))
        elif beat_type == "human_impact":
            frame = _draw_center_text(base, text, size=74)
        else:
            frame = _draw_center_text(base, text, size=68)

        frame.save(frame_path, quality=95)
        clips.append(_prep(frame_path, duration))

    if not clips:
        fallback = _draw_center_text(base, "시장 흐름 업데이트", size=82)
        fallback_path = "output_rank/_v2_fallback.jpg"
        fallback.save(fallback_path, quality=95)
        clips = [_prep(fallback_path, 5.0)]

    final = concatenate_videoclips(clips, method="compose")
    audio = _build_audio(final.duration)
    final = _set_audio(final, audio)
    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)
    return out_path
