import os
import hashlib
import requests
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 환경변수가 비어 있습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "dall-e-3")
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "hd")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1024")


COMMON_BASE = """
Create a HIGH-CTR meme-like but still photorealistic thumbnail image for a Korean finance Instagram account.

Core goal:
- It must stop scrolling instantly
- It must feel provocative, emotional, slightly absurd, and highly clickable
- It must still look like a real image, not flat illustration

Visual direction:
- photorealistic
- meme energy
- exaggerated emotional reaction
- dramatic finance thumbnail
- dark premium background
- expressive face
- realistic skin texture
- realistic camera lighting
- strong contrast
- sharp focus on the subject
- cinematic but not fantasy
- social media viral thumbnail style

Composition rules:
- one main subject only
- subject should dominate the frame
- face must be large and instantly readable
- subject should usually be on the right side
- leave darker empty space for Korean text overlay
- chest-up or waist-up framing
- no clutter
- no collage
- no split screen
- no text inside image
- no logo
- no watermark

Important style rule:
- reaction meme face like viral internet screenshot
- captured mid-reaction moment
- slightly awkward realistic expression
- unfiltered emotional reaction
- The emotion should be slightly over the top, like a meme screenshot
- But the image must still feel like a real photographed moment
- Avoid generic AI poster style
- Avoid polished luxury fashion vibes
- Prefer viral, punchy, absurd, emotional realism

Negative rules:
- no anime
- no illustration
- no cartoon
- no plastic skin
- no extra fingers focus
- no duplicated face
- no bizarre deformations
- no poster typography
"""


