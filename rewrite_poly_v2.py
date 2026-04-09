"""
rewrite_poly_v2.py — 폴리마켓 카드 텍스트 생성 (캐러셀 강화)

변경사항:
- 카드2/3 텍스트 자동 생성
- _volume, _prob 메타데이터 하단 바 연동
- 기존 rewrite_poly.py 기능 100% 유지 + 확장
"""

import re
import hashlib
from datetime import datetime, timezone
from price_data import get_prices_for_topic

HOOKS = {
    "TRUMP_DEAL": [
        "먼저 탄 애들만 웃는다", "이거 보고 탄 애만 이김", "친구는 벌써 들뜬다",
        "나만 또 늦는 그림", "단톡방 먼저 시끄럽다", "캡처 올리는 애들 올라온다",
        "회사에서 몰래 보는중", "이번에도 남들만 먹나",
    ],
    "TRUMP_TARIFF": [
        "월급 로그아웃 각", "지갑 또 타격을 받는다", "마트 가기 무서워짐",
        "체감물가 또 올라간다", "수입주 표정 썩음", "이거 나오면 다 떨림",
        "또 생활비만 아프다", "달러 먼저 튈 수 있다",
    ],
    "BTC_UP": [
        "친구는 벌써 캡처함", "늦으면 또 구경만", "또 나만 못 탄 그림",
        "단톡방 수익인증 각", "회사 몰래 차트 보는중", "지금 안 보면 또 늦음",
        "개미들 또 미쳐감", "나 빼고 다 타는중",
    ],
    "BTC_DOWN": [
        "또 고점 구경하나", "심장 약하면 못봄", "수익인증 끝날수도",
        "방금 웃던 애들 조용", "단톡방 갑자기 정적", "손절 얘기 슬슬 올라온다",
        "들어갔다가 울수도", "또 멘탈 시험 시작",
    ],
    "ETH_UP": [
        "알트방 단체 흥분한다", "이더 먼저 튀면 다 뜀", "또 코인판 미쳐감",
        "친구는 이미 탔을지도", "이번엔 알트장 냄새", "개미들 눈빛 달라짐",
        "불장 기대감 올라간다", "늦으면 또 배아프다",
    ],
    "ETH_DOWN": [
        "알트들 표정 굳음", "또 이더에 당하나", "코인판 갑자기 싸늘하다",
        "수익인증방 조용해진다", "들어가면 멘붕각", "또 고점 물릴수도",
        "이더 눈치게임 시작", "갑자기 분위기 냉각",
    ],
    "OIL": [
        "주유소 가기 무서워짐", "기름값 또 멘붕", "차 끌수록 손해같음",
        "지갑 바로 털림각", "출퇴근비 또 오름", "물가 다시 깨움",
        "기름값 뉴스 또 뜰듯", "이번엔 체감 빨리 옴",
    ],
    "GOLD": [
        "쫄보 돈이 제일 빠름", "겁먹은 돈 다 몰림", "불안할수록 금부터 봄",
        "안전자산 또 인기폭발", "큰돈이 먼저 움직인다", "불안할수록 금을 찾게 된다",
        "시장이 무섭긴 한가봄", "현금 말고 금 찾는중",
    ],
    "RATE": [
        "기대했다가 숨멎함", "월가 지금 멘탈나감", "성장주 표정 굳음",
        "나스닥 또 시험대", "다들 강한 척만 하는중", "한마디에 시장 휘청",
        "기대감이 갑자기 식는다", "미장 하는 애들 긴장중",
    ],
    "CPI": [
        "물가 때문에 다 꼬임", "이 숫자 하나에 뒤집힘", "월가 식은땀 모드",
        "성장주들 표정 굳음", "물가가 제일 무서움", "다들 CPI를 기다린다",
        "나스닥 멘탈 시험중", "이거 하나로 분위기 끝",
    ],
    "BOND": [
        "월가 표정이 바로 굳는다", "국채금리 무섭게 뛴다", "성장주 또 맞는중",
        "다들 안전한척 쫄린다", "채권 때문에 분위기 박살", "월가 아저씨들 한숨을 쉰다",
        "나스닥에 찬물을 끼얹는다", "숫자 하나에 멘탈 흔들",
    ],
    "DEAL": [
        "먼저 탄 놈들만 들뜬다", "시장 갑자기 환호한다", "또 나만 늦는 그림",
        "친구는 벌써 웃는다", "단톡방이 갑자기 활발해진다", "회사에서도 몰래 보게 된다",
        "또 남들만 먹는각", "수익인증 올릴 분위기",
    ],
    "TRADE": [
        "체감물가 또 올라간다", "수출주 눈치게임", "관세 하나에 분위기 바뀜",
        "지갑 먼저 아파지는중", "마트 물가 생각남", "이번엔 생활비 이슈",
        "괜히 장바구니 무서움", "뉴스보다 지갑이 먼저 앎",
    ],
    "STOCK_UP": [
        "다들 강한 척 들뜬다", "월가 표정이 오늘 좋다", "위험자산이 다시 살아난다",
        "수익인증 슬슬 올라옴", "친구는 또 미장 자랑함", "장 끝나고 단톡방 난리",
        "상승장 냄새 좀 남", "다시 욕심나는 그림",
    ],
    "STOCK_DOWN": [
        "다들 강한 척 쫄린다", "월가 표정이 다시 굳는다", "위험자산 눈치게임",
        "수익인증방 갑자기 조용", "친구도 오늘은 말없음", "차트보다 표정이 말해줌",
        "오늘 미장은 쉽지 않다", "멘탈 약하면 못봄",
    ],
    "MIDEAST": [
        "기름값이 다시 튈 수 있다", "유가가 먼저 반응한다", "불안하면 금도 뜀",
        "중동 변수 무시 못함", "이건 기름값으로 옴", "뉴스보다 주유소가 빠름",
        "생활비로 바로 체감된다", "위험자산 먼저 움찔",
    ],
    "MARKET": [
        "지금 돈 방향 바뀜", "친구는 벌써 보고있음", "또 나만 늦는 그림",
        "단톡방에 돌만한 각", "이건 그냥 지나치면 아까움", "오늘 돈 냄새 남",
        "먼저 본 애가 웃음", "또 남들만 알고 감",
    ],
}

