import json
import re
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

API_URL = "https://gamma-api.polymarket.com/markets"

ALLOWED_TOPICS = {"economy", "crypto", "geopolitics"}

SPORTS_KEYWORDS = [
    "fc ", "cf ", "arsenal", "real madrid", "bayern", "sporting cp",
    "nba", "nfl", "mlb", "nhl", "fifa", "world cup", "finals",
    "vs.", "vs ", "o/u", "over/under", "tennis", "masters",
    "cameron norrie", "de minaur", "spurs", "royals", "guardians"
]

POPULAR_KEYWORDS = [
    "iran", "war", "attack", "missile", "ceasefire", "regime", "israel",
    "oil", "wti", "crude", "brent", "gold", "bitcoin", "btc", "ethereum", "eth",
    "fed", "inflation", "rate", "recession", "economy", "s&p 500", "nasdaq",
    "dow", "trump", "china", "russia", "taiwan", "tariff", "hormuz", "strait",
    "yield", "treasury", "stocks", "cpi", "dollar"
]

LOW_QUALITY_WORDS = ["will", "vs", "win", "match", "game", "score", "player", "season"]
ABSTRACT_WORDS = ["tension", "fear", "sentiment", "anxiety", "uncertainty", "concern", "panic"]

MONEY_WORDS = [
    "oil", "wti", "crude", "brent", "gold", "bitcoin", "btc", "ethereum", "eth",
    "fed", "inflation", "rate", "rates", "tariff", "s&p 500", "nasdaq", "dow",
    "economy", "recession", "dollar", "won", "hormuz", "strait", "stocks",
    "yield", "treasury", "cpi"
]

KOREAN_AUDIENCE_PRIORITY = {
    "oil": 34,
    "wti": 34,
    "crude": 34,
    "gold": 28,
    "bitcoin": 30,
    "btc": 30,
    "ethereum": 24,
    "eth": 24,
    "fed": 24,
    "inflation": 26,
    "cpi": 26,
    "rate": 22,
    "tariff": 24,
    "dollar": 18,
    "hormuz": 30,
}

GEO_WITHOUT_MONEY = ["iran", "war", "attack", "missile", "ceasefire", "israel", "regime"]


def parse_outcome_prices(raw: Any) -> List[float]:
    if raw is None:
        return []
    if isinstance(raw, list):
        out = []
        for x in raw:
            try:
                out.append(float(x))
            except Exception:
                pass
        return out
    if isinstance(raw, str):
        raw = raw.strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [float(x) for x in parsed]
        except Exception:
            pass
        try:
            return [float(x.strip().replace("[", "").replace("]", "").replace('"', "")) for x in raw.split(",") if x.strip()]
        except Exception:
            pass
    return []


def parse_outcomes(raw: Any) -> List[str]:
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
        except Exception:
            pass
        return [x.strip().replace('"', "") for x in raw.replace("[", "").replace("]", "").split(",") if x.strip()]
    return []


def pick_yes_price(market: Dict[str, Any]) -> float:
    prices = parse_outcome_prices(market.get("outcomePrices"))
    outcomes = [x.lower() for x in parse_outcomes(market.get("outcomes"))]
    if prices and outcomes and "yes" in outcomes:
        idx = outcomes.index("yes")
        if idx < len(prices):
            return prices[idx]
    return prices[0] if prices else 0.0


def pick_volume(market: Dict[str, Any]) -> float:
    for c in [market.get("volume24hr"), market.get("volume"), market.get("liquidity"), market.get("volumeNum")]:
        try:
            v = float(c)
            if v > 0:
                return v
        except Exception:
            pass
    return 0.0


def pick_end_date(market: Dict[str, Any]) -> str:
    for key in ["endDate", "end_date", "resolutionDate", "closeTime", "closedTime"]:
        value = market.get(key)
        if value:
            return str(value)
    return ""


