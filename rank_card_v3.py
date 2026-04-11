import os
import re
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350

BG_TOP = (8, 12, 18)
BG_BOTTOM = (11, 16, 24)

WHITE = (244, 246, 248)
GRAY = (150, 158, 170)
GRAY_DIM = (102, 110, 122)

ACCENT_NEWS = (210, 220, 232)
ACCENT_POLY = (255, 170, 52)
ACCENT_MARKET = (62, 208, 178)

TRACK = (49, 58, 74)

PAGE_THEME = {
    "news": {"accent": ACCENT_NEWS, "footer": "NEWS", "kicker": "EDITORIAL", "subtitle": "지난 구간 핵심 이슈"},
    "poly": {"accent": ACCENT_POLY, "footer": "POLYMARKET", "kicker": "PREDICTION", "subtitle": "베팅이 몰린 흐름"},
    "market": {"accent": ACCENT_MARKET, "footer": "MARKET", "kicker": "REACTION", "subtitle": "가격이 반응한 구간"},
}

BASE_DIR = os.path.dirname(__file__)
FONT_DIR = os.path.join(BASE_DIR, "fonts")
BOLD_PATH = os.path.join(FONT_DIR, "Pretendard-Bold.ttf")
REG_PATH = os.path.join(FONT_DIR, "Pretendard-Regular.ttf")

def _font(size, bold=False):
    path = BOLD_PATH if bold else REG_PATH
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

FONT_BRAND = _font(20, False)
FONT_KICKER = _font(15, False)
FONT_TITLE = _font(78, True)
FONT_SUB = _font(21, False)
FONT_INDEX = _font(25, True)
FONT_STAR = _font(27, True)
FONT_LABEL_TOP = _font(44, True)
FONT_LABEL = _font(36, True)
FONT_SCORE_TOP = _font(52, True)
FONT_SCORE = _font(40, True)
FONT_NOTE = _font(17, False)
FONT_META = _font(16, False)
FONT_FOOT = _font(17, False)

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _clean_text(text):
    text = str(text).replace("\n", " ").strip()
    while "  " in text:
        text = text.replace("  ", " ")
    return text

def _score_to_int(score):
    try:
        return _clamp(int(round(float(score))), 0, 100)
    except Exception:
        return 0

def _text_w(draw, text, font):
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]

def _draw_text(draw, xy, text, font, fill):
    draw.text(xy, text, font=font, fill=fill)

def _trim_text(draw, text, font, max_width):
    text = _clean_text(text)
    if _text_w(draw, text, font) <= max_width:
        return text
    s = text
    while len(s) > 1:
        s = s[:-1].rstrip()
        cand = s + "…"
        if _text_w(draw, cand, font) <= max_width:
            return cand
    return "…"

def _refine_common_label(text: str) -> str:
    t = _clean_text(text)
    replacements = [
        ("급등 압박", "상방 압력"), ("급등", "강세 확대"), ("상승세", "강세 유지"),
        ("강세 지속", "강세 유지"), ("휴전 임박", "휴전 기대"), ("휴전 4월?", "휴전 기대"),
        ("정상화?", "정상화 기대"), ("돌파?", "상단 테스트"), ("도달?", "상단 도전"),
        ("논의", "기대"), ("반응", "선호 강화"), ("압박", "부담 확대"),
        ("변동성", "변동성 확대"), ("논란", "변수 확대"),
    ]
    for a, b in replacements:
        t = t.replace(a, b)
    short_rules = [
        (r"이란-미국 휴전.*", "휴전 기대 확대"),
        (r"비트코인 .*돌파.*", "비트코인 상단 테스트"),
        (r"유가 .*도달.*", "유가 상단 도전"),
        (r"호르무즈 .*정상화.*", "호르무즈 정상화 기대"),
        (r"트럼프 .*", "트럼프 변수 확대"),
        (r"달러 강세.*", "달러 강세 유지"),
        (r"금리 .*기대.*", "금리 완화 기대"),
        (r"유가 .*압력.*", "유가 상방 압력"),
        (r"환율 .*확대.*", "환율 변동성 확대"),
        (r"금값 .*", "금 선호 강화"),
        (r"금 .*선호.*", "금 선호 강화"),
    ]
    for pattern, repl in short_rules:
        if re.search(pattern, t):
            return repl
    return t

