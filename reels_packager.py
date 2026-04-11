from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _hook(label: str, market_label: str) -> str:
    if "유가" in label or "호르무즈" in label:
        return "유가 건드릴 변수 다시 커졌다"
    if "환율" in label or "달러" in label:
        return "환율이 먼저 예민하게 반응했다"
    if "비트코인" in label:
        return "비트가 다시 돈 흐름 끌고 간다"
    if "금리" in label:
        return "금리 기대가 시장 방향 흔드는 중"
    if "휴전" in label or "중동" in label or "지정학" in label or "전쟁" in label:
        return "헤드라인보다 돈이 먼저 움직였다"
    if "유가" in market_label:
        return "오늘 시장은 유가 변수부터 반영했다"
    return "지금 시장이 먼저 반응한 이슈"


def build_content_pack(news_items: List[Dict], poly_items: List[Dict], market_items: List[Dict]) -> Dict[str, str]:
    top_news = _top(news_items)
    top_poly = _top(poly_items)
    top_market = _top(market_items)
    hook = _hook(top_news["label"], top_market["label"])

    feed_caption = (
        f"{hook}\n\n"
        f"오늘 흐름 핵심만 압축했습니다.\n"
        f"뉴스 1위는 '{top_news['label']}', "
        f"폴리마켓 1위는 '{top_poly['label']}', "
        f"시장 반응 1위는 '{top_market['label']}'입니다.\n\n"
        f"중요도 게이지만 보면 어디에 돈이 먼저 반응했는지 바로 보입니다.\n"
        f"저장해두고 다음 업로드와 비교해보세요."
    )

    reel_caption = (
        f"{hook}\n\n"
        f"뉴스 1위: {top_news['label']}\n"
        f"폴리마켓 1위: {top_poly['label']}\n"
        f"시장 반응 1위: {top_market['label']}\n\n"
        "헤드라인, 베팅, 가격 반응을 한 번에 묶었습니다.\n"
        "저장해두면 다음 흐름 비교할 때 더 잘 보입니다.\n\n"
        "#경제 #경제뉴스 #시장분석 #돈흐름 #폴리마켓 #유가 #환율 #비트코인 #금리 #재테크"
    )

    hashtags = "#경제 #경제뉴스 #시장분석 #돈흐름 #폴리마켓 #유가 #환율 #비트코인 #금리 #재테크"
    return {
        "cover_candidates": "\n".join([
            f"1) {hook}",
            "2) 헤드라인보다 먼저 움직인 돈 흐름",
            "3) 오늘 시장 핵심 15초 정리",
        ]),
        "reel_hook": hook,
        "feed_caption": feed_caption,
        "reel_caption": reel_caption,
        "hashtags": hashtags,
        "cta": "저장해두면 다음 흐름 비교할 때 바로 보입니다.",
    }
