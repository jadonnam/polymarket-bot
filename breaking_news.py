"""
breaking_news.py — 속보 감지 즉시 업로드 시스템

작동 방식:
- NewsAPI에서 최신 기사 수집
- 속보 키워드 감지 시 즉시 카드 생성 + 업로드
- 중복 방지: 이미 올린 속보는 스킵
- Railway에서 10분마다 실행 (Cron: */10 * * * *)
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
BREAKING_FILE = "breaking_history.json"

# ── 속보 트리거 키워드 (이게 뜨면 즉시 업로드) ──────────────
BREAKING_TRIGGERS = [
    # 전쟁/충돌
    "war declared", "military strike", "troops enter", "missile attack",
    "nuclear", "ceasefire agreement", "invasion",
    # 경제 쇼크
    "emergency rate", "rate cut surprise", "fed emergency",
    "market crash", "circuit breaker", "trading halted",
    "bankruptcy", "default",
    # 트럼프 즉각 반응
    "trump signs", "trump declares", "trump announces tariff",
    "executive order",
    # 코인 급변
    "bitcoin crashes", "bitcoin surges", "crypto crash",
    "etf approved", "etf rejected",
    # 유가 급변
    "oil embargo", "opec emergency", "oil supply cut",
    "strait of hormuz", "oil pipeline",
    # 기타 시장 쇼크
    "fed chair", "treasury secretary", "imf warning",
    "bank run", "silicon valley bank", "lehman",
]

# ── 속보 점수 계산 ────────────────────────────────────────
def is_breaking(title, description=""):
    text = f"{title} {description}".lower()
    score = 0

    for kw in BREAKING_TRIGGERS:
        if kw in text:
            score += 30

    # 속보 표현
    if any(w in text for w in ["breaking", "urgent", "just in", "alert", "developing"]):
        score += 20

    # 고중요도 키워드
    if any(w in text for w in ["trump", "fed", "bitcoin", "oil", "gold", "war"]):
        score += 10

    return score >= 30


def load_breaking_history():
    if not os.path.exists(BREAKING_FILE):
        return []
    try:
        with open(BREAKING_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_breaking_history(data):
    with open(BREAKING_FILE, "w") as f:
        json.dump(data[-100:], f, ensure_ascii=False)


def is_breaking_duplicate(title):
    history = load_breaking_history()
    return title in history


def add_breaking_history(title):
    history = load_breaking_history()
    history.append(title)
    save_breaking_history(history)


def fetch_breaking_news():
    """최근 30분 이내 속보 기사 수집"""
    if not NEWS_API_KEY:
        return []

    from_time = (datetime.utcnow() - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S")

    url = "https://newsapi.org/v2/everything"
    params = {
        "q": (
            '("breaking" OR "urgent" OR "just in") AND '
            '("trump" OR "fed" OR "bitcoin" OR "oil" OR "war" OR "gold" OR "tariff" OR "rate")'
        ),
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 20,
        "from": from_time,
        "apiKey": NEWS_API_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        if data.get("status") != "ok":
            return []
        return data.get("articles", [])
    except:
        return []


def get_best_breaking():
    """가장 중요한 속보 반환"""
    articles = fetch_breaking_news()
    if not articles:
        return None

    best = None
    best_score = 0

    for article in articles:
        title = article.get("title", "")
        desc  = article.get("description", "") or ""

        if not title or len(title) < 15:
            continue
        if is_breaking_duplicate(title):
            continue

        score = is_breaking(title, desc)
        if score > best_score:
            best_score = score
            best = article

    if not best or best_score < 30:
        return None

    return {
        "title":       best.get("title", ""),
        "description": best.get("description", "") or "",
        "source":      best.get("source", {}).get("name", ""),
        "is_breaking": True,
    }


def run_breaking_check():
    """
    속보 감지 → 즉시 업로드
    Railway Cron: */10 * * * * (10분마다)
    """
    from rewrite_v2 import rewrite
    from card_v3 import create_card, create_carousel
    from telegram_new import send_image
    from instagram_v2 import upload_carousel, upload_single, build_caption
    from memory import add_history, add_topic
    from polymarket import classify_topic

    print(f"[속보 체크] {datetime.utcnow().strftime('%H:%M:%S')}")

    article = get_best_breaking()
    if not article:
        print("[속보] 없음")
        return False

    title   = article["title"]
    desc    = article["description"]
    topic   = classify_topic(title, desc)

    print(f"[속보 감지!] {title}")

    rewritten = rewrite(title, desc, mode="alert")
    topic_key = rewritten.get("_key", "GENERAL")

    USE_CAROUSEL = os.getenv("USE_CAROUSEL", "true").lower() == "true"

    if USE_CAROUSEL:
        card_paths = create_carousel(rewritten, mode="alert")
    else:
        card_paths = [create_card(rewritten, mode="alert")]

    # 텔레그램
    send_image(card_paths[0])
    print("[속보] 텔레그램 전송 완료")

    # 인스타
    caption = build_caption(rewritten, topic_key=topic_key, is_breaking=True)
    caption = "🚨 속보\n\n" + caption
    if USE_CAROUSEL and len(card_paths) >= 3:
        post_id = upload_carousel(card_paths, caption)
    else:
        post_id = upload_single(card_paths[0], caption)

    if post_id:
        print(f"[속보] 인스타 업로드 완료: {post_id}")

    add_breaking_history(title)
    add_history(title)
    add_topic(topic)

    return True


if __name__ == "__main__":
    run_breaking_check()
