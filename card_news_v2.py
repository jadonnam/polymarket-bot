from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import news as news_module


def _clean(text: str, limit: int = 120) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s[:limit].strip()


def _korean_only(text: str, limit: int = 120) -> str:
    s = str(text or "")
    # Remove direct English sentence exposure from cards.
    s = re.sub(r"[A-Za-z]{3,}", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:limit].strip()


def _contains(text: str, words: List[str]) -> bool:
    t = str(text or "").lower()
    return any(w in t for w in words)


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _pick_top_article(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not articles:
        return {}
    scored: List[tuple[int, Dict[str, Any]]] = []
    for article in articles:
        title = article.get("title", "") or ""
        desc = article.get("description", "") or article.get("content", "") or ""
        text = f"{title} {desc}".lower()
        score = 0
        if news_module.trusted_article(article):
            score += 45
        if article.get("urlToImage"):
            score += 30
        if re.search(r"\d", text):
            score += 10
        if _contains(text, ["nvidia", "apple", "tesla", "bitcoin", "oil", "fed", "inflation", "yield", "usd"]):
            score += 16
        score += min(20, len(_clean(desc, 500)) // 40)
        scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _topic_hint(title: str, desc: str) -> str:
    text = f"{title} {desc}".lower()
    if _contains(text, ["nvidia", "nvda"]):
        return "엔비디아 급등 이유"
    if _contains(text, ["apple", "aapl", "iphone", "ai feature"]):
        return "애플 AI 이슈"
    if _contains(text, ["tesla", "tsla"]):
        return "테슬라 반등 이유"
    if _contains(text, ["bitcoin", "btc", "crypto"]):
        return "비트코인 움직인 이유"
    if _contains(text, ["oil", "wti", "brent", "crude", "hormuz"]):
        return "유가 급등 이유"
    if _contains(text, ["nasdaq", "s&p", "dow", "wall street"]):
        return "오늘 미국장 핵심"
    return "오늘 시장에서 가장 중요한 뉴스"


def _extract_key_number(text: str) -> str:
    nums = re.findall(r"\d+(?:\.\d+)?%?", text or "")
    if nums:
        return nums[0]
    return ""


def _asset_tag(title: str, desc: str) -> str:
    text = f"{title} {desc}".lower()
    if _contains(text, ["oil", "wti", "brent", "crude", "hormuz", "opec"]):
        return "oil"
    if _contains(text, ["bitcoin", "btc", "crypto", "ethereum", "eth"]):
        return "btc"
    if _contains(text, ["usd", "dollar", "fx", "won", "환율"]):
        return "fx"
    if _contains(text, ["nasdaq", "s&p", "dow", "wall street"]):
        return "stocks"
    if _contains(text, ["nvidia", "apple", "tesla"]):
        return "bigtech"
    if _contains(text, ["fed", "inflation", "cpi", "yield", "rate"]):
        return "rates"
    return "market"


def _event_summary_kr(title: str, desc: str) -> str:
    tag = _asset_tag(title, desc)
    if tag == "oil":
        return "중동·공급 이슈가 겹치며 에너지 가격 기대가 빠르게 상향됐습니다."
    if tag == "btc":
        return "위험자산 선호가 되살아나며 가상자산 매수세가 단기 확대됐습니다."
    if tag == "fx":
        return "달러 강세 재가동 신호로 환율 부담이 다시 시장 전면으로 올라왔습니다."
    if tag == "stocks":
        return "대형주 중심 수급이 몰리며 미국 지수 방향성이 한쪽으로 기울었습니다."
    if tag == "bigtech":
        return "실적·가이던스·AI 기대가 결합돼 빅테크 중심 재평가가 진행됐습니다."
    if tag == "rates":
        return "금리 경로 해석이 바뀌면서 채권·주식·환율이 동시에 재조정됐습니다."
    return "핵심 뉴스 한 건이 투자심리와 가격 기준점을 동시에 움직였습니다."


def _core_topic_lines(title: str, desc: str) -> List[str]:
    tag = _asset_tag(title, desc)
    if tag == "oil":
        return ["공급 불확실성 재확대", "에너지 가격 상방 압력", "물가 기대 재자극"]
    if tag == "btc":
        return ["위험자산 심리 반등", "단기 변동성 확대", "유동성 민감 구간"]
    if tag == "fx":
        return ["달러 강세 압력", "원화 변동성 확대", "수입물가 부담 경계"]
    if tag == "stocks":
        return ["미국 지수 방향성 확인", "대형주 수급 쏠림", "옵션 거래량 확대"]
    if tag == "bigtech":
        return ["빅테크 재평가 진행", "AI 기대 심리 강화", "지수 영향력 확대"]
    if tag == "rates":
        return ["금리 경로 재해석", "채권·주식 동시 재조정", "달러 반응 재개"]
    return ["핵심 이벤트 발생", "시장 민감도 상승", "가격 기준점 변화"]


def _market_number_block(title: str, desc: str, market_items: Optional[List[Dict[str, Any]]] = None) -> str:
    tag = _asset_tag(title, desc)
    lead_score = int(_to_float((market_items or [{}])[0].get("score", 0)))
    if tag == "oil":
        return f"WTI/브렌트 민감도 상승 · 시장반응 점수 {lead_score}/100"
    if tag == "btc":
        return f"BTC 변동성 확대 · 위험선호 점수 {lead_score}/100"
    if tag == "fx":
        return f"달러·환율 동반 반응 · 환율경계 점수 {lead_score}/100"
    if tag == "stocks":
        return f"나스닥/대형주 주도 · 지수모멘텀 점수 {lead_score}/100"
    if tag == "bigtech":
        return f"빅테크 수급 집중 · 성장주심리 점수 {lead_score}/100"
    if tag == "rates":
        return f"금리 민감자산 재조정 · 금리압력 점수 {lead_score}/100"
    return f"시장 1차 반응 점수 {lead_score}/100"


def _market_reaction_line(article: Dict[str, Any], market_items: Optional[List[Dict[str, Any]]] = None) -> str:
    title = str(article.get("title", "")).lower()
    if _contains(title, ["oil", "wti", "brent", "crude"]):
        return "WTI/브렌트 변동성 확대, 에너지 섹터 민감 반응"
    if _contains(title, ["bitcoin", "btc"]):
        return "비트코인 변동폭 확대, 위험자산 심리 흔들림"
    if _contains(title, ["fed", "inflation", "yield", "rate"]):
        return "미국채 금리와 달러가 먼저 반응"
    if _contains(title, ["nvidia", "apple", "tesla"]):
        return "빅테크 중심으로 지수와 옵션 거래량 동반 확대"
    top_market = (market_items or [{}])[0].get("label", "")
    if top_market:
        return f"시장 1차 반응: {_clean(top_market, 24)}"
    return "시장 1차 반응: 변동성 확대 구간"


def _why_important_line(article: Dict[str, Any]) -> str:
    title = str(article.get("title", "")).lower()
    if _contains(title, ["oil", "hormuz", "war", "attack"]):
        return "원자재 가격과 물가 기대를 동시에 흔드는 변수"
    if _contains(title, ["fed", "rate", "inflation", "cpi"]):
        return "대출·환율·주식 밸류에이션에 연쇄 영향"
    if _contains(title, ["bitcoin", "crypto"]):
        return "위험자산 선호 강도와 유동성 방향의 신호"
    if _contains(title, ["nvidia", "apple", "tesla"]):
        return "지수 비중이 큰 대형주의 방향성 자체를 바꿈"
    return "오늘 이후 가격 흐름의 기준점이 될 가능성"


def _summary_line(article: Dict[str, Any]) -> str:
    title = _topic_hint(article.get("title", ""), article.get("description", "") or article.get("content", ""))
    return f"한 줄 결론: {title}는 단기 변동성 핵심 변수"


def _kst_text() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=9)).strftime("%Y.%m.%d %H:%M KST")


