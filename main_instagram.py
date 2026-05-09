from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import news as news_module
from content_topics_v1 import pick_single_topic
from card_news_v2 import build_card_news_v2
from card_v3 import create_breaking_image
from market_fact_cards import build_market_fact_cards
from news_template import build_jadonnam_signature_cards
from rank_card_v3 import create_rank_set
from ranking_template import render_ranking_template
from stock_study_template import render_stock_study_template
from simple_news_card import build_simple_news_card_set

try:
    from content_dispatcher import send_storage_image, send_storage_media_group, send_storage_message, send_storage_video
except Exception:
    send_storage_image = None
    send_storage_media_group = None
    send_storage_message = None
    send_storage_video = None

try:
    from threads_auto import (
        run_jadonnam_midday_post,
        run_omniflow_single,
    )
    THREADS_ENABLED = True
except Exception:
    THREADS_ENABLED = False

REGULAR_STATE_FILE = "regular_rank_state.json"
BREAKING_STATE_FILE = "breaking_state.json"
SCORE_HISTORY_FILE = "score_history.json"
THREADS_MIDDAY_STATE_FILE = "threads_midday_state.json"
OUT_DIR = "output_rank"
CARD_OUT_DIR = "output_cardnews"
MARKET_FACT_OUT_DIR = "output_marketfact"
STATIC_REEL_OUT_DIR = "output_static_reel"

REGULAR_POST_MINUTE_WINDOW = int((os.getenv("REGULAR_POST_MINUTE_WINDOW") or "30").strip())
REGULAR_MORNING_MINUTE = 8 * 60 + 10
REGULAR_EVENING_MINUTE = 19 * 60 + 10
BREAKING_COOLDOWN_MINUTES = 720
BREAKING_NEWS_MIN_SCORE = 108
BREAKING_POLY_MIN_SCORE = 92
DRY_RUN_PIPELINE = (os.getenv("DRY_RUN_PIPELINE") or "false").lower() == "true"
SKIP_BREAKING_CHECK = (os.getenv("SKIP_BREAKING_CHECK") or "true").lower() == "true"
ENABLE_TELEGRAM_STORAGE = (os.getenv("ENABLE_TELEGRAM_STORAGE") or "false").lower() == "true"
FORCE_REGULAR_NOW = (os.getenv("FORCE_REGULAR_NOW") or "false").lower() == "true"
USE_REEL_STORY_V2 = (os.getenv("USE_REEL_STORY_V2") or "true").lower() == "true"
CARD_NEWS_MODE = (os.getenv("CARD_NEWS_MODE") or "false").lower() == "true"
CONTENT_MODE = (os.getenv("CONTENT_MODE") or "briefing").strip().lower()
STATIC_REEL_MODE = (os.getenv("STATIC_REEL_MODE") or "false").lower() == "true"
STATIC_REEL_FORMAT = (os.getenv("STATIC_REEL_FORMAT") or "stock_study").strip().lower()
DEFAULT_STOCK_TICKER = (os.getenv("DEFAULT_STOCK_TICKER") or "NVDA").strip().upper()
ENABLE_OPENAI_STATIC_IMAGE = (os.getenv("ENABLE_OPENAI_STATIC_IMAGE") or "false").lower() == "true"
FORCE_REGENERATE_STATIC_BG = (os.getenv("FORCE_REGENERATE_STATIC_BG") or "false").lower() == "true"
REEL_AUTOMATION_ENABLED = (os.getenv("REEL_AUTOMATION_ENABLED") or "false").lower() == "true"

# 스레드 중간 포스팅 시간 (KST 시간 기준)
THREADS_MIDDAY_HOURS = [9, 13, 17, 21]


def now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def selected_pipeline_name() -> str:
    if STATIC_REEL_MODE:
        return "disabled_static_reel"
    if CARD_NEWS_MODE:
        mode = resolve_content_mode()
        if mode == "market_fact":
            return "market_fact"
        return "card_news_v2"
    return "card_news_only"


