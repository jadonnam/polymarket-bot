import os
import json
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("NEWS_API_KEY") or ""
CACHE_FILE = "news_cache.json"

SEARCH_QUERY = (
    '("trump" OR "tariff" OR "trade deal" OR "bitcoin" OR "btc" OR "ethereum" OR "eth" '
    'OR "oil" OR "wti" OR "crude" OR "gold" OR "fed" OR "inflation" OR "cpi" '
    'OR "treasury yield" OR "rate cut" OR "nasdaq" OR "s&p 500" OR "dow" '
    'OR "iran" OR "israel" OR "ceasefire" OR "war")'
)

BLOCK_WORDS = [
    "review", "travel", "fashion", "sports", "movie", "music",
    "celebrity gossip", "entertainment", "restaurant"
]

BOOST_WORDS = [
    "trump", "tariff", "trade deal", "bitcoin", "btc", "ethereum", "eth",
    "oil", "wti", "crude", "gold", "fed", "inflation", "cpi",
    "yield", "rate cut", "nasdaq", "s&p", "dow", "ceasefire", "iran", "israel"
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


def score_article(article):
    title = article.get("title", "") or ""
    desc = article.get("description", "") or ""
    source = (article.get("source", {}) or {}).get("name", "") or ""
    text = f"{title} {desc}".lower()
    score = 0

    for w in BOOST_WORDS:
        if w in text:
            score += 4

    for w in BLOCK_WORDS:
        if w in text:
            score -= 10

    # 기사 품질 필터 강화
    if len(title) < 18:
        score -= 8
    if len(desc) < 40:
        score -= 8
    if "opinion" in text or "analysis" in text:
        score -= 4
    if source:
        score += 4

    if any(k in text for k in ["trump", "bitcoin", "oil", "gold", "fed", "inflation", "yield", "tariff"]):
        score += 12

    if article.get("publishedAt"):
        score += 8

    return score


def fetch_news():
    if not API_KEY:
        return []

    url = "https://newsapi.org/v2/everything"
    from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")

    params = {
        "q": SEARCH_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 30,
        "from": from_date,
        "apiKey": API_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=20)
        data = res.json()
    except:
        return []

    if data.get("status") != "ok":
        print("뉴스 API 응답 이상:", data)
        return []

    return data.get("articles", [])


def get_cached_candidate():
    cache = load_cache()
    title = cache.get("title")
    desc = cache.get("description", "")
    saved_at = cache.get("saved_at")

    if not title or not saved_at:
        return None

    try:
        dt = datetime.fromisoformat(saved_at)
        if datetime.utcnow() - dt <= timedelta(hours=4):
            return {
                "title": title,
                "description": desc,
                "source": cache.get("source", "")
            }
    except:
        return None

    return None


def get_news_candidate():
    articles = fetch_news()

    if not articles:
        return get_cached_candidate()

    scored = [(score_article(a), a) for a in articles]
    scored = [x for x in scored if x[0] >= 18]
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return get_cached_candidate()

    best = scored[0][1]
    title = best.get("title") or ""
    desc = best.get("description") or ""

    if not title:
        return get_cached_candidate()

    save_cache({
        "title": title,
        "description": desc,
        "source": best.get("source", {}).get("name", ""),
        "saved_at": datetime.utcnow().isoformat(),
    })

    return {
        "title": title,
        "description": desc,
        "source": best.get("source", {}).get("name", "")
    }