def _refine_label(text: str, page_type: str) -> str:
    t = _refine_common_label(text)
    if page_type == "news":
        rules = [
            (r".*유가.*", "유가 상방 압력"), (r".*휴전.*", "휴전 기대 확대"),
            (r".*비트.*", "비트코인 강세 유지"), (r".*달러.*", "달러 강세 유지"),
            (r".*금리.*", "금리 완화 기대"), (r".*금.*", "안전자산 선호"),
        ]
    elif page_type == "poly":
        rules = [
            (r".*유가.*", "유가 상단 도전"), (r".*휴전.*", "휴전 베팅 확대"),
            (r".*호르무즈.*", "호르무즈 정상화 기대"), (r".*트럼프.*", "트럼프 변수 확대"),
            (r".*비트.*", "비트코인 상단 테스트"),
        ]
    else:
        rules = [
            (r".*유가.*", "유가 상방 압력"), (r".*환율.*", "환율 변동성 확대"),
            (r".*비트.*", "비트코인 강세 유지"), (r".*금.*", "금 선호 강화"),
            (r".*금리.*", "금리 부담 확대"),
        ]
    for pattern, repl in rules:
        if re.search(pattern, t):
            return repl
    return t

def _hero_note(label: str, page_type: str) -> str:
    if page_type == "news":
        table = {
            "유가 상방 압력": "에너지 가격 이슈 재부각",
            "휴전 기대 확대": "지정학 완화 기대 반영",
            "비트코인 강세 유지": "위험자산 선호 재확대",
            "달러 강세 유지": "환율 부담 지속",
            "금리 완화 기대": "정책 기대 반영",
            "안전자산 선호": "방어 자산 선호 확대",
        }
    elif page_type == "poly":
        table = {
            "유가 상단 도전": "상방 시나리오 베팅 집중",
            "휴전 베팅 확대": "정치 이벤트 자금 유입",
            "호르무즈 정상화 기대": "물류 정상화 기대 반영",
            "트럼프 변수 확대": "정책 변수 베팅 확대",
            "비트코인 상단 테스트": "상단 돌파 기대 유입",
        }
    else:
        table = {
            "유가 상방 압력": "실물 체감 연결 구간",
            "환율 변동성 확대": "달러 영향 확산",
            "비트코인 강세 유지": "위험 선호 유지",
            "금 선호 강화": "안전자산 선호 증가",
            "금리 부담 확대": "고금리 부담 재부각",
        }
    return table.get(label, "이번 구간 핵심 흐름")

def _make_background():
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        r = y / H
        rr = int(BG_TOP[0] * (1 - r) + BG_BOTTOM[0] * r)
        gg = int(BG_TOP[1] * (1 - r) + BG_BOTTOM[1] * r)
        bb = int(BG_TOP[2] * (1 - r) + BG_BOTTOM[2] * r)
        d.line((0, y, W, y), fill=(rr, gg, bb))
    return img

