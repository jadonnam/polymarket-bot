
import os
from PIL import Image, ImageDraw, ImageFont

from prompt_bank_v3 import detect_visual_topic, breaking_prompt, breaking_headline

def _font(size, bold=True):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

def _wrap(text, limit=12):
    t = str(text).strip()
    if len(t) <= limit:
        return [t]
    parts = t.split()
    if len(parts) <= 1:
        return [t[:limit], t[limit:limit*2]]
    line1, line2 = "", ""
    for p in parts:
        if len((line1 + " " + p).strip()) <= limit and not line2:
            line1 = (line1 + " " + p).strip()
        else:
            line2 = (line2 + " " + p).strip()
    return [line1, line2[:limit]]

def _fallback_bg(path):
    from PIL import Image
    img = Image.new("RGB", (1080, 1350), (12, 12, 18))
    img.save(path, quality=95)
    return path

def create_breaking_image(raw_title, out_path="output_breaking.png"):
    topic = detect_visual_topic(raw_title)
    headline = breaking_headline(raw_title)
    prompt = breaking_prompt(raw_title)

    bg_path = "breaking_bg.jpg"
    try:
        from image_generator_new import safe_generate_bg
        safe_generate_bg(
            visual_topic=topic,
            seed_text=headline,
            context_title=headline,
            context_desc=prompt,
            output_path=bg_path,
            title=headline,
            desc=prompt,
        )
    except Exception:
        _fallback_bg(bg_path)

    img = Image.open(bg_path).convert("RGBA").resize((1080, 1350))
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)

    # dark top fade for headline readability
    d.rectangle((0, 0, 1080, 430), fill=(0, 0, 0, 120))
    d.rounded_rectangle((60, 60, 208, 124), radius=18, fill=(255, 59, 59, 230))

    chip_font = _font(34, True)
    title_font = _font(88, True)
    water_font = _font(24, False)

    d.text((89, 73), "속보", font=chip_font, fill=(255, 255, 255, 255))

    lines = _wrap(headline, 14)
    y = 168
    for line in lines[:2]:
        d.text((64 + 4, y + 4), line, font=title_font, fill=(0, 0, 0, 180))
        d.text((64, y), line, font=title_font, fill=(255, 255, 255, 255))
        y += 104

    d.text((912, 1298), "jadonnam", font=water_font, fill=(180, 180, 188, 120))

    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(out_path, quality=95)
    return out_path
