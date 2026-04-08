import re
from card_maker import make_card, WHITE
from image_generator import safe_generate_bg

HIGHLIGHT_COLOR = (247, 205, 70)


def split_highlight(text):
    if not text:
        return [(text, WHITE)]

    matches = list(re.finditer(r'[$]?\d[\d,\.]*\s?(억원|억|만원|원|달러|%|배|일|월)?', text))

    if matches:
        parts = []
        last_end = 0

        for m in matches:
            start, end = m.span()

            if start > last_end:
                parts.append((text[last_end:start], WHITE))

            parts.append((text[start:end], HIGHLIGHT_COLOR))
            last_end = end

        if last_end < len(text):
            parts.append((text[last_end:], WHITE))

        return parts

    return [(text, WHITE)]


def create_card(rewritten, mode="normal"):
    safe_generate_bg(
        title=f"{rewritten.get('title1', '')} / {rewritten.get('title2', '')}",
        desc=f"{rewritten.get('desc1', '')} / {rewritten.get('desc2', '')}",
        visual_topic=rewritten.get("visual_topic", "market_general"),
        visual_variant=rewritten.get("visual_variant", "general_1"),
        output_path="bg.jpg"
    )

    title1_parts = split_highlight(rewritten["title1"])
    title2_parts = split_highlight(rewritten["title2"])
    desc_lines = [rewritten["desc1"], rewritten["desc2"]]

    return make_card(
        eyebrow=rewritten.get("eyebrow", ""),
        title1_parts=title1_parts,
        title2_parts=title2_parts,
        desc_lines=desc_lines,
        brand_text="jadonnam",
        topic_label=rewritten.get("topic", "MARKET"),
        mode=mode,
        accent=rewritten.get("accent", "gold"),
        subtone=rewritten.get("subtone", "white")
    )