def _draw_header(draw, title, subtitle, kicker, accent):
    _draw_text(draw, (70, 42), "JADONNAM", FONT_BRAND, GRAY)
    _draw_text(draw, (W // 2 - _text_w(draw, kicker, FONT_KICKER)//2, 124), kicker, FONT_KICKER, accent)
    title_w = _text_w(draw, title, FONT_TITLE)
    _draw_text(draw, ((W - title_w) // 2, 142), title, FONT_TITLE, WHITE)
    sub_w = _text_w(draw, subtitle, FONT_SUB)
    _draw_text(draw, ((W - sub_w) // 2, 224), subtitle, FONT_SUB, GRAY_DIM)
    draw.line((W // 2 - 50, 278, W // 2 + 50, 278), fill=accent, width=2)

def _draw_bar(draw, x, y, w, h, pct, accent):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=h // 2, fill=TRACK)
    fill_w = int(w * _clamp(pct, 0, 100) / 100)
    if fill_w > 0:
        draw.rounded_rectangle((x, y, x + fill_w, y + h), radius=h // 2, fill=accent)

def _draw_hero_importance(draw, right_x, score_text, top, accent):
    meta = "중요도"
    meta_w = _text_w(draw, meta, FONT_META)
    score_w = _text_w(draw, score_text, FONT_SCORE_TOP)
    total_w = meta_w + 10 + score_w
    start_x = right_x - total_w
    _draw_text(draw, (start_x, top + 34), meta, FONT_META, GRAY)
    _draw_text(draw, (start_x + meta_w + 10, top + 16), score_text, FONT_SCORE_TOP, accent)

def _draw_hero(draw, item, accent, page_type):
    left, right, top = 86, W - 86, 340
    _draw_text(draw, (left + 16, top + 24), "01", FONT_INDEX, GRAY)
    _draw_text(draw, (left + 58, top + 20), "★", FONT_STAR, accent)
    score_text = f"{item['score']}%"
    _draw_hero_importance(draw, right - 18, score_text, top, accent)
    label_x = left + 96
    label = _trim_text(draw, item["label"], FONT_LABEL_TOP, 490)
    _draw_text(draw, (label_x, top + 8), label, FONT_LABEL_TOP, WHITE)
    note = _trim_text(draw, _hero_note(item["label"], page_type), FONT_NOTE, 420)
    _draw_text(draw, (label_x, top + 64), note, FONT_NOTE, GRAY)
    _draw_bar(draw, label_x, top + 102, right - label_x - 16, 16, item["score"], accent)

def _draw_rows(draw, items, accent):
    left, right, label_x, start_y, row_gap = 86, W - 86, 170, 500, 156
    for idx, item in enumerate(items, start=2):
        y = start_y + (idx - 2) * row_gap
        score_text = f"{item['score']}%"
        score_x = right - _text_w(draw, score_text, FONT_SCORE)
        label = _trim_text(draw, item["label"], FONT_LABEL, score_x - label_x - 26)
        _draw_text(draw, (left, y + 2), f"{idx:02d}", FONT_INDEX, GRAY)
        _draw_text(draw, (label_x, y), label, FONT_LABEL, WHITE)
        _draw_text(draw, (score_x, y - 1), score_text, FONT_SCORE, accent)
        _draw_bar(draw, label_x, y + 58, right - label_x, 12, item["score"], accent)

def _draw_footer(draw, footer_text):
    w = _text_w(draw, footer_text, FONT_FOOT)
    _draw_text(draw, (W - 70 - w, H - 54), footer_text, FONT_FOOT, GRAY_DIM)

def _normalize_items(items, fallback_prefix, page_type):
    cleaned = []
    for i, item in enumerate(items[:5], start=1):
        if isinstance(item, dict):
            raw = item.get("label") or item.get("title") or f"{fallback_prefix} {i}"
            score = item.get("score", 0)
        else:
            raw = f"{fallback_prefix} {i}"
            score = 0
        cleaned.append({"label": _refine_label(raw, page_type), "score": _score_to_int(score)})
    while len(cleaned) < 5:
        idx = len(cleaned) + 1
        cleaned.append({"label": f"{fallback_prefix} {idx}", "score": 0})
    return cleaned

def _make_page(title, items, out_path, page_type):
    theme = PAGE_THEME[page_type]
    accent = theme["accent"]
    img = _make_background()
    draw = ImageDraw.Draw(img)
    _draw_header(draw, title, theme["subtitle"], theme["kicker"], accent)
    _draw_hero(draw, items[0], accent, page_type)
    _draw_rows(draw, items[1:], accent)
    _draw_footer(draw, theme["footer"])
    img.save(out_path, quality=95)

def create_rank_set(news, poly, market=None, out_dir="output_rank"):
    _ensure_dir(out_dir)
    news_items = _normalize_items(news, "뉴스", "news")
    poly_items = _normalize_items(poly, "폴리", "poly")
    market_items = _normalize_items(market if market is not None else [], "반응", "market")
    if market is None or len([x for x in market_items if x["score"] > 0]) == 0:
        merged, seen, dedup = [], set(), []
        for x in news_items:
            merged.append({"label": x["label"], "score": x["score"]})
        for x in poly_items:
            merged.append({"label": x["label"], "score": x["score"]})
        merged.sort(key=lambda z: z["score"], reverse=True)
        for item in merged:
            if item["label"] in seen:
                continue
            seen.add(item["label"])
            dedup.append(item)
            if len(dedup) == 5:
                break
        market_items = _normalize_items(dedup, "반응", "market")
    p1 = os.path.join(out_dir, "rank_news.jpg")
    p2 = os.path.join(out_dir, "rank_poly.jpg")
    p3 = os.path.join(out_dir, "rank_market.jpg")
    _make_page("뉴스", news_items, p1, "news")
    _make_page("폴리마켓", poly_items, p2, "poly")
    _make_page("시장 반응", market_items, p3, "market")
    return [p1, p2, p3]

if __name__ == "__main__":
    sample_news = [
        {"label": "유가 상방 압력", "score": 82},
        {"label": "휴전 기대 확대", "score": 78},
        {"label": "비트코인 강세 유지", "score": 75},
        {"label": "달러 강세 유지", "score": 72},
        {"label": "금리 완화 기대", "score": 69},
    ]
    sample_poly = [
        {"label": "유가 상단 도전", "score": 83},
        {"label": "휴전 베팅 확대", "score": 80},
        {"label": "트럼프 변수 확대", "score": 76},
        {"label": "호르무즈 정상화 기대", "score": 73},
        {"label": "비트코인 상단 테스트", "score": 70},
    ]
    sample_market = [
        {"label": "유가 상방 압력", "score": 81},
        {"label": "환율 변동성 확대", "score": 77},
        {"label": "비트코인 강세 유지", "score": 74},
        {"label": "금 선호 강화", "score": 70},
        {"label": "금리 부담 확대", "score": 67},
    ]
    print(create_rank_set(sample_news, sample_poly, sample_market))
