from rewrite_poly import rewrite_poly
from rewrite import rewrite
from card import create_card


def run_test():
    samples = [
        {
            "kind": "poly",
            "question": "Will Trump announce a major trade deal by April 30?",
            "volume": 6200000,
            "yes_price": 0.67,
            "end_date": "2026-04-30T00:00:00Z",
            "mode": "alert",
        },
        {
            "kind": "poly",
            "question": "Will Bitcoin hit $100,000 by May 31?",
            "volume": 12000000,
            "yes_price": 0.64,
            "end_date": "2026-05-31T00:00:00Z",
            "mode": "alert",
        },
        {
            "kind": "poly",
            "question": "Will WTI crude oil hit $100 by April 30?",
            "volume": 7500000,
            "yes_price": 0.72,
            "end_date": "2026-04-30T00:00:00Z",
            "mode": "alert",
        },
        {
            "kind": "news",
            "title": "Treasury yields jump as traders slash rate-cut bets",
            "desc": "Bond markets repriced sharply after fresh inflation concerns hit Wall Street.",
            "mode": "alert",
        },
    ]

    for s in samples:
        if s["kind"] == "poly":
            rewritten = rewrite_poly(
                question=s["question"],
                volume=s["volume"],
                yes_price=s["yes_price"],
                end_date=s["end_date"],
            )
        else:
            rewritten = rewrite(
                title=s["title"],
                desc=s["desc"],
                mode=s["mode"]
            )

        path = create_card(rewritten, mode=s["mode"])
        print(rewritten)
        print(path)
        print("-" * 50)


if __name__ == "__main__":
    run_test()