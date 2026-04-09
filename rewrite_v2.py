import re
import hashlib
from polymarket import classify_topic
from price_data import get_prices_for_topic

NEWS_HOOKS = {
    "TRUMP": [
        "정책 한 줄에 돈의 방향이 바뀐다",
        "정책 변수 하나가 달러를 흔든다",
        "시장은 정치 뉴스도 바로 가격에 반영한다",
        "관세와 달러 기대가 함께 움직인다",
        "정책 뉴스가 곧 시장 뉴스가 된다",
        "정책 변화는 체감보다 가격에 먼저 찍힌다",
    ],
    "BTC": [
        "비트코인이 다시 시장 중심에 섰다",
        "코인판 분위기가 비트에서 먼저 바뀐다",
        "비트코인 흐름이 투자 심리를 흔든다",
        "시장 자금이 다시 비트로 모인다",
        "비트 방향이 알트 분위기까지 바꾼다",
        "코인 시장의 온도가 다시 높아진다",
    ],
    "OIL": [
        "유가 뉴스는 결국 생활비로 이어진다",
        "기름값 변수는 주유소에서 체감된다",
        "유가가 물가를 다시 건드린다",
        "원유 가격은 체감보다 먼저 움직인다",
        "유가가 오르면 생활비 부담도 커진다",
        "국제유가 흐름은 바로 지갑과 연결된다",
    ],
    "GOLD": [
        "불안이 커질수록 금이 먼저 반응한다",
        "안전자산 수요가 다시 강해진다",
        "금값은 시장 공포를 가장 먼저 보여준다",
        "불확실성이 커지면 금으로 돈이 몰린다",
        "위기 국면에서는 금이 먼저 움직인다",
        "시장 불안이 금값에 먼저 찍힌다",
    ],
    "RATE": [
        "금리 기대가 시장 분위기를 바꾼다",
        "달러와 성장주가 동시에 흔들린다",
        "금리 뉴스 하나가 시장 기대를 다시 바꾼다",
        "연준 변수는 주식과 환율을 함께 건드린다",
        "시장 기대치가 다시 조정된다",
        "금리 방향은 위험자산 분위기를 좌우한다",
    ],
    "GENERAL": [
        "시장은 뉴스보다 먼저 움직인다",
        "돈의 방향이 숫자에 먼저 찍힌다",
        "핵심은 기사보다 시장 반응이다",
        "체감보다 돈이 먼저 움직인다",
        "숫자를 보면 왜 움직였는지 보인다",
        "이슈가 가격으로 번지는 순간이다",
    ],
}

NEWS_TITLE2 = {
    "TRUMP": ["달러가 먼저 반응한다", "관세 기대가 다시 흔들린다", "정책 리스크가 커진다", "시장 기대가 다시 바뀐다"],
    "BTC":   ["코인판 분위기가 달라진다", "자금이 다시 붙는다", "변동성이 다시 커진다", "알트도 함께 흔들릴 수 있다"],
    "OIL":   ["생활비에 바로 닿는다", "물가를 다시 자극한다", "주유소 가격으로 이어진다", "체감 가격에 영향을 준다"],
    "GOLD":  ["안전자산 수요가 커진다", "불안이 가격에 반영된다", "금이 시장 공포를 보여준다", "달러와 함께 볼 필요가 있다"],
    "RATE":  ["성장주가 바로 흔들린다", "달러도 민감해진다", "시장 기대가 다시 바뀐다", "금리 민감 자산이 반응한다"],
    "GENERAL": ["시장이 먼저 반응한다", "핵심은 가격 변화다", "숫자가 이미 말하고 있다", "돈의 방향이 드러난다"],
}

CARD2_TITLES = {
    "OIL": [
        ("유가가 오르면", "주유소 가격도 뒤따를 수 있다"),
        ("국제유가 변동은", "국내 물가에도 영향을 줄 수 있다"),
        ("원유 가격이 흔들리면", "생활비 부담도 달라질 수 있다"),
    ],
    "BTC": [
        ("비트가 움직이면", "알트코인도 뒤따르는 경우가 많다"),
        ("기관 자금이 붙으면", "개인 자금이 뒤늦게 따라온다"),
        ("비트 방향은", "코인판 전체 분위기를 바꾼다"),
    ],
    "GOLD": [
        ("시장이 불안해지면", "금으로 돈이 먼저 몰리는 경향이 있다"),
        ("달러 흐름이 약해지면", "금값이 강해질 때가 많다"),
        ("위기 뉴스가 커질수록", "금부터 확인하는 이유가 있다"),
    ],
    "RATE": [
        ("금리 기대가 바뀌면", "성장주가 먼저 반응한다"),
        ("연준 발언 하나가", "주식과 환율을 함께 흔들 수 있다"),
        ("금리 전망은", "달러와 위험자산을 같이 건드린다"),
    ],
    "TRUMP": [
        ("정책이 바뀌면", "달러와 관세 기대도 함께 흔들린다"),
        ("정치 뉴스도", "결국 가격표로 번지는 경우가 많다"),
        ("정책 변수는", "시장 기대를 빠르게 바꾸는 편이다"),
    ],
    "GENERAL": [
        ("이 뉴스의 핵심은", "내 지갑과 연결될 수 있다는 점이다"),
        ("체감은 늦어도", "돈은 먼저 반응한다는 점이다"),
        ("숫자부터 보면", "왜 시장이 움직였는지 더 잘 보인다"),
    ],
}

