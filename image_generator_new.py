"""
image_generator_new.py — 강한 감정 / 강한 자극 / 고CTR용 이미지 생성기

방향:
- 무조건 썸네일형
- 감정 강함
- 자극 강함
- 좋은 뉴스는 기쁘고 들뜬 무드
- 나쁜 뉴스는 어둡고 불안한 무드
- 필요하면 살짝 웃긴 밈 에너지 포함
- 얼굴은 크고 선명하게
- 텍스트 올릴 왼쪽 공간 확보
- 실패 시에도 왜 실패했는지 로그가 남도록 구성
"""

import os
import base64
import random
import hashlib
from PIL import Image, ImageDraw, ImageFilter
from openai import OpenAI

OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY 환경변수가 비어 있습니다.")

client = OpenAI(api_key=OPENAI_API_KEY)

# 안정성 우선. Railway에서 dall-e-3 hd가 자주 실패하면 아래 두 줄만 바꿔서 테스트
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1")
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "high")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1536")

# ─────────────────────────────────────────────────────────────
# 공통 프롬프트
# ─────────────────────────────────────────────────────────────
COMMON_BASE = """
Create a HIGH-CTR photorealistic thumbnail image for a Korean finance Instagram account.

NON-NEGOTIABLE GOAL:
- This must stop scrolling instantly.
- The image must feel emotionally intense, dramatic, and highly clickable.
- It must look like a REAL photo, not generic AI art.

STYLE:
- photorealistic
- cinematic
- dark premium finance thumbnail
- highly emotional
- dramatic but believable
- Korean SNS thumbnail energy
- strong contrast
- expensive, sharp, clean, modern
- not flat, not corporate, not boring

COMPOSITION:
- One main subject only, unless scene explicitly requires two
- Face must be large, clear, fully visible, high detail
- Subject should be on RIGHT side of frame
- LEFT side must have dark empty negative space for Korean text overlay
- Upper-right face placement preferred
- Chest-up or waist-up framing, not tiny full body
- No clutter around the face
- Keep background supportive, not distracting

FACE / EMOTION RULES:
- Emotion must be STRONG
- If bullish / positive / relief / win:
  excited, thrilled, smug, euphoric, wild disbelief, victorious grin
- If bearish / negative / panic / war / inflation / risk:
  shocked, terrified, frozen, stressed, devastated, tense, doom expression
- If absurd or meme-worthy:
  include subtle comic energy without becoming cartoonish
- Expression must feel thumb-stopping

VISUAL RULES:
- Strong lighting contrast
- Dark background preferred
- Real skin texture
- Real eyes
- Real clothing folds
- Premium finance editorial look
- No bland office stock photo feeling

STRICTLY FORBIDDEN:
- no text
- no letters
- no numbers
- no logos
- no watermark
- no duplicated faces
- no collage
- no infographic
- no poster layout
- no anime look
- no plastic skin
- no flat vector vibe
- no washed-out lighting
- no white background
"""