def resolve_content_mode() -> str:
    # auto mode suggestion: 08:10 briefing, 19:10 market_fact
    mode = CONTENT_MODE
    if mode in ("market_fact", "briefing"):
        return mode
    if mode == "auto":
        slot = current_regular_slot()
        if slot == "morning":
            return "briefing"
        if slot == "evening":
            return "market_fact"
    return "briefing"


def generated_at_text() -> str:
    return now_kst().strftime("%Y.%m.%d %H:%M KST")


def _load_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def current_regular_slot() -> Optional[str]:
    now = now_kst()
    total = now.hour * 60 + now.minute
    if REGULAR_MORNING_MINUTE <= total < REGULAR_MORNING_MINUTE + REGULAR_POST_MINUTE_WINDOW:
        return "morning"
    if REGULAR_EVENING_MINUTE <= total < REGULAR_EVENING_MINUTE + REGULAR_POST_MINUTE_WINDOW:
        return "evening"
    return None


def should_run_regular_post() -> bool:
    return FORCE_REGULAR_NOW or current_regular_slot() is not None


def load_regular_state() -> Dict[str, str]:
    return _load_json(REGULAR_STATE_FILE, {"last_morning_date": "", "last_evening_date": "", "last_force_ts": ""})


def save_regular_state(data: Dict[str, str]) -> None:
    _save_json(REGULAR_STATE_FILE, data)


def already_sent_regular() -> bool:
    if FORCE_REGULAR_NOW:
        return False
    state = load_regular_state()
    today = now_kst().strftime("%Y-%m-%d")
    slot = current_regular_slot()
    if slot == "morning":
        return state.get("last_morning_date") == today
    if slot == "evening":
        return state.get("last_evening_date") == today
    return False


def mark_regular_sent() -> None:
    state = load_regular_state()
    today = now_kst().strftime("%Y-%m-%d")
    slot = current_regular_slot()
    if FORCE_REGULAR_NOW:
        state["last_force_ts"] = now_kst().isoformat(timespec="seconds")
    elif slot == "morning":
        state["last_morning_date"] = today
    elif slot == "evening":
        state["last_evening_date"] = today
    save_regular_state(state)


# ── 스레드 중간 포스팅 중복 방지 ────────────────────────────

def already_sent_threads_midday(hour: int) -> bool:
    state = _load_json(THREADS_MIDDAY_STATE_FILE, {})
    today = now_kst().strftime("%Y-%m-%d")
    key = f"{today}_{hour}"
    return state.get(key) is True


def mark_threads_midday_sent(hour: int) -> None:
    state = _load_json(THREADS_MIDDAY_STATE_FILE, {})
    today = now_kst().strftime("%Y-%m-%d")
    key = f"{today}_{hour}"
    state[key] = True
    # 오래된 키 정리 (최근 48시간치만 유지)
    keys_to_keep = {}
    for k, v in state.items():
        try:
            date_str = k.rsplit("_", 1)[0]
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if (now_kst().date() - dt.date()).days <= 2:
                keys_to_keep[k] = v
        except Exception:
            pass
    keys_to_keep[key] = True
    _save_json(THREADS_MIDDAY_STATE_FILE, keys_to_keep)


def should_run_threads_midday() -> Optional[int]:
    now = now_kst()
    hour = now.hour
    minute = now.minute
    # 정해진 시간이고 30분 이내이고 아직 안 보냈으면
    if hour in THREADS_MIDDAY_HOURS and minute < 30:
        if not already_sent_threads_midday(hour):
            return hour
    return None


# ── 스레드 중간 포스팅 실행 ──────────────────────────────────

