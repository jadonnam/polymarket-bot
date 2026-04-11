from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
try:
    from moviepy.editor import ImageClip, concatenate_videoclips
except Exception:
    from moviepy import ImageClip, concatenate_videoclips

W, H = 1080, 1920
BASE_DIR = os.path.dirname(__file__)
FONT_DIR = os.path.join(BASE_DIR, "fonts")
BOLD_PATH = os.path.join(FONT_DIR, "Pretendard-Bold.ttf")
REG_PATH = os.path.join(FONT_DIR, "Pretendard-Regular.ttf")


def _font(size: int, bold: bool = True):
    path = BOLD_PATH if bold else REG_PATH
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _text_image(text: str, subtitle: str, out_path: str) -> None:
    img = Image.new("RGB", (W, H), (8, 10, 18))
    draw = ImageDraw.Draw(img)
    title_font = _font(86, True)
    sub_font = _font(32, False)

    bbox = draw.textbbox((0, 0), text, font=title_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, 760), text, fill=(244, 246, 248), font=title_font)

    sb = draw.textbbox((0, 0), subtitle, font=sub_font)
    sw = sb[2] - sb[0]
    draw.text(((W - sw) // 2, 930), subtitle, fill=(145, 152, 165), font=sub_font)
    img.save(out_path, quality=95)


def _prep(path: str, duration: float):
    clip = ImageClip(path).with_duration(duration)
    clip = clip.resized(height=H)
    if clip.w < W:
        clip = clip.resized(width=W)
    clip = clip.cropped(x_center=clip.w / 2, y_center=clip.h / 2, width=W, height=H)
    return clip


def build_reel(news_path: str = "output_rank/rank_news.jpg", poly_path: str = "output_rank/rank_poly.jpg", market_path: str = "output_rank/rank_market.jpg", hook_text: str = "지금 시장이 먼저 반응한 이슈", out_path: str = "output_rank/reel_output.mp4") -> str:
    Path("output_rank").mkdir(exist_ok=True)
    intro = "output_rank/_reel_intro.jpg"
    outro = "output_rank/_reel_outro.jpg"
    _text_image(hook_text, "오늘 돈 흐름만 빠르게 정리", intro)
    _text_image("전체 흐름은 피드에서 확인", "저장해두면 비교하기 편함", outro)

    clips = [
        _prep(intro, 2.5),
        _prep(news_path, 3.6),
        _prep(poly_path, 3.6),
        _prep(market_path, 3.6),
        _prep(outro, 2.2),
    ]
    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(out_path, fps=30, codec="libx264", audio=False, logger=None)
    return out_path
