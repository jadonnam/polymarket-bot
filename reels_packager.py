from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _cover_candidates(label: str, market_label: str) -> List[str]:
    base = [
        f"{label} 이유 나왔다",
        f"지금 돈은 {label[:8]} 쪽 본다",
        f"오늘 시장 1등 이슈는 {label[:8]}",
    ]
    if "유가" in label:
        base = ["기름값 다시 자극받나", "유가 쪽 돈 몰린다", "주유소 가격 변수 다시 옴"]
    elif "환율" in label or "달러" in label:
        base = ["환율 다시 흔들린다", "달러 쪽 긴장 커졌다", "해외직구 부담 다시 온다"]
    elif "비트코인" in label:
        base = ["비트코인 다시 강해진다", "돈이 다시 코인 쪽 본다", "위험자산 심리 살아난다"]
    elif "금리" in label:
        base = ["금리 기대 다시 흔들린다", "대출이자 변수 다시 온다", "시장 금리 해석 바뀌었다"]
    elif "휴전" in label or "전쟁" in label or "지정학" in label:
        base = ["전쟁보다 돈이 먼저 움직였다", "시장 해석이 뉴스랑 다르다", "지금 돈은 다른 쪽 본다"]
    return base[:3]


def _hook(label: str) -> str:
    if "유가" in label:
        return "기름값 변수 다시 커졌다"
    if "환율" in label or "달러" in label:
        return "환율 부담 다시 커지는 중"
    if "비트코인" in label:
        return "비트코인 다시 위 보는 흐름"
    if "금리" in label:
        return "금리 기대 다시 흔들리는 중"
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
            f"뉴스 / 폴리마켓 / 시장 반응 순서로 보면 돈 흐름이 더 잘 보입니다.\n"
            f"오늘 1위: {top_news['label']}\n"
            f"시장 반응 1위: {top_market['label']}\n\n"
            "저장해두면 나중에 흐름 비교할 때 편합니다."
        ),
        "reel_caption": (
            f"{hook}\n"
            f"뉴스 1위: {top_news['label']}\n"
            f"폴리 1위: {top_poly['label']}\n"
            f"시장 1위: {top_market['label']}"
        ),
        "hashtags": "#경제 #경제뉴스 #돈흐름 #유가 #환율 #비트코인 #금리 #폴리마켓 #재테크 #투자",
        "cta": "저장해두면 나중에 흐름 비교하기 좋습니다.",
    }
