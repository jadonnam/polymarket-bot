import re
import hashlib
from datetime import datetime, timezone
from price_data import get_prices_for_topic

HOOKS = {
    "TRUMP_DEAL": [
        "협상 기대가 시장에 먼저 반영된다",
        "정책 변화는 가격에 먼저 찍힌다",
        "시장 돈이 합의 기대에 반응한다",
        "협상 뉴스가 투자 심리를 바꾼다",
    ],
    "TRUMP_TARIFF": [
        "관세 변수는 결국 물가로 번진다",
        "달러가 먼저 반응할 수 있다",
        "정책 뉴스가 생활비 기대를 바꾼다",
        "관세 이슈는 체감 가격으로 이어진다",
    ],
    "BTC_UP": [
        "비트가 다시 시장 중심에 선다",
        "자금이 비트로 빠르게 붙는다",
        "코인판 분위기가 다시 달아오른다",
        "비트 방향이 알트 심리까지 흔든다",
    ],
    "BTC_DOWN": [
        "비트가 식으면 코인판 공기도 식는다",
        "시장 심리가 빠르게 약해진다",
        "변동성이 다시 부담으로 돌아온다",
        "알트까지 함께 흔들릴 수 있다",
    ],
    "ETH_UP": [
        "이더가 알트 분위기를 이끈다",
        "자금이 다시 알트로 이동한다",
        "시장 기대가 이더에서 먼저 커진다",
        "이더가 코인판 공기를 바꾼다",
    ],
    "ETH_DOWN": [
        "이더가 흔들리면 알트도 약해질 수 있다",
        "알트장이 빠르게 식을 수 있다",
        "시장 기대가 다시 낮아진다",
        "코인판 변동성이 부담으로 돌아온다",
    ],
    "OIL": [
        "유가 변수는 생활비와 직접 연결된다",
        "원유 가격은 결국 주유소로 이어진다",
        "유가 뉴스는 체감 물가를 흔든다",
        "원유 흐름은 생활비 신호가 된다",
    ],
    "GOLD": [
        "금값은 시장 불안을 가장 먼저 보여준다",
        "안전자산 수요가 먼저 강해진다",
        "공포가 커질수록 금으로 돈이 몰린다",
        "위기 국면에서는 금이 먼저 반응한다",
    ],
    "RATE": [
        "금리 기대는 주식과 환율을 함께 흔든다",
        "연준 변수는 위험자산 분위기를 바꾼다",
        "달러와 성장주가 함께 민감해진다",
        "금리 방향은 시장 기대를 다시 조정한다",
    ],
    "CPI": [
        "물가 숫자 하나가 시장 기대를 바꾼다",
        "CPI는 달러와 금리 기대를 함께 흔든다",
        "물가 뉴스는 바로 가격이 된다",
        "숫자 하나가 위험자산 분위기를 바꾼다",
    ],
    "BOND": [
        "채권 금리는 시장 온도를 보여준다",
        "국채 흐름은 위험자산 분위기를 바꾼다",
        "채권이 먼저 시장 신호를 줄 수 있다",
        "금리 민감 자산이 바로 반응한다",
    ],
    "DEAL": [
        "협상 기대가 시장 심리를 살린다",
        "합의 기대가 가격에 먼저 반영된다",
        "돈은 기대감에 먼저 붙는다",
        "협상 뉴스가 분위기를 빠르게 바꾼다",
    ],
    "TRADE": [
        "무역 변수는 결국 장바구니로 번진다",
        "관세 뉴스는 물가 기대를 흔든다",
        "무역 리스크는 달러와 수출 기대를 건드린다",
        "뉴스가 체감 가격으로 이어질 수 있다",
    ],
    "STOCK_UP": [
        "위험자산 분위기가 다시 살아난다",
        "증시가 시장 기대를 끌어올린다",
        "자금이 다시 주식으로 붙는다",
        "월가 분위기가 다시 밝아진다",
    ],
    "STOCK_DOWN": [
        "위험자산 분위기가 다시 식는다",
        "증시가 시장 공포를 키울 수 있다",
        "월가 공기가 무거워질 수 있다",
        "지수 약세가 다른 자산도 흔든다",
    ],
    "MIDEAST": [
        "중동 변수는 결국 유가로 번진다",
        "지정학 뉴스는 가격표를 흔든다",
        "전쟁 뉴스가 돈 흐름까지 바꾼다",
        "유가와 금값이 함께 반응할 수 있다",
    ],
    "MARKET": [
        "확률보다 베팅금이 더 솔직하다",
        "시장은 숫자로 먼저 말한다",
        "돈이 어디로 붙는지가 핵심이다",
        "가격은 기대를 먼저 반영한다",
    ],
}