TITLE2 = {
    "TRUMP_DEAL":  ["또 나만 늦음", "이미 돈은 움직임", "친구는 벌써 탐", "시장 먼저 반응"],
    "TRUMP_TARIFF":["지갑 또 맞는다", "달러 또 튄다", "물가 다시 뜬다", "생활비 멘붕각"],
    "BTC_UP":      ["늦으면 또 구경만", "또 남들만 먹음", "지금 돈 미친듯 붙음", "개미들 눈돌아감"],
    "BTC_DOWN":    ["또 고점 구경하나", "수익인증 끝날수도", "단톡방 갑자기 조용", "심장 약하면 못봄"],
    "ETH_UP":      ["알트장 또 미쳐감", "개미들 지금 흥분한다", "이더가 먼저 튄다", "코인판 단체 광기"],
    "ETH_DOWN":    ["알트장 갑자기 싸늘하다", "또 물릴수도 있음", "분위기 순식간에 식는다", "고점 잡을까 무서움"],
    "OIL":         ["기름값 또 멘붕", "지갑 바로 털림각", "물가 다시 자극", "출퇴근비 또 오른다"],
    "GOLD":        ["겁먹은 돈 몰림", "안전자산 풀매수", "쫄보 자금 먼저 뜀", "불안할수록 금 본다"],
    "RATE":        ["나스닥 숨멎", "월가 지금 멘탈나감", "성장주 또 압박", "기대감 바로 식는다"],
    "CPI":         ["나스닥 식은땀", "물가 하나에 뒤집힘", "성장주 표정 굳음", "금리 기대 박살남"],
    "BOND":        ["월가 표정 썩음", "성장주 또 압박", "채권이 분위기 깸", "미장하는 애들 긴장"],
    "DEAL":        ["시장 갑자기 환호한다", "또 남들만 웃음", "수익인증 각 올라온다", "분위기 급반전"],
    "TRADE":       ["물가 또 꿈틀댐", "수출주 눈치봄", "장바구니 또 아프다", "생활비부터 반응한다"],
    "STOCK_UP":    ["월가 표정 좋음", "다들 강한척 들뜬다", "위험자산 살아남", "또 욕심 올라옴"],
    "STOCK_DOWN":  ["다들 강한척 쫄음", "위험자산 눈치게임", "월가 표정이 다시 굳는다", "오늘 미장은 쉽지 않다"],
    "MIDEAST":     ["유가 먼저 튄다", "금값도 같이 뛴다", "기름값 바로 반응", "생활비로 체감된다"],
    "MARKET":      ["돈 움직인다", "친구는 벌써 본 것 같다", "또 남들만 먼저 안다", "이건 그냥 지나치기 어렵다"],
}

