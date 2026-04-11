from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from typing import Any, Dict, List

import requests

API_KEY = (os.getenv("NEWS_API_KEY") or "").strip()
CACHE_FILE = "news_cache.json"

SEARCH_QUERY = (
    '("trump" OR "tariff" OR "trade deal" OR "bitcoin" OR "btc" OR "ethereum" OR "eth" '
    'OR "oil" OR "wti" OR "crude" OR "brent" OR "gold" OR "fed" OR "inflation" OR "cpi" '
    'OR "treasury yield" OR "rate cut" OR "nasdaq" OR "s&p 500" OR "dow" '
    'OR "iran" OR "israel" OR "ceasefire" OR "war" OR "hormuz" OR "dollar" OR "fx" OR "won")'
)

TRUSTED_DOMAINS = {
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "apnews.com", "bbc.com", "finance.yahoo.com", "marketwatch.com",
    "investing.com", "coindesk.com", "theblock.co", "yna.co.kr", "english.yna.co.kr",
}
TRUSTED_SOURCE_NAMES = {
    "Reuters", "Bloomberg", "CNBC", "The Wall Street Journal", "WSJ",
    "Financial Times", "Associated Press", "AP News", "BBC News",
    "Yahoo Finance", "MarketWatch", "Investing.com", "CoinDesk",
    "The Block", "Yonhap News Agency", "연합뉴스",
}
BLOCKED_DOMAINS = {
    "youtube.com", "youtu.be", "tiktok.com", "instagram.com", "medium.com",
    "substack.com", "blogspot.com", "wordpress.com", "pinterest.com",
    "reddit.com", "fool.com", "benzinga.com", "seekingalpha.com",
    "zerohedge.com", "cointelegraph.com", "cryptopotato.com", "u.today",
    "dailyhodl.com",
}
LOW_QUALITY_PATTERNS = [
    "live updates", "live blog", "opinion", "newsletter", "podcast",
    "editorial", "sponsored", "advertisement", "rumor", "reportedly",
]
MARKET_KEYWORDS = [
    "trump", "tariff", "trade deal", "bitcoin", "btc", "ethereum", "eth",
    "oil", "wti", "crude", "brent", "gold", "fed", "inflation", "cpi",
    "yield", "rate cut", "nasdaq", "s&p", "dow", "ceasefire", "iran",
    "israel", "war", "attack", "hormuz", "dollar", "fx", "won", "환율",
    "유가", "금리", "물가", "비트", "달러", "금값",
]
HIGH_IMPACT_KEYWORDS = [
    "oil", "wti", "crude", "brent", "hormuz", "fed", "inflation", "cpi",
    "yield", "dollar", "fx", "won", "tariff", "bitcoin", "btc",
    "iran", "israel", "war", "attack", "ceasefire", "gold",
]
BREAKING_KEYWORDS = [
    "breaking", "urgent", "developing", "attack", "missile", "strike",
    "ceasefire", "tariff", "fed", "rate", "oil", "bitcoin", "surge",
    "slump", "crash", "default", "bankruptcy", "sanction", "hormuz",
    "iran", "israel", "war",
]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _json_load(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _json_save(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_cache() -> Dict[str, Any]:
    return _json_load(CACHE_FILE, {"saved_at": "", "articles": [], "best": None})


def save_cache(articles: List[Dict[str, Any]]) -> None:
    best = None
    if articles:
        first = articles[0]
        best = {
            "title": first.get("title", ""),
            "description": first.get("description", "") or first.get("content", "") or "",
            "source": article_source_name(first),
            "url": first.get("url", ""),
            "publishedAt": first.get("publishedAt", ""),
        }
    _json_save(CACHE_FILE, {"saved_at": _now_utc().isoformat(), "articles": articles, "best": best})


def get_cached_articles(max_age_hours: int = 6) -> List[Dict[str, Any]]:
    cache = load_cache()
    raw = cache.get("saved_at")
    if not raw:
        return []
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if _now_utc() - dt <= timedelta(hours=max_age_hours):
            return cache.get("articles", []) or []
    except Exception:
        return []
    return []


def get_cached_candidate():
    cache = load_cache()
    raw = cache.get("saved_at")
    best = cache.get("best")
    if not raw or not best:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if _now_utc() - dt <= timedelta(hours=6):
            return best
    except Exception:
        return None
    return None


def normalize_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def domain_is_trusted(domain: str) -> bool:
    return bool(domain) and any(domain == d or domain.endswith("." + d) for d in TRUSTED_DOMAINS)


def domain_is_blocked(domain: str) -> bool:
    return bool(domain) and any(domain == d or domain.endswith("." + d) for d in BLOCKED_DOMAINS)


def source_name_is_trusted(name: str) -> bool:
    low = (name or "").strip().lower()
    return bool(low) and low in {x.lower() for x in TRUSTED_SOURCE_NAMES}


def article_domain(article: Dict[str, Any]) -> str:
    return normalize_domain(article.get("url", ""))


def article_source_name(article: Dict[str, Any]) -> str:
    src = article.get("source", {})
    if isinstance(src, dict):
        return (src.get("name", "") or "").strip()
    return str(src or "").strip()


def article_text(article: Dict[str, Any]) -> str:
    title = clean_spaces(article.get("title", ""))
    desc = clean_spaces(article.get("description", "") or article.get("content", "") or "")
    return f"{title} {desc}".lower()


def trusted_article(article: Dict[str, Any]) -> bool:
    domain = article_domain(article)
    if domain_is_blocked(domain):
        return False
    return domain_is_trusted(domain) or source_name_is_trusted(article_source_name(article))


def published_recent_enough(article: Dict[str, Any], hours: int = 36) -> bool:
    raw = article.get("publishedAt")
    if not raw:
        return True
    try:
        text = str(raw)
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt >= _now_utc() - timedelta(hours=hours)
    except Exception:
        return True


def dedup_key(article: Dict[str, Any]) -> str:
    title = clean_spaces(article.get("title", "")).lower()
    title = re.sub(r"[^a-z0-9가-힣\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()[:120]


def has_market_impact(article: Dict[str, Any]) -> bool:
    text = article_text(article)
    return any(k in text for k in MARKET_KEYWORDS)


def has_high_impact(article: Dict[str, Any]) -> bool:
    text = article_text(article)
    return any(k in text for k in HIGH_IMPACT_KEYWORDS)


def is_low_quality_text(article: Dict[str, Any]) -> bool:
    title = clean_spaces(article.get("title", ""))
    desc = clean_spaces(article.get("description", "") or article.get("content", "") or "")
    text = f"{title} {desc}".lower()
    if len(title) < 18 or len(desc) < 40:
        return True
    if any(p in text for p in LOW_QUALITY_PATTERNS):
        return True
    return False


def is_breaking_candidate(article: Dict[str, Any]) -> bool:
    text = article_text(article)
    title = clean_spaces(article.get("title", "")).lower()
    hit = sum(1 for k in BREAKING_KEYWORDS if k in text)
    if not trusted_article(article):
        return False
    if not has_market_impact(article):
        return False
    if hit >= 2:
        return True
    return any(x in title for x in ["ceasefire", "missile", "attack", "tariff", "fed", "rate", "oil", "bitcoin"])


def score_article(article: Dict[str, Any]) -> int:
    text = article_text(article)
    score = 0
    if domain_is_trusted(article_domain(article)):
        score += 40
    if source_name_is_trusted(article_source_name(article)):
        score += 20
    if published_recent_enough(article, hours=24):
        score += 10
    if re.search(r"\d", text):
        score += 8
    for k in MARKET_KEYWORDS:
        if k in text:
            score += 4
    for k in HIGH_IMPACT_KEYWORDS:
        if k in text:
            score += 5
    return score


def score_breaking_article(article: Dict[str, Any]) -> int:
    text = article_text(article)
    score = 0
    if domain_is_trusted(article_domain(article)):
        score += 50
    if source_name_is_trusted(article_source_name(article)):
        score += 20
    if published_recent_enough(article, hours=6):
        score += 15
    for k in BREAKING_KEYWORDS:
        if k in text:
            score += 7
    for k in HIGH_IMPACT_KEYWORDS:
        if k in text:
            score += 6
    if re.search(r"\d", text):
        score += 6
    return score


def fetch_news(limit: int = 40, hours_back: int = 36) -> List[Dict[str, Any]]:
    cached = get_cached_articles(max_age_hours=6)
    if not API_KEY:
        return cached

    params = {
        "q": SEARCH_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(max(limit, 20), 100),
        "from": (_now_utc() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apiKey": API_KEY,
    }
    try:
        data = requests.get("https://newsapi.org/v2/everything", params=params, timeout=20).json()
    except Exception:
        return cached
    if data.get("status") != "ok":
        print("뉴스 API 응답 이상:", data)
        return cached

    filtered: List[Dict[str, Any]] = []
    seen = set()
    for article in data.get("articles", []) or []:
        if not trusted_article(article):
            continue
        if not has_market_impact(article):
            continue
        if not has_high_impact(article):
            continue
        if is_low_quality_text(article):
            continue
        if not published_recent_enough(article, hours=hours_back):
            continue
        key = dedup_key(article)
        if not key or key in seen:
            continue
        seen.add(key)
        filtered.append(article)

    filtered.sort(key=score_article, reverse=True)
    if filtered:
        save_cache(filtered[:limit])
        return filtered[:limit]
    return cached


def fetch_breaking_news(limit: int = 20, hours_back: int = 12) -> List[Dict[str, Any]]:
    articles = fetch_news(limit=max(limit, 20), hours_back=hours_back)
    out = []
    seen = set()
    for article in articles:
        if not is_breaking_candidate(article):
            continue
        key = dedup_key(article)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(article)
    out.sort(key=score_breaking_article, reverse=True)
    return out[:limit]


def get_news_candidate():
    arts = fetch_news(limit=30, hours_back=12)
    if not arts:
        return get_cached_candidate()
    best = arts[0]
    return {
        "title": best.get("title", ""),
        "description": best.get("description", "") or best.get("content", "") or "",
        "source": article_source_name(best),
        "url": best.get("url", ""),
        "publishedAt": best.get("publishedAt", ""),
    }
