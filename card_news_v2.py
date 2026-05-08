from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import news as news_module


def _clean(text: str, limit: int = 120) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
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
    title = _clean(article.get("title", ""), 52)
    return f"한 줄: {title}"


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

    slide_2 = _clean(lead_desc, 90) or "핵심 이벤트 발표 직후 시장 참가자들이 방향성을 재평가했습니다."
    if len(slide_2) < 24:
        slide_2 = f"{slide_2} 추가 코멘트와 세부 수치가 이어지는 중입니다."

    reaction = _market_reaction_line(lead, market_items=market_items)
    if lead_number:
        reaction = f"핵심 수치 {lead_number} · {reaction}"

    story = {
        "topic": headline,
        "source": lead_source,
        "source_url": lead_url,
        "image_url": lead_image,
        "generated_at": _kst_text(),
        "slides": [
            {"page": 1, "title": headline, "body": _clean(lead_title, 82)},
            {"page": 2, "title": "무슨 일이 있었나", "body": slide_2},
            {"page": 3, "title": "시장 반응/숫자", "body": _clean(reaction, 92)},
            {"page": 4, "title": "왜 중요한가", "body": _clean(_why_important_line(lead), 88)},
            {"page": 5, "title": "한 줄 정리", "body": _clean(_summary_line(lead), 82)},
        ],
        "caption": (
            f"{headline}\n"
            f"{_clean(lead_title, 90)}\n"
            f"{_clean(reaction, 88)}\n"
            f"{_clean(_why_important_line(lead), 80)}\n\n"
            "저장해두고 다음 변동 때 비교하세요."
        ),
        "hashtags": "#경제 #경제뉴스 #시장분석 #미국증시 #비트코인 #유가 #환율 #금리 #투자 #뉴스요약",
        "save_cta": "오늘 핵심 이슈, 저장해두고 내일 시세와 비교",
        "share_cta": "시장 보는 친구에게 공유하면 맥락이 더 빨리 보입니다.",
    }
    return story