DESC2 = {
    "TRUMP_DEAL":  ["관세 기대 뒤집힘", "시장 기대감 급반전", "딜 기대 먼저 반영", "뉴스보다 돈이 빠름"],
    "TRUMP_TARIFF":["달러 먼저 꿈틀", "수입주 표정 굳음", "체감물가 또 불안", "생활비가 먼저 아프다"],
    "BTC_UP":      ["마감 전에 돈이 붙는다", "차트보다 반응 빠름", "단톡방 수익인증 각", "지금 놓치면 또 늦음"],
    "BTC_DOWN":    ["마감 전 멘탈 시험", "수익인증방 조용해진다", "단톡방이 조용해진다", "차트가 사람 잡는중"],
    "ETH_UP":      ["알트 분위기가 달라진다", "코인판 단체 반응", "불장 기대 살아남", "이더 먼저 튀면 따라감"],
    "ETH_DOWN":    ["알트장이 눈치게임에 들어간다", "급락이 오면 순식간이다", "고점 물리면 답없음", "이더 흔들리면 다 흔들"],
    "OIL":         ["물가 자극 바로 옴", "주유소부터 체감됨", "생활비 쪽부터 아프다", "출퇴근비 먼저 올라간다"],
    "GOLD":        ["안전자산부터 반응", "겁먹은 돈이 가장 빠르다", "달러랑 같이 체크", "쫄릴수록 금 찾음"],
    "RATE":        ["월가 촉각 곤두섬", "미장 하는 애들 긴장", "성장주 민감하게 반응", "금리 기대감 흔들림"],
    "CPI":         ["물가 숫자 하나가 끝냄", "기대감 박살나는중", "금리 전망 바로 바뀜", "성장주들 숨참는중"],
    "BOND":        ["국채가 분위기 깸", "성장주 또 맞는중", "채권이 차가운물 뿌림", "월가가 한숨을 쉰다"],
    "DEAL":        ["늦으면 또 배아프다", "돈은 먼저 웃는다", "차트보다 뉴스가 빠름", "이건 단톡방 돌만함"],
    "TRADE":       ["생활비로 바로 온다", "마트 물가 생각남", "장바구니부터 아프다", "수출주들 눈치보는중"],
    "STOCK_UP":    ["월가 분위기가 살아난다", "위험자산 다시 꿈틀", "수익인증 올릴 각", "욕심 올라오면 위험"],
    "STOCK_DOWN":  ["오늘은 쉽지않음", "미장방 공기 싸늘하다함", "위험자산 다 움찔", "차트보다 표정이 먼저"],
    "MIDEAST":     ["주유소 가격으로 옴", "금값도 같이 반응", "중동 뉴스 무시 못함", "생활비까지 연결됨"],
    "MARKET":      ["핵심만 빠르게 보면됨", "돈 냄새 나는 이슈", "먼저 본 애가 유리", "시장 먼저 반응중"],
}

# 카드2 맥락 설명
POLY_CARD2 = {
    "BTC":     ("폴리마켓 예측시장", "전세계 돈이 이 확률에 베팅중"),
    "OIL":     ("실전 투자자들의 판단", "배럴당 가격 방향에 수백억 베팅"),
    "GOLD":    ("스마트 머니 예측", "안전자산 방향에 큰 돈 쏠리는중"),
    "TRUMP":   ("트럼프 정책 예측시장", "관세/딜 방향에 전세계 베팅중"),
    "RATE":    ("금리 방향 예측시장", "연준 결정에 월가 자금 베팅중"),
    "MIDEAST": ("지정학 리스크 예측", "중동 상황 변화에 유가 직결됨"),
    "GENERAL": ("폴리마켓 예측 데이터", "실전 투자자들의 집단 지성"),
}


