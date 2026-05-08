from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import news as news_module


def _contains(text: str, words: List[str]) -> bool:
    t = str(text or "").lower()
    return any(w in t for w in words)


def _clean(text: str, limit: int = 52) -> str:
    text = re.sub(r"\s+", " ", str(text or "").strip())
    return text[:limit].strip()


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _safe_pct(v: float) -> str:
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def _pick_lead_article(articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not articles:
        return {}
    scored = []
    for article in articles:
        text = f"{article.get('title', '')} {article.get('description', '')}".lower()
        score = 20
        if news_module.trusted_article(article):
            score += 35
        if article.get("urlToImage"):
            score += 25
        if _contains(text, ["oil", "wti", "crude", "brent", "hormuz", "iran", "israel", "war", "attack"]):
            score += 20
        if _contains(text, ["fed", "inflation", "cpi", "yield", "usd", "dollar", "bitcoin", "tariff"]):
            score += 15
        if re.search(r"\d", text):
            score += 8
        scored.append((score, article))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def _extract_market_number(news_items: List[Dict[str, Any]], poly_items: List[Dict[str, Any]]) -> str:
    best_news = news_items[0] if news_items else {}
    best_poly = poly_items[0] if poly_items else {}
    n_score = int(_as_float(best_news.get("score", 0)))
    p_score = int(_as_float(best_poly.get("score", 0)))
    gap = n_score - p_score
    if abs(gap) >= 8:
        return f"뉴스 충격 {n_score} vs 베팅 반응 {p_score}"
    if n_score > 0 and p_score > 0:
        avg = (n_score + p_score) / 2.0
        return f"시장 민감도 {int(avg)} / 100"
    return "핵심 수치: 시장 반응 급변"


def _impact_line(text: str) -> str:
    t = text.lower()
    if _contains(t, ["oil", "crude", "brent", "유가", "hormuz"]):
        return "운전자: 주유비 부담 체감 가능성"
    if _contains(t, ["usd", "dollar", "fx", "환율", "원화"]):
        return "해외소비자: 직구/여행 결제 부담 확대"
    if _contains(t, ["fed", "rate", "yield", "금리"]):
        return "대출자: 금리 기대 변화에 상환 부담 민감"
    if _contains(t, ["bitcoin", "btc", "crypto", "비트"]):
        return "투자자: 변동성 확대 구간, 분할 대응 필요"
    return "생활경제: 체감 물가와 투자심리 동시 영향"


def _strong_hook(title: str) -> str:
    t = str(title or "")
    if _contains(t, ["oil", "brent", "wti", "유가", "hormuz"]):
        return "방금 유가를 움직인 단 하나의 뉴스"
    if _contains(t, ["fed", "cpi", "inflation", "금리"]):
        return "금리보다 먼저 반응한 오늘 시장"
    if _contains(t, ["bitcoin", "btc", "비트"]):
        return "코인보다 먼저 움직인 건 공포였다"
    if _contains(t, ["tariff", "trump", "관세"]):
        return "관세 한 줄에 시장 방향이 바뀌었다"
    return "뉴스 한 줄에 돈의 방향이 바뀌었다"


def _make_save_cta(title: str) -> str:
    short = _clean(title, 20)
    return f"{short} 후속 반응 체크용 저장"


def build_reel_story_v2(
    news_items: List[Dict[str, Any]],
    poly_items: List[Dict[str, Any]],
    market_items: List[Dict[str, Any]],
    raw_articles: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    articles = raw_articles or news_module.fetch_news(limit=30, hours_back=24) or []
    lead = _pick_lead_article(articles)

    lead_title = _clean(lead.get("title", "") or (news_items[0]["label"] if news_items else "시장 핵심 변수"), 80)
    lead_desc = _clean(lead.get("description", "") or lead.get("content", ""), 150)
    lead_source = news_module.article_source_name(lead) if lead else "Global Desk"
    lead_image_url = (lead.get("urlToImage") or "").strip()
    published_at = str(lead.get("publishedAt", "") or "")

    now_kst = datetime.now(timezone.utc) + timedelta(hours=9)
    timestamp_text = now_kst.strftime("%m.%d %H:%M KST")
    if published_at:
        timestamp_text = _clean(published_at, 24)

    number_line = _extract_market_number(news_items, poly_items)
    reaction_label = market_items[0]["label"] if market_items else "리스크 오프"
    impact_line = _impact_line(f"{lead_title} {reaction_label}")

    return {
        "flow": [
            {"type": "hook", "text": _strong_hook(lead_title), "duration": 2.8},
            {
                "type": "news_photo",
                "title": lead_title,
                "subtitle": f"{lead_source} · {timestamp_text}",
                "image_url": lead_image_url,
                "duration": 5.0,
            },
            {
                "type": "number_reaction",
                "text": number_line,
                "subtext": f"시장 1차 반응: {_clean(reaction_label, 18)}",
                "duration": 4.5,
            },
            {"type": "human_impact", "text": impact_line, "duration": 4.5},
            {"type": "save_cta", "text": _make_save_cta(lead_title), "duration": 3.2},
        ],
        "meta": {
            "lead_title": lead_title,
            "lead_desc": lead_desc,
            "lead_source": lead_source,
            "lead_image_url": lead_image_url,
            "reel_hook": _strong_hook(lead_title),
            "reel_caption": (
                f"{_strong_hook(lead_title)}\n"
                f"{lead_source}: {lead_title}\n"
                f"{number_line}\n"
                f"{impact_line}\n\n"
                "저장해두고 다음 변동 때 비교하세요."
            ),
            "hashtags": "#경제 #경제뉴스 #시장반응 #인플레 #금리 #환율 #유가 #비트코인 #재테크 #뉴스요약",
        },
    }
