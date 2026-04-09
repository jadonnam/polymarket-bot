"""
card_maker_new.py — jadonnam 카드 생성기 (클린 버전)

레이아웃 개선:
- 텍스트를 하단에 배치 → 얼굴 안 가림
- 하단 데이터바 제거 (깔끔)
- LIVE 뱃지 제거
- 캐러셀 점 제거
- 상단: 브랜드 + 토픽칩만
- 하단: 아이브로 → 제목1 → 제목2 → desc
"""

from PIL import Image, ImageDraw, ImageFont
import os
from datetime import datetime

SIZE = (1080, 1350)
W, H = SIZE

BOLD_FONT = os.path.join("fonts", "Pretendard-Bold.ttf")
REG_FONT  = os.path.join("fonts", "Pretendard-Regular.ttf")

WHITE      = (255, 255, 255)
GRAY_LIGHT = (220, 225, 235)
GRAY_MID   = (160, 170, 185)

ACCENTS = {
    "gold":          (247, 196, 48),
    "neon_gold":     (255, 210, 40),
    "orange":        (255, 138, 48),
    "hot_red":       (255, 60,  60),
    "electric_blue": (68,  195, 255),
    "blue":          (100, 175, 255),
    "green":         (80,  220, 130),
    "red":           (255, 80,  80),
}

# ── 레이아웃 상수 ────────────────────────────────────────
MARGIN_L   = 68
BRAND_Y    = 68       # 상단 브랜드
CHIP_Y     = 112      # 토픽 칩

# 텍스트 블록 — 하단 영역에 집중
EYEBROW_Y  = 780      # 아이브로 시작
TITLE1_Y   = 840      # 제목1
# 제목2, desc는 TITLE1_Y 기준으로 동적 계산

TITLE_MAX_W = 900     # 텍스트 최대 너비 (넓게)
DESC_MAX_W  = 900

OUTPUT_DIR = "output"


def get_font(path, size):
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fit_font(draw, text, path, start, minimum, max_w):
    size = start
    while size >= minimum:
        font = get_font(path, size)
        bbox = draw.textbbox((0, 0), text, font=font)
        if (bbox[2] - bbox[0]) <= max_w:
            return font
        size -= 2
    return get_font(path, minimum)


def fit_rich_font(draw, parts, path, start, minimum, max_w):
    size = start
    while size >= minimum:
        font = get_font(path, size)
        total = 0
        for t, _ in parts:
            if t:
                b = draw.textbbox((0, 0), t, font=font)
                total += b[2] - b[0]
        if total <= max_w:
            return font
        size -= 2
    return get_font(path, minimum)


def draw_rich(draw, x, y, parts, font):
    cx = x
    for text, color in parts:
        if not text:
            continue
        # 그림자
        draw.text((cx + 2, y + 2), text, font=font, fill=(0, 0, 0, 160))
        draw.text((cx, y), text, font=font, fill=color)
        bbox = draw.textbbox((cx, y), text, font=font)
        cx = bbox[2]


def make_overlay(size):
    """하단 강한 그라디언트 오버레이 — 텍스트 가독성"""
    w, h = size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # 전체 약한 어둠
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 25))
    overlay = Image.alpha_composite(overlay, dark)

    # 하단 2/3 강한 그라디언트
    bottom = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bottom)
    grad_start = int(h * 0.35)
    for i in range(h - grad_start):
        alpha = int(210 * (i / (h - grad_start)) ** 1.4)
        alpha = min(alpha, 210)
        bd.line([(0, grad_start + i), (w, grad_start + i)], fill=(0, 0, 0, alpha))
    overlay = Image.alpha_composite(overlay, bottom)

    # 상단 약한 그라디언트 (브랜드바)
    top = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    for i in range(140):
        alpha = int(90 * (1 - i / 140))
        td.line([(0, i), (w, i)], fill=(0, 0, 0, alpha))
    overlay = Image.alpha_composite(overlay, top)

    return overlay


def draw_chip(draw, x, y, text, accent_color):
    font = get_font(BOLD_FONT, 28)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    pad_x, pad_y = 22, 10

    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + th + pad_y * 2),
        radius=24,
        fill=(10, 12, 20, 200)
    )
    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + th + pad_y * 2),
        radius=24,
        outline=accent_color,
        width=2
    )
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=accent_color)


def split_highlight(text, accent_color):
    import re
    if not text:
        return [(text, WHITE)]

    pattern = r'[\$₩]?[\d,]+\.?\d*\s?(?:억원|억|만원|만|원|달러|%|배|bp|K)?'
    matches = list(re.finditer(pattern, text))

    if not matches:
        return [(text, WHITE)]

    parts = []
    last = 0
    for m in matches:
        s, e = m.span()
        if not m.group().strip():
            continue
        if s > last:
            parts.append((text[last:s], WHITE))
        parts.append((text[s:e], accent_color))
        last = e
    if last < len(text):
        parts.append((text[last:], WHITE))

    return parts if parts else [(text, WHITE)]


