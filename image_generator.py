import os
import base64
from openai import OpenAI

client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())

def build_prompt(raw_title="", raw_summary="", mode="normal", source="news", topic="general"):
    title = raw_title
    summary = raw_summary

    if topic == "geopolitics":
        return f"""
Real breaking news photo.

Topic:
{title}

Context:
{summary}

Scene:
- conflict zone, civilians running
- smoke, destroyed street, damaged vehicles
- military presence in distance
- NO close-up face
- NO single person portrait
- NO politician portrait
- focus on situation, not a famous person
- messy real-world environment
- not staged

Camera:
- handheld documentary camera
- slight motion blur
- imperfect focus
- grainy realism

Lighting:
- natural light only
- uneven exposure

Composition:
- subject or action on right
- left side dark and empty for headline

STRICT:
- no text
- no letters
- no words
- no numbers
- no logo
- no watermark
- no signage
- no billboards
- no posters
- no newspaper front pages
- not cinematic
- not illustration
- not AI style
""".strip()

    if topic == "economy":
        return f"""
Real financial news photo.

Topic:
{title}

Context:
{summary}

Scene:
- oil tanker, port, shipping route, refinery, financial district, or trading floor
- blurred charts or market screens in background only
- economic tension atmosphere
- NO war
- NO soldier
- NO weapon
- NO explosion
- NO conflict zone
- NO politician face
- NO close-up face
- no giant portrait in foreground
- realistic editorial environment
- not staged

Camera:
- documentary style camera
- slight grain
- realistic imperfections

Lighting:
- natural light or office ambient light only

Composition:
- main subject on right
- left side dark and empty for headline

STRICT:
- no readable text
- no letters
- no words
- no logo
- no watermark
- not cinematic
- not illustration
- not AI style
""".strip()

    if topic == "crypto":
        return f"""
Real crypto market photo.

Topic:
{title}

Context:
{summary}

Scene:
- trader desk, finance workspace, digital asset market tension
- monitors in background but unreadable
- investors or analysts at work
- NO war
- NO soldier
- NO weapon
- NO explosion
- NO politician
- NO close-up face
- realistic editorial style
- not staged

Camera:
- handheld documentary camera
- slight grain
- imperfect focus

Lighting:
- realistic indoor light only

Composition:
- main subject on right
- left side dark and empty for headline

STRICT:
- no readable text
- no letters
- no words
- no logo
- no watermark
- not cinematic
- not illustration
- not AI style
""".strip()

    if topic == "politics":
        return f"""
Real political news photo.

Topic:
{title}

Context:
{summary}

Scene:
- press crowd, government building, campaign event atmosphere, public event
- people moving, cameras, security presence
- NO giant face close-up
- NO celebrity portrait
- NO poster text
- NO campaign sign text
- realistic documentary atmosphere
- not staged

Camera:
- handheld documentary camera
- slight grain
- imperfect focus

Lighting:
- natural light only

Composition:
- main subject or event on right
- left side dark and empty for headline

STRICT:
- no readable text
- no letters
- no words
- no logo
- no watermark
- not cinematic
- not illustration
- not AI style
""".strip()

    return f"""
Real news photo.

Topic:
{title}

Context:
{summary}

Scene:
- realistic current event setting
- subtle urgency
- no giant face
- no close-up portrait
- documentary realism
- not staged

Camera:
- handheld
- slight grain
- imperfect focus

Composition:
- subject on right
- left side dark empty space

STRICT:
- no readable text
- no letters
- no words
- no logo
- no watermark
- not cinematic
- not illustration
- not AI style
""".strip()

def generate_bg(raw_title="", raw_summary="", mode="normal", source="news", topic="general", output_path="bg.jpg"):
    prompt = build_prompt(raw_title, raw_summary, mode, source, topic)

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

def safe_generate_bg(raw_title="", raw_summary="", mode="normal", source="news", topic="general", output_path="bg.jpg"):
    try:
        return generate_bg(raw_title, raw_summary, mode, source, topic, output_path)
    except Exception as e:
        print("[BG ERROR]", e)
        return output_path