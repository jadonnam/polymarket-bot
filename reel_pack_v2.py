from __future__ import annotations

from pathlib import Path
from typing import List

import numpy as np
from PIL import Image

try:
    from moviepy.editor import ImageClip, concatenate_videoclips
except Exception:
    from moviepy import ImageClip, concatenate_videoclips


try:
    _LANCZOS = Image.Resampling.LANCZOS
except Exception:
    _LANCZOS = Image.LANCZOS


def _set_duration(clip, duration: float):
    if hasattr(clip, "with_duration"):
        return clip.with_duration(duration)
    return clip.set_duration(duration)


def _set_fps(clip, fps: int):
    if hasattr(clip, "with_fps"):
        return clip.with_fps(fps)
    return clip.set_fps(fps)


def _set_position(clip, pos):
    if hasattr(clip, "with_position"):
        return clip.with_position(pos)
    return clip.set_position(pos)


def _fit_and_pan(card_path: str, duration: float, idx: int):
    # Card ratio 4:5 -> reel 9:16. Use subtle pan only.
    with Image.open(card_path) as im:
        src = im.convert("RGB")
        base_h = 1920
        target_w = max(1, int(src.width * (base_h / max(1, src.height))))
        resized = src.resize((target_w, base_h), _LANCZOS)
        frame = np.array(resized)

    clip = ImageClip(frame)
    clip = _set_duration(clip, duration)

    x_start = -36 - (idx * 3)
    x_end = -12 + (idx * 2)

    def pos(t):
        p = 0.0 if duration <= 0 else min(1.0, max(0.0, t / duration))
        x = x_start + (x_end - x_start) * p
        return (x, 0)

    clip = _set_position(clip, pos)
    return clip


def build_reel_pack_v2(
    card_paths: List[str],
    out_path: str = "output_rank/reel_card_news_v2.mp4",
    per_card_sec: float = 3.6,
) -> str:
    Path("output_rank").mkdir(exist_ok=True)

    clips = []
    for idx, path in enumerate(card_paths[:5]):
        clips.append(_fit_and_pan(path, per_card_sec, idx))

    if not clips:
        raise RuntimeError("card_paths is empty")

    final = concatenate_videoclips(clips, method="compose")
    final = _set_fps(final, 30)
    # No music by design. User can add Instagram music manually.
    final.write_videofile(out_path, fps=30, codec="libx264", audio=False, logger=None)
    return out_path