def make_card(
    eyebrow,
    title1_parts,
    title2_parts,
    desc_lines,
    brand_text="jadonnam",
    topic_label="MARKET",
    mode="normal",
    accent="gold",
    subtone="white",
    data_bar=None,      # 사용 안 함 (하위 호환)
    card_index=0,
    total_cards=1,
):
    if not os.path.exists("bg.jpg"):
        raise RuntimeError("bg.jpg 없음")

    accent_color = ACCENTS.get(accent, ACCENTS["gold"])

    # ── 배경 로드 ──────────────────────────────────────────
    bg = Image.open("bg.jpg").convert("RGB")
    tw, th = SIZE
    iw, ih = bg.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    bg = bg.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top  = (nh - th) // 2
    bg = bg.crop((left, top, left + tw, top + th))

    bg_rgba = bg.convert("RGBA")
    overlay = make_overlay(SIZE)
    bg_rgba = Image.alpha_composite(bg_rgba, overlay)

    draw = ImageDraw.Draw(bg_rgba)

    # ── 상단: 브랜드 + 토픽 칩만 ──────────────────────────
    font_brand = get_font(REG_FONT, 32)
    draw.text((MARGIN_L, BRAND_Y), brand_text, font=font_brand, fill=GRAY_LIGHT)
    draw_chip(draw, MARGIN_L, CHIP_Y, topic_label, accent_color)

    # ── 하단 텍스트 블록 ───────────────────────────────────
    # 아이브로
    cur_y = EYEBROW_Y
    if eyebrow:
        font_eyebrow = fit_font(draw, eyebrow, BOLD_FONT, 36, 24, TITLE_MAX_W)
        draw.text((MARGIN_L + 2, cur_y + 2), eyebrow, font=font_eyebrow, fill=(0, 0, 0, 140))
        draw.text((MARGIN_L, cur_y), eyebrow, font=font_eyebrow, fill=accent_color)
        eb = draw.textbbox((0, 0), eyebrow, font=font_eyebrow)
        cur_y += (eb[3] - eb[1]) + 20

    # 제목1
    font_t1 = fit_rich_font(draw, title1_parts, BOLD_FONT, 100, 64, TITLE_MAX_W)
    draw_rich(draw, MARGIN_L, cur_y, title1_parts, font_t1)
    t1b = draw.textbbox((0, 0), "가", font=font_t1)
    cur_y += (t1b[3] - t1b[1]) + 12

    # 제목2
    font_t2 = fit_rich_font(draw, title2_parts, BOLD_FONT, 88, 58, TITLE_MAX_W)
    draw_rich(draw, MARGIN_L, cur_y, title2_parts, font_t2)
    t2b = draw.textbbox((0, 0), "가", font=font_t2)
    cur_y += (t2b[3] - t2b[1]) + 36

    # desc 라인
    for i, line in enumerate(desc_lines[:2]):
        if not line:
            continue
        font_desc = fit_font(draw, line, REG_FONT, 40, 28, DESC_MAX_W)
        draw.text((MARGIN_L + 2, cur_y + 2), line, font=font_desc, fill=(0, 0, 0, 100))
        draw.text((MARGIN_L, cur_y), line, font=font_desc, fill=GRAY_LIGHT)
        db = draw.textbbox((0, 0), line, font=font_desc)
        cur_y += (db[3] - db[1]) + 14

        if cur_y > H - 60:
            break

    # ── 저장 ──────────────────────────────────────────────
    result = bg_rgba.convert("RGB")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%m%d_%H%M%S")
    suffix = f"_c{card_index}" if total_cards > 1 else ""
    out_path = os.path.join(OUTPUT_DIR, f"card_{ts}{suffix}.png")
    result.save(out_path, quality=95)
    print(f"saved: {out_path}")
    return out_path


def make_carousel_set(rewritten, mode="normal", bg_paths=None):
    if bg_paths is None:
        bg_paths = ["bg.jpg", "bg.jpg", "bg.jpg"]

    import shutil
    accent = rewritten.get("accent", "gold")
    accent_color = ACCENTS.get(accent, ACCENTS["gold"])
    topic = rewritten.get("topic", "MARKET")
    paths = []

    # ── 카드 1: 메인 훅 ───────────────────────────────────
    if os.path.exists(bg_paths[0]):
        shutil.copy(bg_paths[0], "bg.jpg")

    p1 = make_card(
        eyebrow=rewritten.get("eyebrow", ""),
        title1_parts=split_highlight(rewritten["title1"], accent_color),
        title2_parts=[(rewritten["title2"], WHITE)],
        desc_lines=[rewritten["desc1"], rewritten["desc2"]],
        brand_text="jadonnam",
        topic_label=topic,
        mode=mode,
        accent=accent,
        card_index=0,
        total_cards=3,
    )
    paths.append(p1)

    # ── 카드 2: 맥락 카드 ──────────────────────────────────
    if os.path.exists(bg_paths[1]):
        shutil.copy(bg_paths[1], "bg.jpg")

    p2 = make_card(
        eyebrow="이게 핵심이다",
        title1_parts=split_highlight(rewritten.get("card2_title1", "지금 숫자 보면"), accent_color),
        title2_parts=[(rewritten.get("card2_title2", "이 숫자가 왜 중요한지 보인다"), WHITE)],
        desc_lines=[rewritten["desc1"], rewritten["desc2"]],
        brand_text="jadonnam",
        topic_label=topic,
        mode=mode,
        accent=accent,
        card_index=1,
        total_cards=3,
    )
    paths.append(p2)

    # ── 카드 3: CTA 카드 ───────────────────────────────────
    if os.path.exists(bg_paths[2]):
        shutil.copy(bg_paths[2], "bg.jpg")

    p3 = make_card(
        eyebrow=rewritten.get("card3_hook", "결국 이 흐름은"),
        title1_parts=[(rewritten.get("card3_title", "내 지갑과 연결된다"), WHITE)],
        title2_parts=[("→ 저장하고 흐름 보기", accent_color)],
        desc_lines=[
            rewritten.get("card3_desc1", "핵심 숫자를 계속 비교해보는 편이 좋다"),
            rewritten.get("card3_desc2", "저장해두면 다음 이슈와 연결해서 보기 쉽다"),
        ],
        brand_text="jadonnam",
        topic_label=topic,
        mode=mode,
        accent=accent,
        card_index=2,
        total_cards=3,
    )
    paths.append(p3)

    return paths
