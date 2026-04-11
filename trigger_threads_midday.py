"""
trigger_threads_midday.py

Railway Cron: 0 9,13,17,21 * * *

실행 시간별 동작:
09시 → 자영업 공감글 + 자돈남 뉴스 기반 단신
13시 → 자영업 공감글 + 자돈남 경제 개념 글
17시 → 자영업 공감글 + 자돈남 뉴스 기반 단신
21시 → 자영업 공감글 + 자돈남 경제 개념 글
"""

import os
from datetime import datetime, timedelta, timezone

from threads_auto import run_omniflow_single, run_jadonnam_midday_post
from polymarket import get_polymarket_markets
import news as news_module


def now_kst():
    return datetime.now(timezone.utc) + timedelta(hours=9)


def get_top_news():
    try:
        articles = news_module.fetch_news(limit=10, hours_back=12) or []
        result = []
        for art in articles[:3]:
            result.append({
                "label": art.get("title", "")[:40],
                "title": art.get("title", ""),
            })
        return result
    except Exception:
        return []


if __name__ == "__main__":
    hour = now_kst().hour
    is_news_turn = hour in [9, 17]

    print(f"[중간 포스팅] KST {hour}시 실행 / 뉴스기반={is_news_turn}")

    # 자영업 공감글
    run_omniflow_single()

    # 자돈남 경제 단신
    top_news = get_top_news() if is_news_turn else []
    run_jadonnam_midday_post(top_news=top_news, is_news_turn=is_news_turn)

    print("[중간 포스팅] 완료")
