from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import news as news_module
from config import CHECK_INTERVAL
from content_topics_v1 import pick_single_topic
from card_news_v2 import build_card_news_v2
from card_v3 import create_breaking_image
from market_fact_cards import build_market_fact_cards
from news_template import build_jadonnam_signature_cards
from rank_card_v3 import create_rank_set
from ranking_template import render_ranking_template
from stock_study_template import render_stock_study_template
from daily_summary_card import (
    build_daily_summary_payload_auto,
    fetch_market_data_bundle,
    write_debug_payload_json,
)
from telegram_curation import build_market_briefing_text

try:
    from content_dispatcher import (
        send_storage_image,
        send_storage_message,
        send_storage_text,
        send_storage_video,
    )
except Exception:
    send_storage_image = None
    send_storage_message = None
    send_storage_text = None
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
BRIEF_OUT_DIR = "output_briefing"
MARKET_FACT_OUT_DIR = "output_marketfact"
STATIC_REEL_OUT_DIR = "output_static_reel"
TELEGRAM_CARD_OUT_DIR = "output_telegram_card"

REGULAR_POST_MINUTE_WINDOW = int((os.getenv("REGULAR_POST_MINUTE_WINDOW") or "120").strip())
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
ENABLE_OPENAI_CARD_IMAGE = (os.getenv("ENABLE_OPENAI_CARD_IMAGE") or "false").lower() == "true"
FORCE_CARD_TEST = (os.getenv("FORCE_CARD_TEST") or "false").lower() == "true"
TEXT_BRIEFING_ONLY = (os.getenv("TEXT_BRIEFING_ONLY") or "true").lower() == "true"
TELEGRAM_SINGLE_CARD = (os.getenv("TELEGRAM_SINGLE_CARD") or "true").lower() == "true"
NEWS_API_KEY_SET = bool((os.getenv("NEWS_API_KEY") or "").strip())
OFF_SCHEDULE_ISSUE_ENABLED = (os.getenv("OFF_SCHEDULE_ISSUE_ENABLED") or "true").lower() == "true"
OFF_SCHEDULE_MIN_SCORE = int((os.getenv("OFF_SCHEDULE_MIN_SCORE") or "58").strip())
OFF_SCHEDULE_COOLDOWN_MINUTES = int((os.getenv("OFF_SCHEDULE_COOLDOWN_MINUTES") or "40").strip())
CARD_SEND_DEDUP_HOURS = int((os.getenv("CARD_SEND_DEDUP_HOURS") or "20").strip())
TELEGRAM_CARD_SEND_STATE_FILE = "telegram_card_send_state.json"
# true: 아침/저녁 슬롯 무시, 뉴스 신호(점수+쿨다운+URL중복)만으로 카드/텍스트 전송
SIGNAL_DRIVEN_SEND = (os.getenv("SIGNAL_DRIVEN_SEND") or "true").lower() == "true"

# 스레드 중간 포스팅 시간 (KST 시간 기준)
THREADS_MIDDAY_HOURS = [9, 13, 17, 21]

_BRIEFING_ENGINE_MODES = (
    "korea_close",
    "us_preopen",
    "macro_issue",
    "company_focus",
    "sector_focus",
)


def now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def selected_pipeline_name() -> str:
    # TEXT_BRIEFING_ONLY는 CARD_NEWS_MODE와 무관하게 최우선 적용
    if TEXT_BRIEFING_ONLY:
        return "telegram_single_card" if TELEGRAM_SINGLE_CARD else "text_market_briefing"
    if STATIC_REEL_MODE:
        return "disabled_static_reel"
    if CARD_NEWS_MODE:
        return "jadonnam_money_carousel"
    return "card_news_only"


def resolve_content_mode() -> str:
    raw = (CONTENT_MODE or "").strip().lower()
    if raw in _BRIEFING_ENGINE_MODES:
        return raw
    if raw in ("market_fact", "briefing"):
        return raw
    if raw == "auto":
        if SIGNAL_DRIVEN_SEND:
            return "briefing"
        slot = current_regular_slot()
        if slot == "morning":
            return "briefing"
        if slot == "evening":
            return "market_fact"
    return "briefing"


