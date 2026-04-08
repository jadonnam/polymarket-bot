import os
import json
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("NEWS_API_KEY") or "aa92972d14a64530aaf56306518f564e"
CACHE_FILE = "news_cache.json"

SEARCH_QUERY = (
    '("trump" OR "iran" OR "war" OR "attack" OR "missile" '
    'OR "oil" OR "gold" OR "bitcoin" OR "btc" '
    'OR "fed" OR "inflation" OR "tariff" '
    'OR "exchange rate" OR "dollar" OR "won" '
    'OR "stock market" OR "nasdaq" OR "s&p 500" OR "dow" '
    'OR "treasury yield" OR "cpi" OR "hormuz" OR "brent" OR "wti")'
)

BLOCK_WORDS = [
    "review", "business class", "flight", "hotel", "travel",
    "celebrity", "movie", "music", "sports", "fashion"
]

BOOST_WORDS = [
    "oil", "gold", "bitcoin", "btc", "fed", "inflation", "tariff",
    "exchange rate", "dollar", "won", "stock market", "nasdaq", "s&p", "dow",
    "crash", "surge", "jump", "spike", "collapse", "hormuz", "brent", "wti",
    "yield", "treasury", "cpi"
]


def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_cached_news():
    cache = load_cache()
    title = cache.get("title")
    desc = cache.get("description", "")
    saved_at = cache.get("saved_at", "")

    if not title:
        return None

    try:
        dt = datetime.fromisoformat(saved_at)
        if datetime.utcnow() - dt <= timedelta(hours=6):
            return title, desc
    except:
        pass

    return None


def score_article(article):
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()
    score = 0

    for word in BOOST_WORDS:
        if word in text:
            score += 3

    for word in BLOCK_WORDS:
        if word in text:
            score -= 8

    if any(w in text for w in ["iran", "war", "attack", "missile", "ceasefire"]) and not any(w in text for w in ["oil", "wti", "crude", "gold", "hormuz"]):
        score -= 30

    if "%" in text or "$" in text:
        score += 8

    return score


def fetch_news():
    url = "https://newsapi.org/v2/everything"
    from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")

    params = {
        "q": SEARCH_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "from": from_date,
        "apiKey": API_KEY,
    }

    res = requests.get(url, params=params, timeout=20)
    data = res.json()

    if data.get("status") != "ok":
        print("뉴스 API 응답 이상:", data)
        return []

    return data.get("articles", [])


def get_fallback_news():
    fallback_list = [
        (
            "Oil prices rise as traders watch supply risk in the Middle East",
            "Energy markets are reacting to potential supply disruption and shipping risk."
        ),
        (
            "Gold gains as investors shift toward safe-haven assets",
            "Money is rotating into defensive assets as macro risk builds."
        ),
        (
            "Bitcoin volatility returns as risk appetite swings",
            "Crypto traders are reacting fast as macro expectations shift."
        ),
        (
            "Treasury yields move as traders reset rate cut bets",
            "Bond markets are repricing the path of interest rates and inflation."
        ),
        (
            "Tariff headlines put global stocks and inflation back in focus",
            "Investors are watching trade pressure, prices, and equity risk together."
        ),
    ]

    idx = datetime.utcnow().hour % len(fallback_list)
    return fallback_list[idx]


def get_news():
    cached = get_cached_news()

    articles = fetch_news()
    if not articles:
        if cached:
            return cached
        return get_fallback_news()

    scored = [(score_article(article), article) for article in articles]
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        if cached:
            return cached
        return get_fallback_news()

    best = scored[0][1]
    title = best.get("title") or ""
    desc = best.get("description") or ""

    if not title:
        if cached:
            return cached
        return get_fallback_news()

    save_cache({
        "title": title,
        "description": desc,
        "saved_at": datetime.utcnow().isoformat()
    })

    return title, desc