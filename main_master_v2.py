"""
main_master_v2.py — 일반 포스팅 + 속보 감지 통합본

Railway Cron:
*/10 * * * *  → python main_master_v2.py

동작:
- 매 10분: 속보 체크
- 매일 08:00 / 19:00: 일반 포스팅 체크
"""

import json
import os
import random
from datetime import datetime, timedelta

from news import get_news_candidate
from rewrite_v2 import rewrite
from polymarket import get_polymarket_markets, classify_topic
from rewrite_poly_v2 import rewrite_poly
from card_v2 import create_card, create_carousel
from telegram_new import send_image
from market_state import detect_surge, update_market_snapshot
from memory import is_duplicate, add_history, is_same_topic, add_topic
from instagram_v2 import upload_carousel, upload_single, build_caption

MIX_FILE = "source_mix.json"
BREAKING_STATE_FILE = "breaking_state.json"

ALLOWED_TOPICS = {"geopolitics", "economy", "crypto"}

POLY_MIN_SCORE = 64
NEWS_MIN_SCORE = 58

# 속보는 더 빡세게
BREAKING_NEWS_MIN_SCORE = 78
BREAKING_POLY_MIN_SCORE = 82

# 같은 속보 너무 자주 안 올리기
BREAKING_COOLDOWN_MINUTES = 180

# 일반 포스팅 시간
REGULAR_POST_HOURS = {8, 19}
REGULAR_POST_MINUTE_WINDOW = 9   # 0~9분 사이만 허용

USE_CAROUSEL = os.getenv("USE_CAROUSEL", "false").lower() == "true"
TEST_FORCE_POST = os.getenv("TEST_FORCE_POST", "false").lower() == "true"


# =========================
# 공통 유틸
# =========================

def now_local():
    return datetime.now()


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# 소스 믹스 기록
# =========================

def load_mix():
    return load_json_file(MIX_FILE, [])


def save_mix(data):
    save_json_file(MIX_FILE, data[-40:])


def add_mix(source_name):
    data = load_mix()
    data.append(source_name)
    save_mix(data)


def recent_poly_count(n=6):
    return sum(1 for x in load_mix()[-n:] if x == "polymarket")


def recent_news_count(n=6):
    return sum(1 for x in load_mix()[-n:] if x == "news")


def source_bias():
    if recent_poly_count(6) >= 4:
        return "news_strong"
    if recent_news_count(6) <= 1:
        return "news_preferred"
    return "balanced"


# =========================
# 속보 상태 기록
# =========================

def load_breaking_state():
    return load_json_file(BREAKING_STATE_FILE, {"items": []})


def save_breaking_state(state):
    items = state.get("items", [])
    # 최근 80개만 저장
    state["items"] = items[-80:]
    save_json_file(BREAKING_STATE_FILE, state)


def was_recent_breaking(key, minutes=BREAKING_COOLDOWN_MINUTES):
    state = load_breaking_state()
    items = state.get("items", [])
    cutoff = now_local() - timedelta(minutes=minutes)

    for item in reversed(items):
        if item.get("key") != key:
            continue
        try:
            ts = datetime.fromisoformat(item["ts"])
            if ts >= cutoff:
                return True
        except Exception:
            continue
    return False


def mark_breaking_posted(key, source, title):
    state = load_breaking_state()
    state["items"].append({
        "key": key,
        "source": source,
        "title": title,
        "ts": now_local().isoformat(timespec="seconds"),
    })
    save_breaking_state(state)


# =========================
# 모드 / 점수
# =========================

def detect_poly_mode(question, topic, is_surge=False):
    text = question.lower()
    if is_surge:
        return "alert"
    if topic == "crypto":
        return "alert"
    if topic == "economy" and any(k in text for k in [
        "oil", "wti", "crude", "gold", "fed", "inflation", "tariff", "yield", "cpi"
    ]):
        return "alert"
    if topic in {"politics", "geopolitics"} and any(k in text for k in [
        "trump", "deal", "tariff", "ceasefire", "war", "attack"
    ]):
        return "alert"
    return "normal"


def detect_news_mode(title, summary):
    text = f"{title} {summary}".lower()
    if any(k in text for k in [
        "breaking", "trump", "tariff", "bitcoin", "oil", "gold",
        "fed", "inflation", "war", "attack", "yield", "cpi"
    ]):
        return "alert"
    return "normal"


