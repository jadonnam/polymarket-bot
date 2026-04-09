import os
import json
import requests
from datetime import datetime, timedelta

NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
BREAKING_FILE = "breaking_history.json"

BREAKING_TRIGGERS = [
    "war declared", "military strike", "troops enter", "missile attack", "nuclear",
    "ceasefire agreement", "invasion", "explosion", "emergency rate", "rate cut surprise",
    "fed emergency", "market crash", "circuit breaker", "trading halted", "bankruptcy",
    "default", "trump announces tariff", "executive order", "bitcoin crashes", "bitcoin surges",
    "crypto crash", "etf approved", "etf rejected", "oil embargo", "opec emergency",
    "oil supply cut", "strait of hormuz", "oil pipeline", "gold surges",
]

PRIORITY_WORDS = [
    "trump", "fed", "bitcoin", "oil", "gold", "war", "inflation",
    "tariff", "hormuz", "missile", "attack", "record", "ban"
]


def is_breaking(title, description=""):
    text = f"{title} {description}".lower()
    score = 0
    for kw in BREAKING_TRIGGERS:
        if kw in text:
            score += 30
    if any(w in text for w in ["breaking", "urgent", "just in", "alert", "developing"]):
        score += 20
    if any(w in text for w in PRIORITY_WORDS):
        score += 12
    if any(w in text for w in ["could", "may", "might", "opinion", "analysis", "rumor"]):
        score -= 16
    return score


def load_breaking_history():
    if not os.path.exists(BREAKING_FILE):
        return []
    try:
        with open(BREAKING_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_breaking_history(data):
    with open(BREAKING_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-100:], f, ensure_ascii=False, indent=2)


def is_breaking_duplicate(title):
    return title in load_breaking_history()


def add_breaking_history(title):
    history = load_breaking_history()
    history.append(title)
    save_breaking_history(history)


def fetch_breaking_news():
    if not NEWS_API_KEY:
        return []
    from_time = (datetime.utcnow() - timedelta(minutes=45)).strftime("%Y-%m-%dT%H:%M:%S")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": '("breaking" OR "urgent" OR "just in" OR "alert" OR "developing") AND ("trump" OR "fed" OR "bitcoin" OR "oil" OR "war" OR "gold" OR "tariff" OR "rate" OR "hormuz")',
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 25,
        "from": from_time,
        "apiKey": NEWS_API_KEY,
    }
    try:
        res = requests.get(url, params=params, timeout=15)
        data = res.json()
        if data.get("status") != "ok":
            return []
        return data.get("articles", [])
    except Exception:
        return []


def get_best_breaking():
    articles = fetch_breaking_news()
    if not articles:
        return None
    best = None
    best_score = 0
    for article in articles:
        title = article.get("title", "")
        desc = article.get("description", "") or ""
        if not title or len(title) < 18:
            continue
        if is_breaking_duplicate(title):
            continue
        score = is_breaking(title, desc)
        if score > best_score:
            best_score = score
            best = article
    if not best or best_score < 42:
        return None
    return {
        "title": best.get("title", ""),
        "description": best.get("description", "") or "",
        "source": best.get("source", {}).get("name", ""),
        "is_breaking": True,
    }


def run_breaking_check():
    from rewrite_v2 import rewrite
    from card_v2 import create_card, create_carousel
    from telegram_new import send_image
    from instagram_v2 import upload_carousel, upload_single, build_caption
    from memory import add_history, add_topic
    from polymarket import classify_topic

    print(f"[속보 체크] {datetime.utcnow().strftime('%H:%M:%S')}")
    article = get_best_breaking()
    if not article:
        print("[속보] 없음")
        return False

    title = article["title"]
    desc = article["description"]
    topic = classify_topic(title, desc)
    rewritten = rewrite(title, desc, mode="alert")
    caption = build_caption(rewritten, topic_key=rewritten.get("_key", "GENERAL"), is_breaking=True)
    use_carousel = os.getenv("USE_CAROUSEL", "false").lower() == "true"

    try:
        if use_carousel:
            image_paths = create_carousel(rewritten, mode="alert")
            post_id = upload_carousel(image_paths, caption)
            if image_paths:
                send_image(image_paths[0], caption=caption[:900])
        else:
            image_path = create_card(rewritten, mode="alert")
            post_id = upload_single(image_path, caption)
            send_image(image_path, caption=caption[:900])

        if not post_id:
            print("[속보 업로드 실패] 인스타 응답 없음")
            return False

        add_breaking_history(title)
        add_history(title)
        add_topic(topic)
        print("[속보 업로드 완료]", title)
        return True

    except Exception as e:
        print("[속보 업로드 실패]", e)
        return False
