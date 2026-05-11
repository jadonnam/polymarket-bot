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


def _line18(s: str) -> str:
    """카드 본문: 한 줄 약 18자 내외 (브랜드 톤)."""
    return _short(s, 18)


def _detect_money_bucket(blob: str, content_mode: str) -> str:
    b = blob.lower()
    pairs: List[Tuple[str, List[str]]] = [
        ("semi", ["반도체", "semiconductor", "nvidia", "하이닉스", "chip", "인공지능"]),
        ("power", ["전력", "power", "electric", "데이터센터", "data center", "전기"]),
        ("oil", ["유가", "oil", "wti", "crude", "brent", "원유"]),
        ("rates", ["금리", "fed", "yield", "cpi", "물가", "채권"]),
        ("fx", ["환율", "won", "krw", "dollar", "달러"]),
        ("crypto", ["bitcoin", "btc", "crypto", "비트", "이더"]),
    ]
    for name, keys in pairs:
        if any(k.lower() in b for k in keys):
            return name
    if content_mode == "korea_close":
        return "korea"
    if content_mode == "us_preopen":
        return "us"
    if content_mode == "company_focus":
        return "company"
    if content_mode == "sector_focus":
        return "sector"
    return "macro"


# PAGE 2: 왜 중요한가 — 뉴스 인용 없이 해석만 (고정 풀, 버킷별)
_PAGE2_COPY: Dict[str, Tuple[str, str, str]] = {
    "semi": (
        "시장은 벌써 다음 수요를 본다",
        "돈은 실적 전에 기대부터 움직인다",
        "한 종목보다 섹터 판이 먼저다",
    ),
    "power": (
        "전기 쓰는 쪽으로 돈이 몰린다",
        "AI 붙으면 전력이 같이 따라온다",
        "한 번 끊기면 바로 흔들린다",
    ),
    "oil": (
        "원유가 움치면 순서가 바뀐다",
        "에너지 값이 오르면 숨이 줄어든다",
        "방향만 잡아도 오늘은 충분하다",
    ),
    "rates": (
        "금리 말보다 돈 방향이 먼저다",
        "채권 금리 움치면 성장주부터 반응",
        "발표 전에 시장이 먼저 찍는다",
    ),
    "fx": (
        "달러 흔들리면 수입·수출이 같이 움직인다",
        "환율은 감정보다 수급이 먼저다",
        "오늘 방향이 내일을 덮기도 한다",
    ),
    "crypto": (
        "위험 쪽으로 기운이 빨리 옮겨간다",
        "작은 뉴스에도 레버가 크다",
        "손이 먼저 가고 설명은 나중이다",
    ),
    "korea": (
        "한국장은 수급이 방향을 잡는다",
        "외국인 손 붙으면 대형이 먼저다",
        "지수보다 누가 사는지가 본론이다",
    ),
    "us": (
        "미국장 전엔 선물이 힌트다",
        "금리·유가·환율이 같이 묶인다",
        "뉴스보다 숫자가 먼저 움직인다",
    ),
    "company": (
        "한 기업 말이 섹터 판을 바꾼다",
        "실적 전에 돈이 먼저 들어온다",
        "대장 움치면 따라붙는 종목이 생긴다",
    ),
    "sector": (
        "섹터 맞으면 작은 종목도 연쇄다",
        "돈은 테마 안에서 왔다 갔다 한다",
        "다음 주도 같은 흐름인지 본다",
    ),
    "macro": (
        "오늘 시장이 고른 축은 하나다",
        "뉴스보다 돈이 먼저 찍는다",
        "내일까지 이어질지가 관건이다",
    ),
}


def build_page2_why_lines(content_mode: str, articles: List[Dict[str, Any]]) -> List[str]:
    blob = _article_blob(articles)
    bucket = _detect_money_bucket(blob, content_mode)
    a, b, c = _PAGE2_COPY.get(bucket, _PAGE2_COPY["macro"])
    return [_line18(a), _line18(b), _line18(c)]


