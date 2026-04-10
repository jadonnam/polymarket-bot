import json
import os
from datetime import datetime, timedelta, timezone

from news import get_news_candidate
from rewrite_v2 import rewrite
from polymarket import get_polymarket_markets, classify_topic
from rewrite_poly_v2 import rewrite_poly
from card_v2 import create_card, create_carousel
from telegram_new import send_image
from market_state import detect_surge, update_market_snapshot
from memory import is_duplicate, add_history, is_same_topic, add_topic
from instagram_v2 import upload_instagram

MIX_FILE = "source_mix.json"
BREAKING_STATE_FILE = "breaking_state.json"
REGULAR_STATE_FILE = "regular_post_state.json"

ALLOWED_TOPICS = {"geopolitics", "economy", "crypto"}

REGULAR_POST_HOURS = {8, 19}
REGULAR_POST_MINUTE_WINDOW = 20

BREAKING_NEWS_MIN_SCORE = 150
BREAKING_POLY_MIN_SCORE = 155
BREAKING_COOLDOWN_MINUTES = 720

USE_CAROUSEL = os.getenv("USE_CAROUSEL", "false").lower() == "true"
TEST_FORCE_POST = os.getenv("TEST_FORCE_POST", "false").lower() == "true"

EXTREME_KR_KEYWORDS = [
    "전쟁", "침공", "공습", "핵", "사망", "폭발", "테러",
    "붕괴", "파산", "대폭락", "긴급", "비상", "역대급", "최악"
]

EXTREME_EN_KEYWORDS = [
    "war", "invasion", "missile", "strike", "attack", "nuclear",
    "death", "dead", "killed", "explosion", "terror", "collapse",
    "bankruptcy", "crash", "emergency", "breaking", "worst ever"
]


def now_kst():
    return datetime.now(timezone.utc) + timedelta(hours=9)


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


def load_breaking_state():
    return load_json_file(BREAKING_STATE_FILE, {"items": []})


def save_breaking_state(state):
    items = state.get("items", [])
    state["items"] = items[-100:]
    save_json_file(BREAKING_STATE_FILE, state)


def load_regular_state():
    return load_json_file(REGULAR_STATE_FILE, {"last_morning_date": "", "last_evening_date": ""})


def save_regular_state(state):
    save_json_file(REGULAR_STATE_FILE, state)


def was_recent_breaking(key, minutes=BREAKING_COOLDOWN_MINUTES):
    state = load_breaking_state()
    cutoff = now_kst() - timedelta(minutes=minutes)

    for item in reversed(state.get("items", [])):
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
        "ts": now_kst().isoformat(timespec="seconds"),
    })
    save_breaking_state(state)


def contains_extreme_keyword(text):
    if not text:
        return False
    low = text.lower()
    return any(k in low for k in EXTREME_EN_KEYWORDS) or any(k in text for k in EXTREME_KR_KEYWORDS)


def current_regular_slot():
    now = now_kst()
    if now.hour == 8 and now.minute < REGULAR_POST_MINUTE_WINDOW:
        return "morning"
    if now.hour == 19 and now.minute < REGULAR_POST_MINUTE_WINDOW:
        return "evening"
    return None


def should_run_regular_post():
    if TEST_FORCE_POST:
        return True
    return current_regular_slot() is not None


def already_posted_this_slot():
    state = load_regular_state()
    today = now_kst().strftime("%Y-%m-%d")
    slot = current_regular_slot()

    if slot == "morning":
        return state.get("last_morning_date") == today
    if slot == "evening":
        return state.get("last_evening_date") == today
    return False


def mark_regular_posted():
    state = load_regular_state()
    today = now_kst().strftime("%Y-%m-%d")
    slot = current_regular_slot()

    if slot == "morning":
        state["last_morning_date"] = today
    elif slot == "evening":
        state["last_evening_date"] = today

    save_regular_state(state)


def detect_news_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in [
        "breaking", "tariff", "bitcoin", "oil", "gold", "fed",
        "inflation", "war", "attack", "yield", "cpi", "hormuz", "missile"
    ]):
        return "alert"
    return "normal"


def detect_poly_mode(question, topic, is_surge=False):
    text = question.lower()
    if is_surge:
        return "alert"
    if topic == "crypto":
        return "alert"
    if topic == "economy" and any(k in text for k in [
        "oil", "wti", "crude", "gold", "fed", "inflation", "tariff", "yield", "cpi", "dollar"
    ]):
        return "alert"
    if topic == "geopolitics" and any(k in text for k in [
        "ceasefire", "war", "attack", "hormuz", "oil"
    ]):
        return "alert"
    return "normal"