def parse_datetime_safe(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None


def is_market_resolved_or_closed(market: Dict[str, Any]) -> bool:
    for key in ["closed", "resolved", "archived"]:
        if isinstance(market.get(key), bool) and market.get(key) is True:
            return True
    status_text = " ".join([
        str(market.get("status", "")),
        str(market.get("gameStatus", "")),
        str(market.get("marketStatus", "")),
    ]).lower()
    return any(word in status_text for word in ["resolved", "closed", "finalized", "ended", "settled", "archived"])


def question_has_expired_date(question: str) -> bool:
    if not question:
        return False
    m = re.search(r"by\s+([A-Z][a-z]+)\s+(\d{1,2})(?:,\s*(\d{4}))?", question.strip())
    if not m:
        return False
    month_name = m.group(1)
    day = int(m.group(2))
    year = int(m.group(3)) if m.group(3) else datetime.now(timezone.utc).year
    try:
        dt = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y").replace(tzinfo=timezone.utc)
        return dt < datetime.now(timezone.utc)
    except Exception:
        return False


def is_market_expired(market: Dict[str, Any]) -> bool:
    dt = parse_datetime_safe(pick_end_date(market))
    if dt is not None and dt < datetime.now(timezone.utc):
        return True
    return question_has_expired_date(str(market.get("question", "")))


def classify_topic(title: str, description: str = "") -> str:
    text = f"{title} {description}".lower()
    if any(k in text for k in SPORTS_KEYWORDS):
        return "sports"
    if any(k in text for k in ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana"]):
        return "crypto"
    if any(k in text for k in [
        "fed", "inflation", "rate", "recession", "economy", "stocks", "oil", "gold",
        "s&p 500", "nasdaq", "dow", "wti", "crude", "strait of hormuz", "hormuz",
        "tariff", "yield", "treasury", "cpi", "dollar"
    ]):
        return "economy"
    if any(k in text for k in [
        "iran", "military", "troops", "missile", "strike", "attack", "israel", "china",
        "taiwan", "ceasefire", "kharg island", "conflict", "regime", "war"
    ]):
        return "geopolitics"
    return "general"


def is_popular_market(question: str, description: str = "") -> bool:
    text = f"{question} {description}".lower()
    return any(k in text for k in POPULAR_KEYWORDS)


def is_money_market(question: str, description: str = "") -> bool:
    text = f"{question} {description}".lower()
    return any(k in text for k in MONEY_WORDS)


def is_abstract_only_market(question: str, description: str = "") -> bool:
    text = f"{question} {description}".lower()
    return any(w in text for w in ABSTRACT_WORDS) and not is_money_market(question, description)


def is_geo_but_not_monetizable(question: str, description: str = "") -> bool:
    text = f"{question} {description}".lower()
    has_geo = any(k in text for k in GEO_WITHOUT_MONEY)
    has_money = any(k in text for k in ["oil", "gold", "hormuz", "crude", "brent", "wti"])
    return has_geo and not has_money


def days_until(end_date: str) -> Optional[int]:
    dt = parse_datetime_safe(end_date)
    if not dt:
        return None
    return max((dt - datetime.now(timezone.utc)).days, 0)


def market_title_natural_score(question: str) -> int:
    q = question.lower()
    score = 0
    if len(question) <= 90:
        score += 12
    if any(k in q for k in ["by april", "by may", "by june", "before "]):
        score += 8
    if any(k in q for k in ["hit", "surpass", "reach", "ceasefire", "tariff", "approval"]):
        score += 10
    return score


def korean_audience_score(question: str, description: str = "") -> int:
    text = f"{question} {description}".lower()
    score = 0
    for key, pts in KOREAN_AUDIENCE_PRIORITY.items():
        if key in text:
            score += pts
    return score


def is_valid_market(market: Dict[str, Any]) -> bool:
    if is_market_resolved_or_closed(market) or is_market_expired(market):
        return False
    question = str(market.get("question", "")).strip()
    description = str(market.get("description", "") or "").strip()
    if not question:
        return False
    topic = classify_topic(question, description)
    if topic not in ALLOWED_TOPICS:
        return False
    if not is_popular_market(question, description):
        return False
    if any(w in question.lower() for w in LOW_QUALITY_WORDS):
        return False
    if is_abstract_only_market(question, description):
        return False
    if is_geo_but_not_monetizable(question, description):
        return False
    if not is_money_market(question, description) and topic != "crypto":
        return False
    yes_price = pick_yes_price(market)
    volume = pick_volume(market)
    if volume <= 250000:
        return False
    if yes_price < 0 or yes_price > 1:
        return False
    if yes_price > 0.97 or yes_price < 0.03:
        return False
    return True


def market_score(market: Dict[str, Any]) -> int:
    yes_price = pick_yes_price(market)
    volume = pick_volume(market)
    question = str(market.get("question", "")).lower()
    description = str(market.get("description", "") or "").lower()
    topic = classify_topic(question, description)
    end_date = pick_end_date(market)
    score = 0

    score += min(int(volume / 120000), 280)
    if 0.08 < yes_price < 0.92:
        score += 35
    if 0.18 < yes_price < 0.82:
        score += 22

    if topic == "economy":
        score += 48
    elif topic == "crypto":
        score += 38
    elif topic == "geopolitics":
        score += 18

    if is_money_market(question, description):
        score += 40

    score += korean_audience_score(question, description)
    score += market_title_natural_score(question)

    dleft = days_until(end_date)
    if dleft is not None:
        if dleft <= 3:
            score += 18
        elif dleft <= 7:
            score += 10

    for word in [
        "oil", "wti", "crude", "brent", "gold", "bitcoin", "btc", "ethereum", "eth",
        "fed", "inflation", "tariff", "nasdaq", "s&p", "dow", "yield", "treasury",
        "cpi", "hormuz", "dollar"
    ]:
        if word in question:
            score += 18

    return score


def normalize_market(market: Dict[str, Any]) -> Dict[str, Any]:
    question = str(market.get("question", "")).strip()
    description = str(market.get("description", "") or "").strip()
    return {
        "question": question,
        "description": description,
        "yes_price": pick_yes_price(market),
        "volume": pick_volume(market),
        "end_date": pick_end_date(market),
        "topic": classify_topic(question, description),
        "raw": market,
    }


def get_polymarket_markets(limit: int = 150) -> List[Dict[str, Any]]:
    params = {
        "limit": limit,
        "active": "true",
        "closed": "false",
        "order": "volume24hr",
        "ascending": "false",
    }
    try:
        res = requests.get(API_URL, params=params, timeout=20)
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print("Polymarket fetch error:", e)
        return []

    if not isinstance(data, list):
        return []

    valid = []
    for market in data:
        if is_valid_market(market):
            valid.append(normalize_market(market))

    valid.sort(key=lambda x: market_score(x["raw"]), reverse=True)
    return valid
