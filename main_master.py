from news import get_news
from rewrite import rewrite
from polymarket import get_polymarket_markets, parse_best_market, classify_topic
from rewrite_poly import rewrite_poly
from card import create_card
from telegram import send_image
from utils_numbers import extract_numbers, choose_best_number
from image_generator import safe_generate_bg
from memory import is_duplicate, add_history, is_same_topic, add_topic, load_history
from market_state import detect_surge, update_market_snapshot

NEWS_ALERT_KEYWORDS = [
    "war", "iran", "attack", "missile", "oil", "gold",
    "inflation", "rate", "fed", "bitcoin", "btc", "tariff",
    "crash", "surge", "jump", "spike", "drop", "collapse",
    "ceasefire", "conflict", "breaking"
]

ALLOWED_TOPICS = {"geopolitics", "economy", "crypto", "politics"}

def detect_news_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in NEWS_ALERT_KEYWORDS):
        return "alert"
    return "normal"

def detect_poly_mode(question, yes_price, topic, is_surge=False):
    text = question.lower()

    if is_surge:
        return "alert"

    if topic == "geopolitics":
        return "alert"

    if topic == "economy" and any(k in text for k in ["oil", "wti", "crude", "gold", "fed", "inflation"]):
        return "alert"

    if topic == "crypto":
        return "normal"

    if topic == "politics":
        return "normal"

    return "normal"

def invalid_topic_shift(title, rewritten):
    source = title.lower()
    out = f"{rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"

    if any(k in source for k in ["iran", "missile", "attack", "war", "ceasefire"]):
        bad = ["유류세", "전기요금", "부동산"]
        return any(b in out for b in bad)

    if "gold" in source and "금" not in out:
        return True
    if "oil" in source and ("유가" not in out and "기름값" not in out):
        return True
    if "bitcoin" in source and "비트코인" not in out:
        return True

    return False

def score_news_item(title, summary, mode, rewritten):
    score = 0
    text = f"{title} {summary}".lower()
    output = f"{rewritten['title1']} {rewritten['title2']}"

    if mode == "alert":
        score += 30

    strong_words = ["iran", "war", "attack", "missile", "oil", "gold", "bitcoin", "fed", "inflation", "tariff"]
    for w in strong_words:
        if w in text:
            score += 8

    numbers = extract_numbers(f"{title} {summary}")
    if numbers:
        score += 10

    hot_words = ["급등", "전쟁", "긴장", "폭등", "하락", "속보", "돌파"]
    for w in hot_words:
        if w in output:
            score += 6

    return score

def score_poly_item(question, volume, yes_price, mode, rewritten, is_surge=False):
    score = 0
    text = question.lower()
    output = f"{rewritten['title1']} {rewritten['title2']}"

    if mode == "alert":
        score += 35

    if is_surge:
        score += 50

    try:
        v = float(volume)
        if v >= 10000000:
            score += 20
        elif v >= 1000000:
            score += 12
        elif v >= 100000:
            score += 6
    except:
        pass

    try:
        p = float(yes_price)
        if 0.05 < p < 0.95:
            if p >= 0.8 or p <= 0.2:
                score += 15
            elif p >= 0.65 or p <= 0.35:
                score += 8
    except:
        pass

    strong_words = ["iran", "war", "attack", "missile", "military", "troops", "trump", "bitcoin", "oil", "gold", "fed", "ceasefire", "wti", "crude"]
    for w in strong_words:
        if w in text:
            score += 8

    for w in ["급등", "전쟁", "긴장", "확률", "%", "속보", "돌파", "몰렸다", "쏠린다"]:
        if w in output:
            score += 6

    return score

def build_news_candidate():
    title, summary = get_news()
    topic = classify_topic(title, summary)

    if topic not in ALLOWED_TOPICS:
        return None

    mode = detect_news_mode(title, summary)

    numbers = extract_numbers(f"{title} {summary}")
    number_hint = choose_best_number(f"{title} {summary}", numbers)

    rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    if invalid_topic_shift(title, rewritten):
        rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    score = score_news_item(title, summary, mode, rewritten)

    return {
        "source": "news",
        "raw_title": title,
        "raw_summary": summary,
        "mode": mode,
        "topic": topic,
        "rewritten": rewritten,
        "score": score
    }