def score_news_candidate(title, summary, rewritten):
    text = f"{title} {summary}".lower()
    out = f"{rewritten['eyebrow']} {rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"
    score = 0

    for k in [
        "bitcoin", "btc", "oil", "wti", "crude", "gold", "fed", "inflation",
        "cpi", "yield", "tariff", "trump", "deal", "nasdaq", "dow", "s&p"
    ]:
        if k in text:
            score += 15

    if any(k in out for k in [
        "늦으면", "또", "지갑", "숨멎", "벌써", "구경만",
        "들뜸", "처맞음", "멘붕", "식은땀", "배아픔", "난리", "쫄림"
    ]):
        score += 18

    if any(k in out for k in [
        "달러", "물가", "나스닥", "유가", "금값", "비트", "관세", "월가"
    ]):
        score += 18

    import re
    if re.search(r"\d+", rewritten.get("title1", "")):
        score += 15

    score += 12
    return score


def score_poly_candidate(question, volume, yes_price, rewritten, is_surge=False):
    text = question.lower()
    out = f"{rewritten['eyebrow']} {rewritten['title1']} {rewritten['title2']} {rewritten['desc1']} {rewritten['desc2']}"
    score = 0

    try:
        v = float(volume)
        if v >= 15_000_000:
            score += 34
        elif v >= 8_000_000:
            score += 28
        elif v >= 4_000_000:
            score += 22
        elif v >= 1_500_000:
            score += 16
    except Exception:
        pass

    try:
        p = float(yes_price)
        if 0.10 <= p <= 0.90:
            score += 18
        if 0.20 <= p <= 0.80:
            score += 10
    except Exception:
        pass

    for k in [
        "bitcoin", "btc", "oil", "wti", "crude", "gold", "fed", "inflation",
        "cpi", "yield", "tariff", "trump", "deal", "nasdaq"
    ]:
        if k in text:
            score += 12

    if is_surge:
        score += 18

    if any(k in out for k in [
        "늦으면", "또", "지갑", "숨멎", "벌써", "구경만",
        "처맞음", "멘붕", "식은땀", "배아픔", "난리", "쫄림"
    ]):
        score += 16

    return score


def rewritten_topic_key(question):
    q = question.lower()
    if any(k in q for k in ["bitcoin", "btc"]):
        return "btc"
    if any(k in q for k in ["ethereum", "eth"]):
        return "eth"
    if any(k in q for k in ["oil", "wti", "crude"]):
        return "oil"
    if "gold" in q:
        return "gold"
    if any(k in q for k in ["fed", "rate", "inflation", "cpi", "yield"]):
        return "macro"
    if any(k in q for k in ["trump", "deal", "tariff"]):
        return "trump_trade"
    if any(k in q for k in ["war", "attack", "ceasefire", "iran", "israel"]):
        return "mideast"
    if any(k in q for k in ["nasdaq", "s&p", "dow"]):
        return "stocks"
    return "general"


# =========================
# 속보용 강한 필터
# =========================

def is_major_breaking_news(title, summary, score):
    text = f"{title} {summary}".lower()

    # 큰 속보 키워드
    strong_keywords = [
        "breaking", "urgent", "attack", "missile", "explosion", "war", "ceasefire",
        "tariff", "emergency", "sanction", "fed", "cpi", "inflation", "rate cut",
        "bitcoin", "btc", "ethereum", "eth", "oil", "gold", "trump"
    ]

    # 진짜 큰 뉴스 성격
    high_impact_patterns = [
        ["war"],
        ["attack"],
        ["missile"],
        ["ceasefire"],
        ["tariff"],
        ["fed"],
        ["cpi"],
        ["inflation"],
        ["bitcoin"],
        ["btc"],
        ["oil"],
        ["gold"],
        ["trump"],
    ]

    keyword_hits = sum(1 for k in strong_keywords if k in text)
    impact_hit = any(all(p in text for p in group) for group in high_impact_patterns)

    if score < BREAKING_NEWS_MIN_SCORE:
        return False

    # 강한 키워드가 너무 적으면 탈락
    if keyword_hits < 1:
        return False

    if not impact_hit:
        return False

    # 너무 가벼운 표현 차단
    weak_noise = [
        "analyst says",
        "could",
        "may",
        "might",
        "opinion",
        "preview",
        "watchlist",
        "rumor",
    ]
    if any(w in text for w in weak_noise) and score < BREAKING_NEWS_MIN_SCORE + 8:
        return False

    return True


