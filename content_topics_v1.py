from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Dict, List


TOPIC_POOL: List[Dict[str, str]] = [
    {"category": "미국 주식", "slug": "us_stocks", "title": "오늘 미국장 핵심 한 줄"},
    {"category": "ETF", "slug": "etf", "title": "지금 ETF 자금이 몰리는 곳"},
    {"category": "AI 기업", "slug": "ai", "title": "AI 기업 밸류에이션 체크포인트"},
    {"category": "반도체", "slug": "semiconductor", "title": "반도체 사이클 지금 어디쯤"},
    {"category": "비트코인", "slug": "bitcoin", "title": "비트코인 움직인 진짜 이유"},
    {"category": "금리", "slug": "rates", "title": "금리 한 줄이 시장을 바꾼 이유"},
    {"category": "CPI", "slug": "cpi", "title": "CPI 발표 후 바로 볼 숫자 3개"},
    {"category": "배당주", "slug": "dividend", "title": "배당주 고를 때 놓치기 쉬운 함정"},
    {"category": "장기투자", "slug": "long_term", "title": "장기투자 수익률을 가르는 습관"},
    {"category": "시장 순위", "slug": "market_rank", "title": "오늘 시장 강약 순위"},
    {"category": "수익률 비교", "slug": "return_compare", "title": "수익률 비교로 보는 자금 이동"},
    {"category": "빅테크", "slug": "big_tech", "title": "빅테크 7종 힘의 균형"},
    {"category": "테슬라/엔비디아/애플", "slug": "tna", "title": "테슬라·엔비디아·애플 누가 주도하나"},
]


def _seed_index() -> int:
    now = datetime.now(timezone.utc) + timedelta(hours=9)
    # Rotate topics in a predictable daily cadence.
    return (now.toordinal() * 3 + now.hour // 8) % max(1, len(TOPIC_POOL))


def pick_daily_topics(limit: int = 2) -> List[Dict[str, str]]:
    if limit <= 0:
        return []
    start = _seed_index()
    out: List[Dict[str, str]] = []
    for i in range(min(limit, len(TOPIC_POOL))):
        out.append(TOPIC_POOL[(start + i) % len(TOPIC_POOL)])
    return out


def pick_single_topic(preferred_slug: str = "") -> Dict[str, str]:
    if preferred_slug:
        for topic in TOPIC_POOL:
            if topic["slug"] == preferred_slug:
                return topic
    idx = _seed_index()
    return TOPIC_POOL[idx]


def random_topic() -> Dict[str, str]:
    return random.choice(TOPIC_POOL)
