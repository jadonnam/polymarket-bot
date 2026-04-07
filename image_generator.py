import os
import base64
from openai import OpenAI

client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())

def build_prompt(raw_title="", raw_summary="", mode="normal", source="news"):
    return f"""
Real breaking news photo, captured in real life.

Topic:
{raw_title}

Context:
{raw_summary}

Scene:
- chaotic real-world situation
- crowded chaotic scene with multiple people moving
- imperfect environment
- smoke, debris, vehicles, people running
- NOT clean, NOT staged

Camera:
- handheld camera
- slight motion blur
- imperfect focus
- real noise / grain

Lighting:
- natural lighting only
- uneven exposure

Composition:
- subject on right
- left side dark empty space
- messy framing

STRICT:
- no text
- no logo
- no watermark
- not cinematic
- not illustration
- not AI style

Mood:
tense, unstable, raw, documentary
""".strip()

def generate_bg(raw_title="", raw_summary="", mode="normal", source="news", output_path="bg.jpg"):
    prompt = build_prompt(raw_title, raw_summary, mode, source)

    result = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1536",
        quality="low"
    )

    image_b64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_b64)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    print(f"bg saved: {output_path}")
    return output_path

def safe_generate_bg(raw_title="", raw_summary="", mode="normal", source="news", output_path="bg.jpg"):
    try:
        return generate_bg(raw_title, raw_summary, mode, source, output_path)
    except Exception as e:
        print("[BG ERROR]", e)
        return output_path