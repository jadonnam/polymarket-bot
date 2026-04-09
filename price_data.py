"""
실시간 가격 데이터 수집 모듈
무료 API만 사용 (API 키 불필요)
"""

import requests

def get_oil_price():
    """WTI 유가 (USD) - Yahoo Finance"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/CL=F"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        return round(price, 2)
    except:
        return None

def get_btc_price():
    """비트코인 가격 (USD) - CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids": "bitcoin", "vs_currencies": "usd"}
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        return int(data["bitcoin"]["usd"])
    except:
        return None

def get_gold_price():
    """금 가격 (USD/oz) - Yahoo Finance"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        return round(price, 2)
    except:
        return None

def get_usd_krw():
    """달러/원 환율 - Yahoo Finance"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/KRW=X"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        return round(price, 1)
    except:
        return None

def get_prices_for_topic(topic):
    """
    토픽별 관련 가격 데이터 반환
    Returns: dict with price info
    """
    if topic == "OIL":
        price = get_oil_price()
        if price:
            krw = get_usd_krw() or 1380
            krw_price = round(price * krw / 159, 0)  # 배럴 → 리터 환산 (원)
            return {
                "usd": f"${price}",
                "desc1": f"WTI 현재 배럴당 {price}달러",
                "desc2": f"국내 리터당 약 {int(krw_price)}원에 영향 줍니다",
            }

    elif topic == "BTC":
        price = get_btc_price()
        if price:
            krw = get_usd_krw() or 1380
            krw_price = round(price * krw / 1_000_000, 1)  # 억원
            return {
                "usd": f"${price:,}",
                "desc1": f"비트코인 현재 {price:,}달러",
                "desc2": f"원화 기준 약 {krw_price}억원입니다",
            }

    elif topic == "GOLD":
        price = get_gold_price()
        if price:
            return {
                "usd": f"${price}",
                "desc1": f"금 현물 온스당 {price}달러",
                "desc2": f"연초 대비 흐름을 같이 보면 좋습니다",
            }

    elif topic in ("RATE", "TRUMP", "GENERAL"):
        usd = get_usd_krw()
        if usd:
            return {
                "usd": f"{usd}원",
                "desc1": f"달러/원 현재 {usd}원",
                "desc2": f"환율 변동이 바로 체감됩니다",
            }

    return None
