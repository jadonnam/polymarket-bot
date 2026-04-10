import hashlib
import re

NEWS_HOOKS = {
    "TRUMP": [
        "정책 한 줄에도 시장이 크게 흔들린다",
        "정책 변화가 돈의 흐름을 바꾼다",
        "달러부터 먼저 반응하는 구간이다",
        "정치 뉴스가 결국 가격에 반영된다",
    ],
    "BTC": [
        "코인판 분위기가 다시 달아오른다",
        "비트 움직임에 시장이 민감하게 반응한다",
        "지금은 흐름을 먼저 보는 쪽이 유리하다",
        "돈이 빠르게 몰리는 구간이다",
    ],
    "OIL": [
        "유가 움직임이 생활비까지 이어질 수 있다",
        "기름값 부담이 다시 커질 수 있다",
        "유가가 오르면 체감 물가도 따라온다",
        "이번엔 체감이 더 빨리 올 수 있다",
    ],
    "GOLD": [
        "불안할수록 금으로 돈이 몰린다",
        "안전자산이 다시 주목받는 구간이다",
        "시장이 흔들릴 때 금이 먼저 반응한다",
        "지금은 금 흐름을 같이 볼 필요가 있다",
    ],
    "RATE": [
        "금리 기대가 시장 분위기를 바꾸고 있다",
        "환율과 증시가 동시에 흔들리는 구간이다",
        "달러 흐름이 다시 중요해졌다",
        "금리 뉴스가 자산 가격에 바로 반영된다",
    ],
    "GENERAL": [
        "지금은 시장 흐름을 먼저 보는 게 중요하다",
        "돈이 움직이는 방향이 바뀌고 있다",
        "핵심만 보면 왜 시장이 흔들리는지 보인다",
        "지금 구간은 방향성이 중요하다",
    ],
}

TITLE2_MAP = {
    "TRUMP": [
        "달러 움직임부터 살펴봐야 한다",
        "관세와 환율 부담이 커질 수 있다",
        "정책 변수의 영향이 다시 커졌다",
    ],
    "BTC": [
        "코인판 기대감이 다시 살아난다",
        "지금은 속도보다 방향이 중요하다",
        "비트 흐름이 시장 분위기를 끌고 간다",
    ],
    "OIL": [
        "기름값 부담이 커질 수 있다",
        "생활비에 바로 영향이 갈 수 있다",
        "체감 물가가 다시 올라갈 수 있다",
    ],
    "GOLD": [
        "시장 불안이 금값에 반영되고 있다",
        "안전자산 선호가 강해지고 있다",
        "지금은 금 흐름을 같이 볼 때다",
    ],
    "RATE": [
        "환율 부담이 커질 수 있다",
        "증시 변동성이 더 커질 수 있다",
        "달러 움직임을 같이 봐야 한다",
    ],
    "GENERAL": [
        "시장 변동성이 커지는 구간이다",
        "방향이 크게 갈릴 수 있는 시점이다",
        "이번 흐름은 그냥 넘기기 어렵다",
    ],
}

DESC1_MAP = {
    "TRUMP": "정책 변화는 달러와 물가 기대를 함께 흔든다",
    "BTC": "비트 움직임은 코인 시장 분위기를 가장 빠르게 보여준다",
    "OIL": "유가가 오르면 기름값과 물가 부담으로 이어질 수 있다",
    "GOLD": "금값은 시장의 불안 심리가 커질 때 먼저 반응하는 편이다",
    "RATE": "금리와 환율 흐름은 주식시장 분위기까지 함께 흔든다",
    "GENERAL": "시장 반응을 보면 어디로 돈이 움직이는지 더 잘 보인다",
}

DESC2_MAP = {
    "TRUMP": "정책 이슈는 늦게 보면 이미 가격에 반영된 경우가 많다",
    "BTC": "이럴 때는 감정보다 숫자와 흐름을 같이 보는 편이 낫다",
    "OIL": "체감은 늦어도 가격은 먼저 움직일 수 있다",
    "GOLD": "불안한 장에서는 금 흐름을 같이 보는 것이 중요하다",
    "RATE": "지금은 환율과 금리 흐름을 함께 체크할 필요가 있다",
    "GENERAL": "이럴수록 큰 방향부터 먼저 확인하는 것이 좋다",
}


