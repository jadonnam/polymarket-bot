from datetime import datetime

def is_post_time():
    now = datetime.now()
    return now.hour in [8, 19]


def is_extreme_news(score, title):
    keywords = [
        "전쟁", "공습", "침공", "핵", "사망", "폭발",
        "붕괴", "파산", "대폭락", "긴급", "비상",
        "역대급", "최악", "테러"
    ]
    return score >= 140 and any(k in title for k in keywords)


def run():
    now = datetime.now()
    print(f"[시간] {now}")

    # dummy example news
    news = {"score": 150, "title": "전쟁 발생"}

    score = news["score"]
    title = news["title"]

    if is_extreme_news(score, title):
        print("[속보] 실행")
        return

    if is_post_time():
        print("[일반 게시] 실행")
        return

    print("[스킵]")


if __name__ == "__main__":
    run()
