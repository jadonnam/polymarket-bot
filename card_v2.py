"""
card_v2.py — 카드 생성 래퍼 (새 모듈 연동)

image_generator_new + card_maker_new 연결
"""

import re
from card_maker_v3 import make_card, make_carousel_set, split_highlight, ACCENTS
from image_generator_new import safe_generate_bg, generate_carousel_bgs


def create_card(rewritten, mode="normal"):
    """단일 카드 생성 (기존 호환)"""
    accent = rewritten.get("accent", "gold")
    accent_color = ACCENTS.get(accent, ACCENTS["gold"])

    # 배경 생성
    safe_generate_bg(
        visual_topic=rewritten.get("visual_topic", "market_general"),
        seed_text=rewritten.get("title1", "") + rewritten.get("title2", ""),
        context_title=rewritten.get("title1", ""),
        context_desc=rewritten.get("desc1", ""),
        output_path="bg.jpg",
    )

    title1_parts = split_highlight(rewritten["title1"], accent_color)
    title2_parts = split_highlight(rewritten["title2"], accent_color)

    # 하단 데이터바
    data_bar = None
    if rewritten.get("_price_usd"):
        data_bar = [("현재가", rewritten["_price_usd"]), ("실시간", "LIVE")]
    elif rewritten.get("_volume") and rewritten.get("_prob"):
        data_bar = [("거래대금", rewritten["_volume"]), ("예측", rewritten["_prob"])]

    return make_card(
        eyebrow=rewritten.get("eyebrow", ""),
        title1_parts=title1_parts,
        title2_parts=title2_parts,
        desc_lines=[rewritten["desc1"], rewritten["desc2"]],
        brand_text="",
        topic_label="",
        mode=mode,
        accent=accent,
        data_bar=data_bar,
        card_index=0,
        total_cards=1,
    )


def create_carousel(rewritten, mode="normal"):
    """캐러셀 3장 생성"""
    visual_topic = rewritten.get("visual_topic", "market_general")
    seed = rewritten.get("title1", "") + rewritten.get("title2", "")

    # 배경 3장 생성
    bg_paths = generate_carousel_bgs(
        visual_topic=visual_topic,
        seed_text=seed,
        context_title=rewritten.get("title1", ""),
        context_desc=rewritten.get("desc1", ""),
    )

    return make_carousel_set(rewritten, mode=mode, bg_paths=bg_paths)
