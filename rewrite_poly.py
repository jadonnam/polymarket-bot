import re
import hashlib
from datetime import datetime, timezone

HOOKS = {
    "TRUMP_DEAL": [
        "먼저 탄 애들만 웃는중",
        "이거 보고 탄 애만 이김",
        "친구는 벌써 신남",
        "나만 또 늦는 그림",
        "단톡방 먼저 난리남",
        "캡처 올리는 애들 나옴",
        "회사에서 몰래 보는중",
        "이번에도 남들만 먹나",
    ],
    "TRUMP_TARIFF": [
        "월급 로그아웃 각",
        "지갑 또 처맞는중",
        "마트 가기 무서워짐",
        "체감물가 또 올라감",
        "수입주 표정 썩음",
        "이거 나오면 다 떨림",
        "또 생활비만 아픔",
        "달러 먼저 튀는각",
    ],
    "BTC_UP": [
        "친구는 벌써 캡처함",
        "늦으면 또 구경만",
        "또 나만 못 탄 그림",
        "단톡방 수익인증 각",
        "회사 몰래 차트 보는중",
        "지금 안 보면 또 늦음",
        "개미들 또 미쳐감",
        "나 빼고 다 타는중",
    ],
    "BTC_DOWN": [
        "또 고점 구경하나",
        "심장 약하면 못봄",
        "수익인증 끝날수도",
        "방금 웃던 애들 조용",
        "단톡방 갑자기 정적",
        "손절 얘기 슬슬 나옴",
        "들어갔다가 울수도",
        "또 멘탈 시험 시작",
    ],
    "ETH_UP": [
        "알트방 단체 흥분중",
        "이더 먼저 튀면 다 뜀",
        "또 코인판 미쳐감",
        "친구는 이미 탔을지도",
        "이번엔 알트장 냄새",
        "개미들 눈빛 달라짐",
        "불장 기대감 올라감",
        "늦으면 또 배아픔",
    ],
    "ETH_DOWN": [
        "알트들 표정 굳음",
        "또 이더에 당하나",
        "코인판 갑자기 싸늘",
        "수익인증방 조용해짐",
        "들어가면 멘붕각",
        "또 고점 물릴수도",
        "이더 눈치게임 시작",
        "갑자기 분위기 냉각",
    ],
    "OIL": [
        "주유소 가기 무서워짐",
        "기름값 또 멘붕",
        "차 끌수록 손해같음",
        "지갑 바로 털림각",
        "출퇴근비 또 오름",
        "물가 다시 깨움",
        "기름값 뉴스 또 뜰듯",
        "이번엔 체감 빨리 옴",
    ],
    "GOLD": [
        "쫄보 돈이 제일 빠름",
        "겁먹은 돈 다 몰림",
        "불안할수록 금부터 봄",
        "안전자산 또 인기폭발",
        "돈 많은 애들 먼저 움직임",
        "쫄리면 금 사는거임",
        "시장이 무섭긴 한가봄",
        "현금 말고 금 찾는중",
    ],
    "RATE": [
        "기대했다가 숨멎함",
        "월가 지금 멘탈나감",
        "성장주 표정 굳음",
        "나스닥 또 시험대",
        "다들 강한 척만 하는중",
        "한마디에 시장 휘청",
        "기대감이 갑자기 식음",
        "미장 하는 애들 긴장중",
    ],
    "CPI": [
        "물가 때문에 다 꼬임",
        "이 숫자 하나에 뒤집힘",
        "월가 식은땀 모드",
        "성장주들 표정 굳음",
        "물가가 제일 무서움",
        "다들 CPI만 기다림",
        "나스닥 멘탈 시험중",
        "이거 하나로 분위기 끝",
    ],
    "BOND": [
        "월가 표정 바로 썩음",
        "국채금리 무섭게 뜀",
        "성장주 또 맞는중",
        "다들 안전한척 쫄림",
        "채권 때문에 분위기 박살",
        "월가 아저씨들 한숨중",
        "나스닥에 찬물 끼얹음",
        "숫자 하나에 멘탈 흔들",
    ],
    "DEAL": [
        "먼저 탄 놈들만 신남",
        "시장 갑자기 환호",
        "또 나만 늦는 그림",
        "친구는 벌써 웃는중",
        "단톡방 갑자기 활발해짐",
        "회사에서 몰래 본다 이거",
        "또 남들만 먹는각",
        "수익인증 올릴 분위기",
    ],
    "TRADE": [
        "체감물가 또 올라감",
        "수출주 눈치게임",
        "관세 하나에 분위기 바뀜",
        "지갑 먼저 아파지는중",
        "마트 물가 생각남",
        "이번엔 생활비 이슈",
        "괜히 장바구니 무서움",
        "뉴스보다 지갑이 먼저 앎",
    ],
    "STOCK_UP": [
        "다들 강한 척 신난중",
        "월가 오늘 표정 좋음",
        "위험자산 다시 살아남",
        "수익인증 슬슬 올라옴",
        "친구는 또 미장 자랑함",
        "장 끝나고 단톡방 난리",
        "상승장 냄새 좀 남",
        "다시 욕심나는 그림",
    ],
    "STOCK_DOWN": [
        "다들 강한 척 쫄는중",
        "월가 또 표정 굳음",
        "위험자산 눈치게임",
        "수익인증방 갑자기 조용",
        "친구도 오늘은 말없음",
        "차트보다 표정이 말해줌",
        "오늘 미장 쉽지않음",
        "멘탈 약하면 못봄",
    ],
    "MIDEAST": [
        "기름값 또 튈 준비중",
        "유가 먼저 반응함",
        "불안하면 금도 뜀",
        "중동 변수 무시 못함",
        "이건 기름값으로 옴",
        "뉴스보다 주유소가 빠름",
        "생활비로 바로 체감됨",
        "위험자산 먼저 움찔",
    ],
    "MARKET": [
        "지금 돈 방향 바뀜",
        "친구는 벌써 보고있음",
        "또 나만 늦는 그림",
        "단톡방에 돌만한 각",
        "이건 그냥 지나치면 아까움",
        "오늘 돈 냄새 남",
        "먼저 본 애가 웃음",
        "또 남들만 알고 감",
    ],
}