def is_major_breaking_poly(question, volume, yes_price, score, is_surge):
    text = question.lower()

    try:
        v = float(volume)
    except Exception:
        v = 0.0

    try:
        p = float(yes_price)
    except Exception:
        p = 0.0

    # 속보형 폴리마켓은 진짜 센 것만
    impact_keywords = [
        "attack", "war", "ceasefire", "trump", "tariff",
        "bitcoin", "btc", "ethereum", "eth", "oil", "gold",
        "fed", "cpi", "inflation"
    ]
    has_impact = any(k in text for k in impact_keywords)

    if score < BREAKING_POLY_MIN_SCORE:
        return False

    if not has_impact:
        return False

    # 거래량과 변동성 둘 중 하나는 세야 함
    if not is_surge and v < 8_000_000:
        return False

    # 확률이 너무 0 or 100에 가까운 건 속보감 약하면 제외
    if p <= 0.03 or p >= 0.97:
        if not is_surge and v < 15_000_000:
            return False

    return True


# =========================
# 후보 빌드
# =========================

def build_news_candidate():
    article = get_news_candidate()
    if not article:
        return None

    title = article["title"]
    summary = article["description"]
    topic = classify_topic(title, summary)

    if topic not in ALLOWED_TOPICS:
        return None

    mode = detect_news_mode(title, summary)
    rewritten = rewrite(title, summary, mode=mode)
    score = score_news_candidate(title, summary, rewritten)

    if score < NEWS_MIN_SCORE:
        return None

    return {
        "source": "news",
        "raw_title": title,
        "raw_summary": summary,
        "mode": mode,
        "topic": topic,
        "rewritten": rewritten,
        "score": score,
    }


def build_poly_candidates():
    markets = get_polymarket_markets(limit=180)
    candidates = []
    seen_topics = set()

    for market in markets[:80]:
        question = market["question"]
        description = market.get("description", "")
        topic = classify_topic(question, description)

        if topic not in ALLOWED_TOPICS:
            continue
        if is_duplicate(question):
            continue

        theme = rewritten_topic_key(question)
        if theme in seen_topics:
            continue

        surge = detect_surge(
            question=question,
            volume=market["volume"],
            yes_price=market["yes_price"],
        )
        mode = detect_poly_mode(question, topic, is_surge=surge)
        rewritten = rewrite_poly(
            question=question,
            volume=market["volume"],
            yes_price=market["yes_price"],
            end_date=market["end_date"],
        )
        score = score_poly_candidate(
            question,
            market["volume"],
            market["yes_price"],
            rewritten,
            is_surge=surge,
        )

        if score < POLY_MIN_SCORE:
            continue

        candidates.append({
            "source": "polymarket",
            "raw_title": question,
            "raw_summary": description,
            "mode": mode,
            "topic": topic,
            "rewritten": rewritten,
            "score": score,
            "volume": market["volume"],
            "yes_price": market["yes_price"],
            "end_date": market["end_date"],
            "is_surge": surge,
        })
        seen_topics.add(theme)

        if len(candidates) >= 12:
            break

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


def choose_winner():
    news_candidate = build_news_candidate()
    poly_candidates = build_poly_candidates()
    best_poly = poly_candidates[0] if poly_candidates else None
    bias = source_bias()

    if bias == "news_strong" and news_candidate:
        return news_candidate

    if bias == "news_preferred" and news_candidate:
        if best_poly is None or news_candidate["score"] >= best_poly["score"] - 4:
            return news_candidate

    if news_candidate and best_poly:
        if news_candidate["score"] >= best_poly["score"] + 5:
            return news_candidate
        if best_poly["score"] >= news_candidate["score"] + 12:
            return best_poly
        return random.choice([news_candidate, best_poly])

    if news_candidate:
        return news_candidate
    if best_poly:
        return best_poly
    return None


def choose_breaking_winner():
    news_candidate = build_news_candidate()
    poly_candidates = build_poly_candidates()
    breaking_candidates = []

    if news_candidate:
        if is_major_breaking_news(
            news_candidate["raw_title"],
            news_candidate["raw_summary"],
            news_candidate["score"],
        ):
            breaking_candidates.append(news_candidate)

    for c in poly_candidates[:5]:
        if is_major_breaking_poly(
            c["raw_title"],
            c["volume"],
            c["yes_price"],
            c["score"],
            c.get("is_surge", False),
        ):
            breaking_candidates.append(c)

    if not breaking_candidates:
        return None

    breaking_candidates.sort(key=lambda x: x["score"], reverse=True)
    return breaking_candidates[0]


