import re
from card_maker import make_card, WHITE

HIGHLIGHT_COLOR = (247, 205, 70)

def split_highlight(text):
    if not text:
        return [(text, WHITE)]

    # 🔥 핵심 수정 (단위 포함)
    matches = list(re.finditer(r'[$]?\d[\d,\.]*\s?(억원|억|만원|원|달러|%|배|일|월)?', text))

    if matches:
        parts = []
        last_end = 0

        for m in matches:
            start, end = m.span()

            # 앞 텍스트
            if start > last_end:
                parts.append((text[last_end:start], WHITE))

            # 숫자+단위 통째 강조
            parts.append((text[start:end], HIGHLIGHT_COLOR))

            last_end = end

        # 마지막 텍스트
        if last_end < len(text):
            parts.append((text[last_end:], WHITE))

        return parts

    return [(text, WHITE)]