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
USE_CACHED_NEWS = (os.getenv("USE_CACHED_NEWS") or "true").lower() == "true"

SEARCH_QUERY = (
    '("trump" OR "tariff" OR "trade deal" OR "bitcoin" OR "btc" OR "ethereum" OR "eth" '
    'OR "oil" OR "wti" OR "crude" OR "brent" OR "gold" OR "fed" OR "inflation" OR "cpi" '
    'OR "treasury yield" OR "rate cut" OR "nasdaq" OR "s&p 500" OR "dow" '
    'OR "iran" OR "israel" OR "ceasefire" OR "war" OR "hormuz" OR "dollar" OR "fx" '
    'OR "KRW" OR "korean won" OR "won/dollar" OR "dollar/won")'
)
# 코스피·코스닥·신고가 등 — 카드뉴스용 대중 이슈 우선 병합
KOREA_MARKET_SEARCH_QUERY = (
    '("kospi" OR "kosdaq" OR "korean stock" OR "seoul stocks" OR "south korea market") '
    'AND ("record" OR "high" OR "surge" OR "rally" OR "plunge" OR "break" OR "milestone" '
    'OR "foreign" OR "investor" OR "chip" OR "semiconductor")'
)
# 버핏·대형주·지정학 — 인스타 카드뉴스용 메인스트림 이슈
MAINSTREAM_CARD_SEARCH_QUERY = (
    '("warren buffett" OR "berkshire hathaway" OR buffett) '
    'OR ("nvidia" OR "apple" OR "tesla" OR "microsoft" OR "amazon") '
    'AND ("surge" OR "fall" OR "record" OR "plunge" OR "rally" OR "buy" OR "sell") '
    'OR ("war" OR "invasion" OR "ceasefire" OR "missile" OR "airstrike") '
    'OR ("investigation" OR "scandal" OR "lawsuit" OR "recall" OR "fraud")'
)
# 속보·테러·총격 등 — 메인 쿼리에 안 잡히면 별도 호출로 앞에 합침
VIRAL_SEARCH_QUERY = (
    '("trump" AND ("shot" OR "shooting" OR "assassination" OR "gunman" OR "attack" OR "wounded"))'
    ' OR ("breaking" AND ("assassination" OR "shooting" OR "shot"))'
    ' OR ("president" AND ("shot" OR "shooting" OR "assassination"))'
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
    "israel", "war", "attack", "hormuz", "dollar", "fx", "krw", "환율",
    "유가", "금리", "물가", "비트", "달러", "금값",
    "kospi", "kosdaq", "korean stock", "seoul", "record high", "all-time",
    "milestone", "surge", "rally", "plunge", "semiconductor", "nvidia",
]
# 카드뉴스 — 대중·흥미·놀라움 (수치·돌파·신고가)
POPULAR_CARD_KEYWORDS = [
    "kospi", "kosdaq", "코스피", "코스닥", "record high", "all-time", "all time",
    "milestone", "historic", "first time", "breaks", "above", "surge", "soar",
    "rally", "jumps", "plunge", "crash", "unexpected", "shock", "stunning",
    "bitcoin", "nvidia", "semiconductor", "tariff", "rate cut", "cpi",
    "inflation", "oil", "gold", "fed", "nasdaq", "s&p", "dow",
    "신고가", "돌파", "급등", "급락", "역대",
]
# 종교·일반 윤리 등 — 시장 무관·클릭률 낮음
OBSCURE_CARD_PENALTY = [
    "pope", "vatican", "archbishop", "cardinal", "homily", "mass at",
    "autonomous weapon", "humanitarian award", "obituary", "celebrity wedding",
    "royal wedding", "fashion week", "recipe", "horoscope",
    "data ownership", "ethical ai", "ai ethics", "ai warning",
    "conference keynote", "wellness", "yoga", "horoscope",
]
# 인스타 카드 — 무조건 통과해야 하는 '훅' (하나 이상)
MANDATORY_CARD_HOOK_ALWAYS = (
    "kospi",
    "kosdaq",
    "코스피",
    "코스닥",
    "buffett",
    "berkshire",
    "warren buffett",
    "war",
    "invasion",
    "missile",
    "airstrike",
    "ceasefire",
    "iran",
    "israel",
    "hormuz",
    "전쟁",
    "공습",
    "발포",
    "assassination",
    "shooting",
    "gunman",
    "trump",
    "tariff",
    "scandal",
    "fraud",
    "investigation",
    "lawsuit",
    "probe",
    "recall",
    "논란",
    "기소",
)
MANDATORY_CARD_HOOK_WITH_MOVE = (
    "nvidia",
    "apple",
    "tesla",
    "microsoft",
    "amazon",
    "meta",
    "semiconductor",
    "삼성",
    "하이닉스",
    "fed",
    "cpi",
    "rate cut",
    "rate hike",
    "oil",
    "wti",
    "crude",
    "gold",
    "nasdaq",
    "s&p",
    "dow",
    "bitcoin",
    "btc",
)
CARD_HOOK_MOVE_WORDS = (
    "surge",
    "soar",
    "plunge",
    "crash",
    "rally",
    "record",
    "historic",
    "milestone",
    "breaks",
    "jumps",
    "slump",
    "급등",
    "급락",
    "돌파",
    "신고가",
    "역대",
    "unexpected",
    "shock",
    "buy",
    "sell",
    "stake",
    "매수",
    "매도",
    "%",
    "percent",
    "all-time",
    "all time",
)
# 거래소 상품·디파이 출시 등 — 카드뉴스에 안 맞는 니치 크립토
NICHE_CRYPTO_PRODUCT_MARKERS = (
    "unveils",
    "vault",
    "launches",
    "introduces",
    "staking",
    "defi",
    "yield push",
    "earn rewards",
    "new product",
    "wallet feature",
    "partnership with",
    "kraken",
    "coinbase card",
    "exchange adds",
    "expanding yield",
    "for btc holders",
    "crypto product",
)
# BTC 가격 급등락·신고가는 니치에서 제외
CRYPTO_PRICE_MOVE_MARKERS = (
    "surge",
    "crash",
    "plunge",
    "rally",
    "soar",
    "tumble",
    "record high",
    "all-time",
    "all time",
    "breaks",
    "hits $",
    "above $",
    "below $",
    "%",
    "percent",
)
# 인스타 카드 — 대중 이슈 가산
INSTAGRAM_CARD_BOOST_GROUPS: List[tuple] = [
    (("buffett", "berkshire", "warren buffett"), 42),
    (("kospi", "kosdaq", "코스피", "코스닥"), 45),
    (
        (
            "war",
            "invasion",
            "ceasefire",
            "missile",
            "airstrike",
            "전쟁",
            "공습",
            "발포",
        ),
        38,
    ),
    (
        (
            "investigation",
            "scandal",
            "lawsuit",
            "probe",
            "fraud",
            "recall",
            "논란",
            "기소",
        ),
        32,
    ),
    (
        ("nvidia", "apple", "tesla", "microsoft", "amazon", "meta", "google"),
        22,
    ),
]
HIGH_IMPACT_KEYWORDS = [
    "oil", "wti", "crude", "brent", "hormuz", "fed", "inflation", "cpi",
    "yield", "dollar", "fx", "krw", "tariff", "bitcoin", "btc",
    "iran", "israel", "war", "attack", "ceasefire", "gold",
]

