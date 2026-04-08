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
    "ceasefire", "conflict", "breaking", "hormuz", "brent", "wti"
]

ALLOWED_TOPICS = {"geopolitics", "economy", "crypto", "politics"}

MONEY_WORDS = [
    "oil", "wti", "crude", "brent", "gold", "bitcoin", "btc", "ethereum", "eth",
    "fed", "inflation", "rate", "rates", "tariff", "nasdaq", "s&p", "dow",
    "hormuz", "strait", "treasury", "yield", "cpi", "recession", "stocks"
]

ABSTRACT_BANNED = [
    "긴장", "불안", "심리", "가능성", "우려", "흐름", "상황",
    "불확실성", "관심", "주목", "해석", "촉각"
]


def detect_news_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in NEWS_ALERT_KEYWORDS):
        return "alert"
    return "normal"


def detect_poly_mode(question, yes_price, topic, is_surge=False):
    text = question.lower()

    if is_surge:
        return "alert"

    if topic == "economy" and any(k in text for k in ["oil", "wti", "crude", "gold", "fed", "inflation", "tariff", "yield", "cpi"]):
        return "alert"

    if topic == "crypto" and any(k in text for k in ["bitcoin", "btc", "ethereum", "eth"]):
        return "alert"

    return "normal"


def invalid_topic_shift(title, rewritten):
    source = title.lower()
    out = f"{rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"

    if any(k in source for k in ["iran", "missile", "attack", "war", "ceasefire"]):
        bad = ["유류세", "전기요금", "부동산", "지원금", "대출"]
        if any(b in out for b in bad):
            return True

    if "gold" in source and "금" not in out:
        return True
    if any(k in source for k in ["oil", "wti", "crude", "brent"]) and ("유가" not in out and "원유" not in out):
        return True
    if "bitcoin" in source and "비트" not in out:
        return True
    if "ethereum" in source and "이더" not in out and "이더리움" not in out:
        return True
    if any(k in source for k in ["fed", "rate", "inflation", "cpi"]) and not any(k in out for k in ["금리", "물가", "인플레"]):
        return True

    return False


def score_news_item(title, summary, mode, rewritten):
    score = 0
    text = f"{title} {summary}".lower()
    output = f"{rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"

    if mode == "alert":
        score += 20

    numbers = extract_numbers(f"{title} {summary}")
    if numbers:
        score += 16

    for w in MONEY_WORDS:
        if w in text:
            score += 10

    if any(w in text for w in ["oil", "wti", "crude", "gold", "bitcoin", "btc", "inflation", "fed", "tariff", "yield"]):
        score += 20

    if any(w in text for w in ["iran", "war", "attack", "missile", "ceasefire"]) and not any(w in text for w in ["oil", "wti", "crude", "gold", "hormuz"]):
        score -= 35

    if any(w in output for w in ABSTRACT_BANNED):
        score -= 20

    if "%" in output:
        score += 10

    return score


def score_poly_item(question, volume, yes_price, mode, rewritten, is_surge=False):
    score = 0
    text = question.lower()
    output = f"{rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"

    if mode == "alert":
        score += 12

    if is_surge:
        score += 30

    try:
        v = float(volume)
        if v >= 20000000:
            score += 36
        elif v >= 10000000:
            score += 30
        elif v >= 5000000:
            score += 24
        elif v >= 2000000:
            score += 18
        elif v >= 500000:
            score += 12
    except:
        pass

    try:
        p = float(yes_price)
        if 0.08 <= p <= 0.92:
            score += 18
        if 0.18 <= p <= 0.82:
            score += 12
        if 0.35 <= p <= 0.65:
            score += 8
    except:
        pass

    for w in MONEY_WORDS:
        if w in text:
            score += 15

    if any(w in text for w in ["iran", "war", "attack", "missile", "ceasefire"]) and not any(w in text for w in ["oil", "wti", "crude", "gold", "hormuz"]):
        score -= 40

    if any(w in output for w in ABSTRACT_BANNED):
        score -= 20

    if "%" in output:
        score += 14

    if any(k in output for k in ["거래", "억", "$", "유가", "금", "비트", "이더", "금리", "관세", "증시", "달러"]):
        score += 20

    return score


def build_news_candidate():
    try:
        title, summary = get_news()
    except:
        return None

    if not title:
        return None

    topic = classify_topic(title, summary)
    if topic not in ALLOWED_TOPICS:
        return None

    text = f"{title} {summary}".lower()
    if any(w in text for w in ["iran", "war", "attack", "missile", "ceasefire"]) and not any(w in text for w in ["oil", "wti", "crude", "gold", "hormuz"]):
        return None

    mode = detect_news_mode(title, summary)
    numbers = extract_numbers(f"{title} {summary}")
    number_hint = choose_best_number(f"{title} {summary}", numbers)

    rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    if invalid_topic_shift(title, rewritten):
        rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    score = score_news_item(title, summary, mode, rewritten)

    if score < 30:
        return None

    return {
        "source": "news",
        "raw_title": title,
        "raw_summary": summary,
        "mode": mode,
        "topic": topic,
        "rewritten": rewritten,
        "score": score
    }


