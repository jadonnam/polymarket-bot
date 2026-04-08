import json
import os
import random

from news import get_news_candidate
from rewrite import rewrite
from polymarket import get_polymarket_markets, classify_topic
from rewrite_poly import rewrite_poly
from card import create_card
from telegram import send_image
from market_state import detect_surge, update_market_snapshot
from memory import is_duplicate, add_history, is_same_topic, add_topic

MIX_FILE = "source_mix.json"
ALLOWED_TOPICS = {"geopolitics", "economy", "crypto", "politics"}

POLY_MIN_SCORE = 64
NEWS_MIN_SCORE = 58


def load_mix():
    if not os.path.exists(MIX_FILE):
        return []
    try:
        with open(MIX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def save_mix(data):
    with open(MIX_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-40:], f, ensure_ascii=False, indent=2)


def add_mix(source_name):
    data = load_mix()
    data.append(source_name)
    save_mix(data)


def recent_poly_count(n=6):
    data = load_mix()
    return sum(1 for x in data[-n:] if x == "polymarket")


def recent_news_count(n=6):
    data = load_mix()
    return sum(1 for x in data[-n:] if x == "news")


def source_bias():
    # 뉴스 체감 비율 더 높게
    if recent_poly_count(6) >= 4:
        return "news_strong"
    if recent_news_count(6) <= 1:
        return "news_preferred"
    return "balanced"


def detect_poly_mode(question, topic, is_surge=False):
    text = question.lower()

    if is_surge:
        return "alert"

    if topic == "crypto":
        return "alert"

    if topic == "economy" and any(k in text for k in ["oil", "wti", "crude", "gold", "fed", "inflation", "tariff", "yield", "cpi"]):
        return "alert"

    if topic in {"politics", "geopolitics"} and any(k in text for k in ["trump", "deal", "tariff", "ceasefire", "war", "attack"]):
        return "alert"

    return "normal"


def detect_news_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in ["breaking", "trump", "tariff", "bitcoin", "oil", "gold", "fed", "inflation", "war", "attack", "yield", "cpi"]):
        return "alert"
    return "normal"


def score_news_candidate(title, summary, rewritten):
    text = f"{title} {summary}".lower()
    out = f"{rewritten['eyebrow']} {rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"
    score = 0

    for k in [
        "bitcoin", "btc", "oil", "wti", "crude", "gold", "fed", "inflation",
        "cpi", "yield", "tariff", "trump", "deal", "nasdaq", "dow", "s&p"
    ]:
        if k in text:
            score += 15

    if any(k in out for k in [
        "늦으면", "또", "지갑", "숨멎", "벌써", "구경만", "들뜸",
        "처맞음", "멘붕", "식은땀", "배아픔", "난리", "쫄림"
    ]):
        score += 18

    if any(k in out for k in [
        "달러", "물가", "나스닥", "유가", "금값", "비트", "관세", "월가"
    ]):
        score += 18

    # 뉴스는 최근성/신뢰감 보너스
    score += 12
    return score


def score_poly_candidate(question, volume, yes_price, rewritten, is_surge=False):
    text = question.lower()
    out = f"{rewritten['eyebrow']} {rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"
    score = 0

    try:
        v = float(volume)
        if v >= 15000000:
            score += 34
        elif v >= 8000000:
            score += 28
        elif v >= 4000000:
            score += 22
        elif v >= 1500000:
            score += 16
    except:
        pass

    try:
        p = float(yes_price)
        if 0.10 <= p <= 0.90:
            score += 18
        if 0.20 <= p <= 0.80:
            score += 10
    except:
        pass

    for k in [
        "bitcoin", "btc", "oil", "wti", "crude", "gold", "fed", "inflation",
        "cpi", "yield", "tariff", "trump", "deal", "nasdaq"
    ]:
        if k in text:
            score += 12

    if is_surge:
        score += 18

    if any(k in out for k in [
        "늦으면", "또", "지갑", "숨멎", "벌써", "구경만", "들뜸",
        "처맞음", "멘붕", "식은땀", "배아픔", "난리", "쫄림"
    ]):
        score += 16

    return score


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


def rewritten_topic_key(question):
    q = question.lower()
    if any(k in q for k in ["bitcoin", "btc"]):
        return "btc"
    if any(k in q for k in ["ethereum", "eth"]):
        return "eth"
    if any(k in q for k in ["oil", "wti", "crude", "brent"]):
        return "oil"
    if "gold" in q:
        return "gold"
    if any(k in q for k in ["fed", "rate", "inflation", "cpi", "yield", "treasury"]):
        return "macro"
    if any(k in q for k in ["trump", "deal", "tariff"]):
        return "trump_trade"
    if any(k in q for k in ["war", "attack", "ceasefire", "iran", "israel"]):
        return "mideast"
    if any(k in q for k in ["nasdaq", "s&p", "dow", "stocks"]):
        return "stocks"
    return "general"


def build_poly_candidates():
    markets = get_polymarket_markets(limit=180)
    candidates = []
    seen_topics = set()

    for market in markets[:80]:
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
            end_date=market["end_date"]
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
        if news_candidate["score"] >= best_poly["score"] + 5:
            return news_candidate
        if best_poly["score"] >= news_candidate["score"] + 12:
            return best_poly
        return random.choice([news_candidate, best_poly])

    if news_candidate:
        return news_candidate

    if best_poly:
        return best_poly

    return None


def run():
    winner = choose_winner()

    if not winner:
        print("보낼 후보 없음 → 종료")
        return

    if is_duplicate(winner["raw_title"]):
        print("중복 제목 스킵:", winner["raw_title"])
        return

    if is_same_topic(winner["topic"]) and winner["score"] < 86:
        print("같은 주제 스킵:", winner["topic"], "/", winner["raw_title"])
        return

    print("선택 소스:", winner["source"])
    print("원본:", winner["raw_title"])
    print("점수:", winner["score"])
    print("아이브로:", winner["rewritten"].get("eyebrow", ""))
    print("제목1:", winner["rewritten"]["title1"])
    print("제목2:", winner["rewritten"]["title2"])
    print("설명1:", winner["rewritten"]["desc1"])
    print("설명2:", winner["rewritten"]["desc2"])

    path = create_card(winner["rewritten"], mode=winner["mode"])
    send_image(path)

    if winner["source"] == "polymarket":
        update_market_snapshot(
            question=winner["raw_title"],
            volume=winner.get("volume", 0),
            yes_price=winner.get("yes_price", 0)
        )

    add_history(winner["raw_title"])
    add_topic(winner["topic"])
    add_mix(winner["source"])

    print("전송 완료")


if __name__ == "__main__":
    run()