# =========================
# 포스팅 실행
# =========================

def post_winner(winner, label="일반"):
    if not winner:
        print(f"[{label}] 보낼 후보 없음 → 종료")
        return False

    if winner["source"] != "test" and is_duplicate(winner["raw_title"]):
        print(f"[{label}] 중복 스킵:", winner["raw_title"])
        return False

    if winner["source"] != "test" and is_same_topic(winner["topic"]) and winner["score"] < 86:
        print(f"[{label}] 같은 주제 스킵:", winner["topic"])
        return False

    rw = winner["rewritten"]
    print(f"[{label}] [소스] {winner['source']} | [점수] {winner['score']}")
    print(f"[eyebrow] {rw.get('eyebrow', '')}")
    print(f"[title1] {rw['title1']}")
    print(f"[title2] {rw['title2']}")
    print(f"[desc1] {rw['desc1']}")
    print(f"[desc2] {rw['desc2']}")

    mode = winner["mode"]
    topic_key = rw.get("_key", "GENERAL")

    if USE_CAROUSEL:
        print(f"[{label}] 캐러셀 3장 생성 중...")
        card_paths = create_carousel(rw, mode=mode)
    else:
        print(f"[{label}] 단일 이미지 생성 중...")
        card_paths = [create_card(rw, mode=mode)]

    try:
        send_image(card_paths[0])
        print(f"[{label}] 텔레그램 전송 완료")
    except Exception as e:
        print(f"[{label}] 텔레그램 스킵/오류: {e}")

    caption = build_caption(rw, topic_key=topic_key)

    if USE_CAROUSEL and len(card_paths) >= 3:
        post_id = upload_carousel(card_paths, caption)
    else:
        post_id = upload_single(card_paths[0], caption)

    if post_id:
        print(f"[{label}] 인스타그램 업로드 완료: {post_id}")
    else:
        print(f"[{label}] 인스타그램 스킵 또는 오류")
        return False

    if winner["source"] == "polymarket":
        update_market_snapshot(
            question=winner["raw_title"],
            volume=winner.get("volume", 0),
            yes_price=winner.get("yes_price", 0),
        )

    if winner["source"] != "test":
        add_history(winner["raw_title"])
        add_topic(winner["topic"])
        add_mix(winner["source"])

    print(f"[{label}] 완료")
    return True


def run_regular():
    print("[일반] 실행 시작")
    winner = choose_winner()

    if not winner and TEST_FORCE_POST:
        print("[TEST] 강제 테스트 모드 실행")
        test_title = "Bitcoin jumps as institutional flows return"
        test_summary = "BTC rises on renewed ETF demand and risk-on sentiment."
        mode = detect_news_mode(test_title, test_summary)
        rewritten = rewrite(test_title, test_summary, mode=mode)
        winner = {
            "source": "test",
            "raw_title": test_title,
            "raw_summary": test_summary,
            "mode": mode,
            "topic": "crypto",
            "rewritten": rewritten,
            "score": 999,
        }

    post_winner(winner, label="일반")


def run_breaking():
    print("[속보] 실행 시작")
    winner = choose_breaking_winner()

    if not winner:
        print("[속보] 큰 속보 없음 → 종료")
        return

    breaking_key = f"{winner['source']}::{winner['raw_title'][:120]}"
    if was_recent_breaking(breaking_key):
        print("[속보] 최근 동일 속보 이미 업로드됨 → 스킵")
        return

    success = post_winner(winner, label="속보")
    if success:
        mark_breaking_posted(
            key=breaking_key,
            source=winner["source"],
            title=winner["raw_title"],
        )


# =========================
# 스케줄 분기
# =========================

def should_run_regular(dt):
    return dt.hour in REGULAR_POST_HOURS and dt.minute <= REGULAR_POST_MINUTE_WINDOW


def run_scheduler():
    dt = now_local()
    print(f"[스케줄] 현재 시각: {dt.strftime('%Y-%m-%d %H:%M:%S')}")

    # 1) 속보는 매 10분마다 체크
    try:
        run_breaking()
    except Exception as e:
        print("[속보 ERROR]", e)

    # 2) 일반 포스팅은 08시 / 19시만
    if should_run_regular(dt):
        try:
            run_regular()
        except Exception as e:
            print("[일반 ERROR]", e)
    else:
        print("[일반] 이번 회차 스킵")


if __name__ == "__main__":
    run_scheduler()