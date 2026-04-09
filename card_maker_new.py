"""
card_maker_new.py — jadonnam 매거진 카드 생성기 (완전 리디자인)

변경사항:
- 3단 레이아웃: 상단 브랜드바 / 중단 메인 텍스트 / 하단 데이터바
- 숫자 하이라이트 강화 (더 크고 대비 강하게)
- 카드 타입별 다른 레이아웃 (normal / alert / carousel_1~3)
- 세로 그라디언트 오버레이 개선 (좌측 어둡게 + 하단 어둡게)
- 폰트 사이즈 계층 명확화
- 브랜드 일관성: jadonnam 고정 위치
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
from datetime import datetime

# ── 캔버스 ──────────────────────────────────────────────
SIZE = (1080, 1350)
W, H = SIZE

# ── 폰트 경로 ────────────────────────────────────────────
BOLD_FONT   = os.path.join("fonts", "Pretendard-Bold.ttf")
REG_FONT    = os.path.join("fonts", "Pretendard-Regular.ttf")

# ── 컬러 시스템 ──────────────────────────────────────────
WHITE       = (255, 255, 255)
WHITE_90    = (255, 255, 255, 230)
GRAY_LIGHT  = (220, 225, 235)
GRAY_MID    = (160, 170, 185)
BLACK_CHIP  = (12, 14, 20, 220)

ACCENTS = {
    "gold":         (247, 196, 48),
    "neon_gold":    (255, 210, 40),
    "orange":       (255, 138, 48),
    "hot_red":      (255, 60,  60),
    "electric_blue":(68,  195, 255),
    "blue":         (100, 175, 255),
    "green":        (80,  220, 130),
    "red":          (255, 80,  80),
}

# ── 레이아웃 상수 ────────────────────────────────────────
MARGIN_L    = 72           # 좌측 여백
BRAND_Y     = 72           # 브랜드 텍스트 Y
CHIP_Y      = 118          # 토픽 칩 Y
EYEBROW_Y   = 210          # 아이브로 Y
TITLE1_Y    = 280          # 제목1 Y
TITLE2_Y    = 420          # 제목2 Y (가변)
DESC_Y      = 620          # 설명 영역 Y
BAR_H       = 110          # 하단 데이터바 높이
BAR_Y       = H - BAR_H    # 하단 데이터바 Y (1240)

TITLE_MAX_W = 580
DESC_MAX_W  = 560
OUTPUT_DIR  = "output"


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
        total = sum(
            draw.textbbox((0, 0), t, font=font)[2] - draw.textbbox((0, 0), t, font=font)[0]
            for t, _ in parts if t
        )
        if total <= max_w:
            return font
        size -= 2
    return get_font(path, minimum)


def draw_rich(draw, x, y, parts, font, shadow=True):
    cx = x
    for text, color in parts:
        if not text:
            continue
        if shadow:
            draw.text((cx + 3, y + 3), text, font=font, fill=(0, 0, 0, 120))
        draw.text((cx, y), text, font=font, fill=color)
        bbox = draw.textbbox((cx, y), text, font=font)
        cx = bbox[2]


def rich_width(draw, parts, font):
    return sum(
        draw.textbbox((0, 0), t, font=font)[2] - draw.textbbox((0, 0), t, font=font)[0]
        for t, _ in parts if t
    )


def make_overlay(size):
    """멀티레이어 오버레이: 좌측 + 하단 + 전체 어둡게"""
    w, h = size
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # 전체 약한 어둠
    dark = Image.new("RGBA", (w, h), (0, 0, 0, 30))
    overlay = Image.alpha_composite(overlay, dark)

    # 좌측 강한 그라디언트 (텍스트 가독성)
    grad = Image.new("L", (w, h), 0)
    px = grad.load()
    safe = int(w * 0.62)
    for x in range(w):
        alpha = int(165 * max(0, 1 - x / safe)) if x <= safe else 0
        for y in range(h):
            px[x, y] = alpha
    left_dark = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    left_dark.putalpha(grad)
    overlay = Image.alpha_composite(overlay, left_dark)

    # 하단 그라디언트 (데이터바)
    bottom = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bottom)
    for i in range(200):
        alpha = int(180 * (i / 200))
        bd.line([(0, h - i), (w, h - i)], fill=(0, 0, 0, alpha))
    overlay = Image.alpha_composite(overlay, bottom)

    # 상단 약한 그라디언트 (브랜드바)
    top = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    for i in range(160):
        alpha = int(100 * (1 - i / 160))
        td.line([(0, i), (w, i)], fill=(0, 0, 0, alpha))
    overlay = Image.alpha_composite(overlay, top)

    return overlay


def draw_chip(draw, x, y, text, accent_color):
    """토픽 칩 (배지)"""
    font = get_font(BOLD_FONT, 27)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    pad_x, pad_y = 20, 9

    # 배경
    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + (bbox[3] - bbox[1]) + pad_y * 2),
        radius=22,
        fill=(10, 12, 20, 210)
    )
    # 테두리
    draw.rounded_rectangle(
        (x, y, x + tw + pad_x * 2, y + (bbox[3] - bbox[1]) + pad_y * 2),
        radius=22,
        outline=accent_color,
        width=2
    )
    draw.text((x + pad_x, y + pad_y), text, font=font, fill=accent_color)


def draw_bottom_bar(draw, img_rgba, y, data_lines, accent_color):
    """하단 데이터바: 실시간 숫자 강조 표시"""
    # 반투명 바 배경
    bar = Image.new("RGBA", (W, BAR_H), (8, 10, 16, 200))
    img_rgba.alpha_composite(bar, dest=(0, y))

    # 구분선
    draw.line([(MARGIN_L, y + 2), (W - MARGIN_L, y + 2)], fill=(*accent_color, 80), width=1)

    font_label = get_font(REG_FONT, 28)
    font_value = get_font(BOLD_FONT, 34)

    if len(data_lines) >= 2:
        # 두 줄 정보
        label1, val1 = data_lines[0]
        label2, val2 = data_lines[1]

        draw.text((MARGIN_L, y + 18), label1, font=font_label, fill=GRAY_MID)
        draw.text((MARGIN_L, y + 52), str(val1), font=font_value, fill=WHITE)

        # 오른쪽 두번째 데이터
        label2_bbox = draw.textbbox((0, 0), str(val2), font=font_value)
        val2_w = label2_bbox[2] - label2_bbox[0]
        rx = W - MARGIN_L - val2_w

        draw.text((rx, y + 18), label2, font=font_label, fill=GRAY_MID)
        draw.text((rx, y + 52), str(val2), font=font_value, fill=accent_color)

    elif len(data_lines) == 1:
        label1, val1 = data_lines[0]
        draw.text((MARGIN_L, y + 18), label1, font=font_label, fill=GRAY_MID)
        draw.text((MARGIN_L, y + 52), str(val1), font=font_value, fill=accent_color)


def split_highlight(text, accent_color):
    """숫자/% 부분 하이라이트 처리"""
    import re
    if not text:
        return [(text, WHITE)]

    # 숫자, %, 달러, 억, 원 등 하이라이트
    pattern = r'[\$₩]?[\d,]+\.?\d*\s?(?:억원|억|만원|만|원|달러|%|배|bp|일|월|년)?'
    matches = list(re.finditer(pattern, text))

    if not matches:
        return [(text, WHITE)]

    parts = []
    last = 0
    for m in matches:
        s, e = m.span()
        if s > last:
            parts.append((text[last:s], WHITE))
        parts.append((text[s:e], accent_color))
        last = e
    if last < len(text):
        parts.append((text[last:], WHITE))

    return parts


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
    data_bar=None,       # [("거래대금", "245억"), ("확률", "72%")] 형태
    card_index=0,        # 캐러셀용 (0=단일, 1/2/3=캐러셀)
    total_cards=1,
):
    if not os.path.exists("bg.jpg"):
        raise RuntimeError("bg.jpg 없음")

    accent_color = ACCENTS.get(accent, ACCENTS["gold"])

    # 배경 로드 및 리사이즈
    bg = Image.open("bg.jpg").convert("RGB")
    # fit-cover
    tw, th = SIZE
    iw, ih = bg.size
    scale = max(tw / iw, th / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    bg = bg.resize((nw, nh), Image.LANCZOS)
    left = (nw - tw) // 2
    top = (nh - th) // 2
    bg = bg.crop((left, top, left + tw, top + th))

    # RGBA 변환
    bg_rgba = bg.convert("RGBA")

    # 오버레이 합성
    overlay = make_overlay(SIZE)
    bg_rgba = Image.alpha_composite(bg_rgba, overlay)

    # draw 객체
    draw = ImageDraw.Draw(bg_rgba)

    # ── 브랜드 텍스트 ──────────────────────────────────────
    font_brand = get_font(REG_FONT, 32)
    draw.text((MARGIN_L, BRAND_Y), brand_text, font=font_brand, fill=GRAY_LIGHT)

    # 캐러셀 인디케이터
    if total_cards > 1:
        dot_x = MARGIN_L + 180
        for i in range(total_cards):
            color = WHITE if i == card_index else GRAY_MID
            r = 6 if i == card_index else 4
            draw.ellipse(
                (dot_x + i * 24 - r, BRAND_Y + 10 - r,
                 dot_x + i * 24 + r, BRAND_Y + 10 + r),
                fill=color
            )

    # ── 토픽 칩 ───────────────────────────────────────────
    draw_chip(draw, MARGIN_L, CHIP_Y, topic_label, accent_color)

    # ── ALERT 모드: 상단 우측 빨간 뱃지 ─────────────────────
    if mode == "alert":
        font_alert = get_font(BOLD_FONT, 24)
        alert_text = "🔴 LIVE"
        alert_bbox = draw.textbbox((0, 0), alert_text, font=font_alert)
        aw = alert_bbox[2] - alert_bbox[0]
        draw.text((W - MARGIN_L - aw, BRAND_Y), alert_text, font=font_alert, fill=(255, 70, 70))

    # ── 아이브로 (소제목) ──────────────────────────────────
    if eyebrow:
        font_eyebrow = fit_font(draw, eyebrow, BOLD_FONT, 38, 26, 560)
        # 그림자
        draw.text((MARGIN_L + 2, EYEBROW_Y + 2), eyebrow, font=font_eyebrow, fill=(0, 0, 0, 150))
        draw.text((MARGIN_L, EYEBROW_Y), eyebrow, font=font_eyebrow, fill=accent_color)

    # ── 제목1 (메인 훅) ────────────────────────────────────
    font_t1 = fit_rich_font(draw, title1_parts, BOLD_FONT, 96, 62, TITLE_MAX_W)
    draw_rich(draw, MARGIN_L, TITLE1_Y, title1_parts, font_t1)

    # 제목1 실제 높이 계산
    t1_bbox = draw.textbbox((0, 0), "가", font=font_t1)
    t1_h = t1_bbox[3] - t1_bbox[1]
    t2_y = TITLE1_Y + t1_h + 18

    # ── 제목2 ──────────────────────────────────────────────
    font_t2 = fit_rich_font(draw, title2_parts, BOLD_FONT, 88, 58, TITLE_MAX_W)
    draw_rich(draw, MARGIN_L, t2_y, title2_parts, font_t2)

    t2_bbox = draw.textbbox((0, 0), "가", font=font_t2)
    t2_h = t2_bbox[3] - t2_bbox[1]
    desc_start_y = t2_y + t2_h + 52

    # ── 설명 라인들 ────────────────────────────────────────
    line_gap = 62
    for i, line in enumerate(desc_lines[:2]):
        if not line:
            continue
        font_desc = fit_font(draw, line, REG_FONT, 42, 28, DESC_MAX_W)
        y_pos = desc_start_y + i * line_gap

        # 하단 바 침범 방지
        if y_pos + 50 > BAR_Y:
            break

        draw.text((MARGIN_L + 2, y_pos + 2), line, font=font_desc, fill=(0, 0, 0, 100))
        draw.text((MARGIN_L, y_pos), line, font=font_desc, fill=GRAY_LIGHT)

    # ── 하단 데이터바 ──────────────────────────────────────
    if data_bar:
        draw_bottom_bar(draw, bg_rgba, BAR_Y, data_bar, accent_color)

    # ── 최종 저장 ──────────────────────────────────────────
    result = bg_rgba.convert("RGB")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%m%d_%H%M%S")
    suffix = f"_c{card_index}" if total_cards > 1 else ""
    out_path = os.path.join(OUTPUT_DIR, f"card_{ts}{suffix}.png")
    result.save(out_path, quality=95)
    print(f"saved: {out_path}")
    return out_path


def make_carousel_set(rewritten, mode="normal", bg_paths=None):
    """
    캐러셀 3장 세트 생성
    bg_paths: [bg1.jpg, bg2.jpg, bg3.jpg] — 없으면 모두 bg.jpg 사용
    """
    if bg_paths is None:
        bg_paths = ["bg.jpg", "bg.jpg", "bg.jpg"]

    accent = rewritten.get("accent", "gold")
    accent_color = ACCENTS.get(accent, ACCENTS["gold"])
    topic = rewritten.get("topic", "MARKET")
    key = rewritten.get("_key", "GENERAL")

    paths = []

    # ── 카드 1: 메인 훅 카드 (기존과 동일) ─────────────────
    if os.path.exists(bg_paths[0]):
        import shutil
        shutil.copy(bg_paths[0], "bg.jpg")

    title1_parts = split_highlight(rewritten["title1"], accent_color)
    title2_parts = [(rewritten["title2"], WHITE)]

    data_bar_1 = None
    if rewritten.get("_price_usd"):
        data_bar_1 = [
            ("현재가", rewritten["_price_usd"]),
            ("실시간", "LIVE"),
        ]

    p1 = make_card(
        eyebrow=rewritten.get("eyebrow", ""),
        title1_parts=title1_parts,
        title2_parts=title2_parts,
        desc_lines=[rewritten["desc1"], rewritten["desc2"]],
        brand_text="jadonnam",
        topic_label=topic,
        mode=mode,
        accent=accent,
        data_bar=data_bar_1,
        card_index=0,
        total_cards=3,
    )
    paths.append(p1)

    # ── 카드 2: 데이터/맥락 카드 ───────────────────────────
    if os.path.exists(bg_paths[1]):
        import shutil
        shutil.copy(bg_paths[1], "bg.jpg")

    card2_title1 = rewritten.get("card2_title1", "지금 숫자 보면")
    card2_title2 = rewritten.get("card2_title2", "이게 왜 중요한지 알게됨")
    card2_desc1 = rewritten.get("desc1", "")
    card2_desc2 = rewritten.get("desc2", "")

    data_bar_2 = None
    if rewritten.get("_volume"):
        data_bar_2 = [
            ("폴리마켓 거래대금", rewritten["_volume"]),
            ("예측 확률", rewritten.get("_prob", "")),
        ]

    p2 = make_card(
        eyebrow="이게 핵심임",
        title1_parts=split_highlight(card2_title1, accent_color),
        title2_parts=[(card2_title2, WHITE)],
        desc_lines=[card2_desc1, card2_desc2],
        brand_text="jadonnam",
        topic_label=topic,
        mode=mode,
        accent=accent,
        data_bar=data_bar_2,
        card_index=1,
        total_cards=3,
    )
    paths.append(p2)

    # ── 카드 3: 결론/CTA 카드 ──────────────────────────────
    if os.path.exists(bg_paths[2]):
        import shutil
        shutil.copy(bg_paths[2], "bg.jpg")

    card3_hook = rewritten.get("card3_hook", "근데 이게 내 지갑이랑")
    card3_title = rewritten.get("card3_title", "어떻게 연결되는지 알아?")
    card3_desc1 = rewritten.get("card3_desc1", "팔로우하면 매일 알려줌")
    card3_desc2 = rewritten.get("card3_desc2", "저장해두면 나중에 유용함")

    p3 = make_card(
        eyebrow=card3_hook,
        title1_parts=[(card3_title, WHITE)],
        title2_parts=[("→ 저장 & 팔로우", accent_color)],
        desc_lines=[card3_desc1, card3_desc2],
        brand_text="jadonnam",
        topic_label=topic,
        mode=mode,
        accent=accent,
        data_bar=None,
        card_index=2,
        total_cards=3,
    )
    paths.append(p3)

    return paths
