import re
from card_maker import make_card, WHITE

HIGHLIGHT_COLOR = (247, 205, 70)

def split_highlight(text):
    if not text:
        return [(text, WHITE)]

    match = re.search(r'[$]?\d[\d,\.]*\s?(억원|억|만원|원|달러|%|배|일|명)?', text)
    if match:
        start, end = match.span()
        return [
            (text[:start], WHITE),
            (text[start:end], HIGHLIGHT_COLOR),
            (text[end:], WHITE),
        ]

    return [(text, WHITE)]

def create_card(rewritten, mode="normal"):
    title1_parts = split_highlight(rewritten["title1"])
    title2_parts = split_highlight(rewritten["title2"])
    desc_lines = [rewritten["desc1"], rewritten["desc2"]]

    return make_card(
        title1_parts=title1_parts,
        title2_parts=title2_parts,
        desc_lines=desc_lines,
        brand_text="jadonnam",
        mode=mode
    )