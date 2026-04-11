from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import news as news_module
from card_v3 import create_breaking_image
from content_dispatcher import send_image, send_media_group, send_message, send_video
from polymarket import get_polymarket_markets
from rank_card_v3 import create_rank_set
from reels_maker_final import build_reel
from reels_packager import build_content_pack

try:
    from instagram_v2 import upload_instagram  # type: ignore
except Exception:
    upload_instagram = None

REGULAR_STATE_FILE = "regular_rank_state.json"
BREAKING_STATE_FILE = "breaking_state.json"
SCORE_HISTORY_FILE = "score_history.json"
OUT_DIR = "output_rank"

REGULAR_POST_MINUTE_WINDOW = 90
BREAKING_COOLDOWN_MINUTES = 720
BREAKING_NEWS_MIN_SCORE = 108
BREAKING_POLY_MIN_SCORE = 92
USE_INSTAGRAM_FOR_BREAKING = (os.getenv("USE_INSTAGRAM_FOR_BREAKING") or "false").lower() == "true"
FORCE_REGULAR_NOW = (os.getenv("FORCE_REGULAR_NOW") or "false").lower() == "true"


def now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


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
    if 8 * 60 <= total < 8 * 60 + REGULAR_POST_MINUTE_WINDOW:
        return "morning"
    if 19 * 60 <= total < 19 * 60 + REGULAR_POST_MINUTE_WINDOW:
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
        end_kst = now.replace(hour=8, minute=0, second=0, microsecond=0)
        start_kst = (end_kst - timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)
    if slot == "evening":
        end_kst = now.replace(hour=19, minute=0, second=0, microsecond=0)
        start_kst = now.replace(hour=8, minute=0, second=0, microsecond=0)
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
    t = str(title)
    if _contains(t, ["strait of hormuz", "hormuz", "호르무즈"]):
        return "호르무즈 변수 확대"
    if _contains(t, ["환율", "달러", "usd", "fx", "won"]):
        return "환율 변동성 확대"
    if _contains(t, ["유가", "oil", "wti", "crude", "brent"]):
        return "유가 상방 압력"
    if _contains(t, ["bitcoin", "btc", "비트"]):
        return "비트코인 강세 유지"
    if _contains(t, ["ethereum", "eth", "이더"]):
        return "이더 강세 유지"
    if _contains(t, ["금리", "fed", "cpi", "inflation", "yield"]):
        return "금리 완화 기대"
    if _contains(t, ["trump", "트럼프", "tariff", "관세"]):
        return "트럼프 변수 확대"
    if _contains(t, ["iran", "israel", "war", "attack", "전쟁", "이란", "이스라엘", "공습"]):
        return "지정학 리스크 확대"
    if _contains(t, ["gold", "금값", "금"]):
        return "안전자산 선호"
    return _clean(t)


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
    q = str(question)
    if _contains(q, ["wti", "oil", "crude", "brent", "유가"]): return "유가 상단 도전"
    if _contains(q, ["ceasefire", "휴전"]): return "휴전 베팅 확대"
    if _contains(q, ["hormuz", "호르무즈"]): return "호르무즈 정상화 기대"
    if _contains(q, ["trump", "트럼프"]): return "트럼프 변수 확대"
    if _contains(q, ["bitcoin", "btc", "비트"]): return "비트코인 상단 테스트"
    if _contains(q, ["gold", "금"]): return "금 선호 확대"
    if _contains(q, ["fed", "cpi", "inflation", "금리"]): return "금리 방향 베팅"
    return _clean(q)


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
    try:
        markets = get_polymarket_markets()
    except Exception:
        markets = []
    if not markets:
        return [
            {"label": "유가 상단 도전", "score": 83},
            {"label": "휴전 베팅 확대", "score": 80},
            {"label": "트럼프 변수 확대", "score": 76},
            {"label": "호르무즈 정상화 기대", "score": 73},
            {"label": "비트코인 상단 테스트", "score": 70},
        ]
    scored = []
    seen = set()
    for m in markets:
        q = m.get("question", "")
        label = _poly_label(q)
        if label in seen:
            continue
        seen.add(label)
        scored.append({
            "label": label,
            "score": _poly_score(q, m.get("volume24hr", m.get("volume", 0)), m.get("yes_price", 0)),
            "question": q,
            "meta": m.get("slug", ""),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    fillers = [
        {"label": "유가 상단 도전", "score": 82},
        {"label": "휴전 베팅 확대", "score": 79},
        {"label": "트럼프 변수 확대", "score": 75},
        {"label": "호르무즈 정상화 기대", "score": 72},
        {"label": "비트코인 상단 테스트", "score": 69},
    ]
    out = scored[:5]
    while len(out) < 5:
        out.append(fillers[len(out)])
    return out[:5]


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
    buckets = {"유가 상방 압력": 0, "환율 변동성 확대": 0, "비트코인 강세 유지": 0, "금 선호 강화": 0, "금리 부담 확대": 0}
    for item in news_items + poly_items:
        label, score = item["label"], item["score"]
        if _contains(label, ["유가", "호르무즈", "oil", "crude", "wti"]): buckets["유가 상방 압력"] += score
        if _contains(label, ["환율", "달러", "usd", "fx"]): buckets["환율 변동성 확대"] += score
        if _contains(label, ["비트", "btc", "코인", "crypto"]): buckets["비트코인 강세 유지"] += score
        if _contains(label, ["금", "gold", "안전자산"]): buckets["금 선호 강화"] += score
        if _contains(label, ["금리", "fed", "cpi", "yield"]): buckets["금리 부담 확대"] += score
        if _contains(label, ["전쟁", "공습", "지정학", "휴전", "이란", "이스라엘"]):
            buckets["유가 상방 압력"] += 6
            buckets["금 선호 강화"] += 6
    ranked = [{"label": k, "score": min(100, max(55, int(v / 2) if v > 0 else 55))} for k, v in buckets.items()]
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
    history = load_score_history()
    news_items = attach_deltas("news", build_news_rank_items(), history)
    poly_items = attach_deltas("poly", build_poly_rank_items(), history)
    market_items = attach_deltas("market", build_market_rank_items(news_items, poly_items), history)
    save_score_history(history)

    paths = create_rank_set(news_items, poly_items, market_items, out_dir=OUT_DIR, generated_at_text=generated_at_text())
    pack = build_content_pack(news_items, poly_items, market_items)
    reel_path = build_reel(paths[0], paths[1], paths[2], pack["reel_hook"], os.path.join(OUT_DIR, "reel_output.mp4"))

    send_media_group(paths)
    send_video(reel_path, caption=pack["reel_hook"])
    send_message(
        f"[커버 후보]\n{pack['cover_candidates']}\n\n"
        f"[피드 캡션]\n{pack['feed_caption']}\n\n"
        f"[릴스 캡션]\n{pack['reel_caption']}\n\n"
        f"[해시태그]\n{pack['hashtags']}\n\n"
        f"[CTA]\n{pack['cta']}"
    )
    mark_regular_sent()
    print("[정규 업로드 완료]")


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
    print("[속보] 뉴스 검사 시작")
    articles = fetch_breaking_news_articles(hours_back=12, limit=20)
    best_news = None
    for art in articles:
        title = art.get("title", "") or ""
        score = _breaking_news_score(art)
        if score < BREAKING_NEWS_MIN_SCORE:
            print("[속보] 뉴스 점수 미달:", score, title[:80])
            continue
        key = f"news::{title.strip()}"
        if was_recent_breaking(key):
            print("[속보] 뉴스 중복 스킵:", title[:80])
            continue
        best_news = {"title": title, "score": score, "key": key}
        break

    if best_news:
        img_path = os.path.join(OUT_DIR, "breaking_news.jpg")
        create_breaking_image(best_news["title"], img_path)
        send_image(img_path, caption=best_news["title"])
        if USE_INSTAGRAM_FOR_BREAKING and upload_instagram is not None:
            try:
                upload_instagram(img_path, best_news["title"])
            except Exception:
                pass
        mark_breaking_posted(best_news["key"], best_news["title"])
        print("[속보 업로드 완료 - 뉴스]", best_news["title"])
    else:
        print("[속보] 뉴스 후보 없음")

    print("[속보] 폴리 검사 시작")
    try:
        markets = get_polymarket_markets()
    except Exception:
        markets = []
    best_poly = None
    for m in markets[:30]:
        q = m.get("question", "")
        score = _breaking_poly_score(q, m.get("volume24hr", m.get("volume", 0)), m.get("yes_price", 0))
        if score < BREAKING_POLY_MIN_SCORE:
            continue
        key = f"poly::{q.strip()}"
        if was_recent_breaking(key):
            print("[속보] 폴리 중복 스킵:", q[:80])
            continue
        best_poly = {"title": q, "score": score, "key": key}
        break

    if best_poly:
        img_path = os.path.join(OUT_DIR, "breaking_poly.jpg")
        create_breaking_image(best_poly["title"], img_path)
        send_image(img_path, caption=best_poly["title"])
        if USE_INSTAGRAM_FOR_BREAKING and upload_instagram is not None:
            try:
                upload_instagram(img_path, best_poly["title"])
            except Exception:
                pass
        mark_breaking_posted(best_poly["key"], best_poly["title"])
        print("[속보 업로드 완료 - 폴리마켓]", best_poly["title"])
    else:
        print("[속보] 폴리 후보 없음 또는 점수 미달")


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        post_breaking()
    except Exception as e:
        print("[속보 처리 오류]", repr(e))
    try:
        if should_run_regular_post():
            if already_sent_regular():
                print("[정규 업로드 스킵] 이미 전송됨")
            else:
                post_regular_rank_cards()
        else:
            print("[정규 업로드 시간 아님]")
    except Exception as e:
        print("[정규 업로드 오류]", repr(e))
        raise


if __name__ == "__main__":
    print("FINAL VERIFIED VERSION LOADED")
    main()
