import requests
import json
import re
from datetime import datetime, timezone

API_URL = "https://gamma-api.polymarket.com/markets"

def parse_outcome_prices(raw):
    if raw is None:
        return []

    if isinstance(raw, list):
        result = []
        for x in raw:
            try:
                result.append(float(x))
            except:
                pass
        return result

    if isinstance(raw, str):
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                result = []
                for x in parsed:
                    try:
                        result.append(float(x))
                    except:
                        pass
                return result
        except:
            pass

        try:
            parts = raw.split(",")
            result = []
            for x in parts:
                x = x.strip().replace("[", "").replace("]", "").replace('"', "")
                if x:
                    result.append(float(x))
            return result
        except:
            pass

    return []

def parse_outcomes(raw):
    if raw is None:
        return []

    if isinstance(raw, list):
        return [str(x).strip() for x in raw]

    if isinstance(raw, str):
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed]
        except:
            pass

        return [x.strip().replace('"', "") for x in raw.replace("[", "").replace("]", "").split(",") if x.strip()]

    return []

def parse_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default

def pick_yes_price(market):
    prices = parse_outcome_prices(market.get("outcomePrices"))
    outcomes = [x.lower() for x in parse_outcomes(market.get("outcomes"))]

    if prices and outcomes and "yes" in outcomes:
        idx = outcomes.index("yes")
        if idx < len(prices):
            return prices[idx]

    if prices:
        return prices[0]

    return 0.0

def pick_volume(market):
    candidates = [
        market.get("volume24hr"),
        market.get("volume"),
        market.get("liquidity"),
        market.get("volumeNum"),
    ]

    for c in candidates:
        try:
            v = float(c)
            if v > 0:
                return v
        except:
            pass

    return 0.0

def pick_end_date(market):
    for key in ["endDate", "end_date", "resolutionDate", "closeTime", "closedTime"]:
        value = market.get(key)
        if value:
            return str(value)
    return ""

def parse_datetime_safe(value):
    if not value:
        return None

    text = str(value).strip()

    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    except:
        pass

    patterns = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in patterns:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except:
            pass

    return None

def is_market_resolved_or_closed(market):
    for key in ["closed", "resolved", "archived", "enableOrderBook"]:
        value = market.get(key)
        if isinstance(value, bool):
            if key in ["closed", "resolved", "archived"] and value is True:
                return True

    status_text = " ".join([
        str(market.get("status", "")),
        str(market.get("gameStatus", "")),
        str(market.get("marketStatus", "")),
    ]).lower()

    bad_words = ["resolved", "closed", "finalized", "ended", "settled", "archived"]
    if any(word in status_text for word in bad_words):
        return True

    return False

def question_has_expired_date(question):
    if not question:
        return False

    q = str(question).strip()

    m = re.search(r"by\s+([A-Z][a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?", q)
    if not m:
        return False

    month_name = m.group(1)
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else datetime.now(timezone.utc).year

    try:
        dt = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
        dt = dt.replace(tzinfo=timezone.utc)
        return dt < datetime.now(timezone.utc)
    except:
        return False

def is_market_expired(market):
    end_date = pick_end_date(market)
    dt = parse_datetime_safe(end_date)

    if dt is not None and dt < datetime.now(timezone.utc):
        return True

    question = str(market.get("question", ""))
    if question_has_expired_date(question):
        return True

    return False

def is_valid_market(market):
    if is_market_resolved_or_closed(market):
        return False

    if is_market_expired(market):
        return False

    question = str(market.get("question", "")).strip()
    if not question:
        return False

    yes_price = pick_yes_price(market)
    volume = pick_volume(market)

    if volume <= 0:
        return False

    if yes_price < 0 or yes_price > 1:
        return False

    if yes_price > 0.97 or yes_price < 0.03:
        return False

    return True

def market_score(market):
    yes_price = pick_yes_price(market)
    volume = pick_volume(market)
    question = str(market.get("question", "")).lower()

    score = 0
    score += min(volume / 100000, 300)

    if 0.05 < yes_price < 0.95:
        score += 40

    for word in ["iran", "war", "attack", "missile", "military", "troops", "trump", "bitcoin", "fed", "oil", "gold"]:
        if word in question:
            score += 15

    return score

def get_polymarket_markets(limit=50):
    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false"
    }

    res = requests.get(API_URL, params=params, timeout=20)
    res.raise_for_status()
    data = res.json()

    if not isinstance(data, list):
        return []

    valid_markets = [m for m in data if is_valid_market(m)]
    return valid_markets

def parse_best_market(markets):
    if not markets:
        raise Exception("No valid market data")

    ranked = sorted(markets, key=market_score, reverse=True)
    m = ranked[0]

    yes_price = pick_yes_price(m)
    volume = pick_volume(m)
    end_date = pick_end_date(m)

    return {
        "question": m.get("question", "Unknown Market"),
        "volume": volume,
        "yes_price": yes_price,
        "end_date": end_date,
        "description": m.get("description", "") or ""
    }

def classify_topic(title, description=""):
    text = f"{title} {description}".lower()

    if any(k in text for k in ["iran", "war", "military", "troops", "missile", "strike", "attack", "israel", "china", "taiwan"]):
        return "geopolitics"
    if any(k in text for k in ["trump", "election", "president", "white house", "campaign", "vote", "senate"]):
        return "politics"
    if any(k in text for k in ["fed", "inflation", "rate", "recession", "economy", "stocks", "oil", "gold"]):
        return "economy"
    if any(k in text for k in ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana"]):
        return "crypto"

    return "general"

def get_top_market():
    markets = get_polymarket_markets(limit=50)
    best = parse_best_market(markets)

    probability_text = f"{int(round(parse_float(best['yes_price']) * 100))}%"
    topic = classify_topic(best["question"], best.get("description", ""))

    return {
        "title": best["question"],
        "probability_text": probability_text,
        "change_text": "▲0%",
        "description": best.get("description", ""),
        "topic": topic
    }