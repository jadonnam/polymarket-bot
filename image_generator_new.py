import os
import base64
import hashlib
from openai import OpenAI
from PIL import Image, ImageDraw, ImageFilter

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 환경변수가 비어 있습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)

IMAGE_MODEL = os.getenv("IMAGE_MODEL", "dall-e-3")
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "hd")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1536")


COMMON_BASE = """
Create a photorealistic, high-CTR thumbnail image for a Korean finance Instagram account.

Rules:
- Must look like a real photograph
- One main subject only
- Strong emotional face
- Subject on the right side
- Left side must remain darker and emptier for Korean text overlay
- Dark cinematic background
- No text, no watermark, no logo, no collage
- Premium but provocative thumbnail energy
"""

SCENE_VARIANTS = {
    "btc_moon": [
        "Young Korean male trader in dark suit, ecstatic disbelief, eyes wide, strong bitcoin rally mood, dark luxury room, glowing gold-blue reflections",
        "Korean investor with shocked smile, phone in hand, bitcoin glow in background, dark premium finance thumbnail"
    ],
    "btc_panic": [
        "Korean trader in suit with panic expression, hands on head, red bearish mood, dark trading room",
        "Young Korean investor staring in horror at phone, cold red-blue lighting, crypto crash mood"
    ],
    "oil_shock": [
        "Shocked Korean businessman, industrial orange-black background, oil refinery glow, fuel price shock mood",
        "Korean office worker with stressed expression, dark industrial backdrop, oil crisis mood"
    ],
    "oil_relief": [
        "Korean businessman with slight relieved expression, warm sunrise over tanker route, calmer oil market mood"
    ],
    "gold_rush": [
        "Korean investor with intense satisfied smile, gold bars glowing behind him, dark luxury vault"
    ],
    "rate_cut_doubt": [
        "Korean finance professional with worried macro expression, dark blue finance room, tense rate market mood"
    ],
    "rate_cut_hype": [
        "Korean trader with stunned hopeful grin, dark premium finance room, upward blue-green glow"
    ],
    "trump_tariff": [
        "Donald Trump with aggressive determined expression, dark dramatic backdrop, tariff tension mood"
    ],
    "trump_deal_positive": [
        "Donald Trump with smug victorious grin, luxury boardroom mood, deal success energy"
    ],
    "trump_deal_negative": [
        "Donald Trump with irritated tense face, dark negotiation room, failed deal mood"
    ],
    "inflation_shock": [
        "Korean office worker checking receipt with horrified face, inflation pain mood, dark warm lighting"
    ],
    "bond_stress": [
        "Senior Korean finance professional with tired stressed face, dark institutional trading room"
    ],
    "stocks_up": [
        "Korean trader with winning smile, green market glow, premium dark newsroom"
    ],
    "stocks_down": [
        "Korean investor with stressed grimace, dark bear market room, red market glow"
    ],
    "trade_tension": [
        "Korean executive with tense face at cargo port, orange industrial darkness, trade war stress"
    ],
    "trade_deal_hype": [
        "Korean businessman with explosive relieved reaction, dark premium boardroom, major deal closed mood"
    ],
    "mideast_tension": [
        "Korean finance guy with grave shocked expression, orange-red geopolitical crisis glow, tanker route tension mood"
    ],
    "mideast_relief": [
        "Korean businessman exhaling in relief, calm sunrise sea route, tension easing mood"
    ],
    "eth_surge": [
        "Young Korean trader with explosive excited expression, blue ethereum glow, dark premium finance room"
    ],
    "eth_drop": [
        "Korean crypto investor with defeated shocked face, blue-red panic light, dark crypto room"
    ],
    "market_general": [
        "Korean finance professional with intense focused face, dark premium newsroom, strong market tension"
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
        context += f"\nContext desc: {context_desc[:140]}"

    return COMMON_BASE + context + f"\n\nScene:\n{scene}"


def _fallback_gradient(output_path="bg.jpg", mood="dark"):
    w, h = 1024, 1536
    img = Image.new("RGB", (w, h), (10, 12, 20))
    draw = ImageDraw.Draw(img)

    if mood == "bright":
        top_color = (32, 24, 14)
        bottom_color = (70, 44, 20)
    else:
        top_color = (10, 12, 20)
        bottom_color = (24, 16, 30)

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

    image_b64 = result.data[0].b64_json
    if not image_b64:
        raise RuntimeError("이미지 생성 응답에 b64_json이 없습니다.")

    image_bytes = base64.b64decode(image_b64)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

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
            prompt = COMMON_BASE + f"\nContext title: {context_title}\nContext desc: {context_desc[:140]}\n\nScene:\n{_stable_pick(variants, variant_seed)}"

            print(f"[IMAGE CAROUSEL] card={i} topic={visual_topic}")

            result = client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                size=IMAGE_SIZE,
                quality=IMAGE_QUALITY,
            )

            image_b64 = result.data[0].b64_json
            if not image_b64:
                raise RuntimeError("캐러셀 이미지 응답에 b64_json이 없습니다.")

            image_bytes = base64.b64decode(image_b64)
            with open(output_path, "wb") as f:
                f.write(image_bytes)

            print(f"[IMAGE CAROUSEL] saved: {output_path}")
            paths.append(output_path)

        except Exception as e:
            mood = "bright" if _is_positive_topic(visual_topic, context_title, context_desc) else "dark"
            print(f"[IMAGE CAROUSEL ERROR] card={i} err={repr(e)}")
            _fallback_gradient(output_path=output_path, mood=mood)
            paths.append(output_path)

    return paths