# ─────────────────────────────────────────────────────────────
# 토픽별 프롬프트
# "자극적"이 핵심. 다만 주제에 따라 감정 방향을 다르게.
# ─────────────────────────────────────────────────────────────
SCENE_VARIANTS = {
    # ── BTC 상승 ─────────────────────────────────────────
    "btc_moon": [
        "Young Korean male trader in dark suit, mouth wide open in ecstatic disbelief, eyes lit up, one hand gripping hair, the other holding phone, giant glowing bitcoin aura behind him, dark luxury penthouse at night, money energy, dramatic gold-blue reflections, feels like he just saw insane profits",
        "Korean crypto guy with wild excited grin, eyebrows raised hard, phone in hand, body leaning forward as if he cannot believe the chart, premium dark room, glowing bitcoin symbol in blurred background, rich cinematic lighting, emotional and addictive thumbnail energy",
        "Korean investor half-laughing half-screaming in joy, shoulders tense, eyes wide, deep gold light on face, dark finance room, blurred upward market glow, subtle meme energy but still realistic and premium",
        "Young Korean businessman celebrating like a madman, fists tight, huge shocked smile, dark skyline behind him, gold neon reflections, bitcoin glow in background, high-adrenaline winning moment"
    ],

    # ── BTC 하락 ─────────────────────────────────────────
    "btc_panic": [
        "Korean male trader in black suit with devastated panic expression, hands on head, eyes frozen, mouth slightly open, deep red emergency glow, dark trading desk, bitcoin symbol blurred behind him, feels like catastrophic loss",
        "Young Korean investor staring in horror at phone, jaw dropped, cold sweat, dark room with red-blue lighting, background chart crash glow, premium but terrifying thumbnail energy",
        "Korean man collapsing emotionally in chair, one hand over mouth, eyes blank with panic, dark office, financial doom mood, cinematic shadows, loss and regret everywhere",
        "Korean trader with both fists at temples, furious and terrified expression, dark finance room, red bearish background glow, highly emotional crash moment"
    ],

    # ── ETH 상승 ─────────────────────────────────────────
    "eth_surge": [
        "Young Korean trader with explosive excited expression, eyes wide, one fist raised, blue ethereum glow behind him, futuristic dark premium finance room, altcoin season energy, intense and addictive",
        "Korean crypto investor laughing in disbelief, head slightly tilted back, bright blue light beams, dark room, intense upward momentum mood, cinematic and premium",
        "Korean trader in dark jacket with manic hopeful grin, blue neon reflections, phone in hand, powerful altcoin rally mood, realistic but highly emotional thumbnail"
    ],

    # ── ETH 하락 ─────────────────────────────────────────
    "eth_drop": [
        "Korean crypto investor in dark room with defeated expression, one hand on forehead, cold blue-red panic light, ethereum glow fading behind him, emotional pain and regret",
        "Young Korean trader with hollow shocked eyes, blue coin symbol blurred behind, tense jaw, dark premium room, altcoin panic mood, realistic and dramatic"
    ],

    # ── 유가 충격 ────────────────────────────────────────
    "oil_shock": [
        "Shocked Korean businessman holding gas receipt, eyes wide in horror, mouth open, orange-black industrial background, oil flames and tanker silhouette, feels like gas prices just exploded",
        "Korean office worker gripping steering wheel in panic, face tense and miserable, fiery orange refinery backdrop, oil shock atmosphere, dark and dramatic",
        "Korean man in suit screaming silently with both hands on head, giant oil tanker and refinery glow behind him, burning orange sky, apocalyptic fuel price shock",
        "Korean driver staring in dread at fuel cost situation, severe stress expression, industrial orange darkness, cinematic oil crisis energy"
    ],

    # ── 유가 완화 ────────────────────────────────────────
    "oil_relief": [
        "Korean businessman exhaling in relief with slight exhausted smile, warm sunrise over calm tanker route, soft orange-blue dawn, relief after chaos, premium but still emotional",
        "Korean driver relaxing slightly with tired half-smile, calmer industrial background, morning light, after-shock relief mood"
    ],

    # ── 금 급등 ──────────────────────────────────────────
    "gold_rush": [
        "Korean investor with greedy shocked smile, eyes locked on glowing gold bars, dark luxury vault, warm golden dramatic light, safe-haven rush energy, rich and intense",
        "Korean businessman gripping gold bar with disbelief and joy, expensive suit, vault background, powerful warm highlights, premium fear-trade thumbnail",
        "Older Korean investor with satisfied but intense expression, touching stacked gold bars, dark luxury scene, fear in market but joy in safe haven"
    ],

    # ── 금리 부정 ────────────────────────────────────────
    "rate_cut_doubt": [
        "Korean finance professional with stressed skeptical face, brow deeply furrowed, blue newsroom glow, macro anxiety mood, dark premium setting, feels like market expectations are collapsing",
        "Korean trader rubbing temples hard, exhausted and tense, dark finance room, cold blue light, interest-rate dread, emotionally heavy and realistic",
        "Korean macro investor with clenched jaw and worried eyes, tablet in hand, dark premium office, uncertainty and dread"
    ],

    # ── 금리 호재 ────────────────────────────────────────
    "rate_cut_hype": [
        "Korean trader with stunned hopeful grin, eyebrows raised, dark finance room with upward blue-green glow, market relief mood, premium and emotional",
        "Young Korean investor with eyes full of hope and disbelief, hands clasped together, dim premium room, rate-cut hype energy, dramatic but believable"
    ],

    # ── 인플레 충격 ───────────────────────────────────────
    "inflation_shock": [
        "Korean economist in suit with panic on face, tie slightly loose, hot orange and electric blue contrast, inflation disaster mood, dramatic and realistic",
        "Korean man checking grocery receipt with expression turning from confusion to horror, warm market lights, cost-of-living crisis energy",
        "Middle-aged Korean office worker staring at wallet in silent despair, dark warm background, inflation pain, deeply relatable"
    ],

    # ── 채권 스트레스 ─────────────────────────────────────
    "bond_stress": [
        "Senior Korean finance professional with tired, strained face, hand on forehead, dark institutional trading room, macro fatigue and bond stress mood",
        "Korean trader with dead tired stare, blue desaturated lighting, bond market pressure, premium gloom"
    ],

    # ── 주식 상승 ────────────────────────────────────────
    "stocks_up": [
        "Korean trader with controlled but intense winning smile, green market glow, premium dark newsroom, feels like a comeback rally",
        "Young Korean investor with excited disbelief and sharp eyes, dark finance room, rising stocks mood, premium and addictive thumbnail"
    ],

    # ── 주식 하락 ────────────────────────────────────────
    "stocks_down": [
        "Korean trader with hunched shoulders and stressed grimace, dark bear market room, heavy atmosphere, financial pressure everywhere",
        "Korean investor leaning over desk with worried face, dark premium setting, red market glow, risk-off panic mood"
    ],

    # ── 무역 긴장 ────────────────────────────────────────
    "trade_tension": [
        "Korean executive with tense face looking out over cargo port, orange industrial darkness, tariff pressure mood, cinematic macro tension",
        "Businessman watching shipping containers with grimace, dark orange-black background, trade war stress"
    ],

    # ── 무역 딜 기대 ─────────────────────────────────────
    "trade_deal_hype": [
        "Korean businessman with explosive relieved reaction, arms slightly raised, luxury boardroom, major deal just closed mood, intense but premium",
        "Two suited figures doing aggressive celebratory handshake, one with ecstatic grin, dark premium negotiation room, deal victory energy"
    ],

    # ── 중동 긴장 ────────────────────────────────────────
    "mideast_tension": [
        "Korean finance guy with grave shocked expression looking at phone, dark premium room, blurred tanker route and orange-red crisis sky behind, geopolitical panic mood",
        "Oil tanker silhouette under smoky orange-red sky, one worried Korean male foreground face in shock, high-stakes macro crisis thumbnail",
        "Korean trader staring in dread at geopolitical alert, dark room, orange war glow, oil route crisis mood"
    ],

    # ── 중동 완화 ────────────────────────────────────────
    "mideast_relief": [
        "Korean finance professional with stunned relief expression, calm sunrise over strategic sea route, warm dawn, tension finally easing but still intense",
        "Oil tanker in peaceful dawn light, Korean businessman exhaling deeply in relief, premium geopolitical calm-after-chaos mood"
    ],

    # ── 트럼프 관세 / 정책 ───────────────────────────────
    "trump_tariff": [
        "Donald Trump with aggressive determined expression, sharp hand gesture, dark premium room, tariff-war tension, high-stakes macro chaos energy",
        "Donald Trump pointing with stern intense face, dark dramatic backdrop, economic warfare mood, powerful and provocative thumbnail"
    ],

    "trump_deal_positive": [
        "Donald Trump with smug victorious grin, luxury boardroom mood, deal just worked, golden dramatic light, strong political-money thumbnail energy",
        "Donald Trump leaning forward with deeply satisfied smile, dark premium office, dealmaker success atmosphere"
    ],

    "trump_deal_negative": [
        "Donald Trump with irritated tense face, dark negotiation room, failed deal mood, frustration and uncertainty everywhere",
        "Donald Trump with skeptical frown, heavy dramatic shadow, deal breakdown energy"
    ],

    # ── 일반 ────────────────────────────────────────────
    "market_general": [
        "Korean finance professional with very intense focused face, dark premium newsroom, sharp contrast, strong market tension, addictive finance thumbnail",
        "Young Korean investor with raised eyebrow and shocked half-smile, dark cinematic office, money and market energy, believable but highly emotional",
        "Korean businessman in suit with strong reaction face, dark luxury finance room, premium editorial mood, scroll-stopping"
    ],
}