def effective_briefing_summary_mode() -> str:
    """
    daily_summary_card / 텍스트 브리핑이 이해하는 모드 키로 정규화.
    - SIGNAL_DRIVEN_SEND: 슬롯 무시, 엔진 키·briefing/market_fact만 반영(기본 톤 macro_issue)
    - 그 외: 기존 KST 슬롯 기반 매핑
    """
    raw = (CONTENT_MODE or "").strip().lower()
    if raw in _BRIEFING_ENGINE_MODES:
        return raw
    if SIGNAL_DRIVEN_SEND:
        if raw == "market_fact":
            return "sector_focus"
        if raw == "briefing":
            return "macro_issue"
        resolved = resolve_content_mode()
        if resolved == "market_fact":
            return "sector_focus"
        return "macro_issue"
    resolved = resolve_content_mode()
    if resolved == "market_fact":
        return "sector_focus"
    slot = current_regular_slot()
    if slot == "evening":
        return "korea_close"
    return "us_preopen"


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


def _regular_slot_schedule_hint() -> str:
    """스킵 로그용 — KST 기준 슬롯 구간(환경변수 REGULAR_POST_MINUTE_WINDOW 반영)."""

    def mm(m: int) -> str:
        return f"{m // 60:02d}:{m % 60:02d}"

    w = REGULAR_POST_MINUTE_WINDOW
    nk = now_kst()
    ms, me = REGULAR_MORNING_MINUTE, REGULAR_MORNING_MINUTE + w
    es, ee = REGULAR_EVENING_MINUTE, REGULAR_EVENING_MINUTE + w
    return (
        f"now_kst={nk.strftime('%m-%d %H:%M')} "
        f"morning_kst={mm(ms)}-{mm(me)} "
        f"evening_kst={mm(es)}-{mm(ee)} "
        f"window={w}m"
    )


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


def _telegram_card_dedup_key(article: Dict[str, Any]) -> str:
    u = str(article.get("url") or "").strip()
    if u.lower().startswith("https://"):
        return u
    t = news_module.clean_spaces(article.get("title", "") or "").encode("utf-8", errors="ignore")
    return "title:" + hashlib.md5(t).hexdigest()


def load_telegram_card_send_state() -> Dict[str, Any]:
    return _load_json(TELEGRAM_CARD_SEND_STATE_FILE, {"url_sends": [], "off_schedule_sends": []})


def save_telegram_card_send_state(data: Dict[str, Any]) -> None:
    data["url_sends"] = (data.get("url_sends") or [])[-120:]
    data["off_schedule_sends"] = (data.get("off_schedule_sends") or [])[-60:]
    _save_json(TELEGRAM_CARD_SEND_STATE_FILE, data)


def _parse_kst_ts(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone(timedelta(hours=9)))
        return dt
    except Exception:
        return None


def record_telegram_card_sent(article: Optional[Dict[str, Any]], off_schedule: bool) -> None:
    if not article:
        return
    key = _telegram_card_dedup_key(article)
    now = now_kst()
    st = load_telegram_card_send_state()
    st.setdefault("url_sends", []).append({"key": key, "ts": now.isoformat(timespec="seconds")})
    if off_schedule:
        st.setdefault("off_schedule_sends", []).append({"ts": now.isoformat(timespec="seconds")})
    save_telegram_card_send_state(st)


