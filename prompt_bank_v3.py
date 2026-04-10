
import re

def _contains(text, words):
    t = str(text).lower()
    return any(w in t for w in words)

def detect_visual_topic(title: str) -> str:
    t = str(title)

    if _contains(t, ["비행기", "격추", "전투기", "drone", "fighter", "shoot down", "downed", "aircraft"]):
        return "air_force_strike"
    if _contains(t, ["환율", "달러", "usd", "fx", "won"]):
        return "fx_panic"
    if _contains(t, ["유가", "oil", "wti", "crude", "brent"]):
        return "oil_shock"
    if _contains(t, ["트럼프", "trump", "관세", "tariff"]):
        return "trump_tension"
    if _contains(t, ["전쟁", "공습", "이란", "이스라엘", "미국", "war", "attack", "iran", "israel", "us"]):
        return "war_flash"
    if _contains(t, ["비트", "bitcoin", "btc", "crypto", "코인"]):
        return "crypto_shock"
    return "market_flash"

def breaking_headline(raw_title: str) -> str:
    t = str(raw_title).strip()

    if _contains(t, ["비행기", "격추", "전투기", "shoot down", "downed", "aircraft"]):
        if _contains(t, ["이란", "iran"]) and _contains(t, ["미국", "us", "u.s"]):
            return "이란, 미군 비행기 격추"
        if _contains(t, ["이란", "iran"]):
            return "이란, 비행기 격추"
        if _contains(t, ["미국", "us", "u.s"]):
            return "미국, 비행기 격추"
        return "비행기 격추"
    if _contains(t, ["환율", "달러", "usd", "fx", "won"]):
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        if m:
            return f"환율 {m.group(1)}원 급등"
        return "환율 급등"
    if _contains(t, ["유가", "oil", "wti", "crude", "brent"]):
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        if m:
            return f"유가 {m.group(1)}달러 급등"
        return "유가 급등"
    if _contains(t, ["트럼프", "trump", "관세", "tariff"]):
        return "트럼프, 관세 압박"
    if _contains(t, ["전쟁", "공습", "이란", "이스라엘", "war", "attack", "iran", "israel"]):
        return "중동 긴장 재점화"
    if _contains(t, ["비트", "bitcoin", "btc", "crypto", "코인"]):
        return "비트 변동성 폭발"
    return t[:20]

def breaking_prompt(title: str) -> str:
    topic = detect_visual_topic(title)

    prompts = {
        "air_force_strike": "realistic editorial war photo, military aircraft emergency, dramatic smoke trail in sky, intense breaking news atmosphere, one strong focal subject, minimal clutter, high contrast, natural realistic lighting, no text, no graphics",
        "fx_panic": "realistic editorial finance photo, shocked Korean businessman looking at currency board, minimal dark background, strong face reaction, urgent macro crisis mood, high contrast, realistic skin texture, no text, no graphics",
        "oil_shock": "realistic editorial energy crisis photo, stressed Korean businessman with refinery glow behind, simple background, intense urgent lighting, strong click-stopping composition, no text, no graphics",
        "trump_tension": "realistic editorial political photo, older male politician with aggressive intense expression, simple dark background, hard news atmosphere, no text, no graphics",
        "war_flash": "realistic editorial war tension photo, breaking crisis atmosphere, one strong dramatic focal subject, smoke and emergency light mood, simple composition, no text, no graphics",
        "crypto_shock": "realistic editorial finance photo, shocked investor looking at phone, dark market room, strong face reaction, urgent crypto move mood, no text, no graphics",
        "market_flash": "realistic editorial breaking news photo, one strong subject, dark simple background, dramatic but realistic lighting, no text, no graphics",
    }
    return prompts.get(topic, prompts["market_flash"])