def score_news_candidate(title, summary, rewritten):
    text = f"{title} {summary}".lower()
    out = f"{rewritten.get('eyebrow','')} {rewritten.get('title1','')} {rewritten.get('title2','')} {rewritten.get('desc1','')} {rewritten.get('desc2','')}"
    score = 0

    for k in [
        "bitcoin", "btc", "oil", "wti", "crude", "gold", "fed",
        "inflation", "cpi", "yield", "tariff", "nasdaq", "dow",
        "s&p", "hormuz", "iran", "dollar", "won", "환율", "유가", "금리"
    ]:
        if k in text:
            score += 16

    if any(k in text for k in ["attack", "missile", "strike", "surge", "plunge", "ceasefire", "crash"]):
        score += 20

    if any(k in out for k in ["달러", "환율", "물가", "유가", "금값", "비트", "금리"]):
        score += 18

    if contains_extreme_keyword(title) or contains_extreme_keyword(summary):
        score += 28

    if any(ch.isdigit() for ch in rewritten.get("title1", "")):
        score += 12

    return score


def score_poly_candidate(question, volume, yes_price, rewritten, is_surge=False):
    text = question.lower()
    score = 0

    try:
        v = float(volume)
        if v >= 20_000_000:
            score += 46
        elif v >= 12_000_000:
            score += 38
        elif v >= 6_000_000:
            score += 28
        elif v >= 2_000_000:
            score += 18
    except Exception:
        pass

    try:
        p = float(yes_price)
        if 0.10 <= p <= 0.90:
            score += 18
        if 0.20 <= p <= 0.80:
            score += 10
        if p >= 0.92 or p <= 0.08:
            score += 12
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
            score += 12
        else:
            score -= 20

    if is_surge:
        score += 22

    return score