def should_allow_off_schedule_issue(score: int, article: Dict[str, Any]) -> bool:
    if score < OFF_SCHEDULE_MIN_SCORE:
        return False
    key = _telegram_card_dedup_key(article)
    now = now_kst()
    cutoff_dup = now - timedelta(hours=CARD_SEND_DEDUP_HOURS)
    cutoff_cd = now - timedelta(minutes=OFF_SCHEDULE_COOLDOWN_MINUTES)
    st = load_telegram_card_send_state()
    for row in st.get("url_sends", []) or []:
        ts = _parse_kst_ts(str(row.get("ts") or ""))
        if ts is None or ts < cutoff_dup:
            continue
        if row.get("key") == key:
            print(
                f"[off_schedule_issue] skip: 동일 기사 URL {CARD_SEND_DEDUP_HOURS}h 이내 재전송 방지"
            )
            return False
    for row in st.get("off_schedule_sends", []) or []:
        ts = _parse_kst_ts(str(row.get("ts") or ""))
        if ts is None:
            continue
        if ts >= cutoff_cd:
            print(
                f"[off_schedule_issue] skip: 오프슬롯 전송 쿨다운 "
                f"{OFF_SCHEDULE_COOLDOWN_MINUTES}분 이내"
            )
            return False
    short_key = key[:72] + ("…" if len(key) > 72 else "")
    print(
        f"[off_schedule_issue] 트리거: score={score} (min={OFF_SCHEDULE_MIN_SCORE}) {short_key}"
    )
    return True


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
    print(f"[selected_pipeline] {selected_pipeline_name()}")
    if STATIC_REEL_MODE:
        print("[static_reel] disabled by policy: focus on saved card news")
        return

    if CARD_NEWS_MODE:
        print("[mode] daily single summary card enabled")
        if TEXT_BRIEFING_ONLY:
            run_text_market_briefing_only()
        else:
            post_simple_news_cards()
        return

    # Non-card-news mode is intentionally disabled.
    print("[policy] CARD_NEWS_MODE=false 경로 비활성화")
    mark_regular_sent()


def _log_final_card_size(path: str) -> None:
    if not os.path.exists(path):
        print(f"[final_card] path={path} size=missing")
        return
    n = os.path.getsize(path)
    kb = n / 1024.0
    label = f"{kb:.0f}kb" if kb >= 100 else f"{kb:.1f}kb"
    base = os.path.basename(path)
    print(f"[final_card] {base} size={label}")


def _briefing_fetch_build_write_send(
    *,
    delivery: str,
) -> Tuple[Any, str, List[Dict[str, Any]], Dict[str, Any], bool]:
    """Fetch, build briefing text, write files, send Telegram. No carousel, no mark_regular_sent."""
    os.makedirs(BRIEF_OUT_DIR, exist_ok=True)
    raw_articles = fetch_news_articles(hours_back=24, limit=24)
    try:
        market_data = fetch_market_data_bundle()
    except Exception as e:
        print(f"[market_data] bundle fetch exception: {repr(e)}")
        market_data = {
            "quotes": {},
            "korea": {},
            "trading_top5": ["거래대금 TOP: 데이터 수집 중", "상위 종목: 반도체/AI 중심"],
            "sector_top5": ["AI·반도체", "에너지", "전력 인프라", "빅테크", "방산·원자재"],
            "data_source_status": {"_bundle": "exception -> fallback"},
        }
    rank_items = build_news_rank_items()
    rank_labels = [str(x.get("label", "")).strip() for x in rank_items[:4] if x.get("label")]

    summary_mode = effective_briefing_summary_mode()
    cm = (CONTENT_MODE or "").strip().lower()
    tail = ""
    if cm not in _BRIEFING_ENGINE_MODES:
        tail = f", resolved={resolve_content_mode()!r}"
    print(f"[market_briefing] content_mode={summary_mode} (CONTENT_MODE={CONTENT_MODE!r}{tail})")
    payload = build_daily_summary_payload_auto(
        articles=raw_articles,
        rank_labels=rank_labels,
        date_line=generated_at_text(),
        content_mode=summary_mode,
        market_data=market_data,
    )
    caption_text = build_market_briefing_text(summary_mode, payload, market_data, raw_articles)
    caption_path = os.path.join(BRIEF_OUT_DIR, "market_briefing.txt")
    debug_path = os.path.join(BRIEF_OUT_DIR, "debug_payload.json")

    try:
        os.makedirs(BRIEF_OUT_DIR, exist_ok=True)
        with open(caption_path, "w", encoding="utf-8") as f:
            f.write(caption_text)
        print(f"[briefing_text] wrote {caption_path}")
    except Exception as e:
        print(f"[briefing_text] write failed: {repr(e)}")

    write_debug_payload_json(
        debug_path,
        content_mode=summary_mode,
        payload=payload,
        caption=caption_text,
        market_data=market_data,
        extra_fields={
            "delivery": delivery,
            "TEXT_BRIEFING_ONLY": TEXT_BRIEFING_ONLY,
            "briefing_path": caption_path,
        },
    )

    try:
        print(f"[briefing_text] chars={len(caption_text)}")
        print(f"[market_briefing] out_briefing={caption_path}")
        print(f"[market_briefing] out_debug={debug_path}")
    except Exception as e:
        print(f"[market_briefing] log failed: {repr(e)}")

    cp_ok = os.path.exists(caption_path)
    if cp_ok:
        print(f"[briefing_text] bytes={os.path.getsize(caption_path)}")

    send_txt = send_storage_text or send_storage_message
    sent_ok = False
    if ENABLE_TELEGRAM_STORAGE:
        if send_txt is not None and caption_text:
            try:
                chunk = 3800
                for i in range(0, len(caption_text), chunk):
                    send_txt(caption_text[i : i + chunk])
                print("[telegram_storage_send] text ok")
                sent_ok = True
            except Exception as e:
                print(f"[telegram_storage_send] text failed: {repr(e)}")
        elif send_txt is None:
            print("[telegram_storage_send] send_storage_text 없음")
    else:
        print("[market_briefing] ENABLE_TELEGRAM_STORAGE=false 전송 생략")

    return summary_mode, payload, raw_articles, market_data, sent_ok


