def score_news(news):
    keywords = ["trump", "iran", "war", "bitcoin", "rate", "fed"]

    score = 0
    for k in keywords:
        if k.lower() in news["title"].lower():
            score += 1

    return score


def pick_top_news(news_list):
    scored = [(n, score_news(n)) for n in news_list]
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[0][0] if scored else None