import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import news as news_module
from polymarket import get_polymarket_markets
from price_data import get_oil_price, get_btc_price, get_gold_price, get_usd_krw
from rank_card_v3 import create_rank_set
from telegram_new import send_image, send_media_group
from card_v3 import create_breaking_image
from prompt_bank_v3 import breaking_headline
from instagram_v2 import upload_instagram

REGULAR_STATE_FILE = "regular_rank_state.json"
BREAKING_STATE_FILE = "breaking_state.json"
REGULAR_POST_MINUTE_WINDOW = 90
BREAKING_COOLDOWN_MINUTES = 720
BREAKING_NEWS_MIN_SCORE = 88
BREAKING_POLY_MIN_SCORE = 92
USE_INSTAGRAM_FOR_BREAKING = os.getenv("USE_INSTAGRAM_FOR_BREAKING", "true").lower() == "true"
OUT_DIR = "output_rank"
TOP_N = 5


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
    if 8 * 60 <= total < 8 * 60 + REGULAR_POST_MINUTE_WINDOW:
        return "morning"
    if 19 * 60 <= total < 19 * 60 + REGULAR_POST_MINUTE_WINDOW:
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


def _clean(text, limit=18):
    text = str(text).strip()
    text = re.sub(r"\s+", " ", text)
    return text[:limit].strip()


def _smart_label(title):
    t = str(title)
    if _contains(t, ["strait of hormuz", "hormuz", "호르무즈"]):
        return "호르무즈 긴장"
    if _contains(t, ["환율", "달러", "usd", "won", "fx"]):
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        return f"환율 {m.group(1)}원" if m else "환율 급등"
    if _contains(t, ["유가", "oil", "wti", "crude", "brent"]):
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        return f"유가 {m.group(1)}달러" if m else "유가 상승"
    if _contains(t, ["bitcoin", "btc", "비트"]):
        return "비트 변동성"
    if _contains(t, ["ethereum", "eth", "이더"]):
        return "이더 변동성"
    if _contains(t, ["금리", "fed", "cpi", "inflation", "yield"]):
        return "금리 압박"
    if _contains(t, ["gold", "금"]):
        return "금값 반응"
    if _contains(t, ["trump", "트럼프", "tariff", "관세"]):
        return "트럼프 관세"
    if _contains(t, ["iran", "israel", "war", "attack", "전쟁", "이란", "이스라엘", "공습", "missile"]):
        return "중동 긴장"
    return _clean(t, 14)


def _published_recent(article, hours=14):
    candidates = [article.get("publishedAt"), article.get("published_at"), article.get("pubDate")]
    cutoff = now_kst() - timedelta(hours=hours)
    for raw in candidates:
        if not raw:
            continue
        text = str(raw).strip()
        try:
            if text.endswith("Z"):
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(text)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            dt_kst = dt.astimezone(timezone(timedelta(hours=9)))
            return dt_kst >= cutoff
        except Exception:
            continue
    return True


def _news_score(title, desc=""):
    text = f"{title} {desc}".lower()
    score = 24
    if _contains(text, ["환율", "usd", "fx", "달러", "won"]):
        score += 24
    if _contains(text, ["oil", "wti", "crude", "brent", "유가"]):
        score += 26
    if _contains(text, ["war", "attack", "missile", "전쟁", "공습", "이란", "israel", "iran", "호르무즈"]):
        score += 28
    if _contains(text, ["fed", "cpi", "inflation", "yield", "금리", "물가"]):
        score += 22
    if _contains(text, ["bitcoin", "btc", "eth", "ethereum", "비트", "코인"]):
        score += 18
    if _contains(text, ["gold", "금"]):
        score += 14
    if _contains(text, ["trump", "관세", "tariff"]):
        score += 14
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

    dist = abs(p - 0.5)
    if dist >= 0.40:
        score += 18
    elif dist >= 0.25:
        score += 10

    if _contains(text, ["strait of hormuz", "hormuz", "호르무즈"]):
        score += 14
    if _contains(text, ["oil", "wti", "crude", "유가", "dollar", "달러", "fx", "환율"]):
        score += 12
    if _contains(text, ["war", "attack", "iran", "israel", "전쟁", "이란", "missile"]):
        score += 14
    if _contains(text, ["btc", "bitcoin", "비트", "eth", "ethereum"]):
        score += 10
    return min(score, 100)


def _meta_news(desc):
    text = str(desc).strip()
    if not text:
        return "최근 기사 흐름 반영"
    text = re.sub(r"\s+", " ", text)
    return text[:44] + ("…" if len(text) > 44 else "")


def _money_short(v: float):
    if v >= 100_000_000:
        return f"${v/100_000_000:.1f}억"
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"${v/1_000:.0f}K"
    return f"${v:.0f}"


