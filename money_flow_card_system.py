from __future__ import annotations

import hashlib
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

from daily_summary_card import DailySummaryPayload, load_reference_page1_photo

W, H = 1080, 1350
BG = (8, 10, 13)
NEON = (0, 255, 132)
WHITE = (255, 255, 255)
GRAY = (168, 174, 184)
BRAND_NAME = "jadonnam_money"
BRAND_LINE = "capital flow note"
SIGNATURE_PRIMARY = "돈은 뉴스보다 먼저 움직인다."

try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = Image.LANCZOS


def _font(size: int, bold: bool = True) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    names = (
        ("Pretendard-Bold.ttf", "Pretendard-Regular.ttf")
        if bold
        else ("Pretendard-Regular.ttf", "Pretendard-Bold.ttf")
    )
    primary = names[0]
    fallback_names = [
        primary,
        "SUIT-Variable.ttf",
        "NotoSansKR-Bold.otf" if bold else "NotoSansKR-Regular.otf",
        "NotoSansKR-Bold.ttf" if bold else "NotoSansKR-Regular.ttf",
    ]
    for name in fallback_names:
        try:
            return ImageFont.truetype(os.path.join("fonts", name), size)
        except Exception:
            continue
    for win in (
        ("malgunbd.ttf", "malgun.ttf") if bold else ("malgun.ttf", "malgunbd.ttf")
    ):
        try:
            return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", win[0]), size)
        except Exception:
            continue
    return ImageFont.load_default()


def _tw(d: ImageDraw.ImageDraw, text: str, font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]) -> int:
    if hasattr(d, "textlength"):
        return int(d.textlength(text, font=font))
    return int(d.textbbox((0, 0), text, font=font)[2])


def _tb(d: ImageDraw.ImageDraw, text: str, font: Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]) -> int:
    bb = d.textbbox((0, 0), text, font=font)
    return int(bb[3] - bb[1])


