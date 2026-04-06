import requests
from datetime import datetime, timezone

def get_polymarket_markets():
    url = "https://gamma-api.polymarket.com/markets"
    params = {
        "limit": 50,
        "active": "true",
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false"
    }

    try:
        res = requests.get(url, params=params, timeout=20)
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print("Polymarket 호출 실패:", e)
        return []

def safe_float(value):
    try:
        return float(value)
    except:
        return None

def parse_yes_price(market):
    outcome_prices = market.get("outcomePrices")
    if outcome_prices:
        if isinstance(outcome_prices, list) and len(outcome_prices) > 0:
            price = safe_float(outcome_prices[0])
            if price is not None:
                return price
        elif isinstance(outcome_prices, str):
            cleaned = outcome_prices.replace("[", "").replace("]", "").split(",")
            if cleaned and len(cleaned) > 0:
                price = safe_float(cleaned[0].strip())
                if price is not None:
                    return price

    prices = market.get("prices")
    if prices:
        if isinstance(prices, list) and len(prices) > 0:
            price = safe_float(prices[0])
            if price is not None:
                return price

    for key in ["lastTradePrice", "bestAsk", "bestBid"]:
        price = safe_float(market.get(key))
        if price is not None:
            return price

    return None

def parse_volume(market):
    for key in ["volume24hr", "volume", "liquidity"]:
        val = safe_float(market.get(key))
        if val is not None:
            return val
    return 0

def is_expired(end_date):
    if not end_date:
        return False
    try:
        dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return dt <= now
    except:
        return False

def is_market_valid(market):
    # inactive / closed 제외
    if market.get("closed") is True:
        return False

    active = market.get("active")
    if active is False:
        return False

    # 마감 지났으면 제외
    end_date = market.get("endDate") or market.get("end_date")
    if is_expired(end_date):
        return False

    # 확률이 너무 끝에 붙은 시장 제외
    yes_price = parse_yes_price(market)
    if yes_price is not None:
       if yes_price >= 0.95 or yes_price <= 0.05:
            return False

    # 질문 자체가 이상하면 제외
    question = (market.get("question") or "").strip()
    if not question:
        return False

    return True

def filter_valid_markets(markets):
    filtered = [m for m in markets if is_market_valid(m)]
    return filtered

def parse_best_market(markets):
    valid_markets = filter_valid_markets(markets)

    if not valid_markets:
        return {
            "question": "폴리마켓 주요 시장 없음",
            "volume": 0,
            "yes_price": None,
            "end_date": None
        }

    best = valid_markets[0]

    question = best.get("question", "질문 없음")
    volume = parse_volume(best)
    yes_price = parse_yes_price(best)
    end_date = best.get("endDate") or best.get("end_date")

    return {
        "question": question,
        "volume": volume,
        "yes_price": yes_price,
        "end_date": end_date
    }