TITLE2 = {
    "TRUMP_DEAL": ["또 나만 늦음", "이미 돈은 움직임", "친구는 벌써 탐", "시장 먼저 반응"],
    "TRUMP_TARIFF": ["지갑 또 맞는다", "달러 또 튄다", "물가 다시 뜬다", "생활비 멘붕각"],
    "BTC_UP": ["늦으면 또 구경만", "또 남들만 먹음", "지금 돈 미친듯 붙음", "개미들 눈돌아감"],
    "BTC_DOWN": ["또 고점 구경하나", "수익인증 끝날수도", "단톡방 갑자기 조용", "심장 약하면 못봄"],
    "ETH_UP": ["알트장 또 미쳐감", "개미들 지금 흥분중", "이더가 먼저 튄다", "코인판 단체 광기"],
    "ETH_DOWN": ["알트장 갑자기 싸늘", "또 물릴수도 있음", "분위기 순식간에 식음", "고점 잡을까 무서움"],
    "OIL": ["기름값 또 멘붕", "지갑 바로 털림각", "물가 다시 자극", "출퇴근비 또 오른다"],
    "GOLD": ["겁먹은 돈 몰림", "안전자산 풀매수", "쫄보 자금 먼저 뜀", "불안할수록 금 본다"],
    "RATE": ["나스닥 숨멎", "월가 지금 멘탈나감", "성장주 또 압박", "기대감 바로 식음"],
    "CPI": ["나스닥 식은땀", "물가 하나에 뒤집힘", "성장주 표정 굳음", "금리 기대 박살남"],
    "BOND": ["월가 표정 썩음", "성장주 또 압박", "채권이 분위기 깸", "미장하는 애들 긴장"],
    "DEAL": ["시장 갑자기 환호", "또 남들만 웃음", "수익인증 각 나옴", "분위기 급반전"],
    "TRADE": ["물가 또 꿈틀댐", "수출주 눈치봄", "장바구니 또 아픔", "생활비부터 반응"],
    "STOCK_UP": ["월가 표정 좋음", "다들 강한척 신남", "위험자산 살아남", "또 욕심 올라옴"],
    "STOCK_DOWN": ["다들 강한척 쫄음", "위험자산 눈치게임", "월가 또 표정 굳음", "오늘 미장 쉽지않음"],
    "MIDEAST": ["유가 먼저 튄다", "금값도 같이 뜸", "기름값 바로 반응", "생활비로 체감됨"],
    "MARKET": ["돈 움직이는중", "친구는 벌써 본듯", "또 남들만 알고감", "이건 그냥 못지나침"],
}