def _short(s: str, n: int) -> str:
    t = re.sub(r"\s+", " ", str(s or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _format_price(v: Any, digits: int = 2) -> str:
    try:
        return format(float(v), f",.{digits}f")
    except Exception:
        return "-"


def _format_pct(v: Any) -> str:
    try:
        x = float(v)
        sign = "+" if x > 0 else ""
        return f"{sign}{x:.2f}%"
    except Exception:
        return "-"


def _flow_arrow(raw: str) -> str:
    s = re.sub(r"[,\s]", "", str(raw or ""))
    if not s or s == "-":
        return "→"
    if s.startswith("-") or s.startswith("−"):
        return "↓"
    try:
        if float(s.replace(",", "")) < 0:
            return "↓"
    except Exception:
        pass
    return "↑"


def _quote_row(market_data: Dict[str, Any], key: str, digits: int = 2) -> Tuple[str, str]:
    q = market_data.get("quotes", {}) if isinstance(market_data, dict) else {}
    row = q.get(key, {}) if isinstance(q, dict) else {}
    return _format_price(row.get("price"), digits), _format_pct(row.get("chg_pct"))


def _pager(n: int) -> str:
    return f"{n}/4"


def _draw_neon_vline(d: ImageDraw.ImageDraw) -> None:
    x = 56
    d.line((x, 120, x, H - 100), fill=NEON, width=2)


def _draw_header(d: ImageDraw.ImageDraw, label_en: str, date_line: str) -> None:
    fs = 22
    d.text((80, 56), label_en.upper(), fill=NEON, font=_font(fs, True))
    d.text((80, 86), date_line, fill=GRAY, font=_font(20, False))


def _draw_footer(d: ImageDraw.ImageDraw, page: int) -> None:
    fb = _font(18, False)
    d.text((80, H - 72), BRAND_NAME, fill=GRAY, font=fb)
    pr = _pager(page)
    d.text((W - 80 - _tw(d, pr, fb), H - 72), pr, fill=GRAY, font=fb)


def _page_base_dark() -> Image.Image:
    return Image.new("RGB", (W, H), BG)


def _apply_photo_bottom_gradient(photo: Image.Image) -> Image.Image:
    base = photo.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    y0 = int(H * 0.52)
    for y in range(y0, H):
        t = (y - y0) / max(1, H - y0)
        a = int(30 + t * 215)
        od.line((0, y, W, y), fill=(0, 0, 0, min(245, a)))
    return Image.alpha_composite(base, overlay).convert("RGB")


def _draw_page1_titles(
    img: Image.Image,
    lines_big: List[str],
    subline: str,
    page: int,
    label_en: str,
    date_line: str,
) -> None:
    d = ImageDraw.Draw(img)
    d.text((80, 56), label_en.upper(), fill=NEON, font=_font(22, True))
    d.text((80, 86), date_line, fill=GRAY, font=_font(20, False))
    y = int(H * 0.58)
    for ln in lines_big:
        d.text((80, y), ln, fill=WHITE, font=_font(56, True))
        y += 72
    d.text((80, y + 8), _short(subline, 28), fill=GRAY, font=_font(24, False))
    _draw_neon_vline(d)
    _draw_footer(d, page)


def _draw_focus_box(d: ImageDraw.ImageDraw, title: str, body: str, y0: int) -> None:
    pad = 24
    wbox = W - 160
    x0 = 80
    h_title = _tb(d, title, _font(22, True)) + 8
    h_body = _tb(d, body, _font(26, False)) + 16
    h = h_title + h_body + pad * 2
    d.rounded_rectangle((x0, y0, x0 + wbox, y0 + h), radius=4, outline=NEON, width=1)
    d.text((x0 + pad, y0 + pad), title, fill=NEON, font=_font(22, True))
    d.text((x0 + pad, y0 + pad + h_title), _short(body, 40), fill=WHITE, font=_font(26, False))


def _kit_korea_close(
    out_dir: str,
    payload: DailySummaryPayload,
    market_data: Dict[str, Any],
    articles: List[Dict[str, Any]],
    preferred_keywords: Optional[List[str]],
) -> Tuple[str, str]:
    date_line = payload.date_line or ""
    k = market_data.get("korea", {}) if isinstance(market_data, dict) else {}
    flows = k.get("flows", {}) if isinstance(k, dict) else {}

    p1, p2, p3, p4 = [os.path.join(out_dir, f"page{i}.jpg") for i in range(1, 5)]

    base, img_used = load_reference_page1_photo(articles, preferred_keywords)
    p1_img = _apply_photo_bottom_gradient(base)
    _draw_page1_titles(
        p1_img,
        ["오늘", "한국장 마감", "한눈에 정리"],
        "시장보다 먼저 움직이는 흐름.",
        1,
        "KOREA CLOSE",
        date_line,
    )
    p1_img.save(p1, quality=95)

    img2 = _page_base_dark()
    d2 = ImageDraw.Draw(img2)
    _draw_neon_vline(d2)
    _draw_header(d2, "MARKET SUMMARY", date_line)
    d2.text((80, 200), "시장 요약", fill=WHITE, font=_font(48, True))
    rows = [
        ("코스피", *_quote_row(market_data, "KOSPI")),
        ("코스닥", *_quote_row(market_data, "KOSDAQ")),
    ]
    t_val, t_pct = "-", "-"
    for ln in payload.number_lines or []:
        if "거래" in str(ln) or "대금" in str(ln):
            m = re.search(r"([\d,.]+)\s*%?\s*\(?\s*([+-]?\d+\.?\d*)\s*%", str(ln))
            if m:
                t_val, t_pct = m.group(1), m.group(2) + "%" if "%" not in m.group(2) else m.group(2)
            else:
                t_val = _short(str(ln).lstrip("· ").strip(), 20)
            break
    if t_val == "-" and kospi_v is not None and kosdaq_v is not None:
        t_val = "장중 집계"
        t_pct = "HTS·앱"
    rows.append(("거래대금", t_val, t_pct if isinstance(t_pct, str) else _format_pct(t_pct)))

    y = 320
    for label, val, pct in rows:
        d2.line((80, y, W - 80, y), fill=(32, 36, 42), width=1)
        d2.text((100, y + 18), label, fill=GRAY, font=_font(26, False))
        d2.text((100, y + 58), val, fill=WHITE, font=_font(36, True))
        d2.text((W - 100 - _tw(d2, pct, _font(32, True)), y + 58), pct, fill=NEON, font=_font(32, True))
        y += 140
    _draw_footer(d2, 2)
    img2.save(p2, quality=95)

    img3 = _page_base_dark()
    d3 = ImageDraw.Draw(img3)
    _draw_neon_vline(d3)
    _draw_header(d3, "FLOW", date_line)
    d3.text((80, 200), "수급 현황", fill=WHITE, font=_font(48, True))
    fy = str(flows.get("foreign", "-"))
    iy = str(flows.get("institution", "-"))
    ry = str(flows.get("retail", "-"))
    flow_rows = [
        ("외국인", fy, _flow_arrow(fy)),
        ("기관", iy, _flow_arrow(iy)),
        ("개인", ry, _flow_arrow(ry)),
    ]
    y = 320
    for label, amt, ar in flow_rows:
        d3.line((80, y, W - 80, y), fill=(32, 36, 42), width=1)
        d3.text((100, y + 20), label, fill=GRAY, font=_font(28, False))
        d3.text((100, y + 64), amt, fill=WHITE, font=_font(34, True))
        d3.text((W - 120, y + 60), ar, fill=NEON, font=_font(40, True))
        y += 145
    _draw_footer(d3, 3)
    img3.save(p3, quality=95)

    img4 = _page_base_dark()
    d4 = ImageDraw.Draw(img4)
    _draw_neon_vline(d4)
    _draw_header(d4, "SECTORS", date_line)
    d4.text((80, 200), "강한 섹터 TOP3", fill=WHITE, font=_font(48, True))
    secs = list(market_data.get("sector_top5", []) or []) if isinstance(market_data, dict) else []
    fixed = ["반도체", "전력·에너지", "AI·데이터센터"]
    picks: List[str] = []
    for s in secs:
        t = str(s).strip()
        if t and t not in picks:
            picks.append(_short(t, 16))
        if len(picks) >= 3:
            break
    while len(picks) < 3:
        picks.append(fixed[len(picks)])
    y = 320
    for i, name in enumerate(picks[:3], start=1):
        d4.text((100, y), f"{i}", fill=NEON, font=_font(44, True))
        d4.text((180, y + 4), name, fill=WHITE, font=_font(40, True))
        y += 100
    _draw_focus_box(d4, "NEXT FOCUS", "외국인 수급이 이어지는지 확인", H - 280)
    _draw_footer(d4, 4)
    img4.save(p4, quality=95)

    hook = "한국장 마감 한눈에 정리"
    return hook, img_used


def _kit_us_preopen(
    out_dir: str,
    payload: DailySummaryPayload,
    market_data: Dict[str, Any],
    articles: List[Dict[str, Any]],
    preferred_keywords: Optional[List[str]],
) -> Tuple[str, str]:
    date_line = payload.date_line or ""
    p1, p2, p3, p4 = [os.path.join(out_dir, f"page{i}.jpg") for i in range(1, 5)]

    base, img_used = load_reference_page1_photo(articles, preferred_keywords)
    p1_img = _apply_photo_bottom_gradient(base)
    _draw_page1_titles(
        p1_img,
        ["미국장", "시작 전", "체크포인트"],
        "오늘 밤 체크해야 할 흐름.",
        1,
        "US PREVIEW",
        date_line,
    )
    p1_img.save(p1, quality=95)

    img2 = _page_base_dark()
    d2 = ImageDraw.Draw(img2)
    _draw_neon_vline(d2)
    _draw_header(d2, "FUTURES", date_line)
    d2.text((80, 200), "주요 지수 선물", fill=WHITE, font=_font(44, True))
    fut = [
        ("나스닥 선물", *_quote_row(market_data, "NQ_FUT")),
        ("S&P500 선물", *_quote_row(market_data, "ES_FUT")),
        ("다우 선물", *_quote_row(market_data, "YM_FUT")),
    ]
    y = 300
    for label, val, pct in fut:
        d2.line((80, y, W - 80, y), fill=(32, 36, 42), width=1)
        d2.text((100, y + 16), label, fill=GRAY, font=_font(26, False))
        d2.text((100, y + 56), val, fill=WHITE, font=_font(34, True))
        d2.text((W - 100 - _tw(d2, pct, _font(30, True)), y + 56), pct, fill=NEON, font=_font(30, True))
        y += 135
    _draw_footer(d2, 2)
    img2.save(p2, quality=95)

    img3 = _page_base_dark()
    d3 = ImageDraw.Draw(img3)
    _draw_neon_vline(d3)
    _draw_header(d3, "KEY DATA", date_line)
    d3.text((80, 200), "주요 지표", fill=WHITE, font=_font(44, True))
    ind = [
        ("미국 10년물 금리", *_quote_row(market_data, "US10Y")),
        ("WTI 유가", *_quote_row(market_data, "WTI")),
        ("달러 인덱스", *_quote_row(market_data, "DXY")),
        ("원/달러 환율", *_quote_row(market_data, "USDKRW")),
    ]
    y = 280
    for label, val, pct in ind:
        d3.line((80, y, W - 80, y), fill=(32, 36, 42), width=1)
        d3.text((100, y + 10), label, fill=GRAY, font=_font(24, False))
        d3.text((100, y + 46), val, fill=WHITE, font=_font(30, True))
        d3.text((W - 100 - _tw(d3, pct, _font(28, True)), y + 46), pct, fill=NEON, font=_font(28, True))
        y += 110
    _draw_footer(d3, 3)
    img3.save(p3, quality=95)

    img4 = _page_base_dark()
    d4 = ImageDraw.Draw(img4)
    _draw_neon_vline(d4)
    _draw_header(d4, "TONIGHT", date_line)
    d4.text((80, 200), "오늘 밤 체크 포인트", fill=WHITE, font=_font(40, True))
    opts = ["CPI", "PCE", "고용", "실적", "연준 발언"]
    hkey = int(hashlib.md5(date_line.encode("utf-8")).hexdigest(), 16)
    picks = [opts[(hkey + i) % len(opts)] for i in range(3)]
    y = 300
    for i, it in enumerate(picks, 1):
        d4.text((100, y), f"{i}.", fill=NEON, font=_font(32, True))
        d4.text((160, y), it, fill=WHITE, font=_font(32, True))
        y += 72
    _draw_focus_box(d4, "FOCUS", "AI 리스크와 반도체 흐름 주목", H - 260)
    _draw_footer(d4, 4)
    img4.save(p4, quality=95)

    return "미국장 시작 전 체크포인트", img_used


def _company_display_name(articles: List[Dict[str, Any]]) -> str:
    if not articles:
        return "핵심 기업"
    t = str(articles[0].get("title") or "")
    if "엔비디아" in t or "nvidia" in t.lower():
        return "엔비디아"
    m = re.search(r"([\w가-힣·]{2,18})(?:\s|,|\()", t)
    if m:
        return _short(m.group(1), 12)
    return _short(t, 12)


def _kit_company_focus(
    out_dir: str,
    payload: DailySummaryPayload,
    market_data: Dict[str, Any],
    articles: List[Dict[str, Any]],
    preferred_keywords: Optional[List[str]],
) -> Tuple[str, str]:
    date_line = payload.date_line or ""
    name = _company_display_name(articles)
    p1, p2, p3, p4 = [os.path.join(out_dir, f"page{i}.jpg") for i in range(1, 5)]

    base, img_used = load_reference_page1_photo(articles, preferred_keywords)
    p1_img = _apply_photo_bottom_gradient(base)
    if name == "엔비디아":
        lines = ["엔비디아,", "AI 시대의", "핵심 기업"]
    else:
        lines = [f"{name},", "지금 시장에서", "핵심 기업"]
    _draw_page1_titles(p1_img, lines, "오늘 장에서 주목할 흐름.", 1, "COMPANY", date_line)
    p1_img.save(os.path.join(out_dir, "page1.jpg"), quality=95)

    img2 = _page_base_dark()
    d2 = ImageDraw.Draw(img2)
    _draw_neon_vline(d2)
    _draw_header(d2, "PROFILE", date_line)
    d2.text((80, 200), "한눈에 보는 기업", fill=WHITE, font=_font(44, True))
    desc = str(articles[0].get("description", "") or "")[:200] if articles else ""
    rows = [
        ("기업명", name),
        ("설립", "—"),
        ("본사", "—"),
        ("시가총액", "—"),
        ("주요 사업", _short(desc, 24) or "AI·반도체·데이터센터"),
    ]
    y = 290
    for k, v in rows:
        d2.text((100, y), k, fill=GRAY, font=_font(24, False))
        d2.text((100, y + 36), v, fill=WHITE, font=_font(30, True))
        y += 92
    _draw_footer(d2, 2)
    img2.save(os.path.join(out_dir, "page2.jpg"), quality=95)

    img3 = _page_base_dark()
    d3 = ImageDraw.Draw(img3)
    _draw_neon_vline(d3)
    _draw_header(d3, "WHY", date_line)
    d3.text((80, 200), "왜 중요한가?", fill=WHITE, font=_font(44, True))
    why = [
        "AI 시대 핵심 인프라",
        "데이터센터 수요 증가",
        "시장 기대감 집중",
    ]
    y = 300
    for ln in why:
        d3.text((100, y), "· " + ln, fill=WHITE, font=_font(32, False))
        y += 68
    _draw_footer(d3, 3)
    img3.save(os.path.join(out_dir, "page3.jpg"), quality=95)

    img4 = _page_base_dark()
    d4 = ImageDraw.Draw(img4)
    _draw_neon_vline(d4)
    _draw_header(d4, "AHEAD", date_line)
    d4.text((80, 200), "앞으로 주목할 포인트", fill=WHITE, font=_font(38, True))
    chk = ["실적", "가이던스", "규제", "경쟁사", "수요"]
    hkey = int(hashlib.md5((name + date_line).encode("utf-8")).hexdigest(), 16)
    picks = [chk[(hkey + i) % len(chk)] for i in range(3)]
    y = 300
    for i, it in enumerate(picks, 1):
        d4.text((100, y), f"{i}.", fill=NEON, font=_font(30, True))
        d4.text((160, y), it, fill=WHITE, font=_font(30, True))
        y += 70
    _draw_focus_box(d4, "CHECK", "AI 인프라 흐름이 이어지는지 확인", H - 260)
    _draw_footer(d4, 4)
    img4.save(os.path.join(out_dir, "page4.jpg"), quality=95)

    return f"{name} 기업 포커스", img_used


def _macro_page1_lines(articles: List[Dict[str, Any]], sector_mode: bool) -> Tuple[List[str], str]:
    blob = " ".join(str(a.get("title", "")) for a in articles[:5])
    if sector_mode:
        return ["반도체·AI 흐름,", "오늘 시장", "한눈에 정리"], "섹터 테마가 자금을 잡는다."
    if any(k in blob for k in ("유가", "원유", "oil", "OPEC")):
        return ["국제유가 급등,", "에너지 시장", "긴장감 확대"], "에너지 값이 물가를 밀어붙인다."
    if any(k in blob.lower() for k in ("금리", "fed", "cpi")):
        return ["금리·물가 이슈,", "시장 변동성", "확대 구간"], "발표 전후로 자금이 빠르게 움직인다."
    t = str(articles[0].get("title", "")) if articles else "핵심 경제 이슈"
    t = _short(t, 14)
    return [f"{t},", "오늘 시장", "핵심 이슈"], "뉴스보다 먼저 움직이는 흐름."


def _kit_macro_issue(
    out_dir: str,
    payload: DailySummaryPayload,
    market_data: Dict[str, Any],
    articles: List[Dict[str, Any]],
    preferred_keywords: Optional[List[str]],
    sector_mode: bool,
) -> Tuple[str, str]:
    date_line = payload.date_line or ""
    p1, p2, p3, p4 = [os.path.join(out_dir, f"page{i}.jpg") for i in range(1, 5)]

    base, img_used = load_reference_page1_photo(articles, preferred_keywords)
    p1_img = _apply_photo_bottom_gradient(base)
    big, sub = _macro_page1_lines(articles, sector_mode)
    _draw_page1_titles(p1_img, big, sub, 1, "MACRO ISSUE" if not sector_mode else "SECTOR", date_line)
    p1_img.save(p1, quality=95)

    bullets = _top_news_bullets_local(articles, 3)
    img2 = _page_base_dark()
    d2 = ImageDraw.Draw(img2)
    _draw_neon_vline(d2)
    _draw_header(d2, "WHAT HAPPENED", date_line)
    d2.text((80, 200), "무슨 일이 있었나?", fill=WHITE, font=_font(40, True))
    y = 300
    for ln in bullets:
        d2.text((100, y), "· " + _short(ln, 32), fill=WHITE, font=_font(30, False))
        y += 76
    _draw_footer(d2, 2)
    img2.save(p2, quality=95)

    img3 = _page_base_dark()
    d3 = ImageDraw.Draw(img3)
    _draw_neon_vline(d3)
    _draw_header(d3, "IMPACT", date_line)
    d3.text((80, 200), "시장에 미치는 영향", fill=WHITE, font=_font(38, True))
    impact = ["유가·에너지 비용", "물가 압력", "관련주 수혜"]
    y = 300
    for ln in impact:
        d3.text((100, y), "· " + ln, fill=WHITE, font=_font(32, False))
        y += 72
    _draw_footer(d3, 3)
    img3.save(p3, quality=95)

    img4 = _page_base_dark()
    d4 = ImageDraw.Draw(img4)
    _draw_neon_vline(d4)
    _draw_header(d4, "NEXT", date_line)
    d4.text((80, 200), "앞으로 체크 포인트", fill=WHITE, font=_font(40, True))
    chk = ["유가 방향", "환율 반응", "금리 민감주"]
    y = 300
    for i, it in enumerate(chk, 1):
        d4.text((100, y), f"{i}.", fill=NEON, font=_font(30, True))
        d4.text((160, y), it, fill=WHITE, font=_font(30, True))
        y += 70
    _draw_focus_box(d4, "NEXT", "유가 흐름이 인플레 방향 결정", H - 260)
    _draw_footer(d4, 4)
    img4.save(p4, quality=95)

    return "핵심 경제 이슈 요약", img_used


def _top_news_bullets_local(articles: List[Dict[str, Any]], k: int) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for a in articles:
        title = str(a.get("title", "")).strip()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(_short(title, 36))
        if len(out) >= k:
            break
    while len(out) < k:
        out.append("후속 헤드라인·수급 반응 확인")
    return out[:k]


def build_carousel_caption_text(
    payload: DailySummaryPayload,
    hook_headline: str,
    articles: List[Dict[str, Any]],
    cover_line1: str = "",
    cover_line2: str = "",
) -> str:
    lines = [
        hook_headline,
        "",
        _short(payload.flow_line or "시장 핵심만 정리.", 80),
        "",
        "#경제 #시장요약 #jadonnam",
    ]
    return "\n".join(lines)


def generate_money_flow_carousel(
    out_dir: str,
    payload: DailySummaryPayload,
    articles: List[Dict[str, Any]],
    content_mode: str,
    preferred_keywords: Optional[List[str]] = None,
    market_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    mode = (content_mode or "macro_issue").strip().lower()
    md = market_data if isinstance(market_data, dict) else {}

    if mode == "korea_close":
        hook, img_u = _kit_korea_close(out_dir, payload, md, articles, preferred_keywords)
    elif mode == "us_preopen":
        hook, img_u = _kit_us_preopen(out_dir, payload, md, articles, preferred_keywords)
    elif mode == "company_focus":
        hook, img_u = _kit_company_focus(out_dir, payload, md, articles, preferred_keywords)
    elif mode == "sector_focus":
        hook, img_u = _kit_macro_issue(out_dir, payload, md, articles, preferred_keywords, sector_mode=True)
    else:
        hook, img_u = _kit_macro_issue(out_dir, payload, md, articles, preferred_keywords, sector_mode=False)

    p1 = os.path.join(out_dir, "page1.jpg")
    p2 = os.path.join(out_dir, "page2.jpg")
    p3 = os.path.join(out_dir, "page3.jpg")
    p4 = os.path.join(out_dir, "page4.jpg")
    page_paths = [p1, p2, p3, p4]

    preview_path = ""
    if (os.getenv("DEBUG_PREVIEW") or "").strip().lower() == "true":
        prev = os.path.join(out_dir, "carousel_preview.jpg")
        try:
            _render_debug_preview(prev, page_paths)
            preview_path = prev
        except Exception as e:
            print(f"[money_flow] preview failed: {repr(e)}")
    else:
        try:
            pprev = os.path.join(out_dir, "carousel_preview.jpg")
            if os.path.exists(pprev):
                os.remove(pprev)
        except OSError:
            pass

    print(f"[money_flow] reference_cards wrote {page_paths}")
    return {
        "page_paths": page_paths,
        "preview_path": preview_path,
        "hook_headline": hook,
        "cover_line1": "",
        "cover_line2": "",
        "brand_line": BRAND_LINE,
        "brand_name": BRAND_NAME,
        "signature_line": SIGNATURE_PRIMARY,
        "image_priority_used": img_u,
    }


def _render_debug_preview(out_path: str, page_paths: List[str]) -> None:
    tw, th = W // 2, H // 2
    canvas = Image.new("RGB", (W, H), BG)
    for i, p in enumerate(page_paths[:4]):
        try:
            im = Image.open(p).convert("RGB").resize((tw, th), _RESAMPLE)
        except Exception:
            im = Image.new("RGB", (tw, th), BG)
        x = (i % 2) * tw
        y = (i // 2) * th
        canvas.paste(im, (x, y))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, H // 2 - 1, W, H // 2 + 1), fill=(24, 28, 34))
    d.rectangle((W // 2 - 1, 0, W // 2 + 1, H), fill=(24, 28, 34))
    d.text((48, H - 52), "DEBUG_PREVIEW", fill=GRAY, font=_font(16, False))
    canvas.save(out_path, quality=90)