def run_threads_midday(hour: int) -> None:
    if not THREADS_ENABLED:
        return
    try:
        is_news_turn = hour in [9, 17]
        top_news = []
        if is_news_turn:
            try:
                articles = news_module.fetch_news(limit=5, hours_back=12) or []
                for art in articles[:3]:
                    top_news.append({
                        "label": art.get("title", "")[:40],
                        "title": art.get("title", ""),
                    })
            except Exception:
                pass

        # 자영업 공감글
        run_omniflow_single()

        # 자돈남 경제 단신
        run_jadonnam_midday_post(top_news=top_news, is_news_turn=is_news_turn)

        mark_threads_midday_sent(hour)
        print(f"[스레드 중간 포스팅 완료] {hour}시")
    except Exception as e:
        print(f"[스레드 중간 포스팅 오류] {repr(e)}")


# ── 나머지 함수들 ────────────────────────────────────────────

def load_breaking_state() -> Dict[str, List[Dict[str, str]]]:
    return _load_json(BREAKING_STATE_FILE, {"items": []})


def save_breaking_state(state: Dict[str, Any]) -> None:
    state["items"] = state.get("items", [])[-100:]
    _save_json(BREAKING_STATE_FILE, state)


def was_recent_breaking(key: str) -> bool:
    state = load_breaking_state()
    cutoff = now_kst() - timedelta(minutes=BREAKING_COOLDOWN_MINUTES)
    for item in reversed(state.get("items", [])):
        if item.get("key") != key:
            continue
        try:
            ts = datetime.fromisoformat(item["ts"])
            if ts >= cutoff:
                return True
        except Exception:
            continue
    return False


def mark_breaking_posted(key: str, title: str) -> None:
    state = load_breaking_state()
    state["items"].append({"key": key, "title": title, "ts": now_kst().isoformat(timespec="seconds")})
    save_breaking_state(state)


def _contains(text: str, words: List[str]) -> bool:
    t = str(text).lower()
    return any(w in t for w in words)


def _clean(text: str, limit: int = 16) -> str:
    text = re.sub(r"\s+", " ", str(text).strip())
    return text[:limit].strip()


def parse_datetime_safe(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def regular_window_bounds() -> Tuple[Optional[datetime], Optional[datetime]]:
    now = now_kst()
    slot = current_regular_slot()
    if slot == "morning":
        end_kst = now.replace(hour=8, minute=10, second=0, microsecond=0)
        start_kst = (end_kst - timedelta(days=1)).replace(hour=19, minute=10, second=0, microsecond=0)
        return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)
    if slot == "evening":
        end_kst = now.replace(hour=19, minute=10, second=0, microsecond=0)
        start_kst = now.replace(hour=8, minute=10, second=0, microsecond=0)
        return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)
    return None, None


def article_in_window(article: Dict[str, Any]) -> bool:
    start_utc, end_utc = regular_window_bounds()
    if not start_utc or not end_utc:
        return True
    dt = parse_datetime_safe(article.get("publishedAt"))
    if dt is None:
        return True
    return start_utc <= dt <= end_utc



def _news_label(title: str) -> str:
    t = str(title or "").strip()
    low = t.lower()
    if _contains(low, ["strait of hormuz", "hormuz", "호르무즈"]): return "호르무즈 변수 확대"
    if _contains(low, ["환율", "달러", "usd", "fx", "won", "dollar", "krw"]): return "환율 변동성 확대"
    if _contains(low, ["유가", "oil", "wti", "crude", "brent", "opec", "refinery"]): return "유가 상방 압력"
    if _contains(low, ["bitcoin", "btc", "비트"]): return "비트코인 강세 유지"
    if _contains(low, ["ethereum", "eth", "이더"]): return "이더 강세 유지"
    if _contains(low, ["금리", "fed", "cpi", "inflation", "yield", "rate cut"]): return "금리 완화 기대"
    if _contains(low, ["trump", "트럼프", "tariff", "관세"]): return "트럼프 변수 확대"
    if _contains(low, ["iran", "israel", "war", "attack", "missile", "전쟁", "이란", "이스라엘", "공습", "ceasefire", "truce"]): return "휴전 기대 확대"
    if _contains(low, ["gold", "금값", "금"]): return "안전자산 선호"
    if _contains(low, ["france", "french", "fra "]): return "유럽 정치 변수"
    return _clean(t, 18)


