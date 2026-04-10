
import os
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

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
BLOCK_WORDS = [
    "review", "travel", "fashion", "sports", "movie", "music",
    "celebrity gossip", "entertainment", "restaurant", "horoscope",
    "lifestyle", "shopping", "recipes", "recipe",
]
LOW_QUALITY_PATTERNS = [
    "live updates", "live blog", "opinion", "newsletter", "podcast",
    "editorial", "sponsored", "advertisement",
]
MARKET_KEYWORDS = [
    "trump", "tariff", "trade deal", "bitcoin", "btc", "ethereum", "eth",
    "oil", "wti", "crude", "brent", "gold", "fed", "inflation", "cpi",
    "yield", "rate cut", "nasdaq", "s&p", "dow", "ceasefire", "iran",
    "israel", "war", "attack", "hormuz", "dollar", "fx", "won", "환율",
    "유가", "금리", "물가", "비트", "달러", "금값"
]
HIGH_IMPACT_KEYWORDS = [
    "oil", "wti", "crude", "brent", "hormuz", "fed", "inflation", "cpi",
    "yield", "dollar", "fx", "won", "tariff", "bitcoin", "btc",
    "iran", "israel", "war", "attack", "ceasefire", "gold"
]

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_cache(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_cached_candidate():
    cache = load_cache()
    title = cache.get("title")
    desc = cache.get("description", "")
    saved_at = cache.get("saved_at")
    if not title or not saved_at:
        return None
    try:
        dt = datetime.fromisoformat(saved_at)
        if datetime.now(timezone.utc) - dt <= timedelta(hours=4):
            return {
                "title": title,
                "description": desc,
                "source": cache.get("source", ""),
                "url": cache.get("url", ""),
                "publishedAt": cache.get("publishedAt", ""),
            }
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
    name = (name or "").strip()
    if not name:
        return False
    if name in TRUSTED_SOURCE_NAMES:
        return True
    return name.lower() in {x.lower() for x in TRUSTED_SOURCE_NAMES}

def article_domain(article) -> str:
    return normalize_domain(article.get("url", "") or article.get("link", ""))

def article_source_name(article) -> str:
    src = article.get("source", {})
    if isinstance(src, dict):
        return (src.get("name", "") or "").strip()
    return str(src or "").strip()

def clean_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()

def article_text(article) -> str:
    title = clean_spaces(article.get("title", ""))
    desc = clean_spaces(article.get("description", "") or article.get("content", "") or article.get("summary", ""))
    return f"{title} {desc}".lower()

def has_market_impact(article) -> bool:
    text = article_text(article)
    return any(k in text for k in MARKET_KEYWORDS)

def has_high_impact(article) -> bool:
    text = article_text(article)
    return any(k in text for k in HIGH_IMPACT_KEYWORDS)

def is_low_quality_text(article) -> bool:
    title = clean_spaces(article.get("title", ""))
    desc = clean_spaces(article.get("description", "") or article.get("content", "") or article.get("summary", ""))
    text = f"{title} {desc}".lower()
    if len(title) < 18 or len(desc) < 40:
        return True
    if any(w in text for w in BLOCK_WORDS):
        return True
    if any(p in text for p in LOW_QUALITY_PATTERNS):
        return True
    return False

def published_recent_enough(article, hours=36) -> bool:
    raw = article.get("publishedAt") or article.get("pubDate") or article.get("published_at")
    if not raw:
        return True
    text = str(raw).strip()
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc) - timedelta(hours=hours)
    except Exception:
        return True

def dedup_key(article) -> str:
    title = clean_spaces(article.get("title", "")).lower()
    title = re.sub(r"[^a-z0-9가-힣\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:120]

def trusted_article(article) -> bool:
    domain = article_domain(article)
    source_name = article_source_name(article)
    if domain_is_blocked(domain):
        return False
    return domain_is_trusted(domain) or source_name_is_trusted(source_name)

def score_article(article):
    title = clean_spaces(article.get("title", ""))
    desc = clean_spaces(article.get("description", "") or article.get("content", "") or article.get("summary", ""))
    domain = article_domain(article)
    source_name = article_source_name(article)
    text = f"{title} {desc}".lower()
    score = 0
    if domain_is_trusted(domain):
        score += 40
    if source_name_is_trusted(source_name):
        score += 20
    if published_recent_enough(article, hours=24):
        score += 10
    for k in MARKET_KEYWORDS:
        if k in text:
            score += 4
    for k in HIGH_IMPACT_KEYWORDS:
        if k in text:
            score += 5
    if re.search(r"\d", text):
        score += 8
    if len(title) >= 28:
        score += 6
    if len(desc) >= 70:
        score += 6
    for w in BLOCK_WORDS:
        if w in text:
            score -= 15
    for p in LOW_QUALITY_PATTERNS:
        if p in text:
            score -= 12
    if "?" in title:
        score -= 6
    if len(title) < 18:
        score -= 12
    if len(desc) < 40:
        score -= 12
    return score

def fetch_news(limit=40):
    if not API_KEY:
        return []
    url = "https://newsapi.org/v2/everything"
    from_date = (datetime.now(timezone.utc) - timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%SZ")
    params = {
        "q": SEARCH_QUERY,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(max(limit, 20), 100),
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
    articles = data.get("articles", []) or []
    filtered, seen = [], set()
    for article in articles:
        title = clean_spaces(article.get("title", ""))
        if not title:
            continue
        if not trusted_article(article):
            continue
        if not has_market_impact(article):
            continue
        if not has_high_impact(article):
            continue
        if is_low_quality_text(article):
            continue
        if not published_recent_enough(article, hours=36):
            continue
        key = dedup_key(article)
        if not key or key in seen:
            continue
        seen.add(key)
        filtered.append(article)
    filtered.sort(key=score_article, reverse=True)
    return filtered[:limit]

def get_news_candidate():
    articles = fetch_news(limit=30)
    if not articles:
        return get_cached_candidate()
    best = articles[0]
    title = best.get("title") or ""
    desc = best.get("description") or best.get("content") or ""
    if not title:
        return get_cached_candidate()
    save_cache({
        "title": title,
        "description": desc,
        "source": article_source_name(best),
        "url": best.get("url", ""),
        "publishedAt": best.get("publishedAt", ""),
        "saved_at": datetime.now(timezone.utc).isoformat(),
    })
    return {
        "title": title,
        "description": desc,
        "source": article_source_name(best),
        "url": best.get("url", ""),
        "publishedAt": best.get("publishedAt", ""),
    }
