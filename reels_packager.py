
from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _hook(label: str, market_label: str = "") -> str:
    label = label or ""
    market_label = market_label or ""
    if "유가" in label:
        return "지금 유가 변수 다시 세게 움직인다"
    if "환율" in label or "달러" in label:
        return "지금 환율 방향 다시 흔들리는 중이다"
    if "비트코인" in label:
        return "지금 돈이 다시 코인 쪽으로 몰린다"
    if "금리" in label:
        return "지금 금리 해석이 다시 바뀌고 있다"
    if "휴전" in label or "전쟁" in label or "지정학" in label:
        return "지금 뉴스보다 돈이 먼저 움직이고 있다"
    if "유가" in market_label:
        return "지금 시장은 유가부터 반응하고 있다"
    return "지금 돈 흐름 먼저 움직인 곳만 본다"


def build_content_pack(news_items: List[Dict], poly_items: List[Dict], market_items: List[Dict]) -> Dict[str, str]:
    top_news = _top(news_items)
    top_poly = _top(poly_items)
    top_market = _top(market_items)
    hook = _hook(top_news["label"], top_market["label"])
    return {
        "cover_candidates": (
            f"1) {hook}\n"
            f"2) 오늘 시장 1등 이슈는 {top_news['label']}\n"
            f"3) 지금 돈은 {top_market['label']} 쪽부터 본다"
        ),
        "reel_hook": hook,
        "feed_caption": (
            f"{hook}\n\n"
            f"뉴스 1위: {top_news['label']}\n"
            f"폴리마켓 1위: {top_poly['label']}\n"
            f"시장 반응 1위: {top_market['label']}\n\n"
            "저장해두면 다음 흐름 비교가 쉬워집니다."
        ),
        "reel_caption": (
            f"{hook}\n\n"
            f"뉴스 1위: {top_news['label']}\n"
            f"폴리마켓 1위: {top_poly['label']}\n"
            f"시장 반응 1위: {top_market['label']}\n\n"
            "저장해두면 다음 장에서 비교가 훨씬 쉬워집니다."
        ),
        "hashtags": "#경제 #경제뉴스 #돈흐름 #유가 #환율 #비트코인 #금리 #폴리마켓 #재테크 #투자",
        "cta": "저장해두면 다음 흐름 비교하기 쉽습니다.",
    }