def _news_score(article: Dict[str, Any]) -> int:
    title = article.get("title", "") or ""
    desc = article.get("description", "") or ""
    text = f"{title} {desc}".lower()
    score = 25
    if _contains(text, ["환율", "usd", "fx", "달러", "won"]): score += 24
    if _contains(text, ["oil", "wti", "crude", "brent", "유가"]): score += 26
    if _contains(text, ["war", "attack", "missile", "전쟁", "공습", "이란", "israel", "iran"]): score += 22
    if _contains(text, ["fed", "cpi", "inflation", "yield", "금리", "물가"]): score += 22
    if _contains(text, ["bitcoin", "btc", "eth", "ethereum", "비트", "코인"]): score += 18
    if _contains(text, ["trump", "관세", "tariff"]): score += 16
    if re.search(r"\d", text): score += 8
    if article_in_window(article): score += 6
    return min(score, 100)


def fetch_news_articles(hours_back: int = 36, limit: int = 40) -> List[Dict[str, Any]]:
    try:
        return news_module.fetch_news(limit=limit, hours_back=hours_back) or []
    except TypeError:
        try:
            return news_module.fetch_news() or []
        except Exception:
            return []
    except Exception:
        return []


def fetch_breaking_news_articles(hours_back: int = 12, limit: int = 20) -> List[Dict[str, Any]]:
    try:
        return news_module.fetch_breaking_news(limit=limit, hours_back=hours_back) or []
    except Exception:
        return []



def _poly_label(question: str) -> str:
    q = str(question or "").strip()
    low = q.lower()

    # 스포츠/연예/잡시장 제거용 라벨
    if _contains(low, ["sevilla", "rory", "fc ", "golf", "nba", "mlb", "nfl", "soccer", "tennis", "f1", "champions"]):
        return "해외 베팅 이슈"
    if _contains(low, ["wti", "oil", "crude", "brent", "유가"]): return "유가 상단 도전"
    if _contains(low, ["ceasefire", "휴전", "truce"]): return "휴전 베팅 확대"
    if _contains(low, ["hormuz", "호르무즈"]): return "호르무즈 정상화 기대"
    if _contains(low, ["trump", "트럼프"]): return "트럼프 변수 확대"
    if _contains(low, ["bitcoin", "btc", "비트"]): return "비트코인 상단 테스트"
    if _contains(low, ["gold", "금"]): return "금 선호 확대"
    if _contains(low, ["fed", "cpi", "inflation", "금리", "rate cut"]): return "금리 방향 베팅"
    if _contains(low, ["us", "iran", "meet", "talk", "deal", "회담"]): return "미국-이란 회담 변수"
    if _contains(low, ["military action", "strike", "attack", "troops"]): return "군사 행동 가능성"
    if low.startswith("will "): return "해외 베팅 이슈"
    return _clean(q, 18)


def _to_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def _poly_score(question: str, volume: Any, yes_price: Any) -> int:
    text = str(question).lower()
    score = 24
    v = _to_float(volume, 0.0)
    p = _to_float(yes_price, 0.0)
    if v >= 20_000_000: score += 42
    elif v >= 10_000_000: score += 36
    elif v >= 5_000_000: score += 28
    elif v >= 1_000_000: score += 18
    if 0.10 <= p <= 0.90: score += 14
    if 0.20 <= p <= 0.80: score += 8
    if _contains(text, ["oil", "wti", "crude", "brent", "hormuz"]): score += 18
    if _contains(text, ["bitcoin", "btc", "eth", "ethereum"]): score += 16
    if _contains(text, ["iran", "israel", "war", "attack", "ceasefire"]): score += 18
    if _contains(text, ["trump", "tariff", "fed", "cpi", "yield"]): score += 14
    return min(score, 100)



def build_poly_rank_items() -> List[Dict[str, Any]]:
    print("[비용절약] Polymarket API 비활성화, 고정 랭크 사용")
    return [
        {"label": "유가 상단 도전", "score": 82},
        {"label": "휴전 베팅 확대", "score": 79},
        {"label": "트럼프 변수 확대", "score": 75},
        {"label": "호르무즈 정상화 기대", "score": 72},
        {"label": "비트코인 상단 테스트", "score": 69},
    ]