def _stable_pick(arr, seed_text):
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return arr[h % len(arr)]


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


def _format_krw_eok(volume_usd):
    v = _to_float(volume_usd, 0.0)
    if v <= 0:
        return "0억"
    krw = v * 1380
    eok = krw / 100_000_000
    if eok >= 100:
        return f"{int(round(eok))}억"
    if eok >= 10:
        return f"{eok:.1f}억"
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
    except:
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
                return f"${int(round(val/1000))}K"
            return f"${int(val)}"
        except:
            pass
    m = re.search(r"(\d+)\s?(?:bp|bps)", q.lower())
    if m:
        return f"{m.group(1)}bp"
    return None


def _pick_theme(question):
    q = question.lower()
    if _contains(q, ["bitcoin", "btc"]):       return "BTC"
    if _contains(q, ["ethereum", "eth"]):       return "ETH"
    if _contains(q, ["oil", "wti", "crude", "brent", "hormuz", "strait"]): return "OIL"
    if _contains(q, ["gold"]):                  return "GOLD"
    if _contains(q, ["fed", "rate", "inflation", "cpi", "yield", "treasury"]): return "RATE"
    if _contains(q, ["nasdaq", "s&p", "dow", "stocks"]): return "STOCK"
    if _contains(q, ["tariff", "china", "exports", "trade deal", "deal"]): return "TRADE"
    if _contains(q, ["trump"]):                 return "TRUMP"
    if _contains(q, ["iran", "israel", "war", "missile", "attack", "ceasefire"]): return "MIDEAST"
    return "MARKET"