SCENE_VARIANTS = {
    "btc_moon": [
        "A shocked Korean man in a suit staring at his phone with wide eyes and half-open mouth, like he cannot believe Bitcoin is exploding again, red and blue trading board lights behind him, viral meme energy, realistic finance room",
        "A Korean office worker in a suit leaning forward with a stunned excited expression while checking his phone, bright crypto board glow in background, feels like a famous meme reaction image but realistic",
        "A Korean trader with a ridiculous but believable look of disbelief, eyes widened, jaw tense, one hand gripping phone, intense red market lights behind him, highly clickable meme-like finance thumbnail",
        "A Korean man in a dark suit frozen in shocked excitement while watching a sudden crypto move, giant red number board lights behind him, realistic but absurd viral reaction energy"
    ],
    "btc_panic": [
        "A Korean trader in a suit staring at his phone in horror, eyes wide and lips tense, red warning lights behind him, panic meme energy but realistic photo",
        "A Korean office worker with an over-the-top devastated reaction while watching a crypto crash, dark finance room, harsh red lighting, viral meme feeling",
        "A Korean man with a terrified frozen face looking at a plunging market, dramatic trading board behind him, finance disaster meme energy"
    ],
    "eth_surge": [
        "A Korean crypto trader with stunned hopeful excitement, glowing blue market lights, phone in hand, dramatic meme-like reaction but realistic",
        "A Korean office worker laughing in disbelief at a sudden altcoin surge, blue finance board behind him, realistic viral meme frame"
    ],
    "eth_drop": [
        "A Korean trader with a crushed expression staring at a phone, blue-red trading board in the background, altcoin panic mood with meme energy",
        "A Korean office worker with hollow shocked eyes in front of an electronic market board, realistic but absurd doom reaction"
    ],
    "oil_shock": [
        "A Korean businessman with a deeply stressed shocked face in front of an industrial refinery glow, feels like gas prices just exploded, meme-level urgency but realistic",
        "A Korean office worker in a suit reacting like he just saw insane fuel costs, orange industrial lights behind him, viral finance meme image",
        "A Korean driver-businessman hybrid look, gripping phone, horrified expression, refinery fires in the background, highly clickable realistic meme style"
    ],
    "oil_relief": [
        "A tired Korean businessman showing a cautious relieved expression, warm dawn industrial background, relief after chaos, realistic finance meme tone",
        "A Korean office worker exhaling in relief while checking energy prices on a phone, calmer orange morning light, subtle meme energy"
    ],
    "gold_rush": [
        "A Korean investor with greedy shocked eyes looking at gold bars like he cannot believe the move, vault background, meme-like safe haven panic but realistic",
        "A Korean businessman in a suit with an absurdly focused expression staring at glowing gold, highly clickable finance meme photo"
    ],
    "rate_cut_doubt": [
        "A Korean macro trader with a skeptical stressed look, dark blue market room, feels like one policy sentence ruined the plan, realistic meme-like reaction",
        "A Korean office worker with eyebrows deeply furrowed and lips tightened while reading rate news, harsh blue newsroom glow, viral finance meme vibe"
    ],
    "rate_cut_hype": [
        "A Korean investor with a stunned relieved grin reacting to policy hopes, blue-green finance room, meme-like but realistic",
        "A Korean trader with an excited cannot-believe-it face after positive rate news, dark premium room, viral thumbnail energy"
    ],
    "inflation_shock": [
        "A Korean office worker with a receipt in hand and a face full of dread, cost of living pain, realistic but exaggerated meme reaction",
        "A Korean businessman shocked by rising prices, warm supermarket-like glow, emotionally strong realistic meme image"
    ],
    "bond_stress": [
        "A tired Korean finance professional rubbing his forehead with a drained expression, institutional finance room, subtle doom meme mood",
        "A Korean bond trader with a dead-inside look, blue-gray market lighting, exhausted realistic finance meme"
    ],
    "stocks_up": [
        "A Korean trader with a wild but believable winning face, green market glow behind him, social media finance meme energy",
        "A Korean office worker staring at rising numbers with stunned happy disbelief, realistic viral market reaction"
    ],
    "stocks_down": [
        "A Korean trader with a grim pained expression in front of a red market board, realistic crash meme frame",
        "A Korean businessman looking at his phone like the market betrayed him, dramatic realistic panic reaction"
    ],
    "trade_tension": [
        "A Korean executive with a tense jaw and worried eyes, cargo port lights behind him, trade war tension in a realistic meme style",
        "A Korean businessman staring into the distance with stress in his face, shipping containers and orange darkness, provocative macro thumbnail"
    ],
    "trade_deal_hype": [
        "A Korean businessman reacting like a huge deal just closed, relieved but intense expression, boardroom background, meme-level click appeal but realistic",
        "A Korean executive with a victorious grin and wide eyes after a major agreement, dark boardroom, viral finance meme shot"
    ],
    "mideast_tension": [
        "A Korean finance guy staring at his phone with dread while orange crisis light fills the room, geopolitical panic meme mood, realistic photo",
        "A Korean businessman frozen in shock as if war headlines just hit, orange-red background glow, realistic but very clickable meme-like composition"
    ],
    "mideast_relief": [
        "A Korean office worker with an exhausted relieved expression after crisis easing, dawn light and calm route background, realistic finance meme feeling"
    ],
    "trump_tariff": [
        "Donald Trump with an aggressive exaggerated expression and pointing gesture, dark dramatic background, viral policy meme energy, realistic",
        "Donald Trump looking intense and provocative, harsh political-finance lighting, highly clickable realistic thumbnail"
    ],
    "trump_deal_positive": [
        "Donald Trump with a smug victorious grin like he just won a high-stakes negotiation, dark boardroom background, realistic but meme-like viral image",
        "Donald Trump with a satisfied dealmaker expression, dramatic policy backdrop, clicky social media finance meme tone"
    ],
    "trump_deal_negative": [
        "Donald Trump with an irritated tense expression, dark negotiation backdrop, failed deal tension, realistic viral meme style",
        "Donald Trump looking annoyed and suspicious under dramatic lighting, provocative political-finance meme image"
    ],
    "market_general": [
        "A Korean finance professional with an intense meme-worthy reaction face, dark market room, realistic viral thumbnail energy",
        "A Korean office worker staring at a phone with absurd disbelief, finance board lights in background, realistic but highly clickable meme image",
        "A Korean man in a suit with a dramatic reaction to market news, dark premium setting, social media viral finance meme style"
    ],
}


def _stable_pick(arr, seed_text):
    if not arr:
        return ""
    h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
    return arr[h % len(arr)]


def build_prompt(visual_topic="market_general", seed_text="", context_title="", context_desc=""):
    variants = SCENE_VARIANTS.get(visual_topic, SCENE_VARIANTS["market_general"])
    scene = _stable_pick(variants, seed_text or context_title or visual_topic)

    context = ""
    if context_title:
        context += f"\nContext title: {context_title}"
    if context_desc:
        context += f"\nContext desc: {context_desc[:160]}"

    return COMMON_BASE + context + f"\n\nScene:\n{scene}"


