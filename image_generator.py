import os
import base64
from PIL import Image, ImageDraw, ImageFilter
from openai import OpenAI

client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1")
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "high")


def build_prompt(title="", desc="", visual_topic="market_general", visual_variant="general_1"):
    common = f"""
Create a premium Instagram finance-news hero image for a Korean SNS magazine account.

Headline context:
{title}
Sub context:
{desc}

Requirements:
- ultra realistic editorial photography
- premium magazine cover quality
- very clickable for Korean social media
- Korean meme energy through facial expression only
- expressive reaction face
- classy but provocative finance-magazine mood
- single clear main subject
- vertical 4:5 composition
- subject mostly on right side
- left side darker and cleaner for Korean headline overlay
- high contrast lighting
- no text
- no letters
- no numbers
- no watermark
- no logos
- no UI
- no collage
- no duplicate face
- no extra fingers
- no deformities
- no sexual content
- no bikinis
- no nudity
"""

    variant_map = {
        "btc_1": "young Korean-looking male trader, eyes wide open, giant realistic bitcoin coin, luxury skyline at night, upward golden light streak",
        "btc_2": "guy in semi-formal outfit with speechless rich-face reaction, giant bitcoin coin, penthouse window, blue and gold neon",
        "btc_3": "young man covering mouth in disbelief, realistic bitcoin coin glowing, upscale city night, jackpot mood",
        "btc_4": "man laughing in shock while watching giant bitcoin, dark luxury room, champagne glow in background only",

        "eth_1": "young trader screaming in excitement, futuristic blue finance room, elegant ethereum mood",
        "eth_2": "guy staring with crazy excited eyes at blue crypto glow, upscale trading desk",
        "eth_3": "young investor with half-laugh half-shock reaction, cool blue light streaks",

        "oil_1": "shocked businessman holding head, huge oil tanker and refinery, burning orange sunset",
        "oil_2": "guy staring in panic at industrial refinery glow, tanker port, orange-black macro crisis mood",
        "oil_3": "man with both hands on head in front of oil terminal, fiery macro sky",

        "gold_1": "excited investor in warm gold vault room, realistic gold bars glowing, rich safe-haven rush mood",
        "gold_2": "close-up of stunned happy investor and stacks of gold bars, premium warm luxury light",

        "rate_1": "worried wall street style trader holding tablet, blue trading floor, anxious macro mood",
        "rate_2": "trader rubbing forehead while staring off-screen, cool blue finance newsroom",
        "rate_3": "man in suit with exhausted stressed face, tablet in hand, dark blue macro desk",

        "bond_1": "middle-aged trader with dead-tired face, blue bond desk, serious macro pressure",
        "bond_2": "trader frowning at tablet, blurred blue screens, bond market stress mood",
        "bond_3": "older finance guy with defeated face in bond room, cool lighting",

        "deal_1": "luxury handshake, one guy grinning like he won big, expensive boardroom",
        "deal_2": "smug businessman with huge grin after closing a deal, dark luxury office",
        "deal_3": "aggressive handshake and ecstatic winner face, premium negotiation room",

        "trump_1": "Donald Trump with confident winner smile, warm presidential spotlight",
        "trump_2": "Donald Trump with smug face in luxurious political room, premium winner vibe",
        "trump_3": "Donald Trump calm but confident, dramatic gold light",

        "trump_anger_1": "Donald Trump shouting angrily, finger pointing, smoky dark room",
        "trump_anger_2": "Donald Trump furious speech moment, hard spotlight, tariff-panic mood",

        "trade_1": "cargo port and tense businessman, orange industrial trade pressure mood",
        "trade_2": "executive watching port containers in stress, tariff tension, macro poster feel",

        "mideast_1": "oil tanker route under smoky orange sky, geopolitical tension, premium editorial look",
        "mideast_2": "tanker and distant military tension, sea haze, dramatic oil-route crisis mood",
        "mideast_3": "strategic sea route with tanker and dark orange sky, market risk feeling",

        "politics_1": "tense press room, worried political staff, dark high-stakes atmosphere",
        "politics_2": "political advisor with stressed expression in press room, muted dark luxury vibe",

        "stocks_1": "investor half-smiling in rising stock mood, green-blue trading lights, premium newsroom",
        "stocks_2": "stressed trader with stock chart glow, dark finance floor, bearish pressure",
        "stocks_3": "man reacting dramatically to stock move, upscale market room",

        "cpi_1": "macro trader in shock, orange-blue inflation stress lighting, stunned face",
        "cpi_2": "worried trader staring at unseen macro number, hot orange macro panic mood",

        "general_1": "premium macro newsroom, elegant finance atmosphere, cinematic business mood",
        "general_2": "dramatic finance room with serious investor, dark luxury mood, premium magazine style",
    }

    base_scene = {
        "trump_positive": "Donald Trump, confident smirk, presidential spotlight, winner mood",
        "trump_negative": "Donald Trump, furious shouting face, dark high-stakes atmosphere",
        "trump_deal_positive": "Donald Trump, smug satisfied smile, strong deal-maker energy, boardroom backdrop",
        "trump_deal_negative": "Donald Trump, irritated frustrated expression, tense negotiation room",
        "trump_tariff": "Donald Trump, aggressive speech moment, forceful expression, economic shock mood",
        "btc_moon": "giant realistic bitcoin coin, luxury skyline, young rich guy losing his mind in shock",
        "btc_panic": "giant realistic bitcoin coin, dark city skyline, stressed young man in suit, red tension",
        "eth_surge": "futuristic finance set, young trader losing his mind in excitement, glossy blue light",
        "eth_drop": "sleek trading room, shocked young trader, blue-red stress lighting",
        "oil_shock": "huge oil tanker and refinery, burning orange sunset, shocked businessman holding head",
        "oil_relief": "oil tanker crossing calmer sea, sunrise, easing energy tension",
        "gold_rush": "luxurious gold bars and vault, excited investor face, warm rich safe-haven rush",
        "gold_cool": "premium gold trading room, cooler safe-haven mood",
        "rate_cut_hype": "Wall Street trader, surprised hopeful face, blue market screens blurred",
        "rate_cut_doubt": "Wall Street trader, worried face holding tablet, dark blue trading floor",
        "inflation_shock": "macro trader, stunned expression, hot orange and blue contrast, inflation shock mood",
        "bond_stress": "middle-aged trader in suit, tired stressed face, bond desk atmosphere",
        "stocks_up": "trader with subtle grin, rising market mood, premium blue-green newsroom",
        "stocks_down": "trader stressed and worried, dark trading floor, bearish premium atmosphere",
        "trade_deal_hype": "aggressive luxury handshake scene, winning expression, business-deal celebration mood",
        "trade_tension": "cargo port with containers, darker orange tension, tariff pressure mood",
        "politics_negative": "tense press room, worried aides in background, political drama mood",
        "mideast_tension": "oil route tanker, distant military tension, dramatic sea haze, geopolitical risk mood",
        "mideast_relief": "tanker under sunrise, calmer strategic sea route, relief after tension",
        "market_general": "premium macro newsroom, elegant finance atmosphere, cinematic business mood",
    }

    scene = variant_map.get(visual_variant) or base_scene.get(visual_topic, base_scene["market_general"])
    return common + "\nScene:\n- " + scene


