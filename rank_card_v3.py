import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350

# 색상
BG_TOP = (6, 10, 20)
BG_BOTTOM = (18, 22, 34)

CARD_BG = (22, 28, 42)
CARD_BORDER = (40, 48, 68)

TEXT_MAIN = (255, 255, 255)
TEXT_SUB = (140, 150, 170)

RED = (255, 80, 80)
ORANGE = (255, 150, 60)
YELLOW = (255, 210, 80)

# 폰트
def _font(size, bold=True):
    base = os.path.dirname(__file__)
    path = os.path.join(
        base,
        "fonts",
        "Pretendard-Bold.ttf" if bold else "Pretendard-Regular.ttf"
    )
    return ImageFont.truetype(path, size)

FONT_TITLE = _font(64, True)
FONT_ITEM = _font(52, True)
FONT_PERCENT = _font(44, True)
FONT_RANK = _font(30, True)

# 배경
def _bg():
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)

    for y in range(H):
        r = y / H
        rr = int(BG_TOP[0] * (1 - r) + BG_BOTTOM[0] * r)
        gg = int(BG_TOP[1] * (1 - r) + BG_BOTTOM[1] * r)
        bb = int(BG_TOP[2] * (1 - r) + BG_BOTTOM[2] * r)
        d.line([(0, y), (W, y)], fill=(rr, gg, bb))

    return img

# 점수 색상
def _color(score):
    if score >= 80:
        return RED
    if score >= 60:
        return ORANGE
    return YELLOW

# 텍스트 줄이기
def _trim(text):
    text = str(text)
    if len(text) > 10:
        return text[:10] + "…"
    return text

# 카드 하나
def _draw_card(draw, x, y, w, h, rank, title, score):
    radius = 40

    # 카드 배경
    draw.rounded_rectangle(
        (x, y, x + w, y + h),
        radius=radius,
        fill=CARD_BG,
        outline=CARD_BORDER,
        width=2
    )

    # 순위
    draw.text((x + 30, y + 25), f"{rank}", font=FONT_RANK, fill=TEXT_SUB)

    # 제목
    draw.text((x + 30, y + 80), _trim(title), font=FONT_ITEM, fill=TEXT_MAIN)

    # 퍼센트
    draw.text((x + w - 140, y + 80), f"{score}%", font=FONT_PERCENT, fill=_color(score))

    # 게이지
    bar_x = x + 30
    bar_y = y + h - 70
    bar_w = w - 60
    bar_h = 22

    # 배경
    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
        radius=12,
        fill=(40, 45, 60)
    )

    # 채워진 부분
    fill_w = int(bar_w * score / 100)

    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h),
        radius=12,
        fill=_color(score)
    )

# 카드 생성
def create_rank_card(kind, items, path):
    img = _bg()
    draw = ImageDraw.Draw(img)

    # 제목
    draw.text((60, 60), kind, font=FONT_TITLE, fill=TEXT_MAIN)

    # 데이터 보정
    while len(items) < 3:
        items.append({"title": "대기중", "score": 0})

    items = items[:3]

    card_h = 280
    gap = 40
    start_y = 180

    for i, item in enumerate(items):
        y = start_y + i * (card_h + gap)

        _draw_card(
            draw,
            50,
            y,
            W - 100,
            card_h,
            i + 1,
            item["title"],
            int(item["score"])
        )

    img.save(path)
    return path

# 합성
def create_rank_set(news, poly, out_dir="output_rank"):
    os.makedirs(out_dir, exist_ok=True)

    n = create_rank_card("뉴스", news, os.path.join(out_dir, "news.png"))
    p = create_rank_card("폴리마켓", poly, os.path.join(out_dir, "poly.png"))

    # 시장 반응 = 합치기
    merged = {}
    for i in news + poly:
        t = i["title"]
        s = int(i["score"])
        if t in merged:
            merged[t] = max(merged[t], s)
        else:
            merged[t] = s

    merged = [{"title": k, "score": v} for k, v in merged.items()]
    merged.sort(key=lambda x: x["score"], reverse=True)

    m = create_rank_card("시장 반응", merged[:3], os.path.join(out_dir, "market.png"))

    return [n, p, m]