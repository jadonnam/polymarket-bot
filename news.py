import os
import json
import re
import requests
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

API_KEY = os.getenv("NEWS_API_KEY") or ""
CACHE_FILE = "news_cache.json"

SEARCH_QUERY = (
    '("trump" OR "tariff" OR "trade deal" OR "bitcoin" OR "btc" OR "ethereum" OR "eth" '
    'OR "oil" OR "wti" OR "crude" OR "gold" OR "fed" OR "inflation" OR "cpi" '
    'OR "treasury yield" OR "rate cut" OR "nasdaq" OR "s&p 500" OR "dow" '
    'OR "iran" OR "israel" OR "ceasefire" OR "war" OR "hormuz" OR "strait of hormuz")'
)

BLOCK_WORDS = {
    "review", "travel", "fashion", "sports", "movie", "music", "celebrity gossip",
    "entertainment", "restaurant", "preview", "watchlist", "rumor", "editorial"
}

LOW_VALUE_WORDS = {
    "opinion", "analysis", "analyst says", "could", "may", "might", "speculation",
    "expected to", "forecast", "if this happens"
}

BOOST_WORDS = {
    "trump", "tariff", "trade deal", "bitcoin", "btc", "ethereum", "eth",
    "oil", "wti", "crude", "gold", "fed", "inflation", "cpi", "yield",
    "rate cut", "nasdaq", "s&p", "dow", "ceasefire", "iran", "israel", "war",
    "attack", "missile", "hormuz"
}

HARD_IMPACT_WORDS = {
    "attack", "missile", "strike", "surge", "spike", "plunge", "slump", "record",
    "tariff", "ceasefire", "explosion", "emergency", "approved", "rejected",
    "ban", "ultimatum", "deadline", "halts", "sanctions", "cuts rates", "holds rates"
}

REACTION_WORDS = {
    "record", "plunge", "surge", "slams", "soars", "crashes", "shock", "ban",
    "approval", "rejection", "deadline", "ultimatum", "strike", "halt", "emergency"
}


def load_cache() -> Dict[str, Any]:
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(data: Dict[str, Any]) -> None:
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parse_published_at(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def is_recent_enough(article: Dict[str, Any], hours: int = 18) -> bool:
    dt = parse_published_at(article.get("publishedAt", ""))
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    return now - dt.astimezone(timezone.utc) <= timedelta(hours=hours)


def normalize_title(title: str) -> str:
    title = re.sub(r"\s*-\s*[^-]+$", "", title.strip())
    title = re.sub(r"[^a-zA-Z0-9\s]", " ", title.lower())
    title = re.sub(r"\s+", " ", title).strip()
    return title


def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_title(a), normalize_title(b)).ratio()


def title_length_score(title: str) -> int:
    n = len(title)
    if 42 <= n <= 92:
        return 12
    if 28 <= n <= 110:
        return 6
    if n < 18:
        return -14
    if n > 130:
        return -10
    return 0


def has_real_impact(text: str) -> bool:
    text = text.lower()
    if any(k in text for k in HARD_IMPACT_WORDS):
        return True
    paired_patterns = [
        ["iran", "oil"], ["war", "oil"], ["hormuz", "oil"], ["fed", "rate"],
        ["fed", "inflation"], ["bitcoin", "surge"], ["bitcoin", "plunge"],
        ["gold", "surge"], ["tariff", "trump"], ["ceasefire", "iran"],
    ]
    return any(all(p in text for p in pair) for pair in paired_patterns)


def reaction_score(text: str) -> int:
    score = 0
    for word in REACTION_WORDS:
        if word in text:
            score += 5
    return score


def score_article(article: Dict[str, Any]) -> int:
    title = article.get("title", "") or ""
    desc = article.get("description", "") or ""
    source = (article.get("source", {}) or {}).get("name", "") or ""
    text = f"{title} {desc}".lower()
    score = 0

    for word in BOOST_WORDS:
        if word in text:
            score += 5
    for word in BLOCK_WORDS:
        if word in text:
            score -= 14
    for word in LOW_VALUE_WORDS:
        if word in text:
            score -= 9

    score += title_length_score(title)
    score += reaction_score(text)

    if len(desc) < 40:
        score -= 10
    elif len(desc) >= 90:
        score += 5

    if source:
        score += 4

    if is_recent_enough(article, hours=8):
        score += 24
    elif is_recent_enough(article, hours=16):
        score += 12
    elif is_recent_enough(article, hours=24):
        score += 4
    else:
        score -= 20

    if has_real_impact(text):
        score += 28

    if any(k in text for k in ["oil", "bitcoin", "gold", "fed", "inflation", "tariff", "hormuz"]):
        score += 15

    if "?" in title:
        score -= 7

    return score


def fetch_news() -> List[Dict[str, Any]]:
    if not API_KEY:
        return []

    url = "https://newsapi.org/v2/everything"
    from_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    params = {
        "q": SEARCH_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 50,
        "from": from_date,
        "apiKey": API_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=20)
        data = res.json()
    except Exception:
        return []

    if data.get("status") != "ok":
        print("뉴스 API 응답 이상:", data)
        return []

    return data.get("articles", [])


def dedupe_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: List[Dict[str, Any]] = []
    for article in articles:
        title = article.get("title", "") or ""
        if not title:
            continue
        if any(title_similarity(title, kept.get("title", "")) >= 0.82 for kept in unique):
            continue
        unique.append(article)
    return unique


def get_cached_candidate() -> Optional[Dict[str, str]]:
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
                "source": cache.get("source", ""),
            }
    except Exception:
        return None

    return None


def get_news_candidate() -> Optional[Dict[str, str]]:
    articles = fetch_news()
    if not articles:
        return get_cached_candidate()

    filtered: List[Dict[str, Any]] = []
    for article in articles:
        title = article.get("title", "") or ""
        desc = article.get("description", "") or ""
        text = f"{title} {desc}".lower()

        if not title:
            continue
        if not is_recent_enough(article, hours=24):
            continue
        if not has_real_impact(text):
            continue
        filtered.append(article)

    filtered = dedupe_articles(filtered)
    scored = [(score_article(a), a) for a in filtered]
    scored = [x for x in scored if x[0] >= 34]
    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return get_cached_candidate()

    best = scored[0][1]
    title = best.get("title") or ""
    desc = best.get("description") or ""
    source = (best.get("source", {}) or {}).get("name", "") or ""

    save_cache({
        "title": title,
        "description": desc,
        "source": source,
        "saved_at": datetime.utcnow().isoformat(),
    })

    return {
        "title": title,
        "description": desc,
        "source": source,
    }