def _fallback_gradient(output_path="bg.jpg"):
    w, h = 1024, 1536
    img = Image.new("RGB", (w, h), (18, 20, 28))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        ratio = y / max(h - 1, 1)
        r = int(18 * (1 - ratio) + 45 * ratio)
        g = int(20 * (1 - ratio) + 30 * ratio)
        b = int(28 * (1 - ratio) + 40 * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    draw.ellipse((650, 140, 980, 460), fill=(255, 180, 70))
    draw.rounded_rectangle((710, 420, 930, 1270), radius=32, fill=(70, 90, 130))
    draw.rounded_rectangle((850, 520, 990, 1270), radius=28, fill=(40, 60, 95))

    img = img.filter(ImageFilter.GaussianBlur(radius=0.8))
    img.save(output_path, quality=95)
    return output_path


def generate_bg(title="", desc="", visual_topic="market_general", visual_variant="general_1", output_path="bg.jpg"):
    prompt = build_prompt(title=title, desc=desc, visual_topic=visual_topic, visual_variant=visual_variant)

    try:
        result = client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size="1024x1536",
            quality=IMAGE_QUALITY,
        )
    except Exception:
        result = client.images.generate(
            model=IMAGE_MODEL,
            prompt=prompt,
            size="1024x1536",
        )

    image_b64 = result.data[0].b64_json
    image_bytes = base64.b64decode(image_b64)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    print(f"bg saved: {output_path}")
    return output_path


def safe_generate_bg(title="", desc="", visual_topic="market_general", visual_variant="general_1", output_path="bg.jpg"):
    try:
        return generate_bg(
            title=title,
            desc=desc,
            visual_topic=visual_topic,
            visual_variant=visual_variant,
            output_path=output_path
        )
    except Exception as e:
        print("[BG ERROR]", e)
        return _fallback_gradient(output_path=output_path)