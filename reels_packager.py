from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _hook(label: str, market_label: str) -> str:
    if "유가" in label or "호르무즈" in label:
        return "지금 유가 변수 다시 세게 움직인다"
    if "환율" in label or "달러" in label:
        return "지금 환율부터 먼저 예민하게 반응했다"
    if "비트코인" in label:
        return "오늘 돈 흐름은 비트가 먼저 끌고 간다"
    if "금리" in label:
        return "지금 시장은 금리 기대부터 가격에 반영 중"
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
        f"오늘 핵심 흐름만 짧게 정리했습니다.\n"
        f"뉴스 1위는 '{top_news['label']}', 폴리마켓 1위는 '{top_poly['label']}', 시장 반응 1위는 '{top_market['label']}'입니다.\n\n"
        f"헤드라인, 베팅, 가격 반응을 한 번에 보면 돈이 먼저 어디로 몰리는지 더 빨리 보입니다.\n"
        f"이건 저장해두고 다음 업로드랑 비교해보세요."
    )

    reel_caption = (
        f"{hook}\n\n"
        f"뉴스 1위: {top_news['label']}\n"
        f"폴리마켓 1위: {top_poly['label']}\n"
        f"시장 반응 1위: {top_market['label']}\n\n"
        "지금 핵심 흐름만 10초대로 압축했습니다.\n"
        "이건 저장해두고 다음 업로드랑 비교해보세요.\n\n"
        "#경제 #경제뉴스 #시장분석 #돈흐름 #폴리마켓 #유가 #환율 #비트코인 #금리 #재테크"
    )

    hashtags = "#경제 #경제뉴스 #시장분석 #돈흐름 #폴리마켓 #유가 #환율 #비트코인 #금리 #재테크"
    return {
        "cover_candidates": "\n".join([
            f"1) {hook}",
            "2) 헤드라인보다 먼저 움직인 돈 흐름",
            "3) 오늘 시장 핵심 10초 정리",
        ]),
        "reel_hook": hook,
        "feed_caption": feed_caption,
        "reel_caption": reel_caption,
        "hashtags": hashtags,
        "cta": "이건 저장해두고 다음 흐름이랑 비교해보세요.",
    }
