"""자돈남 DESK 텔레그램 — reference_pipeline 레퍼런스 프롬프트 1회 생성."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from reference_pipeline import (
    apply_pack_to_article,
    format_desk_telegram_message,
    generate_reference_pack,
    now_kst,
)


def build_desk_briefing_text(
    *,
    articles: List[Dict[str, Any]],
    market_data: Optional[Dict[str, Any]] = None,
    lead_article: Optional[Dict[str, Any]] = None,
    dt: Optional[datetime] = None,
) -> str:
    pack = generate_reference_pack(
        articles,
        market_data=market_data,
        lead_article=lead_article,
    )
    return format_desk_telegram_message(
        pack,
        articles=articles,
        lead_article=lead_article,
        market_data=market_data,
        dt=dt,
    )


def build_desk_with_pack(
    *,
    articles: List[Dict[str, Any]],
    market_data: Optional[Dict[str, Any]] = None,
    lead_article: Optional[Dict[str, Any]] = None,
):
    """DESK 텍스트 + 카드용 pack (OpenAI 1회)."""
    pack = generate_reference_pack(
        articles,
        market_data=market_data,
        lead_article=lead_article,
    )
    desk = format_desk_telegram_message(
        pack,
        articles=articles,
        lead_article=lead_article,
        market_data=market_data,
    )
    return pack, desk


__all__ = [
    "build_desk_briefing_text",
    "build_desk_with_pack",
    "apply_pack_to_article",
    "now_kst",
]
