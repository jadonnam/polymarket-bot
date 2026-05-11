from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import requests
from PIL import Image, ImageDraw, ImageFont

from korea_market_data import fetch_korea_market_data
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

_YAHOO_QUOTE_URL = "https://query1.finance.yahoo.com/v7/finance/quote"
_YAHOO_SCREENER_URL = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"

_SYMBOLS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "USDKRW": "KRW=X",
    "US10Y": "^TNX",
    "WTI": "CL=F",
    "NASDAQ": "^IXIC",
    "SP500": "^GSPC",
}


@dataclass
class DailySummaryPayload:
    date_line: str
    title: str
    news_lines: List[str]
    number_lines: List[str]
    checkpoint: str
    hook_line: str = ""
    why_line: str = ""
    flow_line: str = ""
    summary_line: str = ""
    market_snapshot: Dict[str, Dict[str, Any]] | None = None
    trading_top5: List[str] | None = None
    sector_top5: List[str] | None = None
    content_mode: str = ""
    data_source_status: Dict[str, str] | None = None


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


def _has_keywords(text: str, keywords: List[str]) -> bool:
    low = str(text or "").lower()
    return any(k.lower() in low for k in keywords)


def load_single_news_background(
    articles: List[Dict[str, Any]],
    preferred_keywords: Optional[List[str]] = None,
) -> Image.Image:
    """One real-news style image, keyword-prioritized + deterministic fallback."""
    ensure_fallback_assets()
    keywords = preferred_keywords or []
    ordered: List[Dict[str, Any]] = []
    if keywords:
        preferred = []
        normal = []
        for a in articles[:20]:
            text = f"{a.get('title', '')} {a.get('description', '')}"
            if _has_keywords(text, keywords):
                preferred.append(a)
            else:
                normal.append(a)
        ordered = preferred + normal
    else:
        ordered = articles[:20]

    for a in ordered:
        url = str(a.get("urlToImage") or "").strip()
        if not url:
            continue
        bg = _fetch_image(url)
        if bg is not None:
            print("[daily_summary] background source=url")
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


def _fnum(v: Any, digits: int = 2) -> str:
    try:
        n = float(v)
    except Exception:
        return "-"
    return f"{n:.{digits}f}"


def _fchg(v: Any) -> str:
    try:
        n = float(v)
    except Exception:
        return "-"
    sign = "+" if n > 0 else ""
    return f"{sign}{n:.2f}%"