CARD3_HOOKS = {
    "OIL": ["유가 흐름은 결국", "기름값 변수는 결국"],
    "BTC": ["비트 방향만 봐도", "코인을 하지 않아도"],
    "GOLD": ["금을 사지 않아도", "금값 흐름만 알아도"],
    "RATE": ["미국 금리는", "금리 뉴스 하나가"],
    "TRUMP": ["정책 뉴스도 결국", "정치 변수도 결국"],
    "GENERAL": ["경제 뉴스는 결국", "이런 숫자 뉴스는 결국"],
}

CARD3_TITLES = {
    "OIL": ["내 생활비와 연결된다", "주유소 가격으로 돌아온다"],
    "BTC": ["시장 읽는 눈이 달라진다", "알트 분위기까지 보인다"],
    "GOLD": ["시장의 공포가 보인다", "불안의 방향이 보인다"],
    "RATE": ["내 투자까지 흔든다", "달러 방향도 같이 보여준다"],
    "TRUMP": ["투자 타이밍에 영향을 준다", "달러와 관세 기대를 흔든다"],
    "GENERAL": ["결국 내 지갑 이야기다", "먼저 아는 쪽이 유리하다"],
}

DESC2_FALLBACK = {
    "TRUMP":   ["정책 기대가 다시 바뀐다", "달러부터 먼저 반응한다", "정치가 가격표로 번진다"],
    "BTC":     ["코인판 공기가 달라진다", "자금이 다시 빠르게 붙는다", "시장 기대가 다시 커진다"],
    "OIL":     ["생활비로 바로 연결될 수 있다", "주유소에서 먼저 체감될 수 있다", "물가를 다시 자극할 수 있다"],
    "GOLD":    ["안전자산부터 반응한다", "불안할수록 금을 찾는다", "겁먹은 돈이 먼저 움직인다"],
    "RATE":    ["금리 기대가 다시 흔들린다", "성장주가 더 예민하게 반응한다", "달러 방향도 바뀔 수 있다"],
    "GENERAL": ["핵심은 돈 영향이라는 점이다", "숫자를 보면 흐름이 더 잘 보인다", "시장이 먼저 반응한다"],
}


def _stable_pick(arr, seed_text):
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return arr[h % len(arr)]


def _clean(text, max_len):
    return re.sub(r"\s+", " ", str(text).strip())[:max_len]


def _contains(text, keywords):
    return any(k in text.lower() for k in keywords)


def _compact_price(usd_text):
    if not usd_text:
        return usd_text
    if "$" not in usd_text:
        return usd_text
    try:
        num = float(usd_text.replace("$", "").replace(",", ""))
        if num >= 100000:
            return f"${int(num // 1000)}K"
        if num >= 1000:
            return f"${int(num):,}"
        return f"${num}"
    except Exception:
        return usd_text


def _build_title1_with_number(base_title, price_data, key):
    if not price_data:
        return base_title
    usd = _compact_price(price_data.get("usd", ""))
    if not usd:
        return base_title
    if key == "OIL":
        return f"유가 {usd} 반응"
    if key == "BTC":
        return f"비트 {usd} 움직임"
    if key == "GOLD":
        return f"금값 {usd} 반응"
    if key == "RATE":
        return f"환율 {usd} 체크"
    if key == "TRUMP":
        return f"달러 {usd} 반응"
    return base_title


