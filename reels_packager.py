from __future__ import annotations

from typing import Dict, List


def _top(items: List[Dict]) -> Dict:
    return items[0] if items else {"label": "시장 흐름 변화", "score": 80}


def _linebreak(text: str, max_len: int = 12) -> str:
    text = str(text).strip()
    if len(text) <= max_len:
        return text
    # break on nearest space or Korean chunk
    for i in range(max_len, min(len(text), max_len + 6)):
        if text[i:i+1] == ' ':
            return text[:i].strip() + "
" + text[i+1:].strip()
    return text[:max_len].strip() + "
" + text[max_len:].strip()


def _hook(label: str) -> str:
    if "유가" in label:
        return "지금 유가 변수
다시 세게 움직인다"
    if "환율" in label or "달러" in label:
        return "지금 환율 부담
다시 올라온다"
    if "비트코인" in label:
        return "지금 돈 흐름
다시 코인 쪽 본다"
    if "금리" in label:
        return "지금 금리 해석
다시 갈린다"
    if "휴전" in label or "지정학" in label or "전쟁" in label:
        return "전쟁 뉴스보다
돈이 먼저 움직였다"
    return "지금 시장이
먼저 반응한 이슈"


def _outro(label: str, market_label: str) -> str:
    if "유가" in label:
        return "이 흐름은 저장해둬
주유소 가격에 늦게 온다"
    if "환율" in label or "달러" in label:
        return "이 흐름은 저장해둬
체감은 나중에 온다"
    if "비트코인" in label:
        return "지금 이 흐름
놓치면 또 늦는다"
    return "이 흐름 저장해둬
내일 바로 비교된다"


def _cover_candidates(label: str, market_label: str) -> List[str]:
    if "유가" in label:
        return ["지금 유가 변수 다시 옴", "기름값 다시 흔들린다", "오늘 돈은 유가 먼저 봄"]
    if "환율" in label or "달러" in label:
        return ["환율 다시 흔들린다", "달러 변수 다시 커졌다", "해외직구 부담 다시 옴"]
    if "비트코인" in label:
        return ["비트 다시 위 본다", "돈이 다시 코인 쪽 감", "위험자산 심리 살아남"]
    return [f"{label} 이유 나왔다", f"지금 돈은 {market_label[:8]} 쪽 본다", f"오늘 시장 1등 이슈는 {label[:8]}"]


def build_content_pack(news_items: List[Dict], poly_items: List[Dict], market_items: List[Dict]) -> Dict[str, str]:
    top_news = _top(news_items)
    top_poly = _top(poly_items)
    top_market = _top(market_items)
    hook = _hook(top_news["label"])
    outro = _outro(top_news["label"], top_market["label"])
    candidates = _cover_candidates(top_news["label"], top_market["label"])
    return {
        "cover_candidates": "
".join([f"{i+1}) {c}" for i, c in enumerate(candidates)]),
        "reel_hook": hook,
        "reel_outro": outro,
        "feed_caption": (
            f"{hook.replace(chr(10), ' ')}

"
            f"뉴스 1위: {top_news['label']}
"
            f"폴리마켓 1위: {top_poly['label']}
"
            f"시장 반응 1위: {top_market['label']}

"
            "오늘 돈이 먼저 반응한 흐름만 짧게 묶었습니다.
"
            "저장해두면 내일 비교할 때 바로 보입니다."
        ),
        "reel_caption": (
            f"{hook.replace(chr(10), ' ')}

"
            f"뉴스 1위: {top_news['label']}
"
            f"폴리마켓 1위: {top_poly['label']}
"
            f"시장 반응 1위: {top_market['label']}

"
            "지금 돈이 어디로 먼저 반응했는지 빠르게 정리했습니다.
"
            "저장해두고 내일 흐름 비교해보세요."
        ),
        "hashtags": "#경제 #경제뉴스 #돈흐름 #유가 #환율 #비트코인 #금리 #폴리마켓 #재테크 #투자",
        "cta": outro.replace(chr(10), ' '),
    }
