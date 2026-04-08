import re
from datetime import datetime, timezone

BAD_WORDS = [
    "상황", "흐름", "영향", "변화", "확대", "심화", "통제",
    "가능성", "발생", "심리", "불안", "긴장", "불확실성"
]


def _to_float(value, default=0.0):
    try:
        return float(value)
    except:
        return default


def _pct(yes_price):
    p = _to_float(yes_price, 0.0)
    if 0 <= p <= 1:
        return int(round(p * 100))
    return int(round(p))


def _format_eok(volume):
    v = _to_float(volume, 0.0)
    if v <= 0:
        return ""

    krw = v * 1350
    eok = krw / 100000000

    if eok >= 100:
        return f"{int(round(eok))}억"
    if eok >= 10:
        return f"{eok:.1f}억"
    if v >= 1000000:
        return f"${v/1000000:.1f}M"
    if v >= 1000:
        return f"${v/1000:.0f}K"
    return f"${int(v)}"


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
    except:
        return None


def _contains(text, keywords):
    t = text.lower()
    return any(k in t for k in keywords)


def _pick_theme(question):
    q = question.lower()

    if _contains(q, ["oil", "wti", "crude", "brent", "hormuz", "strait"]):
        return "oil"
    if _contains(q, ["gold"]):
        return "gold"
    if _contains(q, ["bitcoin", "btc"]):
        return "bitcoin"
    if _contains(q, ["ethereum", "eth"]):
        return "ethereum"
    if _contains(q, ["fed", "rate", "rates", "inflation", "cpi", "yield", "treasury"]):
        return "macro"
    if _contains(q, ["tariff", "china", "exports"]):
        return "trade"
    if _contains(q, ["nasdaq", "s&p", "dow", "stocks"]):
        return "stocks"
    if _contains(q, ["trump", "election", "president", "white house"]):
        return "politics"
    if _contains(q, ["iran", "israel", "war", "missile", "attack", "troops", "ceasefire"]):
        return "geopolitics"
    return "market"


def _clean_short(text, max_len=12):
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _sanitize(result):
    for key in ["title1", "title2", "desc1", "desc2"]:
        value = str(result.get(key, "")).strip()
        for bad in BAD_WORDS:
            value = value.replace(bad, "")
        value = re.sub(r"\s+", " ", value).strip()
        if key.startswith("title"):
            value = value[:12]
        else:
            value = value[:18]
        result[key] = value
    return result


def _fallback(question, volume, yes_price, end_date):
    prob = _pct(yes_price)
    vol = _format_eok(volume)
    dday = _days_left(end_date)

    result = {
        "title1": f"확률 {prob}%",
        "title2": f"거래 {vol}" if vol else "돈 붙었다",
        "desc1": f"D-{dday} 남았다" if dday is not None else "마감 전 베팅 증가",
        "desc2": "숫자 있는 카드만 간다"
    }
    return _sanitize(result)


def rewrite_poly(question, volume, yes_price, end_date, retry=0):
    q = str(question or "")
    q_low = q.lower()
    prob = _pct(yes_price)
    vol = _format_eok(volume)
    dday = _days_left(end_date)
    theme = _pick_theme(q)

    if theme == "oil":
        result = {
            "title1": f"유가 확률 {prob}%",
            "title2": f"거래 {vol}" if vol else "유가돈 몰림",
            "desc1": "유가 뛰면 물가 뛴다",
            "desc2": f"D-{dday} 앞두고 베팅" if dday is not None else "원유 시장 먼저 반응",
        }

    elif theme == "gold":
        result = {
            "title1": f"금값 확률 {prob}%",
            "title2": f"거래 {vol}" if vol else "금으로 돈 몰림",
            "desc1": "금 튀면 달러도 본다",
            "desc2": f"D-{dday} 전 베팅 증가" if dday is not None else "안전자산 먼저 반응",
        }

    elif theme == "bitcoin":
        result = {
            "title1": f"비트 확률 {prob}%",
            "title2": f"거래 {vol}" if vol else "비트돈 몰림",
            "desc1": "비트 오르면 알트 붙는다",
            "desc2": f"D-{dday} 전 베팅 증가" if dday is not None else "코인 자금 먼저 반응",
        }

    elif theme == "ethereum":
        result = {
            "title1": f"이더 확률 {prob}%",
            "title2": f"거래 {vol}" if vol else "이더돈 몰림",
            "desc1": "ETH 강하면 시장 돈 돈다",
            "desc2": f"D-{dday} 전 베팅 증가" if dday is not None else "거래대금 먼저 반응",
        }

    elif theme == "macro":
        if _contains(q_low, ["cpi", "inflation"]):
            title1 = f"물가 확률 {prob}%"
            desc1 = "물가 숫자면 금리 본다"
        elif _contains(q_low, ["yield", "treasury"]):
            title1 = f"채권 확률 {prob}%"
            desc1 = "채권 튀면 나스닥 본다"
        else:
            title1 = f"금리 확률 {prob}%"
            desc1 = "금리 숫자면 증시 흔든다"

        result = {
            "title1": title1,
            "title2": f"거래 {vol}" if vol else "금리돈 몰림",
            "desc1": desc1,
            "desc2": f"D-{dday} 전 포지션 쌓임" if dday is not None else "달러 코인 같이 반응",
        }

    elif theme == "trade":
        result = {
            "title1": f"관세 확률 {prob}%",
            "title2": f"거래 {vol}" if vol else "관세돈 몰림",
            "desc1": "관세 붙으면 물가 자극",
            "desc2": f"D-{dday} 전 베팅 증가" if dday is not None else "수출주 먼저 반응",
        }

    elif theme == "stocks":
        result = {
            "title1": f"증시 확률 {prob}%",
            "title2": f"거래 {vol}" if vol else "증시돈 몰림",
            "desc1": "증시 숫자면 코인도 본다",
            "desc2": f"D-{dday} 전 포지션 쌓임" if dday is not None else "위험자산 바로 반응",
        }

    elif theme == "politics":
        result = {
            "title1": f"대선 확률 {prob}%",
            "title2": f"거래 {vol}" if vol else "정치돈 몰림",
            "desc1": "정책 숫자면 달러가 본다",
            "desc2": f"D-{dday} 전 베팅 증가" if dday is not None else "정책 기대 먼저 반응",
        }

    elif theme == "geopolitics":
        if _contains(q_low, ["ceasefire"]):
            title1 = f"휴전 확률 {prob}%"
            desc1 = "휴전 숫자면 유가 본다"
            desc2 = f"D-{dday} 전 베팅 증가" if dday is not None else "유가 금값 먼저 반응"
        elif _contains(q_low, ["attack", "missile", "war", "troops"]):
            title1 = f"공격 확률 {prob}%"
            desc1 = "공격 숫자면 유가 뛴다"
            desc2 = f"D-{dday} 전 베팅 증가" if dday is not None else "원유 금값 먼저 반응"
        else:
            title1 = f"중동 확률 {prob}%"
            desc1 = "중동 숫자면 금값 본다"
            desc2 = f"D-{dday} 전 베팅 증가" if dday is not None else "유가 금값 먼저 반응"

        result = {
            "title1": title1,
            "title2": f"거래 {vol}" if vol else "돈 바로 붙었다",
            "desc1": desc1,
            "desc2": desc2,
        }

    else:
        result = _fallback(q, volume, yes_price, end_date)

    result = _sanitize(result)

    if not result["title1"] or not result["title2"]:
        return _fallback(q, volume, yes_price, end_date)

    return result