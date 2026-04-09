import json
import os
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from news import get_news_candidate
from rewrite_v2 import rewrite
from polymarket import get_polymarket_markets, classify_topic
from rewrite_poly_v2 import rewrite_poly
from card_v2 import create_card, create_carousel
from telegram_new import send_image
from market_state import detect_surge, update_market_snapshot
from memory import is_duplicate, add_history, is_same_topic, add_topic
from instagram_v2 import upload_carousel, upload_single, build_caption

MIX_FILE = "source_mix.json"
BREAKING_STATE_FILE = "breaking_state.json"

ALLOWED_TOPICS = {"geopolitics", "economy", "crypto"}
POLY_MIN_SCORE = 78
NEWS_MIN_SCORE = 70
BREAKING_NEWS_MIN_SCORE = 90
BREAKING_POLY_MIN_SCORE = 94
BREAKING_COOLDOWN_MINUTES = 180

REGULAR_POST_HOURS = {8, 19}
REGULAR_POST_MINUTE_WINDOW = 9

USE_CAROUSEL = os.getenv("USE_CAROUSEL", "false").lower() == "true"
TEST_FORCE_POST = os.getenv("TEST_FORCE_POST", "false").lower() == "true"


KST = ZoneInfo("Asia/Seoul")


def now_local():
    return datetime.now(KST)


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_mix():
    return load_json_file(MIX_FILE, [])


def save_mix(data):
    save_json_file(MIX_FILE, data[-40:])


def add_mix(source_name):
    data = load_mix()
    data.append(source_name)
    save_mix(data)


def recent_poly_count(n=6):
    return sum(1 for x in load_mix()[-n:] if x == "polymarket")


def recent_news_count(n=6):
    return sum(1 for x in load_mix()[-n:] if x == "news")


def source_bias():
    if recent_poly_count(6) >= 4:
        return "news_strong"
    if recent_news_count(6) <= 1:
        return "news_preferred"
    return "balanced"


def load_breaking_state():
    return load_json_file(BREAKING_STATE_FILE, {"items": []})


def save_breaking_state(state):
    items = state.get("items", [])
    state["items"] = items[-80:]
    save_json_file(BREAKING_STATE_FILE, state)


def was_recent_breaking(key, minutes=BREAKING_COOLDOWN_MINUTES):
    state = load_breaking_state()
    items = state.get("items", [])
    cutoff = now_local() - timedelta(minutes=minutes)
    for item in reversed(items):
        if item.get("key") != key:
            continue
        try:
            ts = datetime.fromisoformat(item["ts"])
            if ts >= cutoff:
                return True
        except Exception:
            continue
    return False


def mark_breaking_posted(key, source, title):
    state = load_breaking_state()
    state["items"].append({
        "key": key,
        "source": source,
        "title": title,
        "ts": now_local().isoformat(timespec="seconds"),
    })
    save_breaking_state(state)


def detect_poly_mode(question, topic, is_surge=False):
    text = question.lower()
    if is_surge:
        return "alert"
    if topic == "crypto":
        return "alert"
    if topic == "economy" and any(k in text for k in ["oil", "wti", "crude", "gold", "fed", "inflation", "tariff", "yield", "cpi"]):
        return "alert"
    if topic == "geopolitics" and any(k in text for k in ["ceasefire", "war", "attack", "hormuz", "oil"]):
        return "alert"
    return "normal"


def detect_news_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in [
        "breaking", "tariff", "bitcoin", "oil", "gold", "fed", "inflation",
        "war", "attack", "yield", "cpi", "hormuz", "missile", "record", "plunge"
    ]):
        return "alert"
    return "normal"


def score_news_candidate(title, summary, rewritten):
    text = f"{title} {summary}".lower()
    out = f"{rewritten['eyebrow']} {rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"
    score = 0
    for k in [
        "bitcoin", "btc", "oil", "wti", "crude", "gold", "fed", "inflation",
        "cpi", "yield", "tariff", "nasdaq", "dow", "s&p", "hormuz", "iran", "dollar"
    ]:
        if k in text:
            score += 16
    if any(k in text for k in ["attack", "missile", "strike", "surge", "plunge", "ceasefire", "record", "ban", "approved"]):
        score += 22
    if any(k in out for k in ["달러", "물가", "나스닥", "유가", "금값", "비트", "생활비", "금리", "코인"]):
        score += 18
    if any(ch.isdigit() for ch in rewritten.get("title1", "")):
        score += 14
    return score