def _stable_pick(arr, seed_text):
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return arr[h % len(arr)]


def _clean(text, max_len):
    return re.sub(r"\s+", " ", str(text).strip())[:max_len]


def _contains(text, keywords):
    low = text.lower()
    return any(k in low for k in keywords)


def _pick_key(title, desc):
    text = f"{title} {desc}".lower()

    if _contains(text, ["trump", "tariff", "trade deal", "china", "관세", "트럼프"]):
        return "TRUMP"
    if _contains(text, ["bitcoin", "btc", "ethereum", "eth", "비트", "코인"]):
        return "BTC"
    if _contains(text, ["oil", "wti", "crude", "brent", "hormuz", "유가", "원유"]):
        return "OIL"
    if _contains(text, ["gold", "금값", "금"]):
        return "GOLD"
    if _contains(text, ["fed", "inflation", "cpi", "rate", "yield", "treasury", "dollar", "fx", "금리", "환율", "달러"]):
        return "RATE"
    return "GENERAL"


def _natural_title1(title, key):
    text = title.strip()

    if key == "OIL":
        if "유가" in text:
            return _clean(text, 22)
        return _clean("유가 흐름이 다시 심상치 않다", 22)

    if key == "BTC":
        if "비트" in text or "bitcoin" in text.lower() or "btc" in text.lower():
            return _clean(text, 22)
        return _clean("비트 흐름이 다시 강해지고 있다", 22)

    if key == "RATE":
        if "환율" in text or "달러" in text:
            return _clean(text, 22)
        return _clean("달러와 환율 흐름이 흔들린다", 22)

    if key == "TRUMP":
        return _clean(text, 22)

    if key == "GOLD":
        if "금" in text:
            return _clean(text, 22)
        return _clean("금값 흐름이 다시 강해지고 있다", 22)

    return _clean(text, 22)


def rewrite(title, desc, mode="normal", number_hint=None, retry=0):
    key = _pick_key(title, desc)

    topic_label = {
        "TRUMP": "TRUMP",
        "BTC": "BTC",
        "OIL": "OIL",
        "GOLD": "GOLD",
        "RATE": "RATE",
        "GENERAL": "MARKET",
    }[key]

    visual_topic = {
        "TRUMP": "trump_tariff",
        "BTC": "btc_moon" if _contains(f"{title} {desc}", ["surge", "rise", "jump", "급등", "상승"]) else "btc_panic",
        "OIL": "oil_shock",
        "GOLD": "gold_rush",
        "RATE": "rate_cut_doubt",
        "GENERAL": "market_general",
    }[key]

    accent = {
        "TRUMP": "orange",
        "BTC": "neon_gold",
        "OIL": "orange",
        "GOLD": "gold",
        "RATE": "electric_blue",
        "GENERAL": "gold",
    }[key]

    eyebrow = _stable_pick(NEWS_HOOKS[key], title)
    title1 = _natural_title1(title, key)
    title2 = _stable_pick(TITLE2_MAP[key], title)
    desc1 = DESC1_MAP[key]
    desc2 = DESC2_MAP[key]

    return {
        "eyebrow": _clean(eyebrow, 28),
        "title1": _clean(title1, 24),
        "title2": _clean(title2, 24),
        "desc1": _clean(desc1, 40),
        "desc2": _clean(desc2, 34),
        "topic": topic_label,
        "visual_topic": visual_topic,
        "accent": accent,
        "subtone": "white",
        "card2_title1": _clean("핵심은 이 흐름이 어디까지 번질지다", 24),
        "card2_title2": _clean("지금은 시장이 먼저 반응하고 있다", 26),
        "card3_hook": _clean("결국 중요한 건 돈의 방향이다", 22),
        "card3_title": _clean("지금 흐름을 먼저 보는 편이 낫다", 24),
        "card3_desc1": _clean("숫자보다 중요한 건 시장이 왜 반응했는지 이해하는 것이다", 32),
        "card3_desc2": _clean("저장해두면 다음 움직임을 볼 때 도움이 된다", 30),
        "_key": key,
        "_price_usd": "",
    }