TITLE2 = {
    "TRUMP_DEAL":  ["시장 기대가 커진다", "협상 기대가 살아난다", "기대가 가격에 찍힌다", "돈이 먼저 반응한다"],
    "TRUMP_TARIFF":["달러가 다시 반응한다", "물가 걱정이 커진다", "생활비 부담이 커진다", "관세 변수가 커진다"],
    "BTC_UP":      ["자금이 다시 붙는다", "코인판이 다시 달아오른다", "시장 기대가 살아난다", "변동성이 커진다"],
    "BTC_DOWN":    ["분위기가 빠르게 식는다", "시장 심리가 약해진다", "알트도 함께 흔들릴 수 있다", "변동성이 부담이 된다"],
    "ETH_UP":      ["알트장이 먼저 반응한다", "시장 기대가 커진다", "이더가 분위기를 끈다", "자금이 다시 붙는다"],
    "ETH_DOWN":    ["알트장이 빠르게 식는다", "코인판 공기가 바뀐다", "변동성이 부담이 된다", "시장 심리가 약해진다"],
    "OIL":         ["기름값에 바로 닿는다", "물가를 다시 자극한다", "생활비를 건드린다", "주유소에서 체감된다"],
    "GOLD":        ["안전자산으로 몰린다", "불안이 금값에 찍힌다", "공포가 가격이 된다", "시장 방어 심리가 커진다"],
    "RATE":        ["성장주가 바로 흔들린다", "달러도 같이 민감해진다", "시장 기대가 바뀐다", "나스닥이 반응한다"],
    "CPI":         ["물가 기대가 바뀐다", "달러와 주식이 함께 반응한다", "금리 기대를 흔든다", "시장 분위기를 바꾼다"],
    "BOND":        ["채권이 먼저 신호를 준다", "금리 민감 자산이 흔들린다", "시장 온도가 바뀐다", "월가 표정이 바뀐다"],
    "DEAL":        ["기대가 다시 살아난다", "분위기가 빠르게 바뀐다", "협상 뉴스가 돈을 움직인다", "가격이 먼저 반응한다"],
    "TRADE":       ["장바구니로 번질 수 있다", "달러와 물가를 흔든다", "무역 변수가 커진다", "체감 가격에 닿는다"],
    "STOCK_UP":    ["위험자산이 살아난다", "시장 기대가 커진다", "증시가 분위기를 끈다", "돈이 다시 붙는다"],
    "STOCK_DOWN":  ["위험자산이 식는다", "시장 심리가 약해진다", "공기가 무거워진다", "증시가 다시 흔들린다"],
    "MIDEAST":     ["유가가 같이 반응한다", "금값도 같이 뜰 수 있다", "돈 흐름이 바뀔 수 있다", "지정학이 가격이 된다"],
    "MARKET":      ["시장이 먼저 반응한다", "돈이 이미 움직인다", "확률보다 베팅금이 중요하다", "숫자가 먼저 말한다"],
}