# "won" 단독 문자열은 영어 동사 won(이겼다)과 충돌 — 원화는 아래 정규식만 인정
_WON_CURRENCY_RE = re.compile(
    r"\bkrw\b|korean won|south korean won|won/dollar|dollar/won|"
    r"won strengthens|won weakens|won surges|won tumbles|won slips|won rises|won falls",
    re.I,
)

_SPORTS_URL_MARKERS = (
    "/sport/",
    "/sports/",
    "/football/",
    "/soccer/",
    "/nba/",
    "/nfl/",
    "/mlb/",
    "/cricket/",
    "/rugby/",
    "/f1/",
    "/tennis/",
    "/golf/",
    "/olympics/",
    "/premier-league/",
    "/champions-league/",
)


def is_sports_article(article: Dict[str, Any]) -> bool:
    """BBC /sport/football 등 — 시장 카드·뉴스 후보에서 제외."""
    u = str(article.get("url") or "").lower()
    return any(m in u for m in _SPORTS_URL_MARKERS)
BREAKING_KEYWORDS = [
    "breaking", "urgent", "developing", "attack", "missile", "strike",
    "ceasefire", "tariff", "fed", "rate", "oil", "bitcoin", "surge",
    "slump", "crash", "default", "bankruptcy", "sanction", "hormuz",
    "iran", "israel", "war",
]
VIRAL_BREAKING_MARKERS = (
    "assassination",
    "assassination attempt",
    "shot",
    "shooting",
    "gunman",
    "gunfire",
    "opened fire",
    "wounded",
    "killed",
    "attempt on his life",
    "attempt on life",
    "총격",
    "피격",
    "assassinate",
)


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


_URL_SLUG_DATE = re.compile(r"/(20\d{2})/(\d{1,2})/(\d{1,2})/")


