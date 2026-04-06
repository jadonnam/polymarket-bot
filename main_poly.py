from polymarket import get_polymarket_markets, parse_best_market
from rewrite_poly import rewrite_poly
from card import create_card
from telegram import send_image

def detect_poly_mode(question, yes_price):
    text = question.lower()

    if any(k in text for k in ["iran", "war", "attack", "missile", "military", "troops"]):
        return "alert"

    try:
        if yes_price is not None and float(yes_price) >= 0.75:
            return "alert"
    except:
        pass

    return "normal"

def run():
    markets = get_polymarket_markets()
    market = parse_best_market(markets)

    print("질문:", market["question"])
    print("거래량:", market["volume"])
    print("확률:", market["yes_price"])
    print("종료일:", market["end_date"])

    mode = detect_poly_mode(market["question"], market["yes_price"])
    print("모드:", mode)

    rewritten = rewrite_poly(
        question=market["question"],
        volume=market["volume"],
        yes_price=market["yes_price"],
        end_date=market["end_date"]
    )

    print("변환 제목1:", rewritten["title1"])
    print("변환 제목2:", rewritten["title2"])
    print("변환 설명1:", rewritten["desc1"])
    print("변환 설명2:", rewritten["desc2"])

    path = create_card(rewritten, mode=mode)
    send_image(path)

    print("전송 완료")

if __name__ == "__main__":
    run()