def build_news_candidate():
    article = get_news_candidate()
    if not article:
        return None

    title = article.get("title", "")
    summary = article.get("description", "")
    topic = classify_topic(title, summary)

    if topic not in ALLOWED_TOPICS:
        return None

    mode = detect_news_mode(title, summary)
    rewritten = rewrite(title, summary, mode=mode)
    score = score_news_candidate(title, summary, rewritten)

    return {
        "source": "news",
        "raw_title": title,
        "raw_summary": summary,
        "mode": mode,
        "topic": topic,
        "rewritten": rewritten,
        "score": score,
        "is_surge": False,
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

        theme_key = topic + "_" + ("btc" if "bitcoin" in question.lower() else "general")
        if theme_key in seen_topics:
            continue

        surge = detect_surge(
            question=question,
            volume=market["volume"],
            yes_price=market["yes_price"],
        )

        mode = detect_poly_mode(question, topic, is_surge=surge)
        rewritten = rewrite_poly(
            question=question,
            volume=market["volume"],
            yes_price=market["yes_price"],
            end_date=market["end_date"],
        )

        score = score_poly_candidate(
            question,
            market["volume"],
            market["yes_price"],
            rewritten,
            is_surge=surge,
        )

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
        seen_topics.add(theme_key)

        if len(candidates) >= 12:
            break

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def is_major_breaking_news(candidate):
    if not candidate:
        return False
    text = f"{candidate['raw_title']} {candidate['raw_summary']}"
    if candidate["score"] < BREAKING_NEWS_MIN_SCORE:
        return False
    if not contains_extreme_keyword(text):
        return False
    return True


def is_major_breaking_poly(candidate):
    if not candidate:
        return False

    text = candidate["raw_title"].lower()

    try:
        volume = float(candidate.get("volume", 0))
    except Exception:
        volume = 0.0

    try:
        price = float(candidate.get("yes_price", 0))
    except Exception:
        price = 0.0

    if candidate["score"] < BREAKING_POLY_MIN_SCORE:
        return False

    if volume < 18_000_000:
        return False

    if not (price >= 0.94 or price <= 0.06 or candidate.get("is_surge")):
        return False

    if not any(k in text for k in [
        "bitcoin", "btc", "ethereum", "eth", "oil", "wti", "crude", "gold",
        "war", "attack", "missile", "hormuz", "tariff", "cpi", "fed", "rate", "dollar"
    ]):
        return False

    return True


def choose_breaking_winner(news_candidate, poly_candidates):
    candidates = []

    if news_candidate and is_major_breaking_news(news_candidate):
        candidates.append(news_candidate)

    for c in poly_candidates[:3]:
        if is_major_breaking_poly(c):
            candidates.append(c)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    winner = candidates[0]
    breaking_key = winner["raw_title"].strip().lower()

    if was_recent_breaking(breaking_key):
        return None

    return winner


def choose_regular_winner(news_candidate, poly_candidates):
    slot = current_regular_slot()
    best_poly = poly_candidates[0] if poly_candidates else None

    if slot == "morning":
        morning_pool = []
        if news_candidate:
            morning_pool.append(news_candidate)

        for c in poly_candidates[:5]:
            text = c["raw_title"].lower()
            if any(k in text for k in [
                "oil", "wti", "crude", "dollar", "gold", "bitcoin", "btc",
                "war", "hormuz", "rate", "inflation", "cpi", "fed"
            ]):
                morning_pool.append(c)

        if morning_pool:
            morning_pool.sort(key=lambda x: x["score"], reverse=True)
            top = morning_pool[0]
            if news_candidate and top["source"] == "polymarket" and top["score"] <= news_candidate["score"] + 25:
                return news_candidate
            return top

    if slot == "evening":
        evening_pool = []
        if news_candidate:
            evening_pool.append(news_candidate)
        evening_pool.extend(poly_candidates[:5])

        if evening_pool:
            evening_pool.sort(key=lambda x: x["score"], reverse=True)
            top = evening_pool[0]
            if news_candidate and top["source"] == "polymarket" and top["score"] <= news_candidate["score"] + 25:
                return news_candidate
            return top

    if news_candidate and best_poly:
        if best_poly["score"] > news_candidate["score"] + 25:
            return best_poly
        return news_candidate

    if news_candidate:
        return news_candidate
    if best_poly:
        return best_poly
    return None


def build_caption(rewritten, raw_title, is_breaking=False):
    lines = []

    if is_breaking:
        lines.append("지금 시장이 크게 반응하는 이슈입니다.")
        lines.append("")

    if rewritten.get("eyebrow"):
        lines.append(rewritten["eyebrow"])
        lines.append("")

    if rewritten.get("title1"):
        lines.append(rewritten["title1"])
    if rewritten.get("title2"):
        lines.append(rewritten["title2"])
        lines.append("")

    if rewritten.get("desc1"):
        lines.append(rewritten["desc1"])
    if rewritten.get("desc2"):
        lines.append(rewritten["desc2"])
        lines.append("")

    lines.append("지갑에 영향을 주는 흐름만 정리합니다.")
    lines.append("저장해두면 다음 움직임을 볼 때 도움됩니다.")

    return "\n".join(lines).strip()


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
            image_path = image_paths[0]
        else:
            image_path = create_card(rewritten, mode=mode)

        caption = build_caption(rewritten, raw_title, is_breaking=is_breaking)

        send_image(image_path, caption=caption[:900])
        upload_instagram(image_path, caption)

        add_history(raw_title)
        add_topic(candidate["topic"])
        add_mix(candidate["source"])

        if candidate["source"] == "polymarket":
            update_market_snapshot(
                question=candidate["raw_title"],
                volume=candidate["volume"],
                yes_price=candidate["yes_price"],
            )

        if is_breaking:
            mark_breaking_posted(
                key=raw_title.strip().lower(),
                source=candidate["source"],
                title=raw_title,
            )
        else:
            mark_regular_posted()

        print("[업로드 완료]", raw_title)
        return True

    except Exception as e:
        print("[업로드 실패]", e)
        return False


def main():
    now = now_kst()
    print(f"[스케줄] 현재 시각(KST): {now.isoformat(timespec='seconds')}")

    news_candidate = build_news_candidate()
    poly_candidates = build_poly_candidates()

    breaking = choose_breaking_winner(news_candidate, poly_candidates)
    if breaking:
        print("[속보] 실행:", breaking["raw_title"])
        if post_candidate(breaking, is_breaking=True):
            return

    if should_run_regular_post():
        if already_posted_this_slot():
            print("[정규] 이번 회차 이미 업로드됨")
            return

        regular = choose_regular_winner(news_candidate, poly_candidates)
        if regular:
            slot = current_regular_slot()
            print(f"[정규 {slot}] 실행:", regular["raw_title"])
            post_candidate(regular, is_breaking=False)
        else:
            print("[정규] 후보 없음")
    else:
        print("[정규] 이번 회차 스킵")


if __name__ == "__main__":
    main()