def build_news_rank_items() -> List[Dict[str, Any]]:
    articles = fetch_news_articles(hours_back=36, limit=40)
    if not articles:
        return [
            {"label": "유가 상방 압력", "score": 82},
            {"label": "휴전 기대 확대", "score": 78},
            {"label": "비트코인 강세 유지", "score": 75},
            {"label": "달러 강세 유지", "score": 72},
            {"label": "금리 완화 기대", "score": 69},
        ]
    scored = []
    seen = set()
    for art in articles:
        label = _news_label(art.get("title", ""))
        if label in seen:
            continue
        seen.add(label)
        scored.append({"label": label, "score": _news_score(art), "title": art.get("title", "")})
    scored.sort(key=lambda x: x["score"], reverse=True)
    fillers = [
        {"label": "유가 상방 압력", "score": 80},
        {"label": "휴전 기대 확대", "score": 77},
        {"label": "비트코인 강세 유지", "score": 74},
        {"label": "달러 강세 유지", "score": 71},
        {"label": "금리 완화 기대", "score": 68},
    ]
    out = scored[:5]
    while len(out) < 5:
        out.append(fillers[len(out)])
    return out[:5]



def build_market_rank_items(news_items: List[Dict[str, Any]], poly_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    buckets = {
        "유가 상방 압력": 0,
        "환율 변동성 확대": 0,
        "비트코인 강세 유지": 0,
        "금 선호 강화": 0,
        "금리 부담 확대": 0,
    }

    for item in news_items + poly_items:
        label, score = item["label"], int(item["score"])
        if _contains(label, ["유가", "호르무즈", "oil", "crude", "wti"]): buckets["유가 상방 압력"] += score * 1.20
        if _contains(label, ["환율", "달러", "usd", "fx"]): buckets["환율 변동성 확대"] += score * 1.08
        if _contains(label, ["비트", "btc", "코인", "crypto"]): buckets["비트코인 강세 유지"] += score * 1.12
        if _contains(label, ["금", "gold", "안전자산"]): buckets["금 선호 강화"] += score * 1.05
        if _contains(label, ["금리", "fed", "cpi", "yield"]): buckets["금리 부담 확대"] += score * 1.00
        if _contains(label, ["전쟁", "공습", "지정학", "휴전", "이란", "이스라엘"]):
            buckets["유가 상방 압력"] += 10
            buckets["금 선호 강화"] += 8

    vals = list(buckets.values())
    max_v = max(vals) if vals else 1
    min_v = min(vals) if vals else 0
    ranked = []
    for k, v in buckets.items():
        if max_v == min_v:
            score = 65
        else:
            score = 55 + int((v - min_v) / (max_v - min_v) * 35)
        ranked.append({"label": k, "score": max(45, min(95, score))})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:5]


def load_score_history() -> Dict[str, Dict[str, int]]:
    return _load_json(SCORE_HISTORY_FILE, {"news": {}, "poly": {}, "market": {}})


def save_score_history(data: Dict[str, Dict[str, int]]) -> None:
    _save_json(SCORE_HISTORY_FILE, data)


