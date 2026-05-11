from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def _get(url: str, params: Optional[Dict[str, Any]] = None, timeout: int = 12) -> str:
    res = requests.get(url, params=params or {}, headers=_HEADERS, timeout=timeout)
    res.raise_for_status()
    return res.text


def _to_float(text: str) -> Optional[float]:
    if text is None:
        return None
    s = re.sub(r"[^\d\.\-+]", "", str(text))
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _extract_first(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text, re.I | re.S)
    return m.group(1).strip() if m else None


def _parse_naver_index(code: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": None, "change_pct": None}
    try:
        html = _get("https://finance.naver.com/sise/sise_index.naver", params={"code": code})
        now_v = _extract_first(r'id="now_value"[^>]*>\s*([\d,\.]+)\s*<', html)
        pct = _extract_first(r'([-+]?\d+(?:\.\d+)?)\s*%', html)
        out["value"] = _to_float(now_v) if now_v else None
        out["change_pct"] = _to_float(pct) if pct else None
    except Exception as e:
        print(f"[korea_data] index({code}) failed: {repr(e)}")
    return out


def _parse_usdkrw() -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": None, "change_pct": None}
    try:
        html = _get(
            "https://finance.naver.com/marketindex/exchangeDetail.naver",
            params={"marketindexCd": "FX_USDKRW"},
        )
        val = _extract_first(r'<span class="value">\s*([\d,\.]+)\s*</span>', html)
        pct = _extract_first(r'([-+]?\d+(?:\.\d+)?)\s*%', html)
        out["value"] = _to_float(val) if val else None
        out["change_pct"] = _to_float(pct) if pct else None
    except Exception as e:
        print(f"[korea_data] usdkrw failed: {repr(e)}")
    return out


def _parse_top_traded() -> List[str]:
    try:
        html = _get("https://finance.naver.com/sise/sise_quant.naver")
        # 국내 거래량/거래대금 상위 페이지에서 종목명 anchor 추출
        names = re.findall(r'/item/main\.naver\?code=\d+"\s*class="tltle">([^<]+)</a>', html)
        out: List[str] = []
        seen = set()
        for n in names:
            s = str(n).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= 5:
                break
        return out
    except Exception as e:
        print(f"[korea_data] top_traded failed: {repr(e)}")
        return []


def _parse_top_sectors() -> List[str]:
    try:
        html = _get("https://finance.naver.com/sise/sise_group.naver?type=upjong")
        # 업종명 추출
        names = re.findall(r'sise_group_detail\.naver\?type=upjong&no=\d+">([^<]+)</a>', html)
        out: List[str] = []
        seen = set()
        for n in names:
            s = str(n).strip()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= 5:
                break
        return out
    except Exception as e:
        print(f"[korea_data] top_sectors failed: {repr(e)}")
        return []


def _parse_investor_flows() -> Dict[str, str]:
    """
    외국인/기관/개인 수급.
    페이지 구조가 자주 바뀌므로 보수적으로 파싱하고 실패 시 빈 dict 반환.
    """
    try:
        html = _get("https://finance.naver.com/sise/sise_investor_sum.naver?sosok=0")
        # 최근 행에서 개인/외국인/기관 순매수 금액 유사 패턴 추출
        row = _extract_first(r'<tr[^>]*onmouseover="mouseOver\(this\)"[^>]*>(.*?)</tr>', html)
        if not row:
            return {}
        nums = re.findall(r'class="tah[^"]*">\s*([\-+]?[\d,]+)\s*</td>', row)
        if len(nums) < 4:
            return {}
        # 페이지 구조에 따라 인덱스가 달라질 수 있어 끝 3개 사용
        last3 = nums[-3:]
        return {
            "foreign": f"{last3[0]}",
            "institution": f"{last3[1]}",
            "retail": f"{last3[2]}",
        }
    except Exception as e:
        print(f"[korea_data] flows failed: {repr(e)}")
        return {}


def fetch_korea_market_data() -> Dict[str, Any]:
    """
    국내장 우선 데이터 번들.
    실패해도 예외를 밖으로 던지지 않음.
    """
    try:
        kospi = _parse_naver_index("KOSPI")
    except Exception:
        kospi = {"value": None, "change_pct": None}
    try:
        kosdaq = _parse_naver_index("KOSDAQ")
    except Exception:
        kosdaq = {"value": None, "change_pct": None}
    try:
        usdkrw = _parse_usdkrw()
    except Exception:
        usdkrw = {"value": None, "change_pct": None}
    try:
        flows = _parse_investor_flows()
    except Exception:
        flows = {}
    try:
        top_traded = _parse_top_traded()
    except Exception:
        top_traded = []
    try:
        top_sectors = _parse_top_sectors()
    except Exception:
        top_sectors = []

    return {
        "kospi": kospi,
        "kosdaq": kosdaq,
        "usdkrw": usdkrw,
        "flows": flows,
        "top_traded": top_traded,
        "top_sectors": top_sectors,
    }