def build_card_news_v2(
    topic_seed: str = "",
    news_articles: Optional[List[Dict[str, Any]]] = None,
    market_items: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    articles = news_articles or news_module.fetch_news(limit=30, hours_back=24) or []
    lead = _pick_top_article(articles)

    lead_title = _clean(lead.get("title", ""), 88) or _clean(topic_seed, 48) or "오늘 시장 핵심 이슈"
    lead_desc = _clean(lead.get("description", "") or lead.get("content", ""), 180)
    lead_source = news_module.article_source_name(lead) if lead else "Global Finance Desk"
    lead_url = _clean(lead.get("url", ""), 220)
    lead_image = _clean(lead.get("urlToImage", ""), 220)
    lead_number = _extract_key_number(f"{lead_title} {lead_desc}")
    headline = _topic_hint(lead_title, lead_desc)
    tag = _asset_tag(lead_title, lead_desc)
    core_topics = _core_topic_lines(lead_title, lead_desc)

    slide_2 = _event_summary_kr(lead_title, lead_desc)
    if len(slide_2) < 20:
        slide_2 = "핵심 이벤트 직후 투자자들이 가격 기준을 빠르게 다시 잡았습니다."

    reaction = _market_number_block(lead_title, lead_desc, market_items=market_items)
    reaction_line = _market_reaction_line(lead, market_items=market_items)
    if lead_number:
        reaction = f"핵심 수치 {lead_number} · {reaction}"

    impact = _why_important_line(lead)
    summary = _summary_line(lead)

    image_urls = []
    if lead_image:
        image_urls.append(lead_image)
    for art in articles:
        u = _clean(art.get("urlToImage", ""), 220)
        if u and u not in image_urls:
            image_urls.append(u)
        if len(image_urls) >= 5:
            break

    short_head = _korean_only(headline, 24) or "오늘 시장 핵심"
    short_reaction = _korean_only(reaction, 28)
    if not short_reaction:
        short_reaction = "시장 반응 점검"

    caption_lines = [
        f"1) 오늘 이슈: {_korean_only(headline, 38)}",
        f"2) 발생 배경: {_korean_only(slide_2, 48)}",
        f"3) 시장 숫자: {_korean_only(reaction, 42)}",
        f"4) 1차 반응: {_korean_only(reaction_line, 42)}",
        f"5) 중요한 이유: {_korean_only(impact, 44)}",
        f"6) 결론: {_korean_only(summary, 44)}",
        "저장해두고 다음 장 시작 전에 비교해보세요.",
        "#경제 #경제뉴스 #시장분석 #미국증시 #비트코인 #유가 #환율 #금리 #투자 #뉴스요약",
    ]

    story = {
        "topic": headline,
        "asset_tag": tag,
        "source": lead_source,
        "source_url": lead_url,
        "image_url": lead_image,
        "image_urls": image_urls,
        "generated_at": _kst_text(),
        "slides": [
            {"page": 1, "title": "오늘 시장을 흔든 이슈", "body": short_head},
            {"page": 2, "title": "핵심 주제 1", "body": _korean_only(core_topics[0], 30)},
            {"page": 3, "title": "핵심 주제 2", "body": _korean_only(short_reaction, 30)},
            {"page": 4, "title": "핵심 주제 3", "body": _korean_only(core_topics[2], 30)},
            {"page": 5, "title": "한 줄 결론", "body": "저장하고 다음 변동과 비교"},
        ],
        "caption_lines": caption_lines,
        "caption": "\n".join(caption_lines),
        "hashtags": "#경제 #경제뉴스 #시장분석 #미국증시 #비트코인 #유가 #환율 #금리 #투자 #뉴스요약",
        "save_cta": "오늘 핵심 이슈, 저장해두고 내일 시세와 비교",
        "share_cta": "시장 보는 친구에게 공유하면 맥락이 더 빨리 보입니다.",
    }
    return story
