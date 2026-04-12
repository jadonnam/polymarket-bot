from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _cover_candidates(label: str, market_label: str) -> List[str]:
    if "유가" in label:
        return [
            "지금 시장은 유가부터 반응했다",
            "기름값 변수 다시 세게 움직인다",
            "오늘 돈 흐름 유가에서 시작됐다",
        ]
    if "환율" in label or "달러" in label:
        return [
            "환율 변수 다시 커지는 중",
            "달러 움직임 다시 커졌다",
            "오늘 시장은 환율부터 흔들린다",
        ]
    if "비트코인" in label:
        return [
            "돈이 다시 코인 쪽 본다",
            "비트코인 심리 다시 붙었다",
            "위험자산 쪽 심리 살아났다",
        ]
    if "금리" in label:
        return [
            "금리 기대 다시 흔들린다",
            "대출이자 변수 다시 커졌다",
            "시장 금리 해석이 또 바뀌었다",
        ]
    return [
        f"지금 돈은 {label[:10]} 쪽 본다",
        f"오늘 시장 1등은 {label[:10]}",
        f"{label[:10]} 변수 다시 커졌다",
    ]


def _hook(label: str, market_label: str) -> str:
    if "유가" in label or "유가" in market_label:
        return "지금 시장은 유가부터 반응했다"
    if "환율" in label or "달러" in label:
        return "환율 변수 다시 커지는 중"
    if "비트코인" in label:
        return "돈이 다시 코인 쪽 본다"
    if "금리" in label:
        return "금리 기대 다시 흔들리는 중"
    if "휴전" in label or "지정학" in label or "전쟁" in label:
        return "뉴스보다 돈이 먼저 움직였다"
    return "지금 시장이 먼저 반응한 이슈"


def build_content_pack(news_items: List[Dict], poly_items: List[Dict], market_items: List[Dict]) -> Dict[str, str]:
    top_news = _top(news_items)
    top_poly = _top(poly_items)
    top_market = _top(market_items)
    hook = _hook(top_news["label"], top_market["label"])
    candidates = _cover_candidates(top_news["label"], top_market["label"])
    reel_caption = (
        f"{hook}

"
        f"뉴스 1위: {top_news['label']}
"
        f"폴리 1위: {top_poly['label']}
"
        f"시장 1위: {top_market['label']}

"
        "저장해두면 다음 흐름 비교하기 쉽다."
    )
    return {
        "cover_candidates": "
".join([f"{i+1}) {c}" for i, c in enumerate(candidates)]),
        "reel_hook": hook,
        "feed_caption": reel_caption,
        "reel_caption": reel_caption,
        "hashtags": "#경제 #경제뉴스 #돈흐름 #유가 #환율 #비트코인 #금리 #폴리마켓 #재테크 #투자",
        "cta": "저장해두면 다음 흐름 비교하기 쉽다.",
    }