def run_text_market_briefing_only() -> None:
    """TEXT_BRIEFING_ONLY 전용: 텍스트 브리핑만 (carousel/card/money_flow 미호출)."""
    print("[briefing_only] hard skip carousel pipeline")
    print("[briefing_only] no image generation")
    print("[briefing_only] no card rendering")
    print("[selected_pipeline] text_market_briefing")
    *_, sent_ok = _briefing_fetch_build_write_send(delivery="text_market_briefing")
    if sent_ok:
        print("[briefing_only] send text only")
    if not FORCE_CARD_TEST and not SIGNAL_DRIVEN_SEND:
        mark_regular_sent()
    else:
        print("[card_test] mark_regular_sent 스킵 (FORCE_CARD_TEST)")


def post_simple_news_cards() -> None:
    """Carousel 경로. TEXT_BRIEFING_ONLY일 때는 호출되면 안 됨(방어적 no-op)."""
    if TEXT_BRIEFING_ONLY:
        print("[briefing_only] post_simple_news_cards 호출 차단 (TEXT_BRIEFING_ONLY=true)")
        return

    print("[briefing_only] disabled (carousel pipeline)")
    os.makedirs(CARD_OUT_DIR, exist_ok=True)
    for n in (
        "card_01.jpg",
        "card_02.jpg",
        "card_03.jpg",
        "card_04.jpg",
        "card_05.jpg",
        "daily_summary_card.jpg",
        "page1.jpg",
        "page2.jpg",
        "page3.jpg",
        "page4.jpg",
        "carousel_preview.jpg",
        "caption.txt",
        "debug_payload.json",
    ):
        p = os.path.join(CARD_OUT_DIR, n)
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    summary_mode, payload, raw_articles, market_data, _sent_ok = _briefing_fetch_build_write_send(
        delivery="jadonnam_money_carousel",
    )

    try:
        from money_flow_card_system import generate_money_flow_carousel

        from daily_summary_card import background_keywords_for_mode

        generate_money_flow_carousel(
            CARD_OUT_DIR,
            payload,
            raw_articles,
            summary_mode,
            preferred_keywords=background_keywords_for_mode(summary_mode),
            market_data=market_data,
        )
        print("[carousel] money_flow_card_system 로컬 JPG 생성")
    except Exception as e:
        print(f"[carousel] money_flow optional run failed: {repr(e)}")
    if not FORCE_CARD_TEST:
        mark_regular_sent()
    else:
        print("[card_test] mark_regular_sent 스킵 (FORCE_CARD_TEST)")