def _fallback_gradient(output_path="bg.jpg", mood="dark"):
    w, h = 1024, 1024
    img = Image.new("RGB", (w, h), (10, 12, 20))
    draw = ImageDraw.Draw(img)

    if mood == "bright":
        top_color = (45, 28, 10)
        bottom_color = (90, 55, 20)
    else:
        top_color = (10, 12, 20)
        bottom_color = (32, 14, 20)

    for y in range(h):
        r = y / max(h - 1, 1)
        rr = int(top_color[0] * (1 - r) + bottom_color[0] * r)
        gg = int(top_color[1] * (1 - r) + bottom_color[1] * r)
        bb = int(top_color[2] * (1 - r) + bottom_color[2] * r)
        draw.line([(0, y), (w, y)], fill=(rr, gg, bb))

    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    img.save(output_path, quality=95)
    return output_path


def _is_positive_topic(visual_topic="", context_title="", context_desc=""):
    text = f"{visual_topic} {context_title} {context_desc}".lower()
    positive_keys = ["moon", "surge", "up", "relief", "positive", "hype", "rush", "deal", "win", "rally"]
    negative_keys = ["panic", "shock", "stress", "down", "drop", "negative", "tariff", "tension", "inflation", "war", "attack", "crash"]
    pos = sum(1 for k in positive_keys if k in text)
    neg = sum(1 for k in negative_keys if k in text)
    return pos > neg


def _save_image_from_response(result, output_path):
    if not result.data or len(result.data) == 0:
        raise RuntimeError("이미지 생성 응답에 data가 없습니다.")

    image_url = getattr(result.data[0], "url", None)
    if not image_url:
        raise RuntimeError("이미지 생성 응답에 url이 없습니다.")

    response = requests.get(image_url, timeout=60)
    response.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(response.content)

    return output_path


def generate_bg(
    visual_topic="market_general",
    seed_text="",
    context_title="",
    context_desc="",
    output_path="bg.jpg"
):
    prompt = build_prompt(
        visual_topic=visual_topic,
        seed_text=seed_text,
        context_title=context_title,
        context_desc=context_desc,
    )

    print(f"[IMAGE] model={IMAGE_MODEL} quality={IMAGE_QUALITY} size={IMAGE_SIZE}")
    print(f"[IMAGE] topic={visual_topic}")

    result = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size=IMAGE_SIZE,
        quality=IMAGE_QUALITY,
    )

    _save_image_from_response(result, output_path)
    print(f"[IMAGE] saved: {output_path}")
    return output_path


def safe_generate_bg(
    visual_topic="market_general",
    seed_text="",
    context_title="",
    context_desc="",
    output_path="bg.jpg",
    title="",
    desc="",
    visual_variant="",
):
    if title and not context_title:
        context_title = title
    if desc and not context_desc:
        context_desc = desc

    try:
        return generate_bg(
            visual_topic=visual_topic,
            seed_text=seed_text or title,
            context_title=context_title,
            context_desc=context_desc,
            output_path=output_path,
        )
    except Exception as e:
        mood = "bright" if _is_positive_topic(visual_topic, context_title, context_desc) else "dark"
        print(f"[IMAGE ERROR] {repr(e)}")
        print(f"[IMAGE ERROR] fallback gradient used. mood={mood}")
        return _fallback_gradient(output_path=output_path, mood=mood)


def generate_carousel_bgs(visual_topic, seed_text, context_title="", context_desc=""):
    paths = []
    variants = SCENE_VARIANTS.get(visual_topic, SCENE_VARIANTS["market_general"])

    for i in range(3):
        output_path = f"bg_c{i}.jpg"
        try:
            variant_seed = f"{seed_text}_{i}"
            prompt = (
                COMMON_BASE
                + f"\nContext title: {context_title}"
                + f"\nContext desc: {context_desc[:160]}"
                + f"\n\nScene:\n{_stable_pick(variants, variant_seed)}"
            )

            print(f"[IMAGE CAROUSEL] card={i} topic={visual_topic}")

            result = client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                size=IMAGE_SIZE,
                quality=IMAGE_QUALITY,
            )

            _save_image_from_response(result, output_path)
            print(f"[IMAGE CAROUSEL] saved: {output_path}")
            paths.append(output_path)

        except Exception as e:
            mood = "bright" if _is_positive_topic(visual_topic, context_title, context_desc) else "dark"
            print(f"[IMAGE CAROUSEL ERROR] card={i} err={repr(e)}")
            _fallback_gradient(output_path=output_path, mood=mood)
            paths.append(output_path)

    return paths