def score_poly_candidate(question, volume, yes_price, rewritten, is_surge=False):
    text = question.lower()
    score = 0
    try:
        v = float(volume)
        if v >= 15_000_000:
            score += 42
        elif v >= 8_000_000:
            score += 36
        elif v >= 4_000_000:
            score += 28
        elif v >= 1_500_000:
            score += 20
    except Exception:
        pass
    try:
        p = float(yes_price)
        if 0.10 <= p <= 0.90:
            score += 18
        if 0.20 <= p <= 0.80:
            score += 10
    except Exception:
        pass
    for k in [
        "bitcoin", "btc", "ethereum", "eth", "oil", "wti", "crude", "gold",
        "fed", "inflation", "cpi", "yield", "tariff", "nasdaq", "hormuz", "dollar"
    ]:
        if k in text:
            score += 14
    if any(k in text for k in ["iran", "war", "attack", "missile", "ceasefire"]):
        if any(k in text for k in ["oil", "gold", "hormuz", "crude", "wti"]):
            score += 14
        else:
            score -= 18
    if is_surge:
        score += 22
    return score


def rewritten_topic_key(question):
    q = question.lower()
    if any(k in q for k in ["bitcoin", "btc"]):
        return "btc"
    if any(k in q for k in ["ethereum", "eth"]):
        return "eth"
    if any(k in q for k in ["oil", "wti", "crude", "hormuz"]):
        return "oil"
    if "gold" in q:
        return "gold"
    if any(k in q for k in ["fed", "rate", "inflation", "cpi", "yield"]):
        return "macro"
    if any(k in q for k in ["tariff", "trade deal", "deal"]):
        return "trade"
    if any(k in q for k in ["war", "attack", "ceasefire", "iran", "israel"]):
        return "mideast"
    if any(k in q for k in ["nasdaq", "s&p", "dow"]):
        return "stocks"
    return "general"


def is_major_breaking_news(title, summary, score):
    text = f"{title} {summary}".lower()
    strong_keywords = [
        "breaking", "urgent", "attack", "missile", "explosion", "war", "ceasefire",
        "tariff", "emergency", "fed", "cpi", "inflation", "rate cut",
        "bitcoin", "btc", "ethereum", "eth", "oil", "gold", "hormuz", "record", "ban"
    ]
    if score < BREAKING_NEWS_MIN_SCORE:
        return False
    if sum(1 for k in strong_keywords if k in text) < 1:
        return False
    if any(w in text for w in ["could", "may", "might", "opinion", "analysis", "rumor"]):
        return False
    return True


def is_major_breaking_poly(question, volume, yes_price, score, is_surge):
    text = question.lower()
    try:
        v = float(volume)
    except Exception:
        v = 0.0
    try:
        p = float(yes_price)
    except Exception:
        p = 0.0
    impact_keywords = [
        "bitcoin", "btc", "ethereum", "eth", "oil", "gold", "fed",
        "cpi", "inflation", "hormuz", "tariff"
    ]
    if score < BREAKING_POLY_MIN_SCORE:
        return False
    if not any(k in text for k in impact_keywords):
        return False
    if not is_surge and v < 8_000_000:
        return False
    if p <= 0.03 or p >= 0.97:
        if not is_surge and v < 15_000_000:
            return False
    return True


def build_news_candidate():
    article = get_news_candidate()
    if not article:
        return None
    title = article["title"]
    summary = article["description"]
    topic = classify_topic(title, summary)
    if topic not in ALLOWED_TOPICS:
        return None
    mode = detect_news_mode(title, summary)
    rewritten = rewrite(title, summary, mode=mode)
    score = score_news_candidate(title, summary, rewritten)
    if score < NEWS_MIN_SCORE:
        return None
    return {
        "source": "news",
        "raw_title": title,
        "raw_summary": summary,
        "mode": mode,
        "topic": topic,
        "rewritten": rewritten,
        "score": score,
    }