def build_poly_candidates():
    markets = get_polymarket_markets()
    excluded_titles = set(load_history())
    candidates = []

    for _ in range(min(len(markets), 15)):
        try:
            market = parse_best_market(markets, excluded_titles=list(excluded_titles))
        except:
            break

        excluded_titles.add(market["question"])

        topic = classify_topic(market["question"], market.get("description", ""))
        if topic not in ALLOWED_TOPICS:
            continue

        surge = detect_surge(
            question=market["question"],
            volume=market["volume"],
            yes_price=market["yes_price"]
        )

        mode = detect_poly_mode(
            question=market["question"],
            yes_price=market["yes_price"],
            topic=topic,
            is_surge=surge
        )

        rewritten = rewrite_poly(
            question=market["question"],
            volume=market["volume"],
            yes_price=market["yes_price"],
            end_date=market["end_date"]
        )

        score = score_poly_item(
            market["question"],
            market["volume"],
            market["yes_price"],
            mode,
            rewritten,
            is_surge=surge
        )

        raw_summary = (
            f"volume={market['volume']}, yes={market['yes_price']}, "
            f"end={market['end_date']}, desc={market.get('description', '')}"
        )

        candidates.append({
            "source": "polymarket",
            "raw_title": market["question"],
            "raw_summary": raw_summary,
            "mode": mode,
            "topic": topic,
            "rewritten": rewritten,
            "score": score,
            "volume": market["volume"],
            "yes_price": market["yes_price"],
            "is_surge": surge
        })

    return candidates

def is_usable_candidate(candidate, ignore_topic=False):
    title = candidate["raw_title"]
    topic = candidate["topic"]

    if is_duplicate(title):
        print("중복 제목 스킵:", title)
        return False

    if not ignore_topic and is_same_topic(topic):
        if candidate.get("score", 0) < 80:
            print("같은 주제 스킵:", topic, "/", title)
            return False

    return True

def choose_winner():
    news_candidate = build_news_candidate()
    poly_candidates = build_poly_candidates()

    if news_candidate:
        print("뉴스 점수:", news_candidate["score"])
    else:
        print("뉴스 후보 없음")

    if poly_candidates:
        print("폴리마켓 1등 점수:", poly_candidates[0]["score"])
    else:
        print("폴리마켓 후보 없음")

    usable_poly = None
    for candidate in poly_candidates:
        if is_usable_candidate(candidate, ignore_topic=False):
            usable_poly = candidate
            break

    usable_news = None
    if news_candidate and is_usable_candidate(news_candidate, ignore_topic=False):
        usable_news = news_candidate

    if not usable_poly:
        for candidate in poly_candidates:
            if is_usable_candidate(candidate, ignore_topic=True):
                usable_poly = candidate
                print("주제 필터 완화로 선택:", candidate["raw_title"])
                break

    if not usable_news and news_candidate:
        if is_usable_candidate(news_candidate, ignore_topic=True):
            usable_news = news_candidate
            print("뉴스 주제 필터 완화로 선택:", news_candidate["raw_title"])

    if usable_poly and usable_news:
        if usable_poly["score"] >= usable_news["score"]:
            return usable_poly
        return usable_news

    if usable_poly:
        return usable_poly

    if usable_news:
        return usable_news

    return None

def run():
    winner = choose_winner()

    if not winner:
        print("보낼 후보 없음 → 종료")
        return

    title = winner["raw_title"]
    topic = winner["topic"]

    print("선택 소스:", winner["source"])
    print("원본:", winner["raw_title"])
    print("모드:", winner["mode"])
    print("주제:", winner["topic"])
    print("제목1:", winner["rewritten"]["title1"])
    print("제목2:", winner["rewritten"]["title2"])
    print("설명1:", winner["rewritten"]["desc1"])
    print("설명2:", winner["rewritten"]["desc2"])

    safe_generate_bg(
        raw_title=winner["raw_title"],
        raw_summary=winner["raw_summary"],
        mode=winner["mode"],
        source=winner["source"],
        topic=winner["topic"],
        output_path="bg.jpg"
    )

    path = create_card(winner["rewritten"], mode=winner["mode"])
    send_image(path)

    if winner["source"] == "polymarket":
        update_market_snapshot(
            question=winner["raw_title"],
            volume=winner.get("volume", 0),
            yes_price=winner.get("yes_price", 0)
        )

    add_history(title)
    add_topic(topic)

    print("전송 완료")

if __name__ == "__main__":
    run()