def rewrite_poly(question, volume, yes_price, end_date, retry=0):
    q = question.lower()
    theme = _pick_theme(question)
    prob = _pct(yes_price)
    vol = _format_krw_eok(volume)
    dday = _days_left(end_date)
    target = _extract_target_number(question)

    # 실시간 가격 (OIL/BTC/GOLD는 desc에 실제 가격 보강)
    topic_key_map = {"OIL": "OIL", "BTC": "BTC", "ETH": "BTC", "GOLD": "GOLD",
                     "RATE": "RATE", "TRUMP": "TRUMP"}
    price_data = get_prices_for_topic(topic_key_map.get(theme, "GENERAL"))

    # ── 기본값 ─────────────────────────────────────────────
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
                "eyebrow":  _stable_pick(HOOKS[key], question),
                "title1":   f"무역딜 {prob}%",
                "title2":   _stable_pick(TITLE2["DEAL"], question),
                "desc1":    f"거래대금 {vol}",
                "desc2":    _stable_pick(DESC2["DEAL"], question),
                "topic":    "DEAL",
                "visual_topic": "trump_deal_positive" if prob >= 50 else "trump_deal_negative",
                "accent":   "gold",
                "_key":     "TRUMP",
            })
        elif _contains(q, ["tariff"]):
            key = "TRUMP_TARIFF"
            result.update({
                "eyebrow":  _stable_pick(HOOKS[key], question),
                "title1":   f"관세카드 {prob}%",
                "title2":   _stable_pick(TITLE2["TRUMP_TARIFF"], question),
                "desc1":    f"거래대금 {vol}",
                "desc2":    _stable_pick(DESC2["TRUMP_TARIFF"], question),
                "topic":    "TRUMP",
                "visual_topic": "trump_tariff",
                "accent":   "hot_red",
                "_key":     "TRUMP",
            })
        else:
            result.update({
                "title1":   f"트럼프 변수 {prob}%",
                "title2":   "시장 또 뒤집힘",
                "desc1":    f"거래대금 {vol}",
                "desc2":    "정책 한마디 폭탄",
                "topic":    "TRUMP",
                "visual_topic": "trump_positive" if prob >= 50 else "trump_negative",
                "accent":   "gold" if prob >= 50 else "hot_red",
                "_key":     "TRUMP",
            })

    elif theme == "BTC":
        key = "BTC_UP" if prob >= 50 else "BTC_DOWN"
        price_desc = price_data["desc2"] if price_data else (
            f"마감 {dday}일 남음" if dday is not None else _stable_pick(DESC2[key], question)
        )
        result.update({
            "eyebrow":  _stable_pick(HOOKS[key], question),
            "title1":   f"비트 {target} {prob}%" if target else f"비트코인 {prob}%",
            "title2":   _stable_pick(TITLE2[key], question),
            "desc1":    price_data["desc1"] if price_data else f"거래대금 {vol}",
            "desc2":    price_desc,
            "topic":    "BTC",
            "visual_topic": "btc_moon" if prob >= 50 else "btc_panic",
            "accent":   "neon_gold" if prob >= 50 else "hot_red",
            "_key":     "BTC",
        })

    elif theme == "ETH":
        key = "ETH_UP" if prob >= 50 else "ETH_DOWN"
        result.update({
            "eyebrow":  _stable_pick(HOOKS[key], question),
            "title1":   f"이더 {target} {prob}%" if target else f"이더리움 {prob}%",
            "title2":   _stable_pick(TITLE2[key], question),
            "desc1":    f"거래대금 {vol}",
            "desc2":    _stable_pick(DESC2[key], question),
            "topic":    "ETH",
            "visual_topic": "eth_surge" if prob >= 50 else "eth_drop",
            "accent":   "electric_blue" if prob >= 50 else "hot_red",
            "_key":     "BTC",
        })

    elif theme == "OIL":
        price_desc1 = price_data["desc1"] if price_data else f"거래대금 {vol}"
        price_desc2 = price_data["desc2"] if price_data else _stable_pick(DESC2["OIL"], question)
        result.update({
            "eyebrow":  _stable_pick(HOOKS["OIL"], question),
            "title1":   f"유가 {target} {prob}%" if target else f"유가 급등 {prob}%",
            "title2":   _stable_pick(TITLE2["OIL"], question),
            "desc1":    price_desc1,
            "desc2":    price_desc2,
            "topic":    "OIL",
            "visual_topic": "oil_shock" if prob >= 50 else "oil_relief",
            "accent":   "orange",
            "_key":     "OIL",
        })

    elif theme == "GOLD":
        price_desc1 = price_data["desc1"] if price_data else f"거래대금 {vol}"
        price_desc2 = price_data["desc2"] if price_data else _stable_pick(DESC2["GOLD"], question)
        result.update({
            "eyebrow":  _stable_pick(HOOKS["GOLD"], question),
            "title1":   f"금값 급등 {prob}%",
            "title2":   _stable_pick(TITLE2["GOLD"], question),
            "desc1":    price_desc1,
            "desc2":    price_desc2,
            "topic":    "GOLD",
            "visual_topic": "gold_rush" if prob >= 50 else "gold_cool",
            "accent":   "gold",
            "_key":     "GOLD",
        })

    elif theme == "RATE":
        if _contains(q, ["cpi", "inflation"]):
            result.update({
                "eyebrow":  _stable_pick(HOOKS["CPI"], question),
                "title1":   f"CPI 쇼크 {prob}%",
                "title2":   _stable_pick(TITLE2["CPI"], question),
                "desc1":    f"거래대금 {vol}",
                "desc2":    _stable_pick(DESC2["CPI"], question),
                "topic":    "CPI",
                "visual_topic": "inflation_shock",
                "accent":   "hot_red",
                "_key":     "RATE",
            })
        elif _contains(q, ["yield", "treasury"]):
            result.update({
                "eyebrow":  _stable_pick(HOOKS["BOND"], question),
                "title1":   f"국채금리 {prob}%",
                "title2":   _stable_pick(TITLE2["BOND"], question),
                "desc1":    f"거래대금 {vol}",
                "desc2":    _stable_pick(DESC2["BOND"], question),
                "topic":    "BOND",
                "visual_topic": "bond_stress",
                "accent":   "electric_blue",
                "_key":     "RATE",
            })
        else:
            rate_desc2 = f"마감 {dday}일 남음" if dday is not None else _stable_pick(DESC2["RATE"], question)
            result.update({
                "eyebrow":  _stable_pick(HOOKS["RATE"], question),
                "title1":   f"금리 인하 {prob}%",
                "title2":   _stable_pick(TITLE2["RATE"], question),
                "desc1":    f"거래대금 {vol}",
                "desc2":    rate_desc2,
                "topic":    "RATE",
                "visual_topic": "rate_cut_hype" if prob >= 50 else "rate_cut_doubt",
                "accent":   "electric_blue",
                "_key":     "RATE",
            })

    elif theme == "TRADE":
        if _contains(q, ["deal"]):
            result.update({
                "eyebrow":  _stable_pick(HOOKS["DEAL"], question),
                "title1":   f"무역딜 {prob}%",
                "title2":   _stable_pick(TITLE2["DEAL"], question),
                "desc1":    f"거래대금 {vol}",
                "desc2":    _stable_pick(DESC2["DEAL"], question),
                "topic":    "DEAL",
                "visual_topic": "trade_deal_hype",
                "accent":   "gold",
                "_key":     "TRUMP",
            })
        else:
            result.update({
                "eyebrow":  _stable_pick(HOOKS["TRADE"], question),
                "title1":   f"관세 변수 {prob}%",
                "title2":   _stable_pick(TITLE2["TRADE"], question),
                "desc1":    f"거래대금 {vol}",
                "desc2":    _stable_pick(DESC2["TRADE"], question),
                "topic":    "TRADE",
                "visual_topic": "trade_tension",
                "accent":   "orange",
                "_key":     "TRUMP",
            })

    elif theme == "STOCK":
        key = "STOCK_UP" if prob >= 50 else "STOCK_DOWN"
        result.update({
            "eyebrow":  _stable_pick(HOOKS[key], question),
            "title1":   f"증시 방향 {prob}%",
            "title2":   _stable_pick(TITLE2[key], question),
            "desc1":    f"거래대금 {vol}",
            "desc2":    _stable_pick(DESC2[key], question),
            "topic":    "STOCK",
            "visual_topic": "stocks_up" if prob >= 50 else "stocks_down",
            "accent":   "green" if prob >= 50 else "hot_red",
            "_key":     "RATE",
        })

    elif theme == "MIDEAST":
        is_ceasefire = _contains(q, ["ceasefire"])
        result.update({
            "eyebrow":  _stable_pick(HOOKS["MIDEAST"], question),
            "title1":   f"휴전 성사 {prob}%" if is_ceasefire else f"중동 충돌 {prob}%",
            "title2":   _stable_pick(TITLE2["MIDEAST"], question),
            "desc1":    f"거래대금 {vol}",
            "desc2":    _stable_pick(DESC2["MIDEAST"], question),
            "topic":    "MIDEAST",
            "visual_topic": "mideast_relief" if (is_ceasefire and prob >= 50) else "mideast_tension",
            "accent":   "orange",
            "_key":     "OIL",
        })

    # ── 카드2/3 공통 텍스트 ──────────────────────────────────
    _key = result.get("_key", "GENERAL")
    poly_card2 = POLY_CARD2.get(_key, POLY_CARD2["GENERAL"])
    result["card2_title1"] = poly_card2[0]
    result["card2_title2"] = poly_card2[1]
    result["card3_hook"]   = "폴리마켓이 뭔지 알아?"
    result["card3_title"]  = "예측시장 = 진짜 돈의 방향"
    result["card3_desc1"]  = "팔로우하면 매일 알려줌"
    result["card3_desc2"]  = "저장해두면 나중에 유용함"

    # ── clean ─────────────────────────────────────────────
    for field, max_len in [
        ("eyebrow", 22), ("title1", 20), ("title2", 18),
        ("desc1", 26), ("desc2", 24), ("topic", 12),
        ("visual_topic", 24), ("accent", 20), ("subtone", 20),
        ("card2_title1", 22), ("card2_title2", 22),
        ("card3_hook", 22), ("card3_title", 22),
    ]:
        if field in result:
            result[field] = _clean(result[field], max_len)

    return result
