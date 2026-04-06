from card_maker import make_card
import re

WHITE = (255, 255, 255)
YELLOW = (255, 214, 87)
RED = (255, 92, 92)

RED_WORDS = [
    "급등", "급락", "하락", "전쟁", "충돌", "긴장", "위기",
    "경고", "폭락", "불안", "리스크", "불안정", "폭등", "급변",
    "공격", "미사일", "붕괴", "터졌다"
]

def colorize_text(text, mode="normal"):
    for word in RED_WORDS:
        if word in text:
            before, after = text.split(word, 1)
            return [(before, WHITE), (word, RED), (after, WHITE)]

    m = re.search(r'[\+\-]?[\d,]+(?:\.\d+)?[%원달러배억만]?', text)
    if m:
        number = m.group(0)
        before = text[:m.start()]
        after = text[m.end():]
        return [(before, WHITE), (number, YELLOW), (after, WHITE)]

    return [(text, WHITE)]

def create_card(rewritten, mode="normal"):
    path = make_card(
        title1_parts=colorize_text(rewritten["title1"], mode=mode),
        title2_parts=colorize_text(rewritten["title2"], mode=mode),
        desc_lines=[rewritten["desc1"], rewritten["desc2"]],
        mode=mode
    )
    return path