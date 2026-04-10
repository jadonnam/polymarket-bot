
import json
import os
import re
from datetime import datetime, timedelta, timezone

from telegram_new import send_image, send_media_group
from rank_card_v3 import create_rank_set
from card_v3 import create_breaking_image
from prompt_bank_v3 import breaking_headline

import news as news_module
from polymarket import get_polymarket_markets
from instagram_v2 import upload_instagram

REGULAR_STATE_FILE = "regular_rank_state.json"
BREAKING_STATE_FILE = "breaking_state.json"

REGULAR_POST_MINUTE_WINDOW = 90
BREAKING_COOLDOWN_MINUTES = 720

BREAKING_NEWS_MIN_SCORE = 88
BREAKING_POLY_MIN_SCORE = 92

USE_INSTAGRAM_FOR_BREAKING = os.getenv("USE_INSTAGRAM_FOR_BREAKING", "true").lower() == "true"
OUT_DIR = "output_rank"

def now_kst():
    return datetime.now(timezone.utc) + timedelta(hours=9)

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

def current_regular_slot():
    now = now_kst()
    total = now.hour * 60 + now.minute
    morning_start = 8 * 60
    evening_start = 19 * 60

    if morning_start <= total < morning_start + REGULAR_POST_MINUTE_WINDOW:
        return "morning"
    if evening_start <= total < evening_start + REGULAR_POST_MINUTE_WINDOW:
        return "evening"
    return None

def should_run_regular_post():
    return current_regular_slot() is not None

def load_regular_state():
    return load_json_file(REGULAR_STATE_FILE, {"last_morning_date": "", "last_evening_date": ""})

def save_regular_state(data):
    save_json_file(REGULAR_STATE_FILE, data)

def already_sent_regular():
    state = load_regular_state()
    today = now_kst().strftime("%Y-%m-%d")
    slot = current_regular_slot()
    if slot == "morning":
        return state.get("last_morning_date") == today
    if slot == "evening":
        return state.get("last_evening_date") == today
    return False

def mark_regular_sent():
    state = load_regular_state()
    today = now_kst().strftime("%Y-%m-%d")
    slot = current_regular_slot()

    if slot == "morning":
        state["last_morning_date"] = today
    elif slot == "evening":
        state["last_evening_date"] = today

    save_regular_state(state)

def load_breaking_state():
    return load_json_file(BREAKING_STATE_FILE, {"items": []})

def save_breaking_state(state):
    state["items"] = state.get("items", [])[-100:]
    save_json_file(BREAKING_STATE_FILE, state)

def was_recent_breaking(key):
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

def mark_breaking_posted(key, title):
    state = load_breaking_state()
    state["items"].append({
        "key": key,
        "title": title,
        "ts": now_kst().isoformat(timespec="seconds"),
    })
    save_breaking_state(state)

def _contains(text, words):
    t = str(text).lower()
    return any(w in t for w in words)

def _clean_short(text, limit=22):
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit].strip()

def _smart_label(title):
    t = str(title)

    if _contains(t, ["환율", "달러", "usd", "won", "fx"]):
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        return f"환율 {m.group(1)}원" if m else "환율 급등"

    if _contains(t, ["유가", "oil", "wti", "crude", "brent"]):
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        return f"유가 {m.group(1)}달러" if m else "유가 급등"

    if _contains(t, ["bitcoin", "btc", "비트"]):
        return "비트 변동성"

    if _contains(t, ["ethereum", "eth", "이더"]):
        return "이더 변동성"

    if _contains(t, ["금리", "fed", "cpi", "inflation", "yield"]):
        return "금리 압박"

    if _contains(t, ["trump", "트럼프", "tariff", "관세"]):
        return "트럼프 관세"

    if _contains(t, ["iran", "israel", "war", "attack", "전쟁", "이란", "이스라엘", "공습", "비행기", "격추"]):
        return "중동 긴장"

    return _clean_short(t, 18)

def _news_score(title, desc=""):
    text = f"{title} {desc}".lower()
    score = 25

    if _contains(text, ["환율", "usd", "fx", "달러", "won"]):
        score += 28
    if _contains(text, ["oil", "wti", "crude", "brent", "유가"]):
        score += 26
    if _contains(text, ["war", "attack", "missile", "전쟁", "공습", "이란", "israel", "iran", "비행기", "격추"]):
        score += 28
    if _contains(text, ["fed", "cpi", "inflation", "yield", "금리", "물가"]):
        score += 20
    if _contains(text, ["bitcoin", "btc", "eth", "ethereum", "비트", "코인"]):
        score += 18
    if re.search(r"\d", text):
        score += 8

    return min(score, 100)

def _poly_score(question, volume, yes_price):
    text = str(question).lower()
    score = 20

    try:
        v = float(volume)
    except Exception:
        v = 0.0

    try:
        p = float(yes_price)
    except Exception:
        p = 0.5

    if v >= 20_000_000:
        score += 40
    elif v >= 10_000_000:
        score += 32
    elif v >= 5_000_000:
        score += 24
    elif v >= 1_000_000:
        score += 14

    if p >= 0.90 or p <= 0.10:
        score += 18
    elif p >= 0.80 or p <= 0.20:
        score += 10

    if _contains(text, ["oil", "wti", "crude", "유가", "dollar", "달러", "fx", "환율"]):
        score += 12
    if _contains(text, ["war", "attack", "iran", "israel", "전쟁", "이란", "비행기", "격추"]):
        score += 14
    if _contains(text, ["btc", "bitcoin", "비트", "eth", "ethereum"]):
        score += 10

    return min(score, 100)

