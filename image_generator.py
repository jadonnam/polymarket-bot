import os
import base64
from openai import OpenAI

client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())


def classify_visual_topic(raw_title="", raw_summary="", topic="general"):
    text = f"{raw_title} {raw_summary}".lower()

    if any(k in text for k in ["oil", "wti", "crude", "brent", "hormuz", "tanker", "refinery", "lng"]):
        return "oil"
    if any(k in text for k in ["gold", "bullion", "safe haven"]):
        return "gold"
    if any(k in text for k in ["bitcoin", "btc", "crypto", "ethereum", "eth"]):
        return "crypto"
    if any(k in text for k in ["fed", "inflation", "cpi", "rate", "rates", "bond", "yield", "tariff", "nasdaq", "s&p", "dow", "treasury"]):
        return "macro"
    if any(k in text for k in ["iran", "israel", "missile", "war", "attack", "ceasefire", "troops"]):
        return "geopolitics"

    if topic in ["economy", "crypto", "geopolitics", "politics"]:
        return topic

    return "general"


def build_common_rules():
    return """
STYLE:
- real editorial news photo
- realistic documentary photography
- natural imperfections
- slightly grainy
- not cinematic
- not glossy ad style
- not illustration
- not 3d render
- not infographic
- not poster
- not AI art look

COMPOSITION:
- main subject on right side
- left 45 percent must stay dark, clean, empty
- strong negative space on left for Korean headline
- avoid clutter on left
- one clear subject only
- mobile first vertical composition for Instagram card
- visually premium, clean, expensive looking

LIGHTING:
- realistic ambient light only
- subtle contrast
- moody but clean
- no blown highlights

STRICTLY FORBIDDEN:
- no readable text
- no letters
- no words
- no numbers
- no ticker symbols
- no subtitles
- no captions
- no signage
- no logos
- no watermarks
- no newspaper front pages
- no screenshots
- no UI
- no app interface
- no giant face close-up
- no politician portrait
- no duplicated objects
- no duplicated ships
- no duplicated monitors
- no extra fingers
- no surreal shapes
""".strip()


def build_oil_prompt(title="", summary=""):
    return f"""
Real financial news photo about oil market.

Topic:
{title}

Context:
{summary}

Scene:
- one large crude oil tanker or LNG tanker near port, refinery, or narrow shipping route
- industrial energy infrastructure in distance
- realistic sea haze, refinery lights, pipelines
- premium editorial mood
- no explosion
- no war scene
- no soldiers
- no missile
- no fireball
- no dramatic destruction
- focus on oil supply and price shock atmosphere

Camera:
- telephoto documentary shot
- slight grain
- realistic lens softness
- natural depth

{build_common_rules()}
""".strip()


def build_gold_prompt(title="", summary=""):
    return f"""
Real financial news photo about gold market.

Topic:
{title}

Context:
{summary}

Scene:
- gold bars, vault trays, precious metals desk, macro finance environment
- safe haven asset mood
- maybe blurred market lights in deep background only
- no readable screen text
- no people close-up
- no war scene
- no politician
- elegant but realistic editorial image

Camera:
- documentary financial photography
- subtle grain
- realistic focus falloff

{build_common_rules()}
""".strip()


def build_crypto_prompt(title="", summary=""):
    return f"""
Real financial news photo about crypto market.

Topic:
{title}

Context:
{summary}

Scene:
- one trader workspace, one desk, one monitor cluster
- dark finance room
- digital asset trading atmosphere
- charts only as blurred abstract light shapes
- no readable monitor content
- no coin logos
- no bitcoin logo
- no ethereum logo
- no app screens
- no giant 3d coins
- no cyberpunk style
- realistic premium editorial look

Camera:
- handheld documentary camera
- slight grain
- realistic indoor light
- sharp subject on right, empty dark left

{build_common_rules()}
""".strip()


def build_macro_prompt(title="", summary=""):
    return f"""
Real financial news photo about macroeconomy.

Topic:
{title}

Context:
{summary}

Scene:
- financial district, bond trading room, stock exchange floor, cargo port, container terminal, or central bank style environment
- blurred market activity in background
- no readable data screens
- no politician portrait
- no war scene
- no flags dominating image
- focus on money flow and economic pressure
- clean premium composition

Camera:
- documentary editorial photography
- natural office or city light
- slight grain
- expensive clean visual

{build_common_rules()}
""".strip()


def build_geopolitics_prompt(title="", summary=""):
    return f"""
Real news photo connected to geopolitical risk affecting markets.

Topic:
{title}

Context:
{summary}

Scene:
- oil terminal, port security zone, shipping chokepoint, industrial coastline, surveillance atmosphere
- if tension is implied, show infrastructure risk rather than combat
- distant security presence only if needed
- no active firefight
- no blood
- no bodies
- no battlefield
- no giant politician face
- no protest signs
- focus on market relevant geopolitical risk, not war drama

Camera:
- documentary press photo
- slight grain
- imperfect realism
- dark clean left side
- subject on right

{build_common_rules()}
""".strip()


def build_general_prompt(title="", summary=""):
    return f"""
Real news photo.

Topic:
{title}

Context:
{summary}

Scene:
- current events editorial environment
- money and market relevance
- clean dark negative space on left
- realistic subject on right
- premium visual mood
- no literal text elements

Camera:
- documentary photography
- slight grain
- realistic imperfections

{build_common_rules()}
""".strip()


def build_prompt(raw_title="", raw_summary="", mode="normal", source="news", topic="general"):
    visual_topic = classify_visual_topic(raw_title, raw_summary, topic)

    if visual_topic == "oil":
        return build_oil_prompt(raw_title, raw_summary)
    if visual_topic == "gold":
        return build_gold_prompt(raw_title, raw_summary)
    if visual_topic == "crypto":
        return build_crypto_prompt(raw_title, raw_summary)
    if visual_topic == "macro":
        return build_macro_prompt(raw_title, raw_summary)
    if visual_topic == "geopolitics":
        return build_geopolitics_prompt(raw_title, raw_summary)

    return build_general_prompt(raw_title, raw_summary)


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