DESC2 = {
    "TRUMP_DEAL":  ["협상 기대가 시장에 반영된다", "뉴스보다 돈이 먼저 반응한다", "달러와 관세 기대가 같이 움직인다", "투자 심리가 살아날 수 있다"],
    "TRUMP_TARIFF":["달러가 먼저 반응한다", "수입 물가 걱정이 커질 수 있다", "생활비 부담으로 번질 수 있다", "관세 뉴스는 체감 가격으로 이어진다"],
    "BTC_UP":      ["시장 기대가 다시 커진다", "알트도 함께 따라갈 수 있다", "코인판 공기가 달라진다", "변동성이 다시 살아난다"],
    "BTC_DOWN":    ["시장 심리가 빠르게 약해진다", "알트가 더 크게 흔들릴 수 있다", "차트보다 분위기가 먼저 식는다", "변동성이 부담으로 돌아온다"],
    "ETH_UP":      ["알트장이 먼저 반응할 수 있다", "시장 기대가 다시 커진다", "이더가 코인판 방향을 바꾼다", "분위기가 다시 살아난다"],
    "ETH_DOWN":    ["이더가 흔들리면 알트도 흔들린다", "코인판 공기가 급격히 식는다", "변동성이 다시 부담이 된다", "시장 심리가 약해진다"],
    "OIL":         ["생활비에 직접 닿을 수 있다", "주유소 가격으로 이어질 수 있다", "유가 뉴스는 물가를 자극한다", "체감은 늦어도 돈은 먼저 움직인다"],
    "GOLD":        ["안전자산부터 반응한다", "불안이 커질수록 금이 강해질 수 있다", "금값은 시장 공포를 보여준다", "달러와 함께 체크하면 흐름이 보인다"],
    "RATE":        ["성장주가 더 예민하게 반응한다", "금리 기대가 달러까지 흔든다", "시장이 금리 전망을 다시 계산한다", "월가 분위기가 빠르게 바뀐다"],
    "CPI":         ["물가 숫자가 기대를 바로 바꾼다", "달러와 나스닥이 같이 반응한다", "금리 기대까지 다시 흔들린다", "숫자 하나가 분위기를 끝낼 수 있다"],
    "BOND":        ["채권 금리가 시장 온도를 보여준다", "금리 민감 자산이 바로 반응한다", "국채가 먼저 신호를 줄 수 있다", "채권이 분위기를 바꾸는 날도 많다"],
    "DEAL":        ["협상 기대는 가격으로 먼저 반영된다", "돈은 기대감에 먼저 붙는다", "분위기가 빠르게 바뀔 수 있다", "시장 심리가 살아날 수 있다"],
    "TRADE":       ["무역 변수는 생활비로 이어질 수 있다", "달러와 물가 기대를 같이 흔든다", "관세 뉴스는 체감 가격에 닿는다", "장바구니 부담으로 이어질 수 있다"],
    "STOCK_UP":    ["위험자산 심리가 다시 살아난다", "시장 기대가 커질 수 있다", "증시가 다른 자산 분위기도 끈다", "돈이 다시 주식으로 붙는다"],
    "STOCK_DOWN":  ["위험자산 심리가 빠르게 식는다", "시장 분위기가 무거워질 수 있다", "증시가 다른 자산까지 흔든다", "공포가 가격에 찍힐 수 있다"],
    "MIDEAST":     ["전쟁 뉴스는 결국 유가로 이어진다", "금값과 달러도 같이 반응할 수 있다", "지정학 이슈는 돈 흐름까지 바꾼다", "생활비 변수로 번질 수 있다"],
    "MARKET":      ["핵심은 돈이 어디 붙는지다", "확률보다 베팅금이 더 솔직하다", "시장은 숫자로 먼저 말한다", "저장해두면 다음 흐름을 보기 쉽다"],
}

POLY_CARD2 = {
    "BTC":     ("폴리마켓 예측시장", "전세계 돈이 이 방향에 베팅한다"),
    "OIL":     ("실전 투자자들의 판단", "유가 방향에 실제 돈이 쏠린다"),
    "GOLD":    ("스마트 머니 예측", "안전자산 방향에 돈이 먼저 붙는다"),
    "TRUMP":   ("정책 예측시장", "관세와 협상 기대에 돈이 움직인다"),
    "RATE":    ("금리 방향 예측시장", "연준 기대에 자금이 반응한다"),
    "MIDEAST": ("지정학 리스크 예측", "중동 상황 변화는 유가와 연결된다"),
    "GENERAL": ("폴리마켓 예측 데이터", "실전 투자자의 집단 판단이 모인다"),
}