def _quote_price_ok(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    p = row.get("price")
    if p is None:
        return False
    s = _fnum(p, digits=4)
    return s != "-"


def _fetch_yahoo_quotes() -> Dict[str, Dict[str, Any]]:
    symbols = ",".join(_SYMBOLS.values())
    out: Dict[str, Dict[str, Any]] = {}
    try:
        res = requests.get(
            _YAHOO_QUOTE_URL,
            params={"symbols": symbols},
            timeout=15,
            headers=_HTTP_HEADERS,
        )
        res.raise_for_status()
        data = res.json()
        rows = data.get("quoteResponse", {}).get("result", []) or []
        by_symbol = {str(r.get("symbol", "")): r for r in rows}
        for key, symbol in _SYMBOLS.items():
            r = by_symbol.get(symbol, {})
            out[key] = {
                "price": r.get("regularMarketPrice"),
                "chg_pct": r.get("regularMarketChangePercent"),
                "name": r.get("shortName") or r.get("longName") or key,
            }
    except Exception as e:
        print(f"[market_api] yahoo quote failed: {repr(e)}")
    return out


def _is_dummy_trading_list(items: List[str]) -> bool:
    if not items:
        return True
    return str(items[0]).startswith("거래대금 TOP: 데이터")


def _fetch_most_actives_top5() -> List[str]:
    fallback = [
        "거래대금 TOP: 데이터 수집 중",
        "상위 종목: 반도체/AI 중심",
    ]
    try:
        res = requests.get(
            _YAHOO_SCREENER_URL,
            params={"formatted": "true", "count": 8, "scrIds": "most_actives"},
            timeout=15,
            headers=_HTTP_HEADERS,
        )
        res.raise_for_status()
        data = res.json()
        quotes = (
            data.get("finance", {})
            .get("result", [{}])[0]
            .get("quotes", [])
        )
        out: List[str] = []
        for q in quotes[:5]:
            symbol = str(q.get("symbol", "")).upper()
            name = str(q.get("shortName") or q.get("longName") or symbol)
            if not symbol:
                continue
            out.append(_shorten(f"{symbol} {name}", 26))
        return out or fallback
    except Exception as e:
        print(f"[market_api] most_actives failed: {repr(e)}")
        return fallback


def _is_dummy_sector_list(items: List[str]) -> bool:
    if not items:
        return True
    dummy = {"AI·반도체", "에너지", "전력 인프라", "빅테크", "방산·원자재"}
    return str(items[0]).strip() in dummy


def _fetch_sector_top5() -> List[str]:
    fallback = [
        "AI·반도체",
        "에너지",
        "전력 인프라",
        "빅테크",
        "방산·원자재",
    ]
    try:
        res = requests.get(
            _YAHOO_SCREENER_URL,
            params={"formatted": "true", "count": 30, "scrIds": "day_gainers"},
            timeout=15,
            headers=_HTTP_HEADERS,
        )
        res.raise_for_status()
        data = res.json()
        quotes = (
            data.get("finance", {})
            .get("result", [{}])[0]
            .get("quotes", [])
        )
        bucket: Dict[str, List[float]] = {}
        for q in quotes:
            sector = str(q.get("sector") or "").strip()
            chg = q.get("regularMarketChangePercent")
            if not sector:
                continue
            try:
                fv = float(chg)
            except Exception:
                continue
            bucket.setdefault(sector, []).append(fv)
        ranked = sorted(
            ((k, sum(v) / max(1, len(v))) for k, v in bucket.items()),
            key=lambda x: x[1],
            reverse=True,
        )[:5]
        out = [_shorten(f"{name} {_fchg(avg)}", 28) for name, avg in ranked]
        return out or fallback
    except Exception as e:
        print(f"[market_api] sector_top failed: {repr(e)}")
        return fallback


def _log_market_data_sources(status: Dict[str, str]) -> None:
    try:
        for key in sorted(status.keys()):
            print(f"[market_data] {key}: {status[key]}")
    except Exception as e:
        print(f"[market_data] status log failed: {repr(e)}")


def fetch_market_data_bundle() -> Dict[str, Any]:
    status: Dict[str, str] = {}
    korea: Dict[str, Any] = {}
    try:
        korea = fetch_korea_market_data() or {}
    except Exception as e:
        print(f"[market_api] korea source failed: {repr(e)}")
        korea = {}

    quotes = _fetch_yahoo_quotes()

    def _merge_index(key_dom: str, quote_key: str) -> None:
        row_k = korea.get(key_dom, {}) if isinstance(korea, dict) else {}
        val = row_k.get("value") if isinstance(row_k, dict) else None
        if val is not None:
            quotes[quote_key] = {
                "price": val,
                "chg_pct": row_k.get("change_pct") if isinstance(row_k, dict) else None,
                "name": quote_key,
            }
            status[quote_key.upper()] = "domestic ok"
            return
        status[quote_key.upper()] = "domestic failed"
        yrow = quotes.get(quote_key, {})
        if _quote_price_ok(yrow):
            status[quote_key.upper()] = "domestic failed -> yahoo ok"
        else:
            status[quote_key.upper()] = "domestic failed -> fallback"

    _merge_index("kospi", "KOSPI")
    _merge_index("kosdaq", "KOSDAQ")
    _merge_index("usdkrw", "USDKRW")

    for yk in ("NASDAQ", "SP500", "US10Y", "WTI"):
        yrow = quotes.get(yk, {})
        if _quote_price_ok(yrow):
            status[yk] = "yahoo ok"
        else:
            status[yk] = "yahoo failed -> fallback"

    flows = korea.get("flows", {}) if isinstance(korea, dict) else {}
    if isinstance(flows, dict) and any(flows.get(k) for k in ("foreign", "institution", "retail")):
        status["flows"] = "domestic ok"
    else:
        status["flows"] = "domestic failed -> fallback"

    k_top = list(korea.get("top_traded", []) or []) if isinstance(korea, dict) else []
    k_sec = list(korea.get("top_sectors", []) or []) if isinstance(korea, dict) else []

    if len(k_top) >= 1:
        top5 = k_top[:5]
        status["top_traded"] = "domestic ok"
    else:
        y_top = _fetch_most_actives_top5()
        if not _is_dummy_trading_list(y_top):
            top5 = y_top
            status["top_traded"] = "domestic failed -> yahoo ok"
        else:
            top5 = y_top
            status["top_traded"] = "domestic failed -> fallback"

    if len(k_sec) >= 1:
        sectors = k_sec[:5]
        status["top_sectors"] = "domestic ok"
    else:
        y_sec = _fetch_sector_top5()
        if not _is_dummy_sector_list(y_sec):
            sectors = y_sec
            status["top_sectors"] = "domestic failed -> yahoo ok"
        else:
            sectors = y_sec
            status["top_sectors"] = "domestic failed -> fallback"

    _log_market_data_sources(status)
    return {
        "quotes": quotes,
        "korea": korea,
        "trading_top5": top5,
        "sector_top5": sectors,
        "data_source_status": status,
    }


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


def _number_lines_from_market(
    content_mode: str,
    market_data: Dict[str, Any],
    articles: List[Dict[str, Any]],
    max_lines: int = 4,
) -> List[str]:
    q = market_data.get("quotes", {}) if isinstance(market_data, dict) else {}

    def qline(label: str, key: str, digits: int = 2, unit: str = "") -> str:
        row = q.get(key, {}) if isinstance(q, dict) else {}
        price = _fnum(row.get("price"), digits)
        chg = _fchg(row.get("chg_pct"))
        return f"· {label} {price}{unit} ({chg})"

    if content_mode == "korea_close":
        k = market_data.get("korea", {}) if isinstance(market_data, dict) else {}
        flows = k.get("flows", {}) if isinstance(k, dict) else {}
        t = market_data.get("trading_top5", [])
        s = market_data.get("sector_top5", [])
        lines = [
            qline("KOSPI", "KOSPI", 2),
            qline("KOSDAQ", "KOSDAQ", 2),
            qline("USD/KRW", "USDKRW", 2),
        ]
        if flows and any(flows.get(k) for k in ("foreign", "institution", "retail")):
            f = str(flows.get("foreign", "-"))
            i = str(flows.get("institution", "-"))
            r = str(flows.get("retail", "-"))
            lines.append(_shorten(f"· 수급(외/기/개): {f} / {i} / {r}", 48))
        elif s:
            lines.append(_shorten(f"· 상승 섹터 TOP: {s[0]}", 46))
        else:
            t = market_data.get("trading_top5", [])
            if t:
                lines.append(_shorten(f"· 거래대금 TOP: {t[0]}", 46))
        return lines[:max_lines]

    if content_mode == "us_preopen":
        lines = [
            qline("NASDAQ", "NASDAQ", 2),
            qline("S&P500", "SP500", 2),
            qline("미국10년", "US10Y", 2, "%"),
            qline("WTI", "WTI", 2),
        ]
        return lines[:max_lines]

    if content_mode in ("company_focus", "sector_focus", "macro_issue"):
        lines = [
            qline("NASDAQ", "NASDAQ", 2),
            qline("USD/KRW", "USDKRW", 2),
            qline("미국10년", "US10Y", 2, "%"),
            qline("WTI", "WTI", 2),
        ]
        return lines[:max_lines]

    return _number_lines_from_articles(articles, max_lines=max_lines)


def _checkpoint_line(articles: List[Dict[str, Any]], rank_hints: List[str]) -> str:
    if rank_hints:
        return _shorten(f"체크: {rank_hints[0]} 변화가 오늘 레짐을 가늠하는 축", 52)
    t = str(articles[0].get("title") or "") if articles else ""
    if t:
        return _shorten("체크: 상기 이슈 후속 헤드라인·유동성 반응 속도", 52)
    return "체크: 장 전·장 중 매크로 발표·지정학 뉴스 플로우"


def _money_flow_line(articles: List[Dict[str, Any]]) -> str:
    text = " ".join(
        f"{a.get('title', '')} {a.get('description', '')}" for a in articles[:8]
    ).lower()
    if _has_keywords(text, ["ai", "chip", "nvidia", "semiconductor", "반도체"]):
        return "돈이 AI·반도체로 다시 몰리는 중."
    if _has_keywords(text, ["oil", "crude", "brent", "유가"]):
        return "원자재 쪽 변동성이 커지며 에너지로 자금 이동."
    if _has_keywords(text, ["yield", "rate", "fed", "금리"]):
        return "금리 민감주와 성장주 사이에서 자금 재배치."
    if _has_keywords(text, ["bitcoin", "btc", "crypto", "비트"]):
        return "리스크 선호 자금이 코인과 기술주로 이동."
    return "지금 시장 자금은 실적·현금흐름 강한 곳으로 이동."


def _money_flow_line_with_data(articles: List[Dict[str, Any]], market_data: Dict[str, Any]) -> str:
    base = _money_flow_line(articles)
    q = market_data.get("quotes", {}) if isinstance(market_data, dict) else {}
    try:
        nas = float((q.get("NASDAQ") or {}).get("chg_pct"))
    except Exception:
        nas = 0.0
    try:
        us10 = float((q.get("US10Y") or {}).get("chg_pct"))
    except Exception:
        us10 = 0.0
    if nas > 0 and us10 < 0:
        return "금리 부담이 줄며 성장주·AI로 자금이 재유입."
    if nas < 0 and us10 > 0:
        return "금리 압력으로 기술주에서 방어주로 일부 이동."
    korea = market_data.get("korea", {}) if isinstance(market_data, dict) else {}
    flows = korea.get("flows", {}) if isinstance(korea, dict) else {}
    f = str(flows.get("foreign", ""))
    i = str(flows.get("institution", ""))
    if f.startswith("+") and i.startswith("+"):
        return "외국인·기관 동시 순매수, 대형주 중심으로 자금 유입."
    if f.startswith("+"):
        return "외국인 자금이 반도체·대형주로 다시 들어오는 흐름."
    if i.startswith("+"):
        return "기관 수급이 받쳐주며 지수 하단이 단단해지는 구간."
    return base


def _title_for_mode(content_mode: str) -> str:
    mapping = {
        "korea_close": "한국장 마감 요약",
        "us_preopen": "미국장 시작 전 요약",
        "macro_issue": "핵심 경제 이슈",
        "company_focus": "기업 흐름 한 장 요약",
        "sector_focus": "섹터 흐름 한 장 요약",
    }
    return mapping.get(content_mode, "오늘의 시장 요약")


def _keywords_for_mode(content_mode: str) -> List[str]:
    mapping = {
        "korea_close": ["kospi", "kosdaq", "korea", "krw", "won", "한국"],
        "us_preopen": ["futures", "nasdaq", "s&p", "dxy", "yield", "wti"],
        "macro_issue": ["oil", "rate", "inflation", "ai", "china", "power"],
        "company_focus": ["nvidia", "tesla", "tsmc", "samsung", "aramco"],
        "sector_focus": ["sector", "ai", "semiconductor", "power", "robot", "nuclear"],
    }
    return mapping.get(content_mode, [])


def background_keywords_for_mode(content_mode: str) -> List[str]:
    return _keywords_for_mode((content_mode or "").strip().lower())


def _news_lines_for_mode(content_mode: str, articles: List[Dict[str, Any]]) -> List[str]:
    src = _top_news_bullets(articles, 5)
    if content_mode == "korea_close":
        return [
            _shorten(f"코스피/코스닥 흐름: {src[0]}", 44),
            _shorten(f"수급 포인트: {src[1]}", 44),
            _shorten(f"거래대금·섹터: {src[2]}", 44),
        ]
    if content_mode == "us_preopen":
        return [
            _shorten(f"미국 선물 흐름: {src[0]}", 44),
            _shorten(f"환율·금리 체크: {src[1]}", 44),
            _shorten(f"장 시작 변수: {src[2]}", 44),
        ]
    if content_mode == "company_focus":
        return [
            _shorten(f"기업이 하는 일: {src[0]}", 44),
            _shorten(f"최근 투자/뉴스: {src[1]}", 44),
            _shorten(f"시장 영향 포인트: {src[2]}", 44),
        ]
    if content_mode == "sector_focus":
        return [
            _shorten(f"왜 오르는가: {src[0]}", 44),
            _shorten(f"돈이 들어오는 이유: {src[1]}", 44),
            _shorten(f"다음 체크포인트: {src[2]}", 44),
        ]
    return [
        _shorten(f"헤드라인: {src[0]}", 44),
        _shorten(f"왜 중요한가: {src[1]}", 44),
        _shorten(f"돈 흐름: {src[2]}", 44),
    ]


def build_daily_summary_payload_auto(
    *,
    articles: List[Dict[str, Any]],
    rank_labels: Optional[List[str]] = None,
    date_line: str = "",
    content_mode: str = "macro_issue",
    market_data: Optional[Dict[str, Any]] = None,
) -> DailySummaryPayload:
    rl = rank_labels or []
    mode = (content_mode or "macro_issue").strip().lower()
    md = market_data or fetch_market_data_bundle()
    title = _title_for_mode(mode)
    news_lines = _news_lines_for_mode(mode, articles)
    number_lines = _number_lines_from_market(mode, md, articles, 4)
    checkpoint = _checkpoint_line(articles, rl)
    flow = _money_flow_line_with_data(articles, md)
    return DailySummaryPayload(
        date_line=date_line or "",
        title=title,
        news_lines=news_lines,
        number_lines=number_lines,
        checkpoint=checkpoint,
        hook_line=f"{title} 한 장 정리.",
        why_line="오늘 시장을 움직인 이유만 짧게 정리.",
        flow_line=flow,
        summary_line=f"핵심은 {checkpoint.replace('체크: ', '')}",
        market_snapshot=md.get("quotes", {}),
        trading_top5=md.get("trading_top5", []),
        sector_top5=md.get("sector_top5", []),
        content_mode=mode,
        data_source_status=dict(md.get("data_source_status") or {}),
    )


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
    hook = payload.hook_line or f"{payload.title} 한 장으로 끝."
    why = payload.why_line or "왜 중요한지부터 바로 잡아봄."
    flow = payload.flow_line or "돈이 어디로 움직이는지 같이 체크."
    summary = payload.summary_line or payload.checkpoint
    lines = [f"📌 {hook}", why, flow, summary]
    if payload.trading_top5:
        lines.append(f"거래대금 TOP: {', '.join(payload.trading_top5[:3])}")
    if payload.sector_top5:
        lines.append(f"상승 섹터 TOP: {', '.join(payload.sector_top5[:3])}")
    lines.extend(
        [
            "저장해두고 내일 장 전에 다시 보기.",
            "같이 보는 친구 태그해줘 👀",
            "",
            "#경제 #돈의흐름 #시장요약 #주식공부 #인사이트",
        ]
    )
    return "\n".join(lines)


def render_daily_summary_card(
    out_jpg_path: str,
    payload: DailySummaryPayload,
    articles: List[Dict[str, Any]],
    preferred_background_keywords: Optional[List[str]] = None,
) -> str:
    base = load_single_news_background(articles, preferred_background_keywords)
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
    if payload.trading_top5:
        tline = _shorten("거래대금 TOP5: " + ", ".join(payload.trading_top5[:5]), 66)
        d.text((40, y), tline, fill=(204, 214, 228), font=_font(20, False))
        y += 30
    if payload.sector_top5:
        sline = _shorten("상승 섹터 TOP5: " + ", ".join(payload.sector_top5[:5]), 66)
        d.text((40, y), sline, fill=(204, 214, 228), font=_font(20, False))
        y += 34
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


def write_debug_payload_json(
    path: str,
    *,
    content_mode: str,
    payload: DailySummaryPayload,
    caption: str,
    market_data: Dict[str, Any],
    extra_fields: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        news = list(payload.news_lines or [])
        headline = news[0] if news else ""
        data = {
            "content_mode": content_mode,
            "title": payload.title,
            "headline": headline,
            "number_lines": list(payload.number_lines or []),
            "money_flow_line": payload.flow_line,
            "top_traded": list(payload.trading_top5 or []),
            "top_sectors": list(payload.sector_top5 or []),
            "data_source_status": dict(market_data.get("data_source_status") or {}),
            "caption": caption,
        }
        if extra_fields:
            data.update(extra_fields)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[card_debug] wrote {path}")
    except Exception as e:
        print(f"[card_debug] debug_payload save failed: {repr(e)}")
