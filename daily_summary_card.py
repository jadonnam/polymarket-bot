from __future__ import annotations

import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import requests
from PIL import Image, ImageDraw, ImageFont

from market_layout_system import DEFAULT_MARKET_JPG, ensure_fallback_assets, log_pil_open

W, H = 1080, 1350

try:
    _RESAMPLE = Image.Resampling.LANCZOS
except AttributeError:
    _RESAMPLE = Image.LANCZOS

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


@dataclass
class DailySummaryPayload:
    date_line: str
    title: str
    news_lines: List[str]
    number_lines: List[str]
    checkpoint: str


def _font(size: int, bold: bool = True) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
    name = "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    try:
        return ImageFont.truetype(os.path.join("fonts", name), size)
    except Exception:
        return ImageFont.load_default()


def _fetch_image(url: str) -> Optional[Image.Image]:
    if not url.strip():
        return None
    try:
        res = requests.get(url, timeout=25, headers=_HTTP_HEADERS)
        res.raise_for_status()
        img = Image.open(BytesIO(res.content)).convert("RGB")
        log_pil_open(img, "daily_summary url")
        return img
    except Exception as e:
        print(f"[daily_summary] background url failed: {repr(e)}")
        return None


def _cover_background(img: Image.Image) -> Image.Image:
    src = img.convert("RGB")
    scale = max(W / max(1, src.width), H / max(1, src.height))
    nw, nh = int(src.width * scale), int(src.height * scale)
    resized = src.resize((nw, nh), _RESAMPLE)
    x0 = max(0, (nw - W) // 2)
    y0 = max(0, (nh - H) // 2)
    return resized.crop((x0, y0, x0 + W, y0 + H))


def load_single_news_background(articles: List[Dict[str, Any]]) -> Image.Image:
    """One real-news style image: first successful article image, else fixed fallback (no random deck)."""
    ensure_fallback_assets()
    for a in articles[:12]:
        url = str(a.get("urlToImage") or "").strip()
        if not url:
            continue
        bg = _fetch_image(url)
        if bg is not None:
            print(f"[daily_summary] background source=url")
            return _cover_background(bg)

    p = DEFAULT_MARKET_JPG
    if os.path.exists(p):
        bg = Image.open(p).convert("RGB")
        log_pil_open(bg, "daily_summary fallback")
        print(f"[daily_summary] background source=fallback path={p}")
        return _cover_background(bg)

    ensure_fallback_assets()
    bg = Image.open(DEFAULT_MARKET_JPG).convert("RGB")
    return _cover_background(bg)


def _shorten(s: str, n: int) -> str:
    t = re.sub(r"\s+", " ", str(s or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _top_news_bullets(articles: List[Dict[str, Any]], k: int = 3) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for a in articles:
        title = str(a.get("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        out.append(_shorten(title, 46))
        if len(out) >= k:
            break
    while len(out) < k:
        out.append("뉴스 데이터 수집 중 · 흐름 확인")
    return out[:k]


_num_pat = re.compile(
    r"(?:[+-]?\d{1,4}(?:\.\d+)?)\s*%|(?:\$[\d,]+(?:\.\d+)?)|(?:\b\d{1,2}\.\d{1,2}\s*%\s*(?:yield|yields)?)",
    re.I,
)


def _number_lines_from_articles(articles: List[Dict[str, Any]], max_lines: int = 4) -> List[str]:
    blob = " ".join(
        str(a.get("title") or "") + " " + str(a.get("description") or "")
        for a in articles[:10]
    )
    found: List[str] = []
    for m in _num_pat.finditer(blob):
        snippet = m.group(0).strip()
        if snippet and snippet not in found:
            found.append(snippet)
        if len(found) >= max_lines:
            break

    if len(found) >= 2:
        return [f"· 헤드라인 내 수치: {x}" for x in found[:max_lines]]

    # 뉴스에 %·달러가 거의 없을 때: 한국어 라벨 고정 톤 (랜덤 아님)
    return [
        "· 나스닥·S&P500: 전일 종가·선물 흐름 증권앱 기준",
        "· 달러인덱스·미국채 금리: 지표 발표 캘린더와 동시 확인",
        "· 유가(WTI)·원유: 공급·지정학 헤드라인과 연동",
    ][:max_lines]


def _checkpoint_line(articles: List[Dict[str, Any]], rank_hints: List[str]) -> str:
    if rank_hints:
        return _shorten(f"체크: {rank_hints[0]} 변화가 오늘 레짐을 가늠하는 축", 52)
    t = str(articles[0].get("title") or "") if articles else ""
    if t:
        return _shorten("체크: 상기 이슈 후속 헤드라인·유동성 반응 속도", 52)
    return "체크: 장 전·장 중 매크로 발표·지정학 뉴스 플로우"


def build_daily_summary_payload(
    articles: List[Dict[str, Any]],
    rank_labels: Optional[List[str]] = None,
    date_line: str = "",
    title: str = "오늘의 시장 요약",
) -> DailySummaryPayload:
    rl = rank_labels or []
    return DailySummaryPayload(
        date_line=date_line or "",
        title=title,
        news_lines=_top_news_bullets(articles, 3),
        number_lines=_number_lines_from_articles(articles, 4),
        checkpoint=_checkpoint_line(articles, rl),
    )


def build_caption_text(payload: DailySummaryPayload) -> str:
    lines = [
        f"📌 {payload.date_line}",
        f"{payload.title}",
        "",
        "[핵심 뉴스]",
    ]
    for i, ln in enumerate(payload.news_lines, start=1):
        lines.append(f"{i}. {ln}")
    lines.extend(
        [
            "",
            "[시장 숫자 요약]",
            *payload.number_lines,
            "",
            "[체크포인트]",
            payload.checkpoint,
            "",
            "#경제 #시장요약 #매크로 #투자메모 #JADONNAM",
        ]
    )
    return "\n".join(lines)


def render_daily_summary_card(
    out_jpg_path: str,
    payload: DailySummaryPayload,
    articles: List[Dict[str, Any]],
) -> str:
    base = load_single_news_background(articles)
    img = base.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for y in range(H):
        alpha = int(28 + (y / H) * 55)
        od.line((0, y, W, y), fill=(0, 0, 0, min(120, alpha)))
    od.rectangle((0, 0, W, 220), fill=(0, 0, 0, 140))
    od.rectangle((0, H - 420, W, H), fill=(0, 0, 0, 175))
    img = Image.alpha_composite(img, overlay).convert("RGB")
    d = ImageDraw.Draw(img)

    d.text((40, 36), "JADONNAM", fill=(186, 194, 206), font=_font(22, False))
    d.text((40, 78), payload.date_line, fill=(210, 218, 228), font=_font(24, False))
    d.text((40, 118), payload.title, fill=(247, 249, 252), font=_font(48, True))

    y = 230
    d.text((40, y), "핵심 뉴스", fill=(160, 172, 188), font=_font(22, True))
    y += 42
    for ln in payload.news_lines:
        body = f"· {ln}"
        d.text((52, y), body, fill=(250, 251, 253), font=_font(30, True))
        y += 54

    y += 28
    d.text((40, y), "시장 숫자 요약", fill=(160, 172, 188), font=_font(22, True))
    y += 40
    for ln in payload.number_lines:
        d.text((52, y), ln, fill=(230, 236, 242), font=_font(26, False))
        y += 40

    y += 20
    d.line((40, y, W - 40, y), fill=(80, 92, 112), width=2)
    y += 28
    d.text((40, y), "체크포인트", fill=(160, 172, 188), font=_font(22, True))
    y += 40
    d.text((52, y), payload.checkpoint, fill=(231, 220, 140), font=_font(28, True))

    os.makedirs(os.path.dirname(out_jpg_path) or ".", exist_ok=True)
    img.save(out_jpg_path, quality=95)
    print(f"[daily_summary] wrote {out_jpg_path}")
    return out_jpg_path


def write_caption_file(path: str, payload: DailySummaryPayload) -> str:
    txt = build_caption_text(payload)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[daily_summary] caption txt: {path}")
    return path
