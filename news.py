import os
import requests
from datetime import datetime, timedelta

API_KEY = os.getenv("NEWS_API_KEY")
API_KEY = "aa92972d14a64530aaf56306518f564e"

SEARCH_QUERY = (
    '("trump" OR "iran" OR "war" OR "attack" OR "missile" '
    'OR "oil" OR "gold" OR "bitcoin" OR "btc" '
    'OR "fed" OR "inflation" OR "tariff" '
    'OR "exchange rate" OR "dollar" OR "won" '
    'OR "stock market" OR "nasdaq" OR "s&p 500" OR "dow")'
)

BLOCK_WORDS = [
    "review", "business class", "flight", "hotel", "travel",
    "celebrity", "movie", "music", "sports", "fashion"
]

BOOST_WORDS = [
    "trump", "iran", "war", "attack", "missile",
    "oil", "gold", "bitcoin", "btc",
    "fed", "inflation", "tariff",
    "exchange rate", "dollar", "won",
    "stock market", "nasdaq", "s&p", "dow",
    "crash", "surge", "jump", "spike", "collapse"
]

def score_article(article):
    text = f"{article.get('title', '')} {article.get('description', '')}".lower()
    score = 0

    for word in BOOST_WORDS:
        if word in text:
            score += 2

    for word in BLOCK_WORDS:
        if word in text:
            score -= 5

    return score

def fetch_news():
    url = "https://newsapi.org/v2/everything"

    # 최근 2일치만 가져오게
    from_date = (datetime.utcnow() - timedelta(days=2)).strftime("%Y-%m-%d")

    params = {
        "q": SEARCH_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 30,
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
            "Oil prices jump as geopolitical tension rises",
            "Energy markets are reacting fast as geopolitical risks increase."
        ),
        (
            "Gold rises as investors move to safe havens",
            "Uncertainty in the market is pushing money toward safer assets."
        ),
        (
            "Bitcoin volatility returns as market uncertainty grows",
            "Risk sentiment is shifting and crypto prices are reacting again."
        ),
        (
            "Dollar strengthens as inflation fears return",
            "Currency markets are moving as investors prepare for higher prices."
        ),
        (
            "Stock market wobbles as risk sentiment weakens",
            "Investor confidence is slipping and money is moving more cautiously."
        ),
    ]

    # 시간 기준으로 순환 선택
    idx = datetime.utcnow().minute % len(fallback_list)
    return fallback_list[idx]

def get_news():
    articles = fetch_news()

    if not articles:
        return get_fallback_news()

    scored = [(score_article(article), article) for article in articles]
    scored.sort(key=lambda x: x[0], reverse=True)

    best = scored[0][1]
    title = best.get("title") or "뉴스 없음"
    desc = best.get("description") or ""

    if title == "뉴스 없음":
        return get_fallback_news()

    return title, desc