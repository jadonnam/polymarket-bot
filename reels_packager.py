def _top(items):
    return items[0] if items else {"label":"시장 흐름 변화","score":80}

def _pick_hook(label):
    if "유가" in label: return "지금 돈 흐름, 유가 쪽으로 쏠린다"
    if "휴전" in label: return "시장은 휴전 가능성에 먼저 반응 중"
    if "비트코인" in label: return "비트코인, 다시 강해지는 흐름"
    if "환율" in label or "달러" in label: return "환율 부담, 다시 커지는 중"
    if "금리" in label: return "금리 기대가 시장을 다시 흔든다"
    return "지금 시장이 먼저 반응한 이슈"

def _pick_cover_text(label):
    if "유가" in label: return "유가 다시 움직인다"
    if "휴전" in label: return "휴전 기대 커지는 중"
    if "비트코인" in label: return "비트코인 흐름 바뀌었다"
    if "환율" in label or "달러" in label: return "환율 다시 흔들린다"
    if "금리" in label: return "금리 기대 다시 반영중"
    return "지금 돈 흐름 바뀌었다"

def build_content_pack(news_items, poly_items, market_items):
    top_news=_top(news_items); top_poly=_top(poly_items); top_market=_top(market_items)
    lead=top_news["label"]; hook=_pick_hook(lead); cover_text=_pick_cover_text(lead)
    return {
        "cover_text": cover_text,
        "feed_title": hook,
        "feed_caption": f"{hook}\n\n오늘 시장에서 가장 강하게 반응한 이슈만 정리했습니다.\n뉴스 / 폴리마켓 / 시장 반응 순서로 보면 흐름이 더 잘 보입니다.\n더 빠른 업데이트는 텔레그램에서 먼저 확인하세요.",
        "reel_hook": hook,
        "reel_script": f"오프닝: {hook}\n뉴스: {top_news['label']} {top_news['score']}%\n폴리마켓: {top_poly['label']} {top_poly['score']}%\n시장 반응: {top_market['label']} {top_market['score']}%\n마무리: 전체 흐름은 피드에서 확인",
        "reel_caption": f"{hook}\n뉴스 1위: {top_news['label']}\n폴리마켓 1위: {top_poly['label']}\n시장 반응 1위: {top_market['label']}\n\n전체 흐름은 피드에서 확인.",
        "story_text": f"오늘 1위 이슈: {top_news['label']}\n전체 TOP5는 피드 확인",
        "hashtags": "#경제 #경제뉴스 #돈흐름 #유가 #환율 #비트코인 #금리 #폴리마켓 #재테크 #투자",
        "first_comment": "실시간 흐름은 텔레그램에서 먼저 올립니다.",
    }