def fetch_news_top5():
    items = []

    if hasattr(news_module, "get_news_candidates"):
        try:
            raw = news_module.get_news_candidates(limit=25)
            for a in raw or []:
                items.append({"title": a.get("title", ""), "desc": a.get("description", "") or a.get("summary", "")})
        except Exception:
            pass

    if not items and hasattr(news_module, "fetch_news"):
        try:
            raw = news_module.fetch_news(limit=25)
            for a in raw or []:
                items.append({"title": a.get("title", ""), "desc": a.get("description", "") or a.get("summary", "")})
        except Exception:
            pass

    if not items and hasattr(news_module, "get_news_candidate"):
        try:
            a = news_module.get_news_candidate()
            if a:
                items.append({"title": a.get("title", ""), "desc": a.get("description", "") or a.get("summary", "")})
        except Exception:
            pass

    ranked = []
    for a in items:
        title = a.get("title", "").strip()
        desc = a.get("desc", "").strip()
        if not title:
            continue
        ranked.append({
            "title": _smart_label(title),
            "score": _news_score(title, desc),
            "raw_title": title,
            "raw_desc": desc,
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)

    dedup = []
    seen = set()
    for it in ranked:
        if it["title"] in seen:
            continue
        seen.add(it["title"])
        dedup.append(it)
        if len(dedup) >= 5:
            break
    return dedup

def fetch_poly_top5():
    ranked = []
    try:
        markets = get_polymarket_markets(limit=120)
    except Exception:
        markets = []

    seen = set()
    for m in markets:
        q = m.get("question", "").strip()
        if not q:
            continue
        label = _smart_label(q)
        if label in seen:
            continue
        seen.add(label)

        ranked.append({
            "title": label,
            "score": _poly_score(q, m.get("volume", 0), m.get("yes_price", 0.5)),
            "raw_title": q,
            "volume": m.get("volume", 0),
            "yes_price": m.get("yes_price", 0.5),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:5]

def choose_breaking_candidate(news_top, poly_top):
    news_best = news_top[0] if news_top else None
    poly_best = poly_top[0] if poly_top else None

    candidates = []

    if news_best and news_best["score"] >= BREAKING_NEWS_MIN_SCORE:
        if _contains(news_best["raw_title"], ["전쟁", "공습", "이란", "이스라엘", "환율", "유가", "금리", "트럼프", "관세", "비행기", "격추", "war", "attack", "iran", "oil", "fx", "usd"]):
            candidates.append({
                "source": "news",
                "score": news_best["score"],
                "raw_title": news_best["raw_title"],
                "title": breaking_headline(news_best["raw_title"]),
            })

    if poly_best and poly_best["score"] >= BREAKING_POLY_MIN_SCORE:
        q = poly_best["raw_title"]
        if _contains(q, ["war", "attack", "iran", "israel", "oil", "fx", "dollar", "환율", "유가", "전쟁", "이란", "비행기", "격추"]):
            candidates.append({
                "source": "polymarket",
                "score": poly_best["score"],
                "raw_title": q,
                "title": breaking_headline(q),
            })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    winner = candidates[0]
    key = winner["raw_title"].strip().lower()
    if was_recent_breaking(key):
        return None
    return winner

def post_breaking(candidate):
    image_path = create_breaking_image(candidate["raw_title"], out_path="output_breaking.png")
    caption = f"[속보]\n\n{candidate['title']}".strip()

    send_image(image_path, caption=caption)
    if USE_INSTAGRAM_FOR_BREAKING:
        upload_instagram(image_path, caption)

    mark_breaking_posted(candidate["raw_title"].strip().lower(), candidate["raw_title"])

def send_regular_rank_cards(news_top, poly_top):
    slot = current_regular_slot()
    header = "아침 핵심 이슈" if slot == "morning" else "오늘 핵심 이슈"

    os.makedirs(OUT_DIR, exist_ok=True)
    paths = create_rank_set(news_items=news_top, poly_items=poly_top, out_dir=OUT_DIR, watermark="jadonnam")

    caption = f"[{header}]\n\n2~4페이지 자동 카드".strip()
    send_media_group(paths, caption=caption)
    mark_regular_sent()

def main():
    print(f"[스케줄] 현재 시각(KST): {now_kst().isoformat(timespec='seconds')}")

    news_top = fetch_news_top5()
    poly_top = fetch_poly_top5()

    breaking = choose_breaking_candidate(news_top, poly_top)
    if breaking:
        print("[속보] 자동 게시:", breaking["title"])
        post_breaking(breaking)
        return

    if should_run_regular_post():
        if already_sent_regular():
            print("[정규] 이미 전송됨")
            return
        print("[정규] 2~4페이지 카드 전송")
        send_regular_rank_cards(news_top, poly_top)
        return

    print("[스케줄] 이번 회차 스킵")

if __name__ == "__main__":
    main()