# ─────────────────────────────────────────────────────────────
# 보조 유틸
# ─────────────────────────────────────────────────────────────
def pick_variant(visual_topic, seed_text=""):
    variants = SCENE_VARIANTS.get(visual_topic, SCENE_VARIANTS["market_general"])
    if seed_text:
        h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
        return variants[h % len(variants)]
    return random.choice(variants)


def infer_emotion_hint(visual_topic, context_title="", context_desc=""):
    text = f"{visual_topic} {context_title} {context_desc}".lower()

    positive_keys = [
        "moon", "surge", "up", "relief", "positive", "hype", "rush",
        "deal", "cut", "win", "breakout", "rally"
    ]
    negative_keys = [
        "panic", "shock", "stress", "down", "drop", "negative",
        "tariff", "tension", "inflation", "war", "attack", "crash", "doubt"
    ]

    pos = sum(1 for k in positive_keys if k in text)
    neg = sum(1 for k in negative_keys if k in text)

    if pos > neg:
        return """
EMOTIONAL DIRECTION:
- positive
- exciting
- euphoric
- thrilling
- smug winning energy allowed
- slightly funny meme energy allowed if it increases click-through
"""
    return """
EMOTIONAL DIRECTION:
- negative
- dark
- shocking
- stressful
- anxiety-heavy
- doomy
- if suitable, slightly absurd panic energy allowed to increase click-through
"""


