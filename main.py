from news import get_news
from card import create_card
from telegram import send_image
from rewrite import rewrite
from utils_numbers import extract_numbers, choose_best_number

ALERT_KEYWORDS = [
    "war", "iran", "attack", "missile", "oil", "gold",
    "inflation", "rate", "fed", "bitcoin", "btc", "tariff",
    "crash", "surge", "jump", "spike", "drop", "collapse"
]

def detect_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in ALERT_KEYWORDS):
        return "alert"
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

def run():
    title, summary = get_news()
    print("원본:", title)

    mode = detect_mode(title, summary)
    print("모드:", mode)

    numbers = extract_numbers(f"{title} {summary}")
    number_hint = choose_best_number(f"{title} {summary}", numbers)

    print("추출 숫자들:", numbers)
    print("대표 숫자:", number_hint)

    rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    if invalid_topic_shift(title, rewritten):
        print("주제 이탈 감지 → 재생성")
        rewritten = rewrite(title, summary, mode=mode, number_hint=number_hint)

    print("변환 제목1:", rewritten["title1"])
    print("변환 제목2:", rewritten["title2"])
    print("변환 설명1:", rewritten["desc1"])
    print("변환 설명2:", rewritten["desc2"])

    path = create_card(rewritten, mode=mode)
    send_image(path)

    print("전송 완료")

if __name__ == "__main__":
    run()