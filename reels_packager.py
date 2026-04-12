
from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _cover_candidates(label: str, market_label: str) -> List[str]:
    if "유가" in label:
        return ["지금 유가부터 반응했다", "기름값 변수 다시 커졌다", "시장 돈이 유가로 먼저 갔다"]
    if "환율" in label or "달러" in label:
        return ["환율부터 흔들리기 시작했다", "달러 쪽 긴장 다시 커졌다", "시장 불안은 환율부터 뜬다"]
    if "비트코인" in label:
        return ["비트코인 쪽으로 돈이 쏠린다", "코인 심리 다시 살아났다", "위험자산 선호 다시 붙었다"]
    if "금리" in label:
        return ["금리 기대부터 달라졌다", "대출이자 변수 다시 온다", "시장이 금리 해석을 바꿨다"]
    if "휴전" in label or "전쟁" in label or "지정학" in label:
        return ["뉴스보다 돈이 먼저 움직였다", "시장 해석이 뉴스랑 달랐다", "지금 돈은 다른 쪽을 보고 있다"]
    return [
        f"{label} 이유 나왔다",
        f"지금 돈은 {label[:8]} 쪽 본다",
        f"오늘 시장 1등 이슈는 {label[:8]}",
    ]


def _hook(label: str) -> str:
    if "유가" in label:
        return "지금 시장은 유가부터 반응했다"
    if "환율" in label or "달러" in label:
        return "환율부터 흔들리기 시작했다"
    if "비트코인" in label:
        return "돈이 다시 비트코인으로 간다"
    if "금리" in label:
        return "금리 기대가 다시 바뀌었다"
    if "휴전" in label or "지정학" in label:
        return "뉴스보다 돈이 먼저 움직였다"
    return "지금 시장이 먼저 반응한 이슈"


def build_content_pack(news_items: List[Dict], poly_items: List[Dict], market_items: List[Dict]) -> Dict[str, str]:
    top_news = _top(news_items)
    top_poly = _top(poly_items)
    top_market = _top(market_items)
    hook = _hook(top_news["label"])
    candidates = _cover_candidates(top_news["label"], top_market["label"])
    return {
        "cover_candidates": "\n".join([f"{i+1}) {c}" for i, c in enumerate(candidates)]),
        "reel_hook": hook,
        "feed_caption": (
            f"{hook}\n\n"
            f"뉴스 / 폴리마켓 / 시장 반응 순서로 보면 오늘 돈 흐름이 더 선명하게 보입니다.\n"
            f"뉴스 1위: {top_news['label']}\n"
            f"폴리마켓 1위: {top_poly['label']}\n"
            f"시장 반응 1위: {top_market['label']}\n\n"
            "저장해두면 내일 흐름 비교가 훨씬 쉬워집니다."
        ),
        "reel_caption": (
            f"{hook}\n"
            f"뉴스 1위: {top_news['label']}\n"
            f"폴리 1위: {top_poly['label']}\n"
            f"시장 1위: {top_market['label']}\n\n"
            f"저장해두면 다음 흐름 비교가 쉬워집니다."
        ),
        "hashtags": "#경제 #경제뉴스 #돈흐름 #유가 #환율 #비트코인 #금리 #폴리마켓 #재테크 #투자",
        "cta": "저장해두면 내일 흐름 비교가 쉬워집니다.",
    }
