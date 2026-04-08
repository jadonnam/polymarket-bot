import re
import hashlib
from polymarket import classify_topic

NEWS_HOOKS = {
    "TRUMP": [
        "먼저 탄 애들만 웃는중",
        "한마디에 다 흔들림",
        "정책 한줄에 돈 움직임",
        "또 나만 늦는 그림",
        "뉴스 뜨자마자 분위기 바뀜",
        "친구는 벌써 보고있음",
    ],
    "BTC": [
        "단톡방 벌써 난리남",
        "또 나만 늦는 그림",
        "친구는 수익 캡처중",
        "늦으면 또 구경만",
        "돈 냄새 확 올라옴",
        "회사에서 몰래 보는중",
    ],
    "OIL": [
        "주유소 가기 무서워짐",
        "생활비부터 아파짐",
        "기름값 뉴스 또 뜰듯",
        "물가부터 건드리는중",
        "지갑이 먼저 반응함",
        "출퇴근비 멘붕각",
    ],
    "GOLD": [
        "겁먹은 돈 제일 빠름",
        "쫄보 자금 먼저 뜀",
        "불안하면 금부터 봄",
        "안전자산 찾는중",
        "현금보다 금 보는중",
        "돈 많은 애들 먼저 움직임",
    ],
    "RATE": [
        "기대했다가 숨멎함",
        "월가 지금 멘탈나감",
        "성장주 표정 굳음",
        "나스닥 또 시험대",
        "미장 하는 애들 긴장",
        "한줄 기사에 분위기 박살",
    ],
    "GENERAL": [
        "지금 돈 방향 바뀜",
        "친구는 벌써 보고있음",
        "이건 그냥 지나치면 아까움",
        "또 남들만 알고감",
        "먼저 본 애가 유리함",
        "단톡방 돌만한 이슈",
    ],
}

NEWS_TITLE2 = {
    "TRUMP": ["시장 갑자기 환호", "시장 또 뒤집힘", "지갑 또 맞는다", "달러 먼저 반응"],
    "BTC": ["늦으면 또 구경만", "코인판 다시 들뜸", "지금 돈 미친듯 붙음", "또 남들만 먹음"],
    "OIL": ["기름값 또 멘붕", "물가 다시 자극", "지갑 바로 영향", "출퇴근비 또 오른다"],
    "GOLD": ["겁먹은 돈 몰림", "안전자산 풀매수", "불안할수록 금", "달러도 같이 봄"],
    "RATE": ["나스닥 숨멎", "월가 표정 굳음", "성장주 다시 압박", "금리 기대 흔들림"],
    "GENERAL": ["돈 움직이는중", "시장 먼저 반응", "핵심만 바로 체크", "이슈가 바로 돈됨"],
}

NEWS_DESC2 = {
    "TRUMP": ["관세 기대 바뀜", "정책 한마디 변수", "뉴스보다 돈이 빠름", "달러부터 반응중"],
    "BTC": ["단톡방 수익인증 각", "지금 놓치면 또 늦음", "돈 빠르게 붙는중", "코인방 공기 바뀜"],
    "OIL": ["생활비로 바로 옴", "주유소부터 체감됨", "물가부터 건드림", "지갑 먼저 아파짐"],
    "GOLD": ["쫄릴수록 금 찾음", "안전자산 먼저 반응", "달러랑 같이 체크", "돈 무서우면 금 본다"],
    "RATE": ["월가 촉각 곤두섬", "성장주 민감하게 반응", "기대감 바로 식음", "차트보다 표정이 먼저"],
    "GENERAL": ["핵심만 빠르게 보면됨", "돈 냄새 나는 이슈", "먼저 본 애가 유리", "시장 먼저 반응중"],
}


def _stable_pick(arr, seed_text):
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return arr[h % len(arr)]


def _clean(text, max_len):
    return re.sub(r"\s+", " ", str(text).strip())[:max_len]


def _contains(text, keywords):
    t = text.lower()
    return any(k in t for k in keywords)


def rewrite(title, desc, mode="normal", number_hint=None, retry=0):
    text = f"{title} {desc}".lower()
    topic = classify_topic(title, desc)

    key = "GENERAL"
    visual_topic = "market_general"
    accent = "gold"

    if "trump" in text and _contains(text, ["deal", "trade deal"]):
        key = "TRUMP"
        visual_topic = "trump_deal_positive"
        accent = "gold"
        title1 = "트럼프 딜 떴다"
    elif "trump" in text and "tariff" in text:
        key = "TRUMP"
        visual_topic = "trump_tariff"
        accent = "hot_red"
        title1 = "트럼프 관세 카드"
    elif _contains(text, ["bitcoin", "btc"]):
        key = "BTC"
        visual_topic = "btc_moon"
        accent = "neon_gold"
        title1 = "비트 또 난리남"
    elif _contains(text, ["oil", "wti", "crude", "brent"]):
        key = "OIL"
        visual_topic = "oil_shock"
        accent = "orange"
        title1 = "유가 다시 뜀"
    elif _contains(text, ["gold"]):
        key = "GOLD"
        visual_topic = "gold_rush"
        accent = "gold"
        title1 = "금값 또 뜀"
    elif _contains(text, ["fed", "inflation", "cpi", "rate", "yield", "treasury"]):
        key = "RATE"
        visual_topic = "rate_cut_doubt"
        accent = "electric_blue"
        title1 = "금리 변수 커짐"
    else:
        title1 = "최신 이슈 떴다"

    result = {
        "eyebrow": _stable_pick(NEWS_HOOKS[key], title + desc),
        "title1": title1,
        "title2": _stable_pick(NEWS_TITLE2[key], title + desc),
        "desc1": "시장 먼저 반응함",
        "desc2": _stable_pick(NEWS_DESC2[key], title + desc),
        "topic": "NEWS" if key == "GENERAL" else key,
        "visual_topic": visual_topic,
        "accent": accent,
        "subtone": "white",
    }

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