from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from daily_summary_card import DailySummaryPayload, load_single_news_background

W, H = 1080, 1350
# 단일 포인트 컬러 (토스·핀테크 계열 민트)
ACCENT = (0, 199, 138)
BG_DARK = (11, 13, 18)
TEXT_MUTED = (156, 166, 182)
TEXT_PRIMARY = (248, 250, 252)

try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = Image.LANCZOS


def _font(size: int, bold: bool = True) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _short(s: str, n: int) -> str:
    t = re.sub(r"\s+", " ", str(s or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _article_blob(articles: List[Dict[str, Any]], n: int = 8) -> str:
    parts = []
    for a in articles[:n]:
        parts.append(str(a.get("title", "")))
        parts.append(str(a.get("description", "")))
    return " ".join(parts).lower()


def build_hook_headline(content_mode: str, articles: List[Dict[str, Any]], flow_line: str) -> str:
    """규칙 기반 후킹 헤드라인 (랜덤 없음)."""
    blob = _article_blob(articles)
    rules: List[Tuple[List[str], str]] = [
        (["반도체", "semiconductor", "nvidia", "하이닉스", "chip", "ai"], "돈은 다시 반도체로 몰렸다"),
        (["전력", "power", "electric", "데이터센터", "data center"], "AI는 결국 전기를 먹는다"),
        (["유가", "oil", "wti", "crude", "brent"], "원유 한 방에 자금 방향이 바뀐다"),
        (["금리", "fed", "yield", "cpi", "inflation"], "시장은 이미 다음 유동성을 보고 있다"),
        (["환율", "won", "krw", "dollar", "fx"], "달러 흔들릴 때 돈이 어디로 가는지가 핵심이다"),
        (["bitcoin", "btc", "crypto", "비트"], "위험자산 쪽으로 다시 기운다"),
    ]
    for keys, line in rules:
        if any(k.lower() in blob for k in keys):
            return line
    defaults = {
        "korea_close": "오늘 장, 수급이 방향을 정했다",
        "us_preopen": "미국장 열리기 전 변수는 세 가지뿐이다",
        "macro_issue": "지금 시장이 보는 축은 하나다",
        "company_focus": "기업 하나가 자금의 중심을 잡았다",
        "sector_focus": "섹터 한 줄이 오늘의 답이다",
    }
    return defaults.get(content_mode, "돈이 어디로 움직이는지부터 본다")


def _mode_tag(content_mode: str) -> str:
    return {
        "korea_close": "KOREA CLOSE",
        "us_preopen": "US PREVIEW",
        "macro_issue": "MARKET ISSUE",
        "company_focus": "COMPANY",
        "sector_focus": "SECTOR",
    }.get(content_mode, "MARKET ISSUE")


def _split_headline_two_lines(text: str) -> Tuple[str, str]:
    t = _short(text, 22)
    if len(t) <= 11:
        return t, ""
    return t[:11].rstrip(), t[11:22].rstrip()


def render_page1_hook(
    out_path: str,
    articles: List[Dict[str, Any]],
    hook_headline: str,
    core_sentence: str,
    tag: str,
    preferred_keywords: Optional[List[str]] = None,
) -> None:
    base = load_single_news_background(articles, preferred_keywords).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(H):
        t = y / max(1, H - 1)
        if y > int(H * 0.45):
            a = int(40 + (t - 0.45) * 200)
            od.line((0, y, W, y), fill=(0, 0, 0, min(210, a)))
    img = Image.alpha_composite(base, overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    d.text((48, 52), "jadonnam · money", fill=TEXT_MUTED, font=_font(20, False))
    tag_u = str(tag or "MARKET").upper()[:16]
    tw = d.textbbox((0, 0), tag_u, font=_font(18, True))[2]
    x1, y1 = W - 56 - tw - 28, 44
    d.rounded_rectangle((x1 - 12, y1 - 8, W - 48, y1 + 32), radius=10, outline=ACCENT, width=2)
    d.text((x1, y1), tag_u, fill=TEXT_PRIMARY, font=_font(18, True))

    line1, line2 = _split_headline_two_lines(hook_headline)
    y0 = H - 260
    d.text((48, y0), line1, fill=TEXT_PRIMARY, font=_font(56, True))
    if line2:
        d.text((48, y0 + 72), line2, fill=TEXT_PRIMARY, font=_font(56, True))
    d.text((48, H - 110), _short(core_sentence, 36), fill=ACCENT, font=_font(28, False))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)


def _draw_typography_page(
    out_path: str,
    section_ko: str,
    lines: List[str],
    page_no: int,
) -> None:
    img = Image.new("RGB", (W, H), BG_DARK)
    d = ImageDraw.Draw(img)
    d.rectangle((48, 100, 54, H - 100), fill=ACCENT)
    d.text((72, 88), f"PAGE {page_no}", fill=TEXT_MUTED, font=_font(18, True))
    d.text((72, 132), section_ko, fill=TEXT_PRIMARY, font=_font(44, True))
    y = 220
    for ln in lines[:5]:
        body = _short(ln, 42)
        d.text((72, y), body, fill=TEXT_PRIMARY, font=_font(30, False))
        y += 52
    d.text((72, H - 72), "jadonnam · money", fill=TEXT_MUTED, font=_font(18, False))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)


def _strip_news_prefix(line: str) -> str:
    if ":" in line[:24]:
        return line.split(":", 1)[-1].strip()
    return line.strip()


def render_page2_why(out_path: str, payload: DailySummaryPayload) -> None:
    raw = list(payload.news_lines or [])
    lines = [
        _short(_strip_news_prefix(raw[0]) if raw else "오늘 헤드라인이 방향을 정했다", 40),
        _short(_strip_news_prefix(raw[1]) if len(raw) > 1 else "지수보다 먼저 움든 건 뉴스 흐름이다", 40),
        _short(_strip_news_prefix(raw[2]) if len(raw) > 2 else "내일까지 이어질지가 관건이다", 40),
    ]
    _draw_typography_page(out_path, "왜 중요한가", lines, 2)


def render_page3_flow(out_path: str, payload: DailySummaryPayload) -> None:
    nums = list(payload.number_lines or [])[:3]
    lines = [_short(payload.flow_line or "돈이 어디로 가는지가 핵심이다", 40)]
    lines.extend(_short(x.lstrip("· ").strip(), 40) for x in nums)
    _draw_typography_page(out_path, "돈 흐름", lines[:4], 3)


def render_page4_checkpoint(out_path: str, payload: DailySummaryPayload) -> None:
    lines = [
        _short(payload.checkpoint or "내일 장 전에 다시 확인", 40),
        "지수보다 중요한 건 수급 방향이다.",
        "저장해두고 다음 장에도 비교하면 된다.",
    ]
    _draw_typography_page(out_path, "체크 포인트", lines, 4)


def render_carousel_preview(out_path: str, page_paths: List[str]) -> None:
    tw, th = W // 2, H // 2
    canvas = Image.new("RGB", (W, H), BG_DARK)
    for i, p in enumerate(page_paths[:4]):
        try:
            im = Image.open(p).convert("RGB").resize((tw, th), _RESAMPLE)
        except Exception:
            im = Image.new("RGB", (tw, th), BG_DARK)
        x = (i % 2) * tw
        y = (i // 2) * th
        canvas.paste(im, (x, y))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, H // 2 - 1, W, H // 2 + 1), fill=(32, 38, 48))
    d.rectangle((W // 2 - 1, 0, W // 2 + 1, H), fill=(32, 38, 48))
    d.text((48, H - 56), "carousel preview · jadonnam · money", fill=TEXT_MUTED, font=_font(18, False))
    canvas.save(out_path, quality=92)


def build_carousel_caption_text(payload: DailySummaryPayload, hook_headline: str) -> str:
    raw = list(payload.news_lines or [])
    why_one = _short(_strip_news_prefix(raw[0]) if raw else "오늘 시장이 반응한 이슈가 있다", 120)
    flow = _short(payload.flow_line or "돈이 어디로 움직이는지 같이 본다", 120)
    lines = [
        hook_headline,
        "",
        why_one,
        "",
        flow,
        "",
        "저장해두고 다음 장에도 비교해봐.",
        "친구 태그하고 같이 보기.",
        "",
        "#경제 #돈흐름 #시장요약 #투자메모 #jadonnam",
    ]
    return "\n".join(lines)


def generate_money_flow_carousel(
    out_dir: str,
    payload: DailySummaryPayload,
    articles: List[Dict[str, Any]],
    content_mode: str,
    preferred_keywords: Optional[List[str]] = None,
) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    mode = (content_mode or "macro_issue").strip().lower()
    hook = build_hook_headline(mode, articles, payload.flow_line or "")
    core = _short(payload.flow_line or "지금 시장 자금은 방향을 고른다", 36)
    tag = _mode_tag(mode)

    p1 = os.path.join(out_dir, "page1.jpg")
    p2 = os.path.join(out_dir, "page2.jpg")
    p3 = os.path.join(out_dir, "page3.jpg")
    p4 = os.path.join(out_dir, "page4.jpg")
    prev = os.path.join(out_dir, "carousel_preview.jpg")

    try:
        render_page1_hook(p1, articles, hook, core, tag, preferred_keywords)
    except Exception as e:
        print(f"[money_flow] page1 failed: {repr(e)}")
        Image.new("RGB", (W, H), BG_DARK).save(p1, quality=90)

    for path, fn, pno in (
        (p2, render_page2_why, 2),
        (p3, render_page3_flow, 3),
        (p4, render_page4_checkpoint, 4),
    ):
        try:
            fn(path, payload)
        except Exception as e:
            print(f"[money_flow] render failed {path}: {repr(e)}")
            _draw_typography_page(path, "—", ["데이터 수집 중 · 다시 시도"], pno)

    try:
        render_carousel_preview(prev, [p1, p2, p3, p4])
    except Exception as e:
        print(f"[money_flow] preview failed: {repr(e)}")
        Image.new("RGB", (W, H), BG_DARK).save(prev, quality=90)

    print(f"[money_flow] wrote {p1}, {p2}, {p3}, {p4}, {prev}")
    return {
        "page_paths": [p1, p2, p3, p4],
        "preview_path": prev,
        "hook_headline": hook,
    }