def build_prompt(visual_topic="market_general", seed_text="", context_title="", context_desc=""):
    scene = pick_variant(visual_topic, seed_text=seed_text)
    emotion_hint = infer_emotion_hint(visual_topic, context_title, context_desc)

    context = ""
    if context_title:
        context = f"""
CONTENT CONTEXT (for mood reference only, DO NOT put text in the image):
- title: {context_title}
- description: {context_desc[:160]}
"""

    extra_push = """
ADDITIONAL CLICK-THROUGH BOOST:
- Make the subject look like they just witnessed something life-changing
- Expression should feel instantly readable on a phone screen
- Do not make it classy-boring; make it emotionally impossible to ignore
- Premium, but provocative
- Realistic, but intense
"""

    return COMMON_BASE + "\n" + emotion_hint + "\n" + extra_push + "\n" + context + "\nSCENE:\n" + scene


def _fallback_gradient(output_path="bg.jpg", mood="dark"):
    w, h = 1024, 1536
    base = (10, 12, 20) if mood == "dark" else (30, 25, 18)
    img = Image.new("RGB", (w, h), base)
    draw = ImageDraw.Draw(img)

    if mood == "bright":
        top_color = (45, 35, 20)
        bottom_color = (80, 55, 25)
    else:
        top_color = (10, 12, 20)
        bottom_color = (26, 16, 35)

    for y in range(h):
        ratio = y / max(h - 1, 1)
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    for i in range(160):
        alpha = int(50 * (1 - i / 160))
        draw.ellipse(
            (w - 340 - i, h - 500 - i, w + i, h + i),
            outline=(120, 80, 25, alpha)
        )

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


# ─────────────────────────────────────────────────────────────
# 실제 생성
# ─────────────────────────────────────────────────────────────
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
    print(f"[IMAGE] topic={visual_topic} seed={seed_text[:40]}")
    print(f"[IMAGE] prompt preview={prompt[:300]} ...")

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

    print(f"[IMAGE] bg saved: {output_path}")
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
        variant = variants[i % len(variants)]
        emotion_hint = infer_emotion_hint(visual_topic, context_title, context_desc)
        prompt = COMMON_BASE + "\n" + emotion_hint + """
ADDITIONAL CLICK-THROUGH BOOST:
- Make it intense
- Make it emotional
- Make it highly clickable
- Do not become cartoonish
""" + f"\nSCENE:\n{variant}"

        output_path = f"bg_c{i}.jpg"

        try:
            print(f"[IMAGE CAROUSEL] generating card={i} topic={visual_topic}")
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