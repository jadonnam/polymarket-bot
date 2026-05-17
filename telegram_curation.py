from __future__ import annotations

import os
import re
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests
from PIL import Image

from daily_summary_card import DailySummaryPayload
from desk_briefing import build_desk_briefing_text

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
}

_IMAGE_PRIORITY = [
    "반도체",
    "하이닉스",
    "삼성전자",
    "데이터센터",
    "nvidia",
    "semiconductor",
    "oil",
    "wti",
    "유가",
    "crude",
    "ai",
    "인프라",
    "전력",
    "금리",
    "fed",
    "cpi",
    "환율",
    "달러",
    "wall street",
    "뉴욕",
    "증시",
    "나스닥",
    "공장",
    "정유",
    "lng",
    "월가",
]


def _short(s: str, n: int) -> str:
    t = re.sub(r"\s+", " ", str(s or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _slash_date(date_line: str) -> str:
    m = re.search(r"(\d{4})\.(\d{1,2})\.(\d{1,2})", str(date_line or ""))
    if m:
        return f"{int(m.group(2))}/{int(m.group(3))}"
    return ""


def _fmt_pct(v: Any) -> str:
    try:
        x = float(v)
        sign = "+" if x > 0 else ""
        return f"{sign}{x:.2f}%"
    except Exception:
        return "-"


def _fmt_price(v: Any, digits: int = 2) -> str:
    try:
        return format(float(v), f",.{digits}f")
    except Exception:
        return "-"


def _quote(md: Dict[str, Any], key: str) -> Tuple[str, str]:
    q = md.get("quotes", {}) if isinstance(md, dict) else {}
    row = q.get(key, {}) if isinstance(q, dict) else {}
    return _fmt_price(row.get("price")), _fmt_pct(row.get("chg_pct"))


def _fmt_flow_cell(raw: str) -> str:
    s = str(raw or "").strip()
    return s if s else "집계 확인"


def _flow_word(flows: Dict[str, str]) -> str:
    raw = str(flows.get("foreign", "")).replace(",", "").replace(" ", "")
    if not raw or raw == "-":
        return "외국인 흐름 확인 중"
    try:
        v = float(re.sub(r"[^\d.\-+]", "", raw))
        if v > 0:
            return "외국인 순매수 전환"
        if v < 0:
            return "외국인 순매도 우위"
    except Exception:
        pass
    return "외국인 수급 변동"


def _top_names(trading: List[str], k: int = 2) -> str:
    out: List[str] = []
    for x in trading or []:
        raw = str(x).strip()
        raw = re.sub(r"^\d{6}\s+", "", raw)
        raw = re.sub(r"^[A-Z]{1,5}\s+", "", raw)
        name = raw.split()[0] if raw else ""
        if name and name not in out and "데이터" not in name:
            out.append(name[:12])
        if len(out) >= k:
            break
    return "·".join(out) if out else "대형주·반도체"


def _sector_line(sectors: List[str]) -> str:
    raw = [str(s).strip() for s in (sectors or [])[:2] if str(s).strip()]
    if len(raw) >= 2:
        return f"{_short(raw[0], 10)}·{_short(raw[1], 10)}"
    if raw:
        return f"{_short(raw[0], 10)}·전력"
    return "반도체·전력"


def _korea_line6_oil(c_w: str, p_w: str) -> str:
    try:
        x = float(str(c_w).replace("%", "").replace("+", ""))
        if x > 0.05:
            return "6. 유가 상승 압력 지속"
        if x < -0.05:
            return "6. 유가 하락 쪽 흐름"
    except Exception:
        pass
    if p_w != "-" and p_w:
        return f"6. WTI {p_w}달러 ({c_w})"
    return "6. 유가 흐름 점검"


def _dxy_word(md: Dict[str, Any]) -> str:
    _, c = _quote(md, "DXY")
    try:
        x = float(str(c).replace("%", "").replace("+", ""))
        if x < -0.02:
            return "약세"
        if x > 0.02:
            return "강세"
    except Exception:
        pass
    return "흐름 확인"


def _us_line7_sectors(blob: str, sect: List[str]) -> str:
    if "nvidia" in blob or "엔비디아" in blob:
        return "7. 주목 섹터: 반도체·AI"
    s = _sector_line(sect)
    return f"7. 주목 섹터: {s}"


def _trading_top_line(ttop: List[str]) -> str:
    parts: List[str] = []
    for x in (ttop or [])[:3]:
        t = _short(re.sub(r"^\d{6}\s*", "", str(x).strip()), 18)
        if t and "데이터" not in t:
            parts.append(t)
    if not parts:
        return "5. 거래대금 상위: 대형주 중심"
    return "5. 거래대금 상위: " + ", ".join(parts)


def _hook_one_line(summary_mode: str, payload: DailySummaryPayload, sect: List[str]) -> str:
    if summary_mode == "us_preopen":
        return "오늘 밤 시장이 보는 핵심"
    if summary_mode == "korea_close":
        base = str(payload.flow_line or "").strip()
        if 8 <= len(base) <= 48 and ("돈" in base or "흐름" in base):
            return _short(base, 48)
        return "돈은 어디로 움직이는 중"
    base = str(payload.flow_line or "").strip()
    return _short(base, 48) if base else "돈은 어디로 움직이는 중"


def _article_blob(articles: List[Dict[str, Any]], n: int = 8) -> str:
    parts = []
    for a in articles[:n]:
        parts.append(str(a.get("title", "")))
        parts.append(str(a.get("description", "")))
    return " ".join(parts).lower()


def _score_article_image(a: Dict[str, Any]) -> int:
    t = f"{a.get('title', '')} {a.get('description', '')}".lower()
    s = 0
    for kw in _IMAGE_PRIORITY:
        if kw.lower() in t:
            s += 6
    if str(a.get("urlToImage") or "").strip():
        s += 4
    return s


def pick_curated_image_urls(articles: List[Dict[str, Any]], lo: int = 3, hi: int = 5) -> List[str]:
    ranked = sorted(articles, key=lambda x: -_score_article_image(x))
    seen: set[str] = set()
    out: List[str] = []
    for a in ranked + list(articles):
        u = str(a.get("urlToImage") or "").strip()
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= hi:
            break
    return out[:hi]


def download_curated_images(urls: List[str], out_dir: str) -> List[str]:
    os.makedirs(out_dir, exist_ok=True)
    paths: List[str] = []
    for i, url in enumerate(urls):
        path = os.path.join(out_dir, f"_cur_{i}.jpg")
        try:
            r = requests.get(url, timeout=22, headers=_HTTP_HEADERS)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGB")
            img.save(path, quality=88)
            paths.append(path)
        except Exception as e:
            print(f"[briefing_images] download failed: {repr(e)}")
    return paths


def clear_curation_cache(out_dir: str) -> None:
    if not os.path.isdir(out_dir):
        return
    for name in os.listdir(out_dir):
        if name.startswith("_cur_"):
            try:
                os.remove(os.path.join(out_dir, name))
            except OSError:
                pass


def build_market_briefing_text(
    summary_mode: str,
    payload: DailySummaryPayload,
    market_data: Dict[str, Any],
    articles: List[Dict[str, Any]],
) -> str:
    """자돈남 DESK 형식 (① 헤드 · ② 해석 · ③ 볼 것). summary_mode는 톤 힌트용."""
    _ = summary_mode, payload
    return build_desk_briefing_text(
        articles=articles,
        market_data=market_data,
        lead_article=articles[0] if articles else None,
    )


def build_market_curation_text(
    summary_mode: str,
    payload: DailySummaryPayload,
    market_data: Dict[str, Any],
    articles: List[Dict[str, Any]],
) -> str:
    return build_market_briefing_text(summary_mode, payload, market_data, articles)
