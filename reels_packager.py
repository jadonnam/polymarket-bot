
from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _cover_candidates(label: str, market_label: str) -> List[str]:
    if "유가" in label:
        return [
            "유가 변수 다시 세게 움직인다",
            "지금 기름값 변수 다시 커졌다",
            "오늘 돈 흐름 유가부터 흔들린다",
        ]
    if "환율" in label or "달러" in label:
        return [
            "환율 다시 흔들리기 시작했다",
            "달러 움직이면 체감물가 먼저 온다",
            "오늘 돈은 환율부터 반응했다",
        ]
    if "비트코인" in label:
        return [
            "비트코인 쪽 심리 다시 붙었다",
            "지금 돈은 다시 코인 쪽 본다",
            "위험자산 심리 다시 살아났다",
        ]
    if "금리" in label:
        return [
            "금리 해석 다시 바뀌는 중",
            "대출이자 변수 다시 커졌다",
            "시장 금리 기대 다시 흔들린다",
        ]
    if "휴전" in label or "전쟁" in label or "지정학" in label:
        return [
            "뉴스보다 돈이 먼저 움직였다",
            "지금 시장은 다른 신호를 본다",
            "지정학 변수 다시 가격에 반영된다",
        ]
    return [
        f"{label[:10]} 이유 나왔다",
        f"지금 돈은 {label[:10]} 쪽 본다",
        f"오늘 시장 1등 이슈는 {label[:10]}",
    ]


def _hook(label: str, market_label: str) -> str:
    if "유가" in label:
        return "지금 유가 변수 다시 세게 움직인다"
    if "환율" in label or "달러" in label:
        return "지금 환율 변수 다시 커지는 중"
    if "비트코인" in label:
        return "지금 돈은 다시 코인 쪽 본다"
    if "금리" in label:
        return "금리 기대 다시 흔들리는 중"
    if "휴전" in label or "지정학" in label or "전쟁" in label:
        return "뉴스보다 돈이 먼저 움직였다"
    if "유가" in market_label:
        return "지금 시장은 유가부터 반응했다"
    return "지금 시장이 먼저 반응한 이슈"


def build_content_pack(news_items: List[Dict], poly_items: List[Dict], market_items: List[Dict]) -> Dict[str, str]:
    top_news = _top(news_items)
    top_poly = _top(poly_items)
    top_market = _top(market_items)
    hook = _hook(top_news["label"], top_market["label"])
    candidates = _cover_candidates(top_news["label"], top_market["label"])
    return {
        "cover_candidates": "\n".join([f"{i+1}) {c}" for i, c in enumerate(candidates)]),
        "reel_hook": hook,
        "feed_caption": (
            f"{hook}\n\n"
            f"오늘 뉴스 1위는 {top_news['label']}\n"
            f"폴리마켓 1위는 {top_poly['label']}\n"
            f"시장 반응 1위는 {top_market['label']}\n\n"
            "저장해두면 내일 흐름 비교할 때 훨씬 쉽습니다."
        ),
        "reel_caption": (
            f"{hook}\n\n"
            f"뉴스 1위: {top_news['label']}\n"
            f"폴리마켓 1위: {top_poly['label']}\n"
            f"시장 반응 1위: {top_market['label']}\n\n"
            "저장해두면 내일 비교하기 편합니다."
        ),
        "hashtags": "#경제 #경제뉴스 #돈흐름 #유가 #환율 #비트코인 #금리 #폴리마켓 #재테크 #투자",
        "cta": "저장해두면 내일 흐름 비교하기 좋습니다.",
    }