def article_url_slug_year_stale(article: Dict[str, Any]) -> bool:
    """
    원문 URL에 /YYYY/MM/DD/ 형태가 있고 YYYY가 현재 연도보다 이전이면,
    publishedAt이 최근으로 잘못 온 재노출·구기사를 배제한다(예: .../markets/2024/05/13/...).
    """
    url = str(article.get("url") or "").replace("\\", "/")
    m = _URL_SLUG_DATE.search(url)
    if not m:
        return False
    try:
        y = int(m.group(1))
    except ValueError:
        return False
    return y < _now_utc().year


def _filter_articles_freshness(
    articles: List[Dict[str, Any]], *, hours_back: int
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for a in articles or []:
        if is_sports_article(a):
            continue
        if not published_recent_enough(a, hours=hours_back):
            continue
        if article_url_slug_year_stale(a):
            continue
        out.append(a)
    return out


def dedup_key(article: Dict[str, Any]) -> str:
    title = clean_spaces(article.get("title", "")).lower()
    title = re.sub(r"[^a-z0-9가-힣\s]", " ", title)
    return re.sub(r"\s+", " ", title).strip()[:120]


def has_market_impact(article: Dict[str, Any]) -> bool:
    text = article_text(article)
    if any(k in text for k in MARKET_KEYWORDS):
        return True
    return bool(_WON_CURRENCY_RE.search(text))


def has_high_impact(article: Dict[str, Any]) -> bool:
    text = article_text(article)
    if any(k in text for k in HIGH_IMPACT_KEYWORDS):
        return True
    return bool(_WON_CURRENCY_RE.search(text))


def is_low_quality_text(article: Dict[str, Any]) -> bool:
    title = clean_spaces(article.get("title", ""))
    desc = clean_spaces(article.get("description", "") or article.get("content", "") or "")
    text = f"{title} {desc}".lower()
    if is_viral_breaking(article) and len(title) >= 12:
        return any(p in text for p in LOW_QUALITY_PATTERNS)
    if len(title) < 18 or len(desc) < 40:
        return True
    if any(p in text for p in LOW_QUALITY_PATTERNS):
        return True
    return False


def is_press_release_wire(article: Dict[str, Any]) -> bool:
    """
    정식 매체 도메인에 올라오는 PR·배포용 보도(예: AP press-release + PR Newswire) 제외.
    """
    raw_u = str(article.get("url") or "").strip()
    u = raw_u.lower()
    path = ""
    try:
        path = urlparse(u).path.lower() if u else ""
    except Exception:
        path = ""
    if "/press-release" in path or "/press_releases/" in path or "/press-room/" in path:
        return True
    if any(
        x in u
        for x in (
            "prnewswire",
            "pr-newswire",
            "businesswire.com",
            "globenewswire",
            "accesswire.com",
        )
    ):
        return True
    title_l = clean_spaces(article.get("title", "") or "").lower()
    blob = article_text(article)
    needles = (
        "issued on behalf",
        "on behalf of",
        "not for distribution",
        "for immediate release",
        "press release:",
        "(press release)",
        "pr newswire",
        "via business wire",
        "globenewswire",
    )
    return any(n in title_l or n in blob for n in needles)


def is_viral_breaking(article: Dict[str, Any]) -> bool:
    """트럼프 총격·암살 시도 등 — 카드뉴스 우선."""
    if not trusted_article(article):
        return False
    text = article_text(article).lower()
    title = clean_spaces(article.get("title", "")).lower()
    if any(m in text or m in title for m in VIRAL_BREAKING_MARKERS):
        if any(
            k in text or k in title
            for k in (
                "trump",
                "president",
                "white house",
                "fed",
                "iran",
                "war",
                "oil",
                "market",
                "bitcoin",
            )
        ):
            return True
        if "trump" in text or "trump" in title:
            return True
        if any(m in title for m in ("assassination", "shooting", "shot", "gunman")):
            return True
    if "breaking" in title and any(
        k in title for k in ("trump", "shot", "shooting", "assassination", "attack")
    ):
        return True
    return False


def is_breaking_candidate(article: Dict[str, Any]) -> bool:
    if is_viral_breaking(article):
        return True
    text = article_text(article)
    title = clean_spaces(article.get("title", "")).lower()
    hit = sum(1 for k in BREAKING_KEYWORDS if k in text)
    if not trusted_article(article):
        return False
    if not has_market_impact(article) and not is_viral_breaking(article):
        return False
    if hit >= 2:
        return True
    return any(x in title for x in ["ceasefire", "missile", "attack", "tariff", "fed", "rate", "oil", "bitcoin"])


def instagram_card_min_score() -> int:
    try:
        return max(80, int((os.getenv("INSTAGRAM_CARD_MIN_SCORE") or "100").strip()))
    except ValueError:
        return 100


def is_mandatory_mainstream_card_topic(article: Dict[str, Any]) -> bool:
    """
    인스타 카드 — 대중·흥미 훅이 없으면 무조건 제외.
    속보·코스피·버핏·전쟁·스캔들·대형 급변·지수 돌파만 통과.
    """
    if is_viral_breaking(article):
        return True
    if is_niche_crypto_product_article(article):
        return False
    text = article_text(article).lower()
    title_l = clean_spaces(article.get("title", "") or "").lower()
    blob = f"{title_l} {text}"
    for k in OBSCURE_CARD_PENALTY:
        if k in blob:
            return False
    boring = (
        "vault",
        "unveils",
        "launches product",
        "new feature",
        "podcast",
        "newsletter",
        "opinion column",
    )
    if any(k in blob for k in boring) and not any(
        k in blob for k in MANDATORY_CARD_HOOK_ALWAYS
    ):
        return False
    if any(k in blob for k in MANDATORY_CARD_HOOK_ALWAYS):
        return True
    has_move = any(m in blob for m in CARD_HOOK_MOVE_WORDS) or bool(
        re.search(r"\d", title_l)
    )
    if not has_move:
        return False
    if any(k in blob for k in MANDATORY_CARD_HOOK_WITH_MOVE):
        if any(k in blob for k in ("bitcoin", "btc")):
            return any(k in blob for k in CRYPTO_PRICE_MOVE_MARKERS)
        return True
    if re.search(r"\b(record|milestone|all[- ]time|historic)\b", blob):
        return True
    return False


def is_niche_crypto_product_article(article: Dict[str, Any]) -> bool:
    """거래소·디파이 상품 출시 등 — BTC 시세 급변 뉴스는 제외하지 않음."""
    if is_viral_breaking(article):
        return False
    text = article_text(article).lower()
    title_l = clean_spaces(article.get("title", "") or "").lower()
    blob = f"{title_l} {text}"
    if not any(k in blob for k in ("bitcoin", "btc", "crypto", "ethereum", "eth", "defi")):
        return False
    if any(k in blob for k in CRYPTO_PRICE_MOVE_MARKERS):
        return False
    product_hit = sum(1 for m in NICHE_CRYPTO_PRODUCT_MARKERS if m in blob)
    if product_hit >= 2:
        return True
    if product_hit >= 1 and any(
        k in blob for k in ("unveil", "vault", "launch", "introduce", "yield", "staking", "holders")
    ):
        return True
    return False


def score_instagram_card_article(article: Dict[str, Any]) -> int:
    """인스타 카드뉴스 선별용 — 메인스트림·대중 이슈 우선, 니치 크립토·무관 주제 감점."""
    if not is_mandatory_mainstream_card_topic(article):
        return -999
    if is_niche_crypto_product_article(article):
        return -999
    score = score_article(article)
    text = article_text(article)
    title_l = clean_spaces(article.get("title", "") or "").lower()
    blob = f"{title_l} {text}"
    for keys, bonus in INSTAGRAM_CARD_BOOST_GROUPS:
        if any(k in blob for k in keys):
            score += bonus
    if re.search(r"\b\d{3,5}\b", blob) and any(
        k in blob for k in ("kospi", "kosdaq", "코스피", "index", "s&p", "nasdaq", "dow")
    ):
        score += 28
    if any(k in blob for k in ("buffett", "berkshire")) and any(
        k in blob for k in ("buy", "sell", "stake", "purchase", "매수", "매도", "지분")
    ):
        score += 35
    if "bitcoin" in blob or "btc" in blob:
        if not any(k in blob for k in CRYPTO_PRICE_MOVE_MARKERS):
            score -= 25
    return score


def score_article(article: Dict[str, Any]) -> int:
    text = article_text(article)
    title_l = clean_spaces(article.get("title", "") or "").lower()
    score = 0
    if is_viral_breaking(article):
        score += 120
    if domain_is_trusted(article_domain(article)):
        score += 40
    if source_name_is_trusted(article_source_name(article)):
        score += 20
    if published_recent_enough(article, hours=24):
        score += 10
    if published_recent_enough(article, hours=6):
        score += 12
    if re.search(r"\d", text):
        score += 8
    for k in MARKET_KEYWORDS:
        if k in text:
            score += 4
    for k in HIGH_IMPACT_KEYWORDS:
        if k in text:
            score += 5
    for k in POPULAR_CARD_KEYWORDS:
        if k in text or k in title_l:
            score += 9
    if any(k in text or k in title_l for k in ("kospi", "kosdaq", "코스피", "코스닥")):
        score += 25
    if re.search(r"\b(record|milestone|all[- ]time|historic|breaks?\s+\d)\b", text):
        score += 18
    for k in OBSCURE_CARD_PENALTY:
        if k in text or k in title_l:
            score -= 45
    if is_breaking_candidate(article):
        score += 20
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


def _fetch_newsapi_articles(
    query: str,
    *,
    limit: int = 30,
    hours_back: int = 12,
    require_high_impact: bool = True,
) -> List[Dict[str, Any]]:
    if not API_KEY:
        return []
    params = {
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": min(max(limit, 10), 100),
        "from": (_now_utc() - timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "apiKey": API_KEY,
    }
    try:
        data = requests.get("https://newsapi.org/v2/everything", params=params, timeout=20).json()
    except Exception as e:
        print(f"[news] extra query failed: {repr(e)}")
        return []
    if data.get("status") != "ok":
        return []
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for article in data.get("articles", []) or []:
        if not trusted_article(article):
            continue
        if is_sports_article(article):
            continue
        if require_high_impact and not has_market_impact(article) and not is_viral_breaking(article):
            continue
        if is_low_quality_text(article):
            continue
        if is_press_release_wire(article):
            continue
        if not published_recent_enough(article, hours=hours_back):
            continue
        if article_url_slug_year_stale(article):
            continue
        key = dedup_key(article)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(article)
    return out


def fetch_news_for_cards(limit: int = 40, hours_back: int = 12) -> List[Dict[str, Any]]:
    """카드뉴스용 — 속보(총격·암살 등) 우선 병합."""
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _add(batch: List[Dict[str, Any]]) -> None:
        for a in batch or []:
            k = dedup_key(a)
            if k and k not in seen:
                seen.add(k)
                merged.append(a)

    hb = max(6, min(hours_back, 36))
    _add(_fetch_newsapi_articles(VIRAL_SEARCH_QUERY, limit=25, hours_back=hb, require_high_impact=False))
    _add(
        _fetch_newsapi_articles(
            KOREA_MARKET_SEARCH_QUERY, limit=20, hours_back=hb, require_high_impact=False
        )
    )
    _add(
        _fetch_newsapi_articles(
            MAINSTREAM_CARD_SEARCH_QUERY, limit=22, hours_back=hb, require_high_impact=False
        )
    )
    _add(fetch_breaking_news(limit=20, hours_back=hb))
    _add(fetch_news(limit=limit, hours_back=hb))

    def _sort_key(a: Dict[str, Any]) -> tuple:
        return (1 if is_viral_breaking(a) else 0, score_instagram_card_article(a))

    merged.sort(key=_sort_key, reverse=True)
    if merged:
        print(
            f"[news] fetch_news_for_cards n={len(merged)} "
            f"viral_top={is_viral_breaking(merged[0])}"
        )
    return merged[:limit]


def fetch_news(limit: int = 40, hours_back: int = 36) -> List[Dict[str, Any]]:
    cached = get_cached_articles(max_age_hours=6)
    if USE_CACHED_NEWS and cached:
        filtered_cache = [
            a
            for a in cached
            if not is_press_release_wire(a)
            and not is_sports_article(a)
            and published_recent_enough(a, hours=hours_back)
            and not article_url_slug_year_stale(a)
        ]
        if filtered_cache:
            print("[비용절약] USE_CACHED_NEWS=true, 캐시 뉴스 사용(기사별 날짜·URL 연도 재검증)")
            return filtered_cache[:limit]
        print("[뉴스] 캐시 사용 불가(만료·PR·날짜·URL연도 제외 등) — API로 다시 가져옵니다")
    if not API_KEY:
        return _filter_articles_freshness(cached, hours_back=hours_back)

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
        return _filter_articles_freshness(cached, hours_back=hours_back)
    if data.get("status") != "ok":
        print("뉴스 API 응답 이상:", data)
        return _filter_articles_freshness(cached, hours_back=hours_back)

    filtered: List[Dict[str, Any]] = []
    seen = set()
    for article in data.get("articles", []) or []:
        if not trusted_article(article):
            continue
        if is_sports_article(article):
            continue
        if not has_market_impact(article):
            continue
        if not has_high_impact(article):
            continue
        if is_low_quality_text(article):
            continue
        if is_press_release_wire(article):
            continue
        if not published_recent_enough(article, hours=hours_back):
            continue
        if article_url_slug_year_stale(article):
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
    return _filter_articles_freshness(cached, hours_back=hours_back)


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