def _stable_pick(arr, seed_text):
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return arr[h % len(arr)]


def _to_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _pct(yes_price):
    p = _to_float(yes_price, 0.0)
    if 0 <= p <= 1:
        return int(round(p * 100))
    return int(round(p))


def _format_krw_eok(volume_usd):
    v = _to_float(volume_usd, 0.0)
    if v <= 0:
        return "0억"
    krw = v * 1380
    eok = krw / 100_000_000
    if eok >= 100:
        return f"{int(round(eok))}억"
    return f"{eok:.1f}억"


def _days_left(end_date):
    if not end_date:
        return None
    text = str(end_date).strip()
    try:
        if text.endswith("Z"):
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        delta = dt - datetime.now(timezone.utc)
        return max(delta.days, 0)
    except Exception:
        return None


def _contains(text, keywords):
    t = text.lower()
    return any(k in t for k in keywords)


def _clean(text, max_len):
    return re.sub(r"\s+", " ", str(text).strip())[:max_len]


def _extract_target_number(question):
    q = str(question)
    m = re.search(r"\$([\d,]+(?:\.\d+)?)", q)
    if m:
        n = m.group(1).replace(",", "")
        try:
            val = float(n)
            if val >= 10000:
                return f"${int(round(val / 1000))}K"
            return f"${int(val)}"
        except Exception:
            pass
    m = re.search(r"(\d+)\s?(?:bp|bps)", q.lower())
    if m:
        return f"{m.group(1)}bp"
    return None


def _pick_theme(question):
    q = question.lower()
    if _contains(q, ["bitcoin", "btc"]): return "BTC"
    if _contains(q, ["ethereum", "eth"]): return "ETH"
    if _contains(q, ["oil", "wti", "crude", "brent", "hormuz", "strait"]): return "OIL"
    if _contains(q, ["gold"]): return "GOLD"
    if _contains(q, ["fed", "rate", "inflation", "cpi", "yield", "treasury"]): return "RATE"
    if _contains(q, ["nasdaq", "s&p", "dow", "stocks"]): return "STOCK"
    if _contains(q, ["tariff", "china", "exports", "trade deal", "deal"]): return "TRADE"
    if _contains(q, ["trump"]): return "TRUMP"
    if _contains(q, ["iran", "israel", "war", "missile", "attack", "ceasefire"]): return "MIDEAST"
    return "MARKET"