DESC2 = {
    "TRUMP_DEAL": ["관세 기대 뒤집힘", "시장 기대감 급반전", "딜 기대 먼저 반영", "뉴스보다 돈이 빠름"],
    "TRUMP_TARIFF": ["달러 먼저 꿈틀", "수입주 표정 굳음", "체감물가 또 불안", "생활비가 먼저 아픔"],
    "BTC_UP": ["마감 전 돈 붙는중", "차트보다 반응 빠름", "단톡방 수익인증 각", "지금 놓치면 또 늦음"],
    "BTC_DOWN": ["마감 전 멘탈 시험", "수익인증방 조용해짐", "단톡방 정적 오는중", "차트가 사람 잡는중"],
    "ETH_UP": ["알트들 눈빛 달라짐", "코인판 단체 반응", "불장 기대 살아남", "이더 먼저 튀면 따라감"],
    "ETH_DOWN": ["알트장 눈치게임", "급락 오면 순식간", "고점 물리면 답없음", "이더 흔들리면 다 흔들"],
    "OIL": ["물가 자극 바로 옴", "주유소부터 체감됨", "생활비 쪽부터 아픔", "출퇴근비 먼저 올라감"],
    "GOLD": ["안전자산부터 반응", "겁먹은 돈 제일 빠름", "달러랑 같이 체크", "쫄릴수록 금 찾음"],
    "RATE": ["월가 촉각 곤두섬", "미장 하는 애들 긴장", "성장주 민감하게 반응", "금리 기대감 흔들림"],
    "CPI": ["물가 숫자 하나가 끝냄", "기대감 박살나는중", "금리 전망 바로 바뀜", "성장주들 숨참는중"],
    "BOND": ["국채가 분위기 깸", "성장주 또 맞는중", "채권이 차가운물 뿌림", "월가 한숨 모드"],
    "DEAL": ["늦으면 또 배아픔", "돈은 먼저 웃는중", "차트보다 뉴스가 빠름", "이건 단톡방 돌만함"],
    "TRADE": ["생활비로 바로 옴", "마트 물가 생각남", "장바구니부터 아픔", "수출주들 눈치보는중"],
    "STOCK_UP": ["월가 분위기 살아남", "위험자산 다시 꿈틀", "수익인증 올릴 각", "욕심 올라오면 위험"],
    "STOCK_DOWN": ["오늘은 쉽지않음", "미장방 공기 싸늘함", "위험자산 다 움찔", "차트보다 표정이 먼저"],
    "MIDEAST": ["주유소 가격으로 옴", "금값도 같이 반응", "중동 뉴스 무시 못함", "생활비까지 연결됨"],
    "MARKET": ["핵심만 빠르게 보면됨", "돈 냄새 나는 이슈", "먼저 본 애가 유리", "시장 먼저 반응중"],
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

    krw = v * 1350
    eok = krw / 100000000

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
                man = int(round(val / 10000))
                return f"{man}만달러"
            return f"{int(val)}달러"
        except:
            pass

    m = re.search(r"(\d+)\s?(?:bp|bps)", q.lower())
    if m:
        return f"{m.group(1)}bp"

    return None


def _pick_theme(question):
    q = question.lower()

    if _contains(q, ["bitcoin", "btc"]):
        return "BTC"
    if _contains(q, ["ethereum", "eth"]):
        return "ETH"
    if _contains(q, ["oil", "wti", "crude", "brent", "hormuz", "strait"]):
        return "OIL"
    if _contains(q, ["gold"]):
        return "GOLD"
    if _contains(q, ["fed", "rate", "rates", "inflation", "cpi", "yield", "treasury"]):
        return "RATE"
    if _contains(q, ["nasdaq", "s&p", "dow", "stocks"]):
        return "STOCK"
    if _contains(q, ["tariff", "china", "exports", "trade deal", "deal"]):
        return "TRADE"
    if _contains(q, ["trump"]):
        return "TRUMP"
    if _contains(q, ["election", "president", "white house"]):
        return "POLITICS"
    if _contains(q, ["iran", "israel", "war", "missile", "attack", "troops", "ceasefire"]):
        return "MIDEAST"
    return "MARKET"


def rewrite_poly(question, volume, yes_price, end_date, retry=0):
    q = question.lower()
    theme = _pick_theme(question)
    prob = _pct(yes_price)
    vol = _format_krw_eok(volume)
    dday = _days_left(end_date)
    target = _extract_target_number(question)

    result = {
        "eyebrow": _stable_pick(HOOKS["MARKET"], question),
        "title1": f"확률 {prob}%",
        "title2": _stable_pick(TITLE2["MARKET"], question),
        "desc1": f"거래대금 {vol}",
        "desc2": _stable_pick(DESC2["MARKET"], question),
        "topic": "MARKET",
        "visual_topic": "market_general",
        "accent": "gold",
        "subtone": "white",
    }

    if theme == "TRUMP":
        if _contains(q, ["deal", "trade deal"]):
            key = "TRUMP_DEAL"
            result.update({
                "eyebrow": _stable_pick(HOOKS[key], question),
                "title1": f"무역딜 {prob}%",
                "title2": _stable_pick(TITLE2["DEAL"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["DEAL"], question),
                "topic": "DEAL",
                "visual_topic": "trump_deal_positive" if prob >= 50 else "trump_deal_negative",
                "accent": "gold",
            })
        elif _contains(q, ["tariff"]):
            key = "TRUMP_TARIFF"
            result.update({
                "eyebrow": _stable_pick(HOOKS[key], question),
                "title1": f"관세카드 {prob}%",
                "title2": _stable_pick(TITLE2["TRUMP_TARIFF"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["TRUMP_TARIFF"], question),
                "topic": "TRUMP",
                "visual_topic": "trump_tariff",
                "accent": "hot_red",
            })
        else:
            result.update({
                "eyebrow": _stable_pick(HOOKS["MARKET"], question),
                "title1": f"트럼프 변수 {prob}%",
                "title2": "시장 또 뒤집힘",
                "desc1": f"거래대금 {vol}",
                "desc2": "정책 한마디 폭탄",
                "topic": "TRUMP",
                "visual_topic": "trump_positive" if prob >= 50 else "trump_negative",
                "accent": "gold" if prob >= 50 else "hot_red",
            })

    elif theme == "BTC":
        key = "BTC_UP" if prob >= 50 else "BTC_DOWN"
        result.update({
            "eyebrow": _stable_pick(HOOKS[key], question),
            "title1": f"비트 {target} {prob}%" if target else f"비트코인 {prob}%",
            "title2": _stable_pick(TITLE2[key], question),
            "desc1": f"거래대금 {vol}",
            "desc2": f"마감 {dday}일 남음" if dday is not None else _stable_pick(DESC2[key], question),
            "topic": "BTC",
            "visual_topic": "btc_moon" if prob >= 50 else "btc_panic",
            "accent": "neon_gold" if prob >= 50 else "hot_red",
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
        })

    elif theme == "OIL":
        result.update({
            "eyebrow": _stable_pick(HOOKS["OIL"], question),
            "title1": f"유가 {target} {prob}%" if target else f"유가 급등 {prob}%",
            "title2": _stable_pick(TITLE2["OIL"], question),
            "desc1": f"거래대금 {vol}",
            "desc2": _stable_pick(DESC2["OIL"], question),
            "topic": "OIL",
            "visual_topic": "oil_shock" if prob >= 50 else "oil_relief",
            "accent": "orange",
        })

    elif theme == "GOLD":
        result.update({
            "eyebrow": _stable_pick(HOOKS["GOLD"], question),
            "title1": f"금값 급등 {prob}%",
            "title2": _stable_pick(TITLE2["GOLD"], question),
            "desc1": f"거래대금 {vol}",
            "desc2": _stable_pick(DESC2["GOLD"], question),
            "topic": "GOLD",
            "visual_topic": "gold_rush" if prob >= 50 else "gold_cool",
            "accent": "gold",
        })

    elif theme == "RATE":
        if _contains(q, ["cpi", "inflation"]):
            result.update({
                "eyebrow": _stable_pick(HOOKS["CPI"], question),
                "title1": f"CPI 쇼크 {prob}%",
                "title2": _stable_pick(TITLE2["CPI"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["CPI"], question),
                "topic": "CPI",
                "visual_topic": "inflation_shock",
                "accent": "hot_red",
            })
        elif _contains(q, ["yield", "treasury"]):
            result.update({
                "eyebrow": _stable_pick(HOOKS["BOND"], question),
                "title1": f"국채금리 {prob}%",
                "title2": _stable_pick(TITLE2["BOND"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["BOND"], question),
                "topic": "BOND",
                "visual_topic": "bond_stress",
                "accent": "electric_blue",
            })
        else:
            result.update({
                "eyebrow": _stable_pick(HOOKS["RATE"], question),
                "title1": f"금리 인하 {prob}%",
                "title2": _stable_pick(TITLE2["RATE"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": f"마감 {dday}일 남음" if dday is not None else _stable_pick(DESC2["RATE"], question),
                "topic": "RATE",
                "visual_topic": "rate_cut_hype" if prob >= 50 else "rate_cut_doubt",
                "accent": "electric_blue",
            })

    elif theme == "TRADE":
        if _contains(q, ["deal"]):
            result.update({
                "eyebrow": _stable_pick(HOOKS["DEAL"], question),
                "title1": f"무역딜 {prob}%",
                "title2": _stable_pick(TITLE2["DEAL"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["DEAL"], question),
                "topic": "DEAL",
                "visual_topic": "trade_deal_hype",
                "accent": "gold",
            })
        else:
            result.update({
                "eyebrow": _stable_pick(HOOKS["TRADE"], question),
                "title1": f"관세 변수 {prob}%",
                "title2": _stable_pick(TITLE2["TRADE"], question),
                "desc1": f"거래대금 {vol}",
                "desc2": _stable_pick(DESC2["TRADE"], question),
                "topic": "TRADE",
                "visual_topic": "trade_tension",
                "accent": "orange",
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
        })

    elif theme == "MIDEAST":
        result.update({
            "eyebrow": _stable_pick(HOOKS["MIDEAST"], question),
            "title1": f"휴전 성사 {prob}%" if _contains(q, ["ceasefire"]) else f"중동 충돌 {prob}%",
            "title2": _stable_pick(TITLE2["MIDEAST"], question),
            "desc1": f"거래대금 {vol}",
            "desc2": _stable_pick(DESC2["MIDEAST"], question),
            "topic": "MIDEAST",
            "visual_topic": "mideast_relief" if _contains(q, ["ceasefire"]) and prob >= 50 else "mideast_tension",
            "accent": "orange",
        })

    result["eyebrow"] = _clean(result.get("eyebrow", ""), 22)
    result["title1"] = _clean(result["title1"], 18)
    result["title2"] = _clean(result["title2"], 16)
    result["desc1"] = _clean(result["desc1"], 18)
    result["desc2"] = _clean(result["desc2"], 16)
    result["topic"] = _clean(result["topic"], 12)
    result["visual_topic"] = _clean(result["visual_topic"], 24)
    result["accent"] = _clean(result.get("accent", "gold"), 20)
    result["subtone"] = _clean(result.get("subtone", "white"), 20)

    return result