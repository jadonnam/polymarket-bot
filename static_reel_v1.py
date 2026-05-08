from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from PIL import Image, ImageDraw, ImageFont

from logo_asset_manager import load_logo, load_symbol_icon

try:
    from moviepy.editor import ImageClip
except Exception:
    from moviepy import ImageClip

W, H = 1080, 1920


def _font(size: int, bold: bool = True):
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _base() -> Image.Image:
    img = Image.new("RGB", (W, H), (7, 9, 13))
    d = ImageDraw.Draw(img)
    for y in range(H):
        v = int(12 + 26 * (y / H))
        d.line([(0, y), (W, y)], fill=(v, v, v + 3))
    return img


def _poster_stock_study() -> Image.Image:
    img = _base()
    d = ImageDraw.Draw(img)
    d.text((60, 72), "매일 미국 주식 1종목 공부하기", fill=(245, 248, 251), font=_font(64, True))
    d.text((60, 156), "오늘의 종목", fill=(192, 200, 212), font=_font(36, False))

    logo = load_logo("NVDA", 420)
    img.paste(logo, ((W - logo.width) // 2, 430), logo)
    d.text((60, 1280), "NVIDIA", fill=(246, 249, 252), font=_font(128, True))
    d.text((60, 1426), "NVDA · 빅테크 시가총액 상위", fill=(214, 221, 230), font=_font(46, True))
    d.rounded_rectangle((60, 1580, 1020, 1700), radius=24, fill=(18, 24, 32))
    d.text((92, 1618), "핵심 한 줄: AI 수요가 실적 가이던스를 다시 올렸다", fill=(231, 237, 244), font=_font(36, True))
    d.text((60, 1780), "JADONNAM", fill=(176, 185, 198), font=_font(30, False))
    return img


def _poster_ranking() -> Image.Image:
    img = _base()
    d = ImageDraw.Draw(img)
    d.text((60, 72), "올해 반도체 기업 수익률 순위", fill=(245, 248, 251), font=_font(60, True))
    d.text((60, 154), "저장형 순위 카드", fill=(188, 197, 209), font=_font(34, False))

    rows: List[tuple[str, str, str]] = [
        ("NVDA", "NVIDIA", "+38.2%"),
        ("AVGO", "Broadcom", "+27.4%"),
        ("AMD", "AMD", "+19.5%"),
        ("TSM", "TSMC", "+14.1%"),
        ("ASML", "ASML", "+11.6%"),
    ]
    y = 320
    for idx, (sym, name, ret) in enumerate(rows, start=1):
        lg = load_logo(sym, 94)
        img.paste(lg, (72, y), lg)
        d.text((190, y + 10), f"{idx}. {name}", fill=(238, 242, 247), font=_font(46, True))
        color = (95, 214, 128) if not ret.startswith("-") else (255, 101, 101)
        d.text((832, y + 18), ret, fill=color, font=_font(40, True))
        d.line([(70, y + 116), (1010, y + 116)], fill=(42, 50, 62), width=1)
        y += 126

    icon = load_symbol_icon("etf", 120)
    img.paste(icon, (900, 76), icon)
    d.rounded_rectangle((60, 1540, 1020, 1690), radius=24, fill=(18, 24, 32))
    d.text((92, 1586), "한 장 저장하고 다음 분기 실적 시즌 전에 다시 확인", fill=(231, 237, 244), font=_font(35, True))
    d.text((60, 1780), "JADONNAM", fill=(176, 185, 198), font=_font(30, False))
    return img


def _build_caption(fmt: str) -> str:
    if fmt == "ranking":
        lines = [
            "올해 반도체 수익률 상위 종목 한 번에 정리",
            "상승률만 보지 말고 매출/마진 구조 같이 체크",
            "실적 시즌 전 비교용으로 저장해두세요",
            "다음 분기 발표 때 순위 변화가 핵심 포인트",
            "#미국주식 #반도체 #수익률 #투자공부 #경제뉴스 #저장콘텐츠",
        ]
    else:
        lines = [
            "매일 미국 주식 1종목 공부하기",
            "오늘은 NVIDIA: 실적과 가이던스가 핵심",
            "주가보다 사업지표를 먼저 보면 흐름이 보입니다",
            "실적 시즌 전에 다시 보기용으로 저장하세요",
            "#미국주식 #엔비디아 #주식공부 #빅테크 #투자공부 #저장콘텐츠",
        ]
    return "\n".join(lines)


def build_static_reel_v1(
    output_dir: str = "output_static_reel",
    reel_format: str = "stock_study",
    duration_sec: float = 18.0,
) -> Dict[str, str]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    fmt = (reel_format or "stock_study").strip().lower()
    if fmt not in ("stock_study", "ranking"):
        fmt = "stock_study"

    poster_path = os.path.join(output_dir, "poster.jpg")
    reel_path = os.path.join(output_dir, "reel_output.mp4")
    caption_path = os.path.join(output_dir, "caption.txt")

    poster = _poster_ranking() if fmt == "ranking" else _poster_stock_study()
    poster.save(poster_path, quality=95)

    clip = ImageClip(poster_path)
    if hasattr(clip, "with_duration"):
        clip = clip.with_duration(duration_sec)
    else:
        clip = clip.set_duration(duration_sec)
    clip.write_videofile(reel_path, fps=30, codec="libx264", audio=False, logger=None)

    caption_text = _build_caption(fmt)
    with open(caption_path, "w", encoding="utf-8") as f:
        f.write(caption_text + "\n")

    return {"poster_path": poster_path, "reel_path": reel_path, "caption_path": caption_path, "caption_text": caption_text}
