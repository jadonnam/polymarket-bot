import hashlib
import re


def _stable_pick(options, seed_text):
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return options[h % len(options)]


def _clean(text, max_len=None):
    text = str(text).replace("\n", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if max_len:
        return text[:max_len].strip()
    return text


def _remove_english_noise(text):
    text = re.sub(r"[A-Za-z]{4,}", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_number_block(text):
    nums = re.findall(r"\d+(?:[.,]\d+)?", text)
    if not nums:
        return ""
    return nums[0]


def _contains(text, keywords):
    low = text.lower()
    return any(k in low for k in keywords)


def _topic_key(title, desc):
    text = f"{title} {desc}".lower()

    if _contains(text, ["bitcoin", "btc", "ethereum", "eth", "비트", "코인"]):
        return "CRYPTO"
    if _contains(text, ["oil", "wti", "crude", "brent", "hormuz", "유가", "원유", "휘발유"]):
        return "OIL"
    if _contains(text, ["dollar", "usd", "fx", "환율", "달러", "원화"]):
        return "FX"
    if _contains(text, ["fed", "cpi", "inflation", "rate", "yield", "금리", "물가", "인플레"]):
        return "RATE"
    if _contains(text, ["gold", "금값", "금"]):
        return "GOLD"
    if _contains(text, ["trump", "tariff", "trade", "china", "관세", "트럼프"]):
        return "TRUMP"
    if _contains(text, ["war", "attack", "missile", "iran", "israel", "ukraine", "전쟁", "공습", "이란", "이스라엘"]):
        return "GEO"
    return "GENERAL"


def _make_eyebrow(key, seed):
    table = {
        "CRYPTO": [
            "지금은 코인 흐름을 먼저 보는 구간이다",
            "코인판 분위기가 다시 달라지고 있다",
            "돈이 먼저 반응하는 코인 구간이다",
        ],
        "OIL": [
            "유가 움직임은 생활비로 이어진다",
            "유가가 뛰면 체감 물가도 따라온다",
            "기름값 뉴스는 결국 지갑 문제다",
        ],
        "FX": [
            "환율 움직임은 바로 체감된다",
            "달러가 흔들리면 지갑도 흔들린다",
            "환율 뉴스는 돈 흐름부터 바꾼다",
        ],
        "RATE": [
            "금리와 물가는 자산 가격을 흔든다",
            "지금은 금리 흐름이 더 중요하다",
            "물가와 금리 뉴스는 늦게 보면 늦다",
        ],
        "GOLD": [
            "불안할수록 돈은 금으로 간다",
            "시장이 흔들릴수록 금이 움직인다",
            "안전자산이 다시 주목받는 구간이다",
        ],
        "TRUMP": [
            "정책 한 줄이 시장을 흔든다",
            "정치 뉴스가 결국 가격에 반영된다",
            "정책 변수는 돈 흐름부터 바꾼다",
        ],
        "GEO": [
            "전쟁 뉴스는 가격부터 움직인다",
            "지정학 이슈는 생각보다 빨리 반영된다",
            "정치보다 먼저 돈이 반응하는 구간이다",
        ],
        "GENERAL": [
            "지금은 흐름을 먼저 봐야 한다",
            "돈이 움직이는 방향이 바뀌고 있다",
            "이번 이슈는 그냥 넘기기 어렵다",
        ],
    }
    return _stable_pick(table[key], seed)


def _make_title1(title, desc, key):
    merged = _remove_english_noise(f"{title} {desc}")
    num = _extract_number_block(merged)

    if key == "CRYPTO":
        if "비트" in merged:
            return "비트 흐름이 다시 강해지고 있다"
        if "이더" in merged:
            return "이더 흐름이 다시 살아나고 있다"
        return "코인판 분위기가 다시 달아오른다"

    if key == "OIL":
        if num:
            return f"유가 {num}달러까지 올라왔다"
        return "유가가 다시 뛰고 있다"

    if key == "FX":
        if num:
            return f"환율이 {num}원대까지 올라왔다"
        return "환율 흐름이 다시 흔들린다"

    if key == "RATE":
        return "금리 변수의 영향이 다시 커졌다"

    if key == "GOLD":
        if num:
            return f"금값이 {num}선까지 올라왔다"
        return "금값 흐름이 다시 강해졌다"

    if key == "TRUMP":
        if "관세" in merged:
            return "관세 이슈가 시장을 다시 흔든다"
        return "정책 변수의 영향이 다시 커졌다"

    if key == "GEO":
        if "전쟁" in merged or "공습" in merged:
            return "전쟁 이슈에 시장이 먼저 반응했다"
        return "지정학 불안이 다시 커지고 있다"

    return "시장 흐름이 다시 크게 흔들린다"


def _make_title2(key, seed):
    table = {
        "CRYPTO": [
            "코인판 기대감이 다시 살아난다",
            "비트 흐름이 시장 분위기를 끌고 간다",
            "돈이 몰리는 방향부터 봐야 한다",
        ],
        "OIL": [
            "기름값 부담이 다시 커질 수 있다",
            "생활비 압박이 다시 올라올 수 있다",
            "이번엔 체감 물가까지 이어질 수 있다",
        ],
        "FX": [
            "수입물가 부담이 커질 수 있다",
            "환율 부담이 생활비로 번질 수 있다",
            "달러 강세가 지갑 부담으로 이어진다",
        ],
        "RATE": [
            "증시 변동성이 더 커질 수 있다",
            "달러와 주식이 같이 흔들릴 수 있다",
            "이 흐름은 자산 가격까지 흔든다",
        ],
        "GOLD": [
            "불안한 돈이 금으로 몰리고 있다",
            "안전자산 선호가 다시 강해졌다",
            "시장 불안이 금값에 반영되고 있다",
        ],
        "TRUMP": [
            "관세와 환율 부담이 다시 커질 수 있다",
            "정책 이슈가 물가까지 흔들 수 있다",
            "시장 불안이 다시 커질 수 있다",
        ],
        "GEO": [
            "유가와 환율이 같이 흔들릴 수 있다",
            "전쟁 이슈가 물가로 번질 수 있다",
            "시장은 이미 위험을 먼저 반영했다",
        ],
        "GENERAL": [
            "지금은 방향부터 먼저 봐야 한다",
            "이 구간은 돈 흐름이 더 중요하다",
            "시장은 이미 먼저 움직이고 있다",
        ],
    }
    return _stable_pick(table[key], seed)


def _make_desc1(key):
    table = {
        "CRYPTO": "비트 움직임은 코인 시장 분위기를 가장 빠르게 보여준다",
        "OIL": "유가가 오르면 기름값과 물가 부담으로 이어지기 쉽다",
        "FX": "환율이 오르면 수입물가와 생활비 부담도 같이 커진다",
        "RATE": "금리와 물가 뉴스는 주식과 환율까지 함께 흔든다",
        "GOLD": "금값은 시장 불안이 커질 때 가장 먼저 반응하는 편이다",
        "TRUMP": "정책 변화는 달러와 물가 기대를 함께 흔든다",
        "GEO": "전쟁 이슈는 유가와 환율부터 먼저 움직이게 만든다",
        "GENERAL": "돈이 어디로 움직이는지 보면 시장 흐름이 더 잘 보인다",
    }
    return table[key]


def _make_desc2(key):
    table = {
        "CRYPTO": "이럴 때는 감정보다 숫자와 흐름을 같이 보는 편이 낫다",
        "OIL": "기름값은 늦게 오르는 것 같아도 시장은 먼저 반응한다",
        "FX": "환율은 늦게 보면 이미 생활비에 반영된 뒤일 수 있다",
        "RATE": "금리 흐름은 늦게 보면 이미 가격에 반영된 경우가 많다",
        "GOLD": "불안한 장에서는 금 흐름을 같이 보는 것이 중요하다",
        "TRUMP": "정책 뉴스는 늦게 보면 이미 가격에 반영된 경우가 많다",
        "GEO": "지정학 뉴스는 생각보다 훨씬 빨리 가격에 반영된다",
        "GENERAL": "이럴수록 큰 방향부터 먼저 확인하는 것이 좋다",
    }
    return table[key]


def rewrite(title, desc, mode="normal", number_hint=None, retry=0):
    seed = f"{title} {desc}"
    key = _topic_key(title, desc)

    eyebrow = _make_eyebrow(key, seed)
    title1 = _make_title1(title, desc, key)
    title2 = _make_title2(key, seed)
    desc1 = _make_desc1(key)
    desc2 = _make_desc2(key)

    visual_topic_map = {
        "CRYPTO": "btc_moon" if _contains(seed, ["급등", "상승", "반등", "surge", "rise", "jump"]) else "btc_panic",
        "OIL": "oil_shock",
        "FX": "rate_cut_doubt",
        "RATE": "rate_cut_doubt",
        "GOLD": "gold_rush",
        "TRUMP": "trump_tariff",
        "GEO": "mideast_tension",
        "GENERAL": "market_general",
    }

    accent_map = {
        "CRYPTO": "neon_gold",
        "OIL": "orange",
        "FX": "electric_blue",
        "RATE": "electric_blue",
        "GOLD": "gold",
        "TRUMP": "orange",
        "GEO": "orange",
        "GENERAL": "gold",
    }

    topic_label_map = {
        "CRYPTO": "BTC",
        "OIL": "OIL",
        "FX": "RATE",
        "RATE": "RATE",
        "GOLD": "GOLD",
        "TRUMP": "TRUMP",
        "GEO": "MIDEAST",
        "GENERAL": "MARKET",
    }

    return {
        "eyebrow": _clean(eyebrow, 28),
        "title1": _clean(title1, 24),
        "title2": _clean(title2, 24),
        "desc1": _clean(desc1, 40),
        "desc2": _clean(desc2, 34),
        "topic": topic_label_map[key],
        "visual_topic": visual_topic_map[key],
        "accent": accent_map[key],
        "subtone": "white",
        "card2_title1": _clean("핵심은 이 흐름이 어디까지 번질지다", 24),
        "card2_title2": _clean("시장은 항상 뉴스보다 먼저 움직인다", 24),
        "card3_hook": _clean("결국 중요한 건 돈의 방향이다", 22),
        "card3_title": _clean("지금 흐름을 먼저 보는 편이 낫다", 24),
        "card3_desc1": _clean("숫자보다 중요한 건 시장이 왜 먼저 반응했는지 이해하는 것이다", 34),
        "card3_desc2": _clean("저장해두면 다음 움직임을 볼 때 도움이 된다", 30),
        "_key": key,
        "_price_usd": "",
    }