def attach_deltas(page_key: str, items: List[Dict[str, Any]], history: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    prev = history.get(page_key, {})
    out = []
    for item in items:
        label = item["label"]
        score = int(item["score"])
        delta = None
        if label in prev:
            delta = score - int(prev[label])
        new_item = dict(item)
        new_item["delta"] = delta
        out.append(new_item)
    history[page_key] = {item["label"]: int(item["score"]) for item in items}
    return out


def post_regular_rank_cards() -> None:
    print(f"[mode] CARD_NEWS_MODE={str(CARD_NEWS_MODE).lower()}")
    print(f"[mode] USE_REEL_STORY_V2={str(USE_REEL_STORY_V2).lower()}")
    print(f"[mode] selected pipeline={selected_pipeline_name()}")
    if STATIC_REEL_MODE:
        print("[static_reel] disabled by policy: focus on saved card news")
        return

    if CARD_NEWS_MODE:
        print("[mode] simple image-first renderer enabled")
        post_simple_news_cards()
        return

    # Non-card-news mode is intentionally disabled.
    print("[policy] CARD_NEWS_MODE=false 경로 비활성화")
    mark_regular_sent()


def post_simple_news_cards() -> None:
    os.makedirs(CARD_OUT_DIR, exist_ok=True)
    for n in ("card_01.jpg", "card_02.jpg", "card_03.jpg", "card_04.jpg", "card_05.jpg"):
        p = os.path.join(CARD_OUT_DIR, n)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    raw_articles = fetch_news_articles(hours_back=24, limit=20)
    lead = raw_articles[0] if raw_articles else {}
    image_url = str(lead.get("urlToImage", ""))
    titles = [
        "오늘 시장을 흔든 이슈",
        "유가가 다시 움직인 이유",
        "비트코인이 반응한 구간",
        "금리가 만든 부담",
        "다음 시장 체크포인트",
    ]
    tags = ["OIL", "OIL", "BTC", "RATE", "US STOCK"]

    card_paths = build_simple_news_card_set(
        out_dir=CARD_OUT_DIR,
        image_url=image_url,
        titles=titles,
        tags=tags,
        source_label="JADONNAM",
    )
    for p in card_paths:
        print(f"[simple_news_card] output check: {p} exists={os.path.exists(p)}")

    if ENABLE_TELEGRAM_STORAGE and send_storage_media_group is not None:
        send_storage_media_group(card_paths)
        print("[simple_news_card] 저장 채널 카드 5장 전송 완료")
    else:
        print("[simple_news_card] 저장 채널 전송 생략")

    print("[simple_news_card] caption/reel/instagram upload disabled")
    mark_regular_sent()


def post_card_news_v2() -> None:
    os.makedirs(CARD_OUT_DIR, exist_ok=True)
    raw_articles = fetch_news_articles(hours_back=24, limit=30)
    top = raw_articles[0] if raw_articles else {}
    img = str(top.get("urlToImage", ""))
    cards = [
        {
            "headline": "오늘 시장을 흔든 이슈",
            "tag": "OIL",
            "image_url": img,
            "prompt": "Reuters/Bloomberg documentary realism, cinematic financial news photograph, strong subject, vertical composition, no text, no watermark, no logo.",
        },
        {
            "headline": "유가가 다시 움직인 이유",
            "tag": "OIL",
            "image_url": img,
            "prompt": "Oil market financial news scene, Reuters style realism, strong subject, vertical composition, no text, no watermark, no logo.",
        },
        {
            "headline": "비트코인이 반응한 구간",
            "tag": "BTC",
            "image_url": img,
            "prompt": "Crypto market documentary realism, financial news mood, cinematic high contrast, strong subject, no text, no watermark, no logo.",
        },
        {
            "headline": "금리가 만든 부담",
            "tag": "RATE",
            "image_url": img,
            "prompt": "Interest-rate financial news photo, macro newsroom realism, cinematic high contrast, strong subject, no text, no watermark, no logo.",
        },
        {
            "headline": "다음 시장 체크포인트",
            "tag": "US STOCK",
            "image_url": img,
            "prompt": "US stock market documentary realism, business editorial, strong subject, vertical composition, no text, no watermark, no logo.",
        },
    ]
    ordered_card_paths = build_jadonnam_signature_cards(CARD_OUT_DIR, cards)

    expected_files = ordered_card_paths
    for path in expected_files:
        exists = os.path.exists(path)
        print(f"[card_news_v2] output check: {path} exists={exists}")

    if ENABLE_TELEGRAM_STORAGE:
        if send_storage_media_group is not None:
            send_storage_media_group(ordered_card_paths)
            print("[카드뉴스 v2] 저장 채널 카드 5장 전송 완료")
        else:
            print("[카드뉴스 v2] send_storage_media_group 미사용(모듈 없음)")
    else:
        print("[카드뉴스 v2] ENABLE_TELEGRAM_STORAGE=false, 저장 채널 전송 생략")

    print("[카드뉴스 v2] 릴스 자동화 비활성화")
    print("[카드뉴스 v2] 인스타 자동업로드 비활성화")
    mark_regular_sent()


def _topic_symbol(topic_slug: str) -> str:
    mapping = {
        "bitcoin": "BTC",
        "ai": "NVDA",
        "semiconductor": "NVDA",
        "big_tech": "AAPL",
        "tna": "TSLA",
        "rates": "SPY",
        "cpi": "SPY",
        "us_stocks": "SPY",
        "etf": "QQQ",
        "market_rank": "QQQ",
    }
    return mapping.get(topic_slug, "SPY")


def post_market_fact_content() -> None:
    os.makedirs(MARKET_FACT_OUT_DIR, exist_ok=True)
    # Remove old artifacts first to avoid stale outputs.
    for name in ("card_01.jpg", "card_02.jpg", "card_03.jpg", "card_04.jpg", "card_05.jpg"):
        p = os.path.join(MARKET_FACT_OUT_DIR, name)
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"[market_fact] removed stale file: {p}")
            except Exception as e:
                print(f"[market_fact] stale file remove failed: {p} err={repr(e)}")

    raw_articles = fetch_news_articles(hours_back=24, limit=40)
    topic = pick_single_topic()
    topic_title = str(topic.get("title", "오늘 시장 핵심"))
    topic_slug = str(topic.get("slug", "market_fact"))

    image_urls: List[str] = []
    for article in raw_articles:
        u = str(article.get("urlToImage", "")).strip()
        if u and u not in image_urls:
            image_urls.append(u)
        if len(image_urls) >= 5:
            break

    bullets = [
        f"{str(topic.get('category', '시장'))} 핵심 포인트",
        "오늘 자금이 가장 먼저 반응한 구간",
        "수급·심리·변동성에서 동시에 확인",
        "내일 장 시작 전 체크할 기준점",
        "한 줄 결론: 저장 후 비교",
    ]

    rank_rows = []
    for idx, it in enumerate(build_market_rank_items(build_news_rank_items(), build_poly_rank_items())[:10], start=1):
        rank_rows.append({"symbol": "QQQ", "label": it.get("label", f"자산 {idx}"), "value": f"{it.get('score', 0)}%"})

    card_paths = [
        render_stock_study_template(company_name_kr="엔비디아", ticker="NVDA", rank_text="#1", out_path=os.path.join(MARKET_FACT_OUT_DIR, "card_01.jpg")),
        render_ranking_template("ETF 수익률 TOP10", rank_rows, out_path=os.path.join(MARKET_FACT_OUT_DIR, "card_02.jpg")),
        render_ranking_template("반도체 수익률 TOP10", rank_rows, out_path=os.path.join(MARKET_FACT_OUT_DIR, "card_03.jpg")),
        render_ranking_template("AI 기업 비교 TOP10", rank_rows, out_path=os.path.join(MARKET_FACT_OUT_DIR, "card_04.jpg")),
        render_stock_study_template(company_name_kr="저장하고 내일 재확인", ticker="NVDA", rank_text="#SAVE", out_path=os.path.join(MARKET_FACT_OUT_DIR, "card_05.jpg")),
    ]

    expected_files = card_paths
    for path in expected_files:
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else -1
        mtime = os.path.getmtime(path) if exists else -1
        print(f"[market_fact] output check: {path} exists={exists} size={size} mtime={mtime}")

    if ENABLE_TELEGRAM_STORAGE:
        if send_storage_media_group is not None:
            send_storage_media_group(card_paths)
            print("[market_fact] 저장 채널 카드 5장 전송 완료")
        else:
            print("[market_fact] send_storage_media_group 미사용(모듈 없음)")
    else:
        print("[market_fact] ENABLE_TELEGRAM_STORAGE=false, 저장 채널 전송 생략")

    print("[market_fact] 릴스 자동화 비활성화")
    print("[market_fact] 인스타 자동업로드 비활성화")
    mark_regular_sent()