def rewrite_poly(question, volume, yes_price, end_date, retry=0):
    q = question.lower()
    theme = _pick_theme(question)
    prob = _pct(yes_price)
    vol = _format_krw_eok(volume)
    dday = _days_left(end_date)
    target = _extract_target_number(question)

    topic_key_map = {
        "OIL": "OIL", "BTC": "BTC", "ETH": "BTC", "GOLD": "GOLD",
        "RATE": "RATE", "TRUMP": "TRUMP", "TRADE": "TRUMP", "STOCK": "RATE"
    }
    price_data = get_prices_for_topic(topic_key_map.get(theme, "GENERAL"))

    result = {
        "eyebrow":  _stable_pick(HOOKS["MARKET"], question),
        "title1":   f"확률 {prob}%",
        "title2":   _stable_pick(TITLE2["MARKET"], question),
        "desc1":    f"거래대금 {vol}",
        "desc2":    _stable_pick(DESC2["MARKET"], question),
        "topic":    "MARKET",
        "visual_topic": "market_general",
        "accent":   "gold",
        "subtone":  "white",
        "_key":     "GENERAL",
        "_volume":  vol,
        "_prob":    f"{prob}%",
        "_price_usd": price_data.get("usd", "") if price_data else "",
    }

    if theme == "TRUMP":
        if _contains(q, ["deal", "trade deal"]):
            key = "TRUMP_DEAL"
            result.update({
                "eyebrow": _stable_pick(HOOKS[key], question),
                "title1": f"무역딜 {prob}%",
                "title2": _stable_pick(TITLE2[key], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2[key], question),
                "topic": "DEAL",
                "visual_topic": "trump_deal_positive" if prob >= 50 else "trump_deal_negative",
                "accent": "gold",
                "_key": "TRUMP",
            })
        elif _contains(q, ["tariff"]):
            key = "TRUMP_TARIFF"
            result.update({
                "eyebrow": _stable_pick(HOOKS[key], question),
                "title1": f"관세 변수 {prob}%",
                "title2": _stable_pick(TITLE2[key], question),
                "desc1": price_data["desc1"] if price_data else f"거래대금 {vol}",
                "desc2": price_data["desc2"] if price_data else _stable_pick(DESC2[key], question),
                "topic": "TRADE",
                "visual_topic": "trump_tariff",
                "accent": "hot_red",
                "_key": "TRUMP",
            })

    elif theme == "BTC":
        key = "BTC_UP" if prob >= 50 else "BTC_DOWN"
        result.update({
            "eyebrow": _stable_pick(HOOKS[key], question),
            "title1": f"비트 {target} {prob}%" if target else f"비트 방향 {prob}%",
            "title2": _stable_pick(TITLE2[key], question),
            "desc1": price_data["desc1"] if price_data else f"거래대금 {vol}",
            "desc2": price_data["desc2"] if price_data else _stable_pick(DESC2[key], question),
            "topic": "BTC",
            "visual_topic": "btc_moon" if prob >= 50 else "btc_panic",
            "accent": "neon_gold" if prob >= 50 else "hot_red",
            "_key": "BTC",
        })

    elif theme == "ETH":
        key = "ETH_UP" if prob >= 50 else "ETH_DOWN"
        result.update({
            "eyebrow": _stable_pick(HOOKS[key], question),
            "title1": f"이더 {target} {prob}%" if target else f"이더리움 {prob}%",
            "title2": _stable_pick(TITLE2[key], question),
            "desc1": f"거래대금 {vol}",
            "desc2": _stable_pick(DESC2[key], question),
            "topic": "ETH",
            "visual_topic": "eth_surge" if prob >= 50 else "eth_drop",
            "accent": "electric_blue" if prob >= 50 else "hot_red",
            "_key": "BTC",
        })

    elif theme == "OIL":
        result.update({
            "eyebrow": _stable_pick(HOOKS["OIL"], question),
            "title1": f"유가 {target} {prob}%" if target else f"유가 방향 {prob}%",
            "title2": _stable_pick(TITLE2["OIL"], question),
            "desc1": price_data["desc1"] if price_data else f"거래대금 {vol}",
            "desc2": price_data["desc2"] if price_data else _stable_pick(DESC2["OIL"], question),
            "topic": "OIL",
            "visual_topic": "oil_shock" if prob >= 50 else "oil_relief",
            "accent": "orange",
            "_key": "OIL",
        })

    elif theme == "GOLD":
        result.update({
            "eyebrow": _stable_pick(HOOKS["GOLD"], question),
            "title1": f"금값 방향 {prob}%",
            "title2": _stable_pick(TITLE2["GOLD"], question),
            "desc1": price_data["desc1"] if price_data else f"거래대금 {vol}",
            "desc2": price_data["desc2"] if price_data else _stable_pick(DESC2["GOLD"], question),
            "topic": "GOLD",
            "visual_topic": "gold_rush",
            "accent": "gold",
            "_key": "GOLD",
        })

    elif theme == "RATE":
        if _contains(q, ["cpi", "inflation"]):
            result.update({
                "eyebrow": _stable_pick(HOOKS["CPI"], question),
                "title1": f"CPI 변수 {prob}%",
                "title2": _stable_pick(TITLE2["CPI"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["CPI"], question),
                "topic": "CPI",
                "visual_topic": "inflation_shock",
                "accent": "hot_red",
                "_key": "RATE",
            })
        elif _contains(q, ["yield", "treasury"]):
            result.update({
                "eyebrow": _stable_pick(HOOKS["BOND"], question),
                "title1": f"국채 변수 {prob}%",
                "title2": _stable_pick(TITLE2["BOND"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["BOND"], question),
                "topic": "BOND",
                "visual_topic": "bond_stress",
                "accent": "electric_blue",
                "_key": "RATE",
            })
        else:
            result.update({
                "eyebrow": _stable_pick(HOOKS["RATE"], question),
                "title1": f"금리 변수 {target} {prob}%" if target else f"금리 방향 {prob}%",
                "title2": _stable_pick(TITLE2["RATE"], question),
                "desc1": price_data["desc1"] if price_data else f"거래대금 {vol}",
                "desc2": price_data["desc2"] if price_data else _stable_pick(DESC2["RATE"], question),
                "topic": "RATE",
                "visual_topic": "rate_cut_hype" if prob >= 50 else "rate_cut_doubt",
                "accent": "electric_blue",
                "_key": "RATE",
            })

    elif theme == "TRADE":
        key = "DEAL" if _contains(q, ["deal", "agreement"]) else "TRADE"
        result.update({
            "eyebrow": _stable_pick(HOOKS[key], question),
            "title1": f"무역 변수 {prob}%",
            "title2": _stable_pick(TITLE2[key], question),
            "desc1": f"거래대금 {vol}",
            "desc2": _stable_pick(DESC2[key], question),
            "topic": "TRADE" if key == "TRADE" else "DEAL",
            "visual_topic": "trade_deal_hype" if key == "DEAL" and prob >= 50 else "trade_tension",
            "accent": "orange" if key == "TRADE" else "gold",
            "_key": "TRUMP",
        })

    elif theme == "STOCK":
        key = "STOCK_UP" if prob >= 50 else "STOCK_DOWN"
        result.update({
            "eyebrow": _stable_pick(HOOKS[key], question),
            "title1": f"증시 방향 {prob}%",
            "title2": _stable_pick(TITLE2[key], question),
            "desc1": f"거래대금 {vol}",
            "desc2": _stable_pick(DESC2[key], question),
            "topic": "STOCK",
            "visual_topic": "stocks_up" if prob >= 50 else "stocks_down",
            "accent": "green" if prob >= 50 else "hot_red",
            "_key": "RATE",
        })

    elif theme == "MIDEAST":
        result.update({
            "eyebrow": _stable_pick(HOOKS["MIDEAST"], question),
            "title1": f"중동 변수 {prob}%",
            "title2": _stable_pick(TITLE2["MIDEAST"], question),
            "desc1": f"거래대금 {vol}",
            "desc2": _stable_pick(DESC2["MIDEAST"], question),
            "topic": "MIDEAST",
            "visual_topic": "mideast_relief" if _contains(q, ["ceasefire", "normal", "relief"]) and prob >= 50 else "mideast_tension",
            "accent": "orange",
            "_key": "MIDEAST",
        })

    card2_pair = POLY_CARD2.get(result["_key"], POLY_CARD2["GENERAL"])
    dday_text = f"D-{dday}" if dday is not None else "마감 전"

    result["card2_title1"] = _clean(card2_pair[0], 20)
    result["card2_title2"] = _clean(card2_pair[1], 24)
    result["card3_hook"] = _clean(f"{dday_text} 시장이 먼저 반응한다", 20)
    result["card3_title"] = _clean("결국 내 돈과 연결된다", 20)
    result["card3_desc1"] = _clean("확률보다 어디에 돈이 몰리는지 보는 것이 더 중요하다", 30)
    result["card3_desc2"] = _clean("저장해두면 다음 흐름을 비교해서 보기 쉽다", 28)

    for field, max_len in [
        ("eyebrow", 24), ("title1", 22), ("title2", 20),
        ("desc1", 30), ("desc2", 30), ("topic", 12),
        ("visual_topic", 24), ("accent", 20), ("subtone", 20),
        ("card2_title1", 20), ("card2_title2", 24),
        ("card3_hook", 20), ("card3_title", 20),
        ("card3_desc1", 30), ("card3_desc2", 28),
    ]:
        result[field] = _clean(result.get(field, ""), max_len)

    return result