def fetch_news_top5():
    items = []
    raw = []

    if hasattr(news_module, "get_news_candidates"):
        try:
            raw = news_module.get_news_candidates(limit=40)
        except TypeError:
            try:
                raw = news_module.get_news_candidates()
            except Exception:
                raw = []
        except Exception:
            raw = []

    if not raw and hasattr(news_module, "fetch_news"):
        try:
            raw = news_module.fetch_news(limit=40)
        except TypeError:
            try:
                raw = news_module.fetch_news()
            except Exception:
                raw = []
        except Exception:
            raw = []

    ranked = []
    for a in raw or []:
        title = str(a.get("title", "")).strip()
        desc = str(a.get("description", "") or a.get("summary", "")).strip()
        if not title:
            continue
        if not _published_recent(a, hours=14):
            continue
        ranked.append({
            "title": _smart_label(title),
            "score": _news_score(title, desc),
            "raw_title": title,
            "meta": _meta_news(desc),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    dedup, seen = [], set()
    for it in ranked:
        key = it["title"]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(it)
        if len(dedup) >= TOP_N:
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
        q = str(m.get("question", "")).strip()
        if not q:
            continue
        label = _smart_label(q)
        if label in seen:
            continue
        seen.add(label)
        volume = m.get("volume", 0)
        yes_price = m.get("yes_price", 0.5)
        try:
            meta = f"확률 {int(round(float(yes_price) * 100))}% · 거래 { _money_short(float(volume)) }"
        except Exception:
            meta = "확률/거래대금 반영"
        ranked.append({
            "title": label,
            "score": _poly_score(q, volume, yes_price),
            "raw_title": q,
            "meta": meta,
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:TOP_N]


def build_market_top5(news_top: List[Dict], poly_top: List[Dict]):
    topic_strength = {
        "유가 상승 압력": 0,
        "환율 변동성": 0,
        "비트 반응": 0,
        "금값 반응": 0,
        "금리 압박": 0,
        "중동 리스크": 0,
    }

    for item in news_top:
        t = item.get("title", "")
        s = int(item.get("score", 0))
        if _contains(t, ["유가"]):
            topic_strength["유가 상승 압력"] += s
        if _contains(t, ["환율", "달러"]):
            topic_strength["환율 변동성"] += s
        if _contains(t, ["비트", "이더"]):
            topic_strength["비트 반응"] += s
        if _contains(t, ["금값", "금"]):
            topic_strength["금값 반응"] += s
        if _contains(t, ["금리", "cpi", "fed"]):
            topic_strength["금리 압박"] += s
        if _contains(t, ["중동", "호르무즈"]):
            topic_strength["중동 리스크"] += s

    for item in poly_top:
        t = item.get("title", "")
        s = int(item.get("score", 0))
        if _contains(t, ["유가", "호르무즈"]):
            topic_strength["유가 상승 압력"] += s
        if _contains(t, ["환율", "달러"]):
            topic_strength["환율 변동성"] += s
        if _contains(t, ["비트", "이더"]):
            topic_strength["비트 반응"] += s
        if _contains(t, ["금값", "금"]):
            topic_strength["금값 반응"] += s
        if _contains(t, ["금리"]):
            topic_strength["금리 압박"] += s
        if _contains(t, ["중동", "호르무즈"]):
            topic_strength["중동 리스크"] += s

    market_items = []
    oil = get_oil_price()
    fx = get_usd_krw()
    btc = get_btc_price()
    gold = get_gold_price()

    source_meta = {
        "유가 상승 압력": f"WTI {oil:.2f}달러" if oil else "에너지 이슈 반영",
        "환율 변동성": f"USD/KRW {fx:.1f}" if fx else "환율 이슈 반영",
        "비트 반응": f"BTC ${btc:,}" if btc else "코인 민감도 반영",
        "금값 반응": f"금 {gold:.2f}달러" if gold else "안전자산 반영",
        "금리 압박": "금리·물가 기사 민감도",
        "중동 리스크": "전쟁/호르무즈 이슈 반영",
    }

    for title, raw_score in topic_strength.items():
        if raw_score <= 0:
            continue
        score = min(100, max(38, int(round(raw_score / 2.2))))
        market_items.append({
            "title": title,
            "score": score,
            "meta": source_meta.get(title, "시장 반응 반영"),
        })

    market_items.sort(key=lambda x: x["score"], reverse=True)
    return market_items[:TOP_N]


def choose_breaking_candidate(news_top, poly_top):
    candidates = []
    if news_top:
        best = news_top[0]
        if best["score"] >= BREAKING_NEWS_MIN_SCORE:
            candidates.append({
                "source": "news",
                "score": best["score"],
                "raw_title": best["raw_title"],
                "title": breaking_headline(best["raw_title"]),
            })
    if poly_top:
        best = poly_top[0]
        if best["score"] >= BREAKING_POLY_MIN_SCORE:
            candidates.append({
                "source": "polymarket",
                "score": best["score"],
                "raw_title": best["raw_title"],
                "title": breaking_headline(best["raw_title"]),
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


def send_regular_rank_cards(news_top, poly_top, market_top):
    slot = current_regular_slot()
    header = "아침 핵심 이슈" if slot == "morning" else "저녁 핵심 이슈"
    os.makedirs(OUT_DIR, exist_ok=True)
    paths = create_rank_set(news_items=news_top, poly_items=poly_top, market_items=market_top, out_dir=OUT_DIR)
    send_media_group(paths, caption=f"[{header}]\n\n뉴스 / 폴리마켓 / 시장 반응 TOP5")
    mark_regular_sent()


def main():
    print(f"[스케줄] 현재 시각(KST): {now_kst().isoformat(timespec='seconds')}")
    news_top = fetch_news_top5()
    poly_top = fetch_poly_top5()
    market_top = build_market_top5(news_top, poly_top)

    breaking = choose_breaking_candidate(news_top, poly_top)
    if breaking:
        print("[속보] 자동 게시:", breaking["title"])
        post_breaking(breaking)
        return

    if should_run_regular_post():
        if already_sent_regular():
            print("[정규] 이미 전송됨")
            return
        print("[정규] 랭킹 카드 3장 전송")
        send_regular_rank_cards(news_top, poly_top, market_top)
        return

    print("[스케줄] 이번 회차 스킵")


if __name__ == "__main__":
    main()