def _compact_metric_line(line: str) -> str:
    s = re.sub(r"\s+", " ", str(line or "").strip()).lstrip("·").strip()
    s = re.sub(r"\bCAPEX\b", "설비투자", s, flags=re.I)
    return _line18(s)


def build_page3_flow_lines(content_mode: str, payload: DailySummaryPayload) -> List[str]:
    flow = _line18(payload.flow_line or "돈이 어디로 가는지가 핵심이다")
    nums = list(payload.number_lines or [])
    picked: List[str] = []
    for raw in nums:
        if len(picked) >= 2:
            break
        c = _compact_metric_line(raw)
        if c and c not in picked and c != "-":
            picked.append(c)
    if len(picked) == 0:
        picked = [_line18("지수 숫자는 방향만 본다"), _line18("둘이 같이 움치면 굳어진다")]
    elif len(picked) == 1:
        picked.append(_line18("그 옆 숫자가 같이 가는지 본다"))
    return [flow, picked[0], picked[1]]


def _strip_checkpoint(cp: str) -> str:
    s = re.sub(r"\s+", " ", str(cp or "").strip())
    s = re.sub(r"^체크:\s*", "", s)
    return s


def build_page4_checkpoint_lines(content_mode: str, articles: List[Dict[str, Any]], payload: DailySummaryPayload) -> List[str]:
    blob = _article_blob(articles)
    bucket = _detect_money_bucket(blob, content_mode)
    first = _line18(_strip_checkpoint(payload.checkpoint or "내일 장 전에 다시 본다"))

    if content_mode == "korea_close" or bucket == "korea":
        rest = (
            "외국인 수급이 이어지는지 본다",
            "거래대금 유지되면 흐름도 이어진다",
        )
    elif content_mode == "us_preopen" or bucket == "us":
        rest = (
            "선물 방향이 장 초반을 지배한다",
            "금리보다 유동성 반응이 먼저다",
        )
    elif bucket in ("semi", "power", "sector"):
        rest = (
            "같은 테마가 이어지면 저장 가치 있다",
            "다음 뉴스보다 숫자가 먼저 움직인다",
        )
    else:
        rest = (
            "다음 뉴스보다 숫자가 먼저 움직인다",
            "같은 흐름이면 저장해 두자",
        )
    return [first, _line18(rest[0]), _line18(rest[1])]


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
    for ln in lines[:3]:
        body = _line18(ln)
        d.text((72, y), body, fill=TEXT_PRIMARY, font=_font(30, False))
        y += 52
    d.text((72, H - 72), "jadonnam · money", fill=TEXT_MUTED, font=_font(18, False))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    img.save(out_path, quality=95)


def render_page2_why(out_path: str, payload: DailySummaryPayload, articles: List[Dict[str, Any]]) -> None:
    mode = (payload.content_mode or "macro_issue").strip().lower()
    lines = build_page2_why_lines(mode, articles)
    _draw_typography_page(out_path, "왜 중요한가", lines, 2)


def render_page3_flow(out_path: str, payload: DailySummaryPayload) -> None:
    mode = (payload.content_mode or "macro_issue").strip().lower()
    lines = build_page3_flow_lines(mode, payload)
    _draw_typography_page(out_path, "돈 흐름", lines, 3)


def render_page4_checkpoint(out_path: str, payload: DailySummaryPayload, articles: List[Dict[str, Any]]) -> None:
    mode = (payload.content_mode or "macro_issue").strip().lower()
    lines = build_page4_checkpoint_lines(mode, articles, payload)
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


def build_carousel_caption_text(
    payload: DailySummaryPayload,
    hook_headline: str,
    articles: List[Dict[str, Any]],
) -> str:
    mode = (payload.content_mode or "macro_issue").strip().lower()
    p2 = build_page2_why_lines(mode, articles)
    why_one = p2[0] if p2 else "오늘 돈이 고른 방향이 있다"
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
        (p2, lambda pth, pl: render_page2_why(pth, pl, articles), 2),
        (p3, render_page3_flow, 3),
        (p4, lambda pth, pl: render_page4_checkpoint(pth, pl, articles), 4),
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