def build_poly_candidates():
    markets = get_polymarket_markets(limit=180)
    candidates = []
    seen_topics = set()
    for market in markets[:90]:
        question = market["question"]
        description = market.get("description", "")
        topic = classify_topic(question, description)
        if topic not in ALLOWED_TOPICS:
            continue
        if is_duplicate(question):
            continue
        theme = rewritten_topic_key(question)
        if theme in seen_topics:
            continue
        surge = detect_surge(question=question, volume=market["volume"], yes_price=market["yes_price"])
        mode = detect_poly_mode(question, topic, is_surge=surge)
        rewritten = rewrite_poly(
            question=question,
            volume=market["volume"],
            yes_price=market["yes_price"],
            end_date=market["end_date"],
        )
        score = score_poly_candidate(question, market["volume"], market["yes_price"], rewritten, is_surge=surge)
        if score < POLY_MIN_SCORE:
            continue
        candidates.append({
            "source": "polymarket",
            "raw_title": question,
            "raw_summary": description,
            "mode": mode,
            "topic": topic,
            "rewritten": rewritten,
            "score": score,
            "volume": market["volume"],
            "yes_price": market["yes_price"],
            "end_date": market["end_date"],
            "is_surge": surge,
        })
        seen_topics.add(theme)
        if len(candidates) >= 12:
            break
    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def choose_winner():
    news_candidate = build_news_candidate()
    poly_candidates = build_poly_candidates()
    best_poly = poly_candidates[0] if poly_candidates else None
    bias = source_bias()
    if bias == "news_strong" and news_candidate:
        return news_candidate
    if bias == "news_preferred" and news_candidate:
        if best_poly is None or news_candidate["score"] >= best_poly["score"] - 4:
            return news_candidate
    if news_candidate and best_poly:
        if news_candidate["score"] >= best_poly["score"] + 6:
            return news_candidate
        if best_poly["score"] >= news_candidate["score"] + 10:
            return best_poly
        return random.choice([news_candidate, best_poly])
    return news_candidate or best_poly


def choose_breaking_winner():
    news_candidate = build_news_candidate()
    poly_candidates = build_poly_candidates()
    breaking_candidates = []
    if news_candidate and is_major_breaking_news(news_candidate["raw_title"], news_candidate["raw_summary"], news_candidate["score"]):
        breaking_candidates.append(news_candidate)
    for c in poly_candidates[:5]:
        if is_major_breaking_poly(c["raw_title"], c["volume"], c["yes_price"], c["score"], c["is_surge"]):
            breaking_candidates.append(c)
    if not breaking_candidates:
        return None
    breaking_candidates.sort(key=lambda x: x["score"], reverse=True)
    winner = breaking_candidates[0]
    if was_recent_breaking(winner["raw_title"].strip().lower()):
        return None
    return winner


def post_candidate(candidate, is_breaking=False):
    if not candidate:
        return False
    rewritten = candidate["rewritten"]
    mode = candidate["mode"]
    raw_title = candidate["raw_title"]
    if is_same_topic(candidate["topic"]):
        print("[스킵] 같은 토픽 연속 방지:", candidate["topic"])
        return False
    try:
        if USE_CAROUSEL:
            image_paths = create_carousel(rewritten, mode=mode)
            caption = build_caption(rewritten, topic_key=rewritten.get("_key", "GENERAL"), is_breaking=is_breaking)
            post_id = upload_carousel(image_paths, caption)
            if image_paths:
                send_image(image_paths[0], caption=caption[:900])
        else:
            image_path = create_card(rewritten, mode=mode)
            caption = build_caption(rewritten, topic_key=rewritten.get("_key", "GENERAL"), is_breaking=is_breaking)
            post_id = upload_single(image_path, caption)
            send_image(image_path, caption=caption[:900])
        if not post_id:
            print("[업로드 실패] 인스타 응답 없음")
            return False
        add_history(raw_title)
        add_topic(candidate["topic"])
        add_mix(candidate["source"])
        if candidate["source"] == "polymarket":
            update_market_snapshot(question=candidate["raw_title"], volume=candidate["volume"], yes_price=candidate["yes_price"])
        if is_breaking:
            mark_breaking_posted(key=raw_title.strip().lower(), source=candidate["source"], title=raw_title)
        print("[업로드 완료]", raw_title)
        return True
    except Exception as e:
        print("[업로드 실패]", e)
        return False


def should_run_regular_post():
    if TEST_FORCE_POST:
        return True
    now = now_local()
    return now.hour in REGULAR_POST_HOURS and now.minute <= REGULAR_POST_MINUTE_WINDOW


def main():
    print(f"[시작] {now_local().isoformat(timespec='seconds')}")
    breaking = choose_breaking_winner()
    if breaking:
        print("[속보 후보]", breaking["raw_title"])
        if post_candidate(breaking, is_breaking=True):
            return
    if should_run_regular_post():
        candidate = choose_winner()
        if candidate:
            print("[일반 후보]", candidate["raw_title"])
            post_candidate(candidate, is_breaking=False)
        else:
            print("[일반 후보] 없음")
    else:
        print("[일반 포스팅 시간 아님]")


if __name__ == "__main__":
    main()
