import os
from typing import Any, Dict, List

import requests

DEFAULT_URL = os.getenv("POLYMARKET_API_URL") or "https://gamma-api.polymarket.com/markets"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def get_polymarket_markets(limit: int = 60) -> List[Dict[str, Any]]:
    params = {
        "limit": min(max(limit, 1), 100),
        "active": "true",
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false",
    }
    try:
        res = requests.get(DEFAULT_URL, params=params, timeout=20)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print("[polymarket] fetch failed:", repr(e))
        return []

    markets: List[Dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        question = item.get("question") or item.get("title") or ""
        yes_price = (
            item.get("lastTradePrice")
            or item.get("yesPrice")
            or item.get("outcomes", [{}])[0].get("price") if isinstance(item.get("outcomes"), list) and item.get("outcomes") else 0
        )
        market = {
            "question": question,
            "volume24hr": _as_float(item.get("volume24hr") or item.get("volume") or 0),
            "yes_price": _as_float(yes_price),
            "end_date": item.get("endDate") or item.get("end_date") or "",
            "slug": item.get("slug") or "",
        }
        if question:
            markets.append(market)
    return markets