def _theme_key(question):
    text = question.lower()

    if any(k in text for k in ["oil", "wti", "crude", "brent", "hormuz", "strait"]):
        return "oil"
    if "gold" in text:
        return "gold"
    if any(k in text for k in ["bitcoin", "btc"]):
        return "bitcoin"
    if any(k in text for k in ["ethereum", "eth"]):
        return "ethereum"
    if any(k in text for k in ["fed", "inflation", "rate", "rates", "cpi", "yield", "treasury"]):
        return "macro"
    if any(k in text for k in ["tariff", "china", "exports"]):
        return "trade"
    if any(k in text for k in ["nasdaq", "s&p", "dow", "stocks"]):
        return "stocks"
    if any(k in text for k in ["trump", "election", "president", "white house"]):
        return "politics"
    if any(k in text for k in ["iran", "war", "attack", "missile", "ceasefire"]):
        return "geopolitics"
    return "other"


def _is_money_relevant(question, description=""):
    text = f"{question} {description}".lower()
    return any(k in text for k in MONEY_WORDS)


def _is_publishable_poly(question, description, rewritten):
    text = f"{question} {description}".lower()
    out = f"{rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"

    if not _is_money_relevant(question, description):
        return False

    if any(w in out for w in ABSTRACT_BANNED):
        return False

    if any(w in text for w in ["iran", "war", "attack", "missile", "ceasefire"]) and not any(k in text for k in ["oil", "wti", "crude", "gold", "hormuz"]):
        return False

    if "%" not in out:
        return False

    if not any(k in out for k in ["거래", "억", "$", "유가", "금", "비트", "이더", "금리", "관세", "증시", "달러"]):
        return False

    return True


def build_poly_candidates():
    markets = get_polymarket_markets(limit=150)
    excluded_titles = set(load_history())
    candidates = []
    theme_seen = set()

    ranked = sorted(markets, key=lambda m: m.get("_score", 0), reverse=True)

    for market in ranked[:50]:
        question = market["question"]
        if question in excluded_titles:
            continue

        topic = classify_topic(question, market.get("description", ""))
        if topic not in ALLOWED_TOPICS:
            continue

        theme = _theme_key(question)
        if theme in theme_seen:
            continue

        surge = detect_surge(
            question=question,
            volume=market["volume"],
            yes_price=market["yes_price"]
        )

        mode = detect_poly_mode(
            question=question,
            yes_price=market["yes_price"],
            topic=topic,
            is_surge=surge
        )

        rewritten = rewrite_poly(
            question=question,
            volume=market["volume"],
            yes_price=market["yes_price"],
            end_date=market["end_date"]
        )

        if not _is_publishable_poly(question, market.get("description", ""), rewritten):
            continue

        score = score_poly_item(
            question,
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
            "raw_title": question,
            "raw_summary": raw_summary,
            "mode": mode,
            "topic": topic,
            "theme": theme,
            "rewritten": rewritten,
            "score": score,
            "volume": market["volume"],
            "yes_price": market["yes_price"],
            "is_surge": surge
        })
        theme_seen.add(theme)

        if len(candidates) >= 12:
            break

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def is_usable_candidate(candidate, ignore_topic=False):
    title = candidate["raw_title"]
    topic = candidate["topic"]

    if is_duplicate(title):
        print("중복 제목 스킵:", title)
        return False

    if candidate["source"] == "polymarket" and candidate.get("score", 0) < 58:
        print("점수 부족 스킵:", candidate["score"], "/", title)
        return False

    if not ignore_topic and is_same_topic(topic):
        if candidate.get("score", 0) < 88:
            print("같은 주제 스킵:", topic, "/", title)
            return False

    return True


def choose_winner():
    poly_candidates = build_poly_candidates()

    if poly_candidates:
        print("폴리마켓 상위 점수:", [c["score"] for c in poly_candidates[:5]])
    else:
        print("폴리마켓 후보 없음")

    usable_poly = None
    for candidate in poly_candidates:
        if is_usable_candidate(candidate, ignore_topic=False):
            usable_poly = candidate
            break

    if not usable_poly:
        for candidate in poly_candidates:
            if is_usable_candidate(candidate, ignore_topic=True):
                usable_poly = candidate
                print("주제 필터 완화로 선택:", candidate["raw_title"])
                break

    if usable_poly:
        return usable_poly

    news_candidate = build_news_candidate()
    if news_candidate:
        print("뉴스 점수:", news_candidate["score"])
        if is_usable_candidate(news_candidate, ignore_topic=True):
            return news_candidate

    return None


def run():
    winner = choose_winner()

    if not winner:
        print("보낼 후보 없음 → 종료")
        return

    title = winner["raw_title"]

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
    add_topic(winner["topic"])

    print("전송 완료")


if __name__ == "__main__":
    run()