def rewrite(title, desc, mode="normal", number_hint=None, retry=0):
    text = f"{title} {desc}".lower()
    _ = classify_topic(title, desc)

    key = "GENERAL"
    visual_topic = "market_general"
    accent = "gold"
    topic_label = "MARKET"

    if _contains(text, ["trump", "tariff", "trade deal", "china"]):
        key = "TRUMP"
        topic_label = "TRUMP"
        accent = "orange"
        visual_topic = "trump_deal_positive" if _contains(text, ["deal", "agreement", "pause", "relief"]) else "trump_tariff"
    elif _contains(text, ["bitcoin", "btc", "ethereum", "eth"]):
        key = "BTC"
        topic_label = "BTC"
        accent = "neon_gold" if _contains(text, ["surge", "jump", "rally", "gain", "rise", "bounce"]) else "hot_red"
        visual_topic = "btc_moon" if accent == "neon_gold" else "btc_panic"
    elif _contains(text, ["oil", "wti", "crude", "brent", "hormuz", "strait"]):
        key = "OIL"
        topic_label = "OIL"
        accent = "orange"
        visual_topic = "oil_relief" if _contains(text, ["ease", "relief", "normal", "ceasefire"]) else "oil_shock"
    elif _contains(text, ["gold"]):
        key = "GOLD"
        topic_label = "GOLD"
        accent = "gold"
        visual_topic = "gold_rush"
    elif _contains(text, ["fed", "inflation", "cpi", "rate", "yield", "treasury", "dollar", "fx"]):
        key = "RATE"
        topic_label = "RATE"
        accent = "electric_blue"
        visual_topic = "rate_cut_hype" if _contains(text, ["cut", "cool", "fall", "easing"]) else "rate_cut_doubt"

    price_data = get_prices_for_topic(topic_label if topic_label in {"OIL", "BTC", "GOLD", "RATE", "TRUMP"} else "GENERAL")

    base_title1 = {
        "TRUMP": "정책 변수가 다시 커진다",
        "BTC": "코인판이 다시 흔들린다",
        "OIL": "유가 변수가 다시 커진다",
        "GOLD": "안전자산 수요가 다시 뜬다",
        "RATE": "금리 기대가 다시 흔들린다",
        "GENERAL": "시장 분위기가 다시 바뀐다",
    }[key]

    eyebrow = _stable_pick(NEWS_HOOKS[key], title)
    title1 = _build_title1_with_number(base_title1, price_data, key)
    title2 = _stable_pick(NEWS_TITLE2[key], title)
    desc1 = price_data.get("desc1", "") if price_data else ""
    desc2 = price_data.get("desc2", "") if price_data else ""

    if not desc1:
        desc1 = {
            "TRUMP": "정책 뉴스는 달러와 물가 기대를 함께 흔든다",
            "BTC": "비트 방향은 코인판 분위기를 가장 빨리 보여준다",
            "OIL": "유가가 움직이면 결국 생활비에도 영향이 온다",
            "GOLD": "금값은 시장 불안이 커질 때 먼저 반응하는 편이다",
            "RATE": "금리 기대가 바뀌면 성장주와 달러가 예민하게 움직인다",
            "GENERAL": "시장 돈은 뉴스보다 먼저 반응하는 경우가 많다",
        }[key]

    if not desc2:
        desc2 = _stable_pick(DESC2_FALLBACK[key], title)

    card2_title1, card2_title2 = _stable_pick(CARD2_TITLES[key], title)
    card3_hook = _stable_pick(CARD3_HOOKS[key], title)
    card3_title = _stable_pick(CARD3_TITLES[key], title)

    card3_desc1 = {
        "TRUMP": "정책 이슈는 결국 투자 타이밍과 연결될 수 있다",
        "BTC": "비트 흐름을 알면 알트 분위기까지 같이 읽기 쉽다",
        "OIL": "유가는 기름값과 물가까지 연결되는 핵심 숫자다",
        "GOLD": "금값은 시장 공포를 읽는 쉬운 신호 중 하나다",
        "RATE": "금리 이슈는 달러와 주식과 채권까지 함께 건드린다",
        "GENERAL": "숫자부터 보면 왜 시장이 움직였는지 빨리 이해된다",
    }[key]

    card3_desc2 = {
        "TRUMP": "정책 뉴스는 늦게 보면 이미 가격이 반영된 경우가 많다",
        "BTC": "코인은 분위기가 빨라서 먼저 보는 쪽이 유리하다",
        "OIL": "유가 이슈는 체감이 늦게 와도 돈은 먼저 움직인다",
        "GOLD": "불안할수록 금부터 체크하면 시장 공기를 읽기 쉽다",
        "RATE": "금리 뉴스는 그냥 넘기면 내 투자에도 뒤늦게 영향이 온다",
        "GENERAL": "저장해두면 다음 이슈를 볼 때 연결해서 보기 좋다",
    }[key]

    return {
        "eyebrow": _clean(eyebrow, 24),
        "title1": _clean(title1, 22),
        "title2": _clean(title2, 20),
        "desc1": _clean(desc1, 34),
        "desc2": _clean(desc2, 30),
        "topic": topic_label,
        "visual_topic": visual_topic,
        "accent": accent,
        "subtone": "white",
        "card2_title1": _clean(card2_title1, 24),
        "card2_title2": _clean(card2_title2, 26),
        "card3_hook": _clean(card3_hook, 20),
        "card3_title": _clean(card3_title, 22),
        "card3_desc1": _clean(card3_desc1, 30),
        "card3_desc2": _clean(card3_desc2, 30),
        "_key": key,
        "_price_usd": price_data.get("usd", "") if price_data else "",
    }
