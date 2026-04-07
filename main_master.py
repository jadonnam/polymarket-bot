import alert
print("ALERT FILE:", alert.__file__)
from news import get_news
from rewrite import rewrite
from polymarket import get_polymarket_markets, parse_best_market
from rewrite_poly import rewrite_poly
from card import create_card
from telegram import send_image
from utils_numbers import extract_numbers, choose_best_number

NEWS_ALERT_KEYWORDS = [
    "war", "iran", "attack", "missile", "oil", "gold",
    "inflation", "rate", "fed", "bitcoin", "btc", "tariff",
    "crash", "surge", "jump", "spike", "drop", "collapse"
]

def detect_news_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in NEWS_ALERT_KEYWORDS):
        return "alert"
    return "normal"

def detect_poly_mode(question, yes_price):
    text = question.lower()

    if any(k in text for k in ["iran", "war", "attack", "missile", "military", "troops"]):
        return "alert"

    try:
        if yes_price is not None and 0.05 < float(yes_price) < 0.95:
            return "alert"
    except:
        pass

    return "normal"

def invalid_topic_shift(title, rewritten):
    source = title.lower()
    out = f"{rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"

    if any(k in source for k in ["iran", "missile", "attack", "war"]):
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

    hot_words = ["급등", "전쟁", "긴장", "리스크", "불안", "폭등", "하락"]
    for w in hot_words:
        if w in output:
            score += 6

    return score

def score_poly_item(question, volume, yes_price, mode, rewritten):
    score = 0
    text = question.lower()
    output = f"{rewritten['title1']} {rewritten['title2']}"

    if mode == "alert":
        score += 35

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

    strong_words = ["iran", "war", "attack", "missile", "military", "troops", "trump", "bitcoin"]
    for w in strong_words:
        if w in text:
            score += 8

    hot_words = ["급등", "전쟁", "긴장", "리스크", "불안", "확률", "%"]
    for w in hot_words:
        if w in output:
            score += 6

    return score

def build_news_candidate():
    title, summary = get_news()
    mode = detect_news_mode(title, summary)

    numbers = extract_numbers(f"{title} {summary}")
    number_hint = choose_best_number(f"{title} {summary}", numbers)

    rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    if invalid_topic_shift(title, rewritten):
        print("뉴스 주제 이탈 감지 → 재생성")
        rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    score = score_news_item(title, summary, mode, rewritten)

    return {
        "source": "news",
        "raw_title": title,
        "raw_summary": summary,
        "mode": mode,
        "rewritten": rewritten,
        "score": score
    }

def build_poly_candidate():
    markets = get_polymarket_markets()
    market = parse_best_market(markets)

    mode = detect_poly_mode(market["question"], market["yes_price"])

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
        rewritten
    )

    return {
        "source": "polymarket",
        "raw_title": market["question"],
        "raw_summary": f"volume={market['volume']}, yes={market['yes_price']}, end={market['end_date']}",
        "mode": mode,
        "rewritten": rewritten,
        "score": score
    }

def run():
    news_candidate = build_news_candidate()
    poly_candidate = build_poly_candidate()

    print("뉴스 점수:", news_candidate["score"])
    print("폴리마켓 점수:", poly_candidate["score"])

    if poly_candidate["score"] >= news_candidate["score"]:
        winner = poly_candidate
    else:
        winner = news_candidate

    print("선택 소스:", winner["source"])
    print("원본:", winner["raw_title"])
    print("모드:", winner["mode"])
    print("제목1:", winner["rewritten"]["title1"])
    print("제목2:", winner["rewritten"]["title2"])
    print("설명1:", winner["rewritten"]["desc1"])
    print("설명2:", winner["rewritten"]["desc2"])

    path = create_card(winner["rewritten"], mode=winner["mode"])
    send_image(path)

    print("전송 완료")

if __name__ == "__main__":
    run()