def _breaking_news_score(article: Dict[str, Any]) -> int:
    try:
        return news_module.score_breaking_article(article)
    except Exception:
        return 0


def _breaking_poly_score(question: str, volume: Any, yes_price: Any) -> int:
    score = _poly_score(question, volume, yes_price)
    if _contains(question, ["ceasefire", "attack", "war", "hormuz", "oil", "bitcoin", "fed"]):
        score += 10
    return min(score, 100)


def post_breaking() -> None:
    print("[속보] 운영 비활성화")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    if CARD_NEWS_MODE:
        os.makedirs(CARD_OUT_DIR, exist_ok=True)
        os.makedirs(MARKET_FACT_OUT_DIR, exist_ok=True)
    if STATIC_REEL_MODE:
        os.makedirs(STATIC_REEL_OUT_DIR, exist_ok=True)

    print(f"[mode] CARD_NEWS_MODE={str(CARD_NEWS_MODE).lower()}")
    print(f"[mode] USE_REEL_STORY_V2={str(USE_REEL_STORY_V2).lower()}")
    print(f"[mode] CONTENT_MODE={CONTENT_MODE}")
    print(f"[mode] STATIC_REEL_MODE={str(STATIC_REEL_MODE).lower()}")
    print(f"[mode] STATIC_REEL_FORMAT={STATIC_REEL_FORMAT}")
    print(f"[mode] DEFAULT_STOCK_TICKER={DEFAULT_STOCK_TICKER}")
    print(f"[mode] ENABLE_OPENAI_STATIC_IMAGE={str(ENABLE_OPENAI_STATIC_IMAGE).lower()}")
    print(f"[mode] FORCE_REGENERATE_STATIC_BG={str(FORCE_REGENERATE_STATIC_BG).lower()}")
    print(f"[mode] resolved content mode={resolve_content_mode()}")
    print(f"[mode] selected pipeline={selected_pipeline_name()}")

    print(
        "[debug schedule]",
        "FORCE_REGULAR_NOW=", FORCE_REGULAR_NOW,
        "current_regular_slot()=", current_regular_slot(),
        "should_run_regular_post()=", should_run_regular_post(),
        "already_sent_regular()=", already_sent_regular(),
    )
    if FORCE_REGULAR_NOW:
        print("[안내] FORCE_REGULAR_NOW 테스트 후 Railway 환경변수를 false로 원복하세요")

    # 속보 체크
    if DRY_RUN_PIPELINE:
        print("[비용절약] DRY_RUN_PIPELINE=true, 속보 검사 생략")
    elif SKIP_BREAKING_CHECK:
        print("[비용절약] SKIP_BREAKING_CHECK=true, 속보 검사 생략")
    else:
        try:
            post_breaking()
        except Exception as e:
            print("[속보 처리 오류]", repr(e))

    # 정규 업로드 (08:10 / 19:10 KST)
    try:
        print("[정규 업로드 체크 시작]")
        if should_run_regular_post():
            if already_sent_regular():
                print("[정규 업로드 스킵] 이미 전송됨")
            else:
                print("[정규 업로드 실행]")
                post_regular_rank_cards()
        else:
            print("[정규 업로드 시간 아님]")
    except Exception as e:
        print("[정규 업로드 오류]", repr(e))
        raise

    # 스레드 중간 포스팅 (09 / 13 / 17 / 21시)
    try:
        target_hour = should_run_threads_midday()
        if target_hour is not None:
            print(f"[스레드 중간 포스팅] {target_hour}시 실행")
            run_threads_midday(target_hour)
        else:
            print("[스레드 중간 포스팅 시간 아님]")
    except Exception as e:
        print("[스레드 중간 포스팅 오류]", repr(e))


if __name__ == "__main__":
    print("main_instagram loaded")
    main()