def post_card_news_v2() -> None:
    if TEXT_BRIEFING_ONLY:
        print("[briefing_only] post_card_news_v2 호출 차단 (TEXT_BRIEFING_ONLY=true)")
        return
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
        print("[briefing_only] skipped card v2 storage image send (텍스트 전용 정책)")
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
    if TEXT_BRIEFING_ONLY:
        print("[briefing_only] post_market_fact_content 호출 차단 (TEXT_BRIEFING_ONLY=true)")
        return
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
        print("[briefing_only] skipped market_fact storage image send (텍스트 전용 정책)")
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
    if TEXT_BRIEFING_ONLY and TELEGRAM_SINGLE_CARD:
        os.makedirs(TELEGRAM_CARD_OUT_DIR, exist_ok=True)
    if CARD_NEWS_MODE:
        os.makedirs(BRIEF_OUT_DIR, exist_ok=True)
        if not TEXT_BRIEFING_ONLY:
            os.makedirs(CARD_OUT_DIR, exist_ok=True)
            os.makedirs(MARKET_FACT_OUT_DIR, exist_ok=True)
    if STATIC_REEL_MODE:
        os.makedirs(STATIC_REEL_OUT_DIR, exist_ok=True)

    print(f"[env] TEXT_BRIEFING_ONLY={str(TEXT_BRIEFING_ONLY).lower()}")
    print(f"[env] TELEGRAM_SINGLE_CARD={str(TELEGRAM_SINGLE_CARD).lower()}")
    print(
        f"[env] TELEGRAM_CARD_USE_NEWS_IMAGE="
        f"{str((os.getenv('TELEGRAM_CARD_USE_NEWS_IMAGE') or 'false').lower() == 'true').lower()}"
    )
    _ct = (os.getenv("CARD_TEMPLATE") or "photo").strip().lower()
    if _ct not in ("photo", "badge", "quote"):
        _ct = "photo"
    print(f"[env] CARD_TEMPLATE={_ct}")
    print(f"[env] NEWS_API_KEY={'set' if NEWS_API_KEY_SET else 'missing'}")
    print(f"[env] FORCE_CARD_TEST={str(FORCE_CARD_TEST).lower()}")
    print(f"[env] CONTENT_MODE={CONTENT_MODE}")
    print(f"[env] SIGNAL_DRIVEN_SEND={str(SIGNAL_DRIVEN_SEND).lower()}")

    print(f"[mode] CARD_NEWS_MODE={str(CARD_NEWS_MODE).lower()}")
    print(f"[mode] USE_REEL_STORY_V2={str(USE_REEL_STORY_V2).lower()}")
    print(f"[mode] CONTENT_MODE={CONTENT_MODE}")
    print(f"[mode] STATIC_REEL_MODE={str(STATIC_REEL_MODE).lower()}")
    print(f"[mode] STATIC_REEL_FORMAT={STATIC_REEL_FORMAT}")
    print(f"[mode] DEFAULT_STOCK_TICKER={DEFAULT_STOCK_TICKER}")
    print(f"[mode] ENABLE_OPENAI_STATIC_IMAGE={str(ENABLE_OPENAI_STATIC_IMAGE).lower()}")
    print(f"[mode] ENABLE_OPENAI_CARD_IMAGE={str(ENABLE_OPENAI_CARD_IMAGE).lower()}")
    print(f"[mode] FORCE_CARD_TEST={str(FORCE_CARD_TEST).lower()}")
    print(f"[mode] TEXT_BRIEFING_ONLY={str(TEXT_BRIEFING_ONLY).lower()}")
    print(f"[mode] FORCE_REGENERATE_STATIC_BG={str(FORCE_REGENERATE_STATIC_BG).lower()}")
    print(f"[mode] resolved content mode={resolve_content_mode()}")
    print(f"[mode] effective briefing engine mode={effective_briefing_summary_mode()}")
    print(f"[mode] selected pipeline={selected_pipeline_name()}")
    print(f"[selected_pipeline] {selected_pipeline_name()}")

    # TEXT_BRIEFING_ONLY는 CARD_NEWS_MODE와 무관하게 최우선 실행 후 즉시 return
    if TEXT_BRIEFING_ONLY:
        print("[briefing_only] enabled")
        try:
            from telegram_single_card import (
                best_single_card_candidate,
                best_single_card_candidate_relaxed,
            )

            slot_active = should_run_regular_post()
            cached_arts: Optional[List[Dict[str, Any]]] = None
            issue_signal = False
            issue_off_schedule = False
            iss_score = -1
            iss_cand: Optional[Dict[str, Any]] = None

            if SIGNAL_DRIVEN_SEND:
                if OFF_SCHEDULE_ISSUE_ENABLED and not FORCE_CARD_TEST:
                    cached_arts = fetch_news_articles(hours_back=36, limit=40)
                    iss_score, iss_cand = best_single_card_candidate(cached_arts)
                    if iss_cand is None:
                        iss_score, iss_cand = best_single_card_candidate_relaxed(
                            cached_arts
                        )
                    if iss_cand is not None and should_allow_off_schedule_issue(
                        iss_score, iss_cand
                    ):
                        issue_signal = True
                        issue_off_schedule = True
                should_send_text = FORCE_CARD_TEST or issue_signal
            else:
                if (
                    TELEGRAM_SINGLE_CARD
                    and OFF_SCHEDULE_ISSUE_ENABLED
                    and not FORCE_CARD_TEST
                    and not slot_active
                ):
                    cached_arts = fetch_news_articles(hours_back=36, limit=40)
                    iss_score, iss_cand = best_single_card_candidate(cached_arts)
                    if iss_cand is not None and should_allow_off_schedule_issue(
                        iss_score, iss_cand
                    ):
                        issue_off_schedule = True
                should_send_text = (
                    FORCE_CARD_TEST or slot_active or issue_off_schedule
                )

            if not should_send_text:
                if SIGNAL_DRIVEN_SEND:
                    print(
                        "[briefing_only] skip send: "
                        "신호 없음 또는 차단(점수·쿨다운·URL중복 / "
                        "OFF_SCHEDULE_ISSUE_ENABLED=false) "
                        f"| min_score={OFF_SCHEDULE_MIN_SCORE} "
                        f"cooldown_m={OFF_SCHEDULE_COOLDOWN_MINUTES} "
                        f"best_score={iss_score}"
                    )
                else:
                    print(
                        "[briefing_only] skip send: "
                        "정규 슬롯 아님 · 오프슬롯 이슈 트리거 없음 "
                        "(FORCE_CARD_TEST=false, OFF_SCHEDULE_ISSUE_ENABLED="
                        f"{str(OFF_SCHEDULE_ISSUE_ENABLED).lower()}, "
                        f"min_score={OFF_SCHEDULE_MIN_SCORE}) "
                        f"| {_regular_slot_schedule_hint()}"
                    )
            record_off_schedule = (SIGNAL_DRIVEN_SEND and issue_signal) or (
                not SIGNAL_DRIVEN_SEND and issue_off_schedule
            )

            if should_send_text:
                allow_send = False
                if FORCE_CARD_TEST:
                    allow_send = True
                elif SIGNAL_DRIVEN_SEND:
                    allow_send = issue_signal
                elif slot_active:
                    allow_send = not already_sent_regular()
                elif issue_off_schedule:
                    allow_send = True

                if allow_send:
                    if TELEGRAM_SINGLE_CARD:
                        from telegram_single_card import (
                            build_telegram_caption,
                            run_telegram_single_card,
                        )

                        print("[market_briefing] content_mode=single_trusted_news")
                        arts = (
                            cached_arts
                            if cached_arts is not None
                            else fetch_news_articles(hours_back=36, limit=40)
                        )
                        card_path, picked = run_telegram_single_card(
                            articles=arts,
                            out_dir=TELEGRAM_CARD_OUT_DIR,
                        )
                        if (
                            card_path
                            and picked
                            and ENABLE_TELEGRAM_STORAGE
                            and send_storage_image is not None
                        ):
                            try:
                                send_storage_image(
                                    card_path,
                                    build_telegram_caption(picked),
                                )
                                print("[telegram_storage_send] photo ok")
                                print("[briefing_only] send single card only")
                                if not FORCE_CARD_TEST:
                                    if not SIGNAL_DRIVEN_SEND and slot_active:
                                        mark_regular_sent()
                                    if picked:
                                        record_telegram_card_sent(
                                            picked,
                                            off_schedule=record_off_schedule,
                                        )
                            except Exception as e:
                                print(f"[telegram_single_card] send_storage_image failed: {repr(e)}")
                                *_ignore, sent_ok = _briefing_fetch_build_write_send(
                                    delivery="text_market_briefing"
                                )
                                if sent_ok:
                                    print("[telegram_storage_send] text ok")
                                    print("[briefing_only] send text only")
                                    if not FORCE_CARD_TEST:
                                        if not SIGNAL_DRIVEN_SEND and slot_active:
                                            mark_regular_sent()
                                        if picked:
                                            record_telegram_card_sent(
                                                picked,
                                                off_schedule=record_off_schedule,
                                            )
                        else:
                            if not card_path or not picked:
                                print(
                                    "[telegram_single_card] 카드 생성 불가 — 텍스트 브리핑으로 대체"
                                )
                            elif not ENABLE_TELEGRAM_STORAGE:
                                print(
                                    "[telegram_single_card] ENABLE_TELEGRAM_STORAGE=false 전송 생략"
                                )
                            elif send_storage_image is None:
                                print(
                                    "[telegram_single_card] send_storage_image 없음 — 텍스트 브리핑으로 대체"
                                )
                            *_ignore, sent_ok = _briefing_fetch_build_write_send(
                                delivery="text_market_briefing"
                            )
                            if sent_ok:
                                print("[telegram_storage_send] text ok")
                                print("[briefing_only] send text only")
                                if not FORCE_CARD_TEST:
                                    if not SIGNAL_DRIVEN_SEND and slot_active:
                                        mark_regular_sent()
                                    if picked:
                                        record_telegram_card_sent(
                                            picked,
                                            off_schedule=record_off_schedule,
                                        )
                    else:
                        *_ignore, sent_ok = _briefing_fetch_build_write_send(
                            delivery="text_market_briefing"
                        )
                        if sent_ok:
                            print("[telegram_storage_send] text ok")
                            print("[briefing_only] send text only")
                            if not FORCE_CARD_TEST:
                                if not SIGNAL_DRIVEN_SEND and slot_active:
                                    mark_regular_sent()
                else:
                    print(
                        "[briefing_only] skip send: "
                        "이미 오늘 정규 슬롯 전송됨 (regular_rank_state.json)"
                    )
            return
        except Exception as e:
            print("[briefing_only] text briefing failed:", repr(e))
            return

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

    # 정규 업로드 (08:10 / 19:10 KST) + 카드 즉시 테스트
    try:
        print("[정규 업로드 체크 시작]")
        if CARD_NEWS_MODE and FORCE_CARD_TEST:
            print("[card_test] FORCE_CARD_TEST=true — 슬롯 무시, CONTENT_MODE 기준 즉시 실행")
            post_simple_news_cards()
        elif should_run_regular_post():
            if already_sent_regular():
                print("[정규 업로드 스킵] 이미 전송됨")
            else:
                print("[정규 업로드 실행]")
                post_regular_rank_cards()
        else:
            print("[정규 업로드 시간 아님]")
    except Exception as e:
        # 카드/정규 경로 실패 시에도 워커는 계속 (스레드 등 후속 플로우 유지)
        print("[정규 업로드 오류]", repr(e))

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


def _sleep_until_next_cycle(seconds: int, stop_state: dict) -> None:
    remaining = max(1, seconds)
    while remaining > 0 and not stop_state["stop"]:
        step = min(30, remaining)
        time.sleep(step)
        remaining -= step


if __name__ == "__main__":
    stop_state: dict = {"stop": False}

    def _handle_stop(*_args):
        stop_state["stop"] = True
        print("[worker] stop signal received")

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    print("main_instagram loaded")
    print(f"[worker] loop CHECK_INTERVAL={CHECK_INTERVAL}s")
    while not stop_state["stop"]:
        try:
            main()
        except Exception as e:
            print("[worker] main() error:", repr(e))
        if stop_state["stop"]:
            break
        _sleep_until_next_cycle(CHECK_INTERVAL, stop_state)
