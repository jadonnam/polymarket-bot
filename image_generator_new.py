"""
image_generator_new.py — DALL-E 이미지 생성 (밈/자극 강화 + 변형 다양화)

변경사항:
- 프롬프트 "밈 에너지" 강화: 과장된 표정, 드라마틱한 리액션
- visual_variant 랜덤 선택 (매번 다른 이미지)
- 캐러셀용 3장 연속 생성 지원
- 폴백 그라디언트 개선
"""

import os
import base64
import random
import hashlib
from PIL import Image, ImageDraw, ImageFilter
from openai import OpenAI

client = OpenAI(api_key=(os.getenv("OPENAI_API_KEY") or "").strip())

IMAGE_MODEL   = os.getenv("IMAGE_MODEL", "dall-e-3")
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "hd")


# ── 공통 프롬프트 베이스 ────────────────────────────────────
COMMON_BASE = """
Create a photorealistic image for a Korean finance SNS account.

CRITICAL STYLE:
- Must look like a REAL photograph, NOT AI-generated
- Photojournalism quality: sharp, natural lighting, authentic skin texture
- Korean finance thumbnail energy: one person with a strong but realistic emotional reaction
- The face must be FULLY VISIBLE — the most important element
- Subject takes up right 55% of frame, face clearly visible in upper portion
- Left 45% intentionally dark/empty for Korean text overlay
- NO softbox lighting, NO studio look — dramatic natural or environmental light
- High contrast, deep shadows, cinematic but raw and authentic
- Dark background: night city, dark office, dim room — never bright or white

FACE REQUIREMENTS:
- Strong expression: open mouth or tense face, hands on head optional, realistic eyes and skin detail
- Must look like a real Korean person caught in a genuine emotional moment
- Think: premium finance thumbnail, cinematic and believable
- Face positioned in UPPER RIGHT of frame so bottom text doesnt cover it

STRICT NO:
- No text, letters, numbers, watermarks, logos
- No plastic skin, no surreal anatomy, no poster-like fantasy look  
- No studio lighting or white backgrounds
- No split panels, collages, duplicate faces
- No nudity or inappropriate content
"""

# ── 씬별 프롬프트 ────────────────────────────────────────────
SCENE_VARIANTS = {

    # ── BTC 상승 ─────────────────────────────────────────────
    "btc_moon": [
        "Young Korean-looking male in expensive suit, jaw literally dropping open in disbelief, eyes bulging wide, both hands gripping head, giant glowing bitcoin coin floating in background, dark luxury penthouse at night, gold and blue neon reflections",
        "20s Korean guy in semi-formal outfit screaming silently with fists clenched in the air, celebrating enormous profit, giant realistic bitcoin coin behind him, dramatic upward gold light beams, dark city skyline",
        "Korean trader in shock-smile hybrid expression, one hand pointing at something off-screen, the other covering mouth, blurred bitcoin chart glow in background, dark premium trading desk",
        "Young man with wild excited eyes and manic grin, phone in hand, bitcoin price notification visible concept (no actual text), champagne bottle nearby, dark luxury room",
    ],

    # ── BTC 하락 ─────────────────────────────────────────────
    "btc_panic": [
        "Korean man in suit with hands covering face in despair, peeking through fingers with terrified expression, bitcoin coin with red aura in background, dark trading room, dramatic red lighting",
        "Young trader with horror-movie expression, hands gripping head, sweating, dark finance room, red emergency lighting atmosphere, chaos energy",
        "Korean guy slumped in chair with dead eyes, defeated expression, dark office, cold blue light, existential dread mood",
        "Man with both fists pressing against temples, eyes squeezed shut, grimacing in financial pain, dark premium room, deep shadows",
    ],

    # ── 유가 충격 ────────────────────────────────────────────
    "oil_shock": [
        "Shocked Korean businessman in suit holding a gas station receipt with expression of absolute horror, mouth wide open screaming, gas pump nozzle visible, industrial orange-black background, fire and oil tanker silhouette",
        "Korean man in office clothes grabbing steering wheel with white knuckles, face twisted in agony as he looks at gas price display (no text visible), fiery orange industrial backdrop",
        "Businessman with both hands on sides of head screaming, massive oil refinery and tankers behind him, dramatic orange-red sunset, apocalyptic energy atmosphere",
        "Korean man in suit pointing frantically at something off-screen with jaw dropped, giant oil tanker port behind him, burning orange sky, extreme shock reaction",
    ],

    # ── 유가 안정 ────────────────────────────────────────────
    "oil_relief": [
        "Korean man exhaling deeply in relief, eyes closed, slight smile, oil tanker crossing calm sea at sunrise, warm golden light, tension easing mood",
        "Businessman with relieved half-smile looking upward, industrial port background, calmer orange-blue dawn lighting",
    ],

    # ── 금값 ─────────────────────────────────────────────────
    "gold_rush": [
        "Korean investor with wide greedy eyes and huge smile, surrounded by stacks of gleaming gold bars, warm vault lighting, rich premium atmosphere, wealth obsession energy",
        "Man in expensive suit gently cradling a gold bar like it is precious, eyes lit up with pure joy, luxury safe room, warm golden ambient light",
        "Korean businessman pumping fist in air with ecstatic expression, realistic gold bars glowing behind him, premium dark warm room, winner energy",
        "Older Korean man with knowing satisfied smile touching gold bar stack, dark luxury background, safe-haven rush mood",
    ],

    # ── 금리 의심 ────────────────────────────────────────────
    "rate_cut_doubt": [
        "Wall Street-style Korean trader with deeply furrowed brow and stressed expression, staring intensely at something off-screen, dark blue trading floor with blurred screens, anxiety and tension",
        "Korean man in suit rubbing temples with both hands, eyes closed, exhausted stressed face, cool blue finance newsroom, macro dread atmosphere",
        "Trader with half-grimace expression, one eyebrow raised skeptically, tablet in hand, dark blue premium office, uncertainty mood",
        "Korean finance guy with clenched jaw and worried eyes, staring into distance, blurred market data glow behind him, tense serious mood",
    ],

    # ── 금리 기대 ────────────────────────────────────────────
    "rate_cut_hype": [
        "Korean trader with cautious excited expression, eyebrows raised, slight hopeful smile, blurred green trading screens behind, premium blue-green newsroom, cautious optimism",
        "Young Korean investor with wide hopeful eyes, hands clasped together, dark finance room with soft upward lighting, anticipation mood",
    ],

    # ── 트럼프 긍정 ──────────────────────────────────────────
    "trump_positive": [
        "Donald Trump with supremely confident winner smirk, arms crossed, warm golden presidential spotlight, power and dominance mood, premium political atmosphere",
        "Donald Trump with raised fist and triumphant expression, dramatic warm lighting from above, luxury political setting, deal-maker victorious energy",
    ],

    # ── 트럼프 부정 ──────────────────────────────────────────
    "trump_negative": [
        "Donald Trump with furious red-faced expression, finger pointing aggressively, smoky dark dramatic room, conflict and chaos energy, high-stakes atmosphere",
        "Donald Trump mid-shout with intense angry expression, dark dramatic backdrop, economic shock mood, forceful chaotic energy",
    ],

    # ── 트럼프 관세 ──────────────────────────────────────────
    "trump_tariff": [
        "Donald Trump with aggressive confident expression making sharp hand gesture, dark room with industrial/trade backdrop, tariff-war tension mood, forceful economic policy energy",
        "Donald Trump pointing directly at viewer with stern determined expression, dark premium room, economic warfare mood, high stakes atmosphere",
    ],

    # ── 트럼프 딜 긍정 ───────────────────────────────────────
    "trump_deal_positive": [
        "Donald Trump with massive satisfied smug grin, leaning forward, luxury boardroom, deal-maker champion energy, premium negotiation victory mood",
        "Donald Trump with clasped hands and calculating satisfied smile, dark luxury office, powerful deal closed atmosphere",
    ],

    # ── 트럼프 딜 부정 ───────────────────────────────────────
    "trump_deal_negative": [
        "Donald Trump with irritated dismissive expression, arms slightly spread, tense negotiation room, deal-breaking frustrated energy",
        "Donald Trump with skeptical frowning face, dark premium room, failed negotiation mood",
    ],

    # ── 인플레이션 ───────────────────────────────────────────
    "inflation_shock": [
        "Korean economist in suit with mouth open in shock, eyes wide, grabbing tie in panic, hot orange and electric blue contrast lighting, CPI shock atmosphere, economic emergency mood",
        "Korean man checking grocery receipt with progressively worsening expression turning to horror, orange warm market lighting, inflation reality hitting hard mood",
        "Middle-aged Korean man in suit with defeated face looking at wallet, dark warm lighting, cost-of-living crisis mood, relatable economic despair",
    ],

    # ── 채권 스트레스 ────────────────────────────────────────
    "bond_stress": [
        "Senior Korean finance professional with tired stress-lined face, one hand on forehead, dark bond trading room atmosphere, institutional worry mood",
        "Korean trader staring blankly with thousand-yard stare, bond market pressure, cool blue desaturated lighting, macroeconomic fatigue",
    ],

    # ── 주식 상승 ────────────────────────────────────────────
    "stocks_up": [
        "Korean trader with barely-contained excitement, subtle winning smile with raised eyebrows, green market glow behind, premium newsroom, controlled euphoria",
        "Young Korean investor with cautious thumbs up and excited eyes, dark finance room, rising market energy, cautious optimism",
    ],

    # ── 주식 하락 ────────────────────────────────────────────
    "stocks_down": [
        "Korean trader with hunched shoulders and stressed expression, dark trading floor, bearish pressure atmosphere, macro weight of the world",
        "Korean investor with both hands pressing on desk, leaning forward with worried grimace, dark bear market room, heavy atmosphere",
    ],

    # ── 무역딜 ──────────────────────────────────────────────
    "trade_deal_hype": [
        "Two figures in expensive suits doing aggressive celebratory handshake, one with massive ecstatic grin, luxury dark boardroom, deal-closing victory energy",
        "Korean businessman with explosive celebratory reaction, arms raised, luxury negotiation room, major deal just closed mood",
    ],

    # ── 무역 긴장 ────────────────────────────────────────────
    "trade_tension": [
        "Korean executive with tense furrowed brow watching cargo port from window, dark orange industrial atmosphere, tariff pressure mood, macro stress",
        "Businessman with grimace watching shipping containers in distance, darker orange-black trade tension atmosphere",
    ],

    # ── 중동 긴장 ────────────────────────────────────────────
    "mideast_tension": [
        "Oil tanker silhouette under dramatic smoky orange-red sky, strategic chokepoint atmosphere, geopolitical risk premium mood, cinematic macro crisis scene",
        "Korean finance professional with grave expression looking at phone, oil route map concept in blurred background, geopolitical stress mood, dark premium setting",
    ],

    # ── 중동 완화 ────────────────────────────────────────────
    "mideast_relief": [
        "Oil tanker under sunrise, calmer strategic sea route, golden dawn reflecting on water, relief after tension mood, ceasefire energy",
    ],

    # ── 정치 부정 ────────────────────────────────────────────
    "politics_negative": [
        "Tense Washington-style press room, worried Korean-looking political aide with phone, dark high-stakes atmosphere, drama and uncertainty mood",
    ],

    # ── 이더리움 상승 ────────────────────────────────────────
    "eth_surge": [
        "Young Korean trader with manic excited expression, blue ethereum glow surrounding him, futuristic dark finance set, altcoin season energy, controlled chaos",
        "Korean crypto investor pumping both fists in air, electric blue light beams, dark premium room, altcoin euphoria",
    ],

    # ── 이더리움 하락 ────────────────────────────────────────
    "eth_drop": [
        "Korean trader with hands covering face, peeking through fingers, blue-red stressed lighting, dark crypto trading room, altcoin panic mood",
        "Young investor with slack-jawed expression of disbelief, cold blue light, dark premium setting, crypto disappointment",
    ],

    # ── 일반 ────────────────────────────────────────────────
    "market_general": [
        "Korean finance professional with intensely focused expression, dark premium newsroom, cinematic macro atmosphere, editorial finance magazine mood",
        "Korean investor with calculating expression, one hand on chin, dark luxury finance room, market analysis mood",
        "Young Korean trader with raised eyebrow and slight smirk, dark blue premium setting, sharp market instinct energy",
    ],
}


def pick_variant(visual_topic, seed_text=""):
    """시드 기반 랜덤 변형 선택 (같은 뉴스는 항상 같은 이미지)"""
    variants = SCENE_VARIANTS.get(visual_topic, SCENE_VARIANTS["market_general"])
    if seed_text:
        h = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
        return variants[h % len(variants)]
    return random.choice(variants)


def build_prompt(visual_topic="market_general", seed_text="", context_title="", context_desc=""):
    scene = pick_variant(visual_topic, seed_text=seed_text)

    context = ""
    if context_title:
        context = f"\nContent context (for mood reference only, DO NOT add text):\n{context_title}"
        if context_desc:
            context += f" — {context_desc[:80]}"

    return COMMON_BASE + context + f"\n\nSCENE:\n{scene}"


def _fallback_gradient(output_path="bg.jpg"):
    """API 실패 시 폴백 그라디언트 이미지"""
    w, h = 1024, 1536
    img = Image.new("RGB", (w, h), (10, 12, 20))
    draw = ImageDraw.Draw(img)

    # 어두운 그라디언트
    for y in range(h):
        ratio = y / max(h - 1, 1)
        r = int(10 * (1 - ratio) + 28 * ratio)
        g = int(12 * (1 - ratio) + 18 * ratio)
        b = int(20 * (1 - ratio) + 35 * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # 우측 하단 광원 효과
    for i in range(120):
        alpha = int(40 * (1 - i / 120))
        draw.ellipse(
            (w - 300 - i, h - 400 - i, w + i, h + i),
            outline=(80, 60, 20, alpha)
        )

    img = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    img.save(output_path, quality=95)
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

    print(f"[DALL-E] bg saved: {output_path}")
    return output_path


def safe_generate_bg(
    visual_topic="market_general",
    seed_text="",
    context_title="",
    context_desc="",
    output_path="bg.jpg",
    # 하위 호환성 (기존 card.py가 이 파라미터들을 넘김)
    title="",
    desc="",
    visual_variant="",
):
    # 기존 호환 파라미터 처리
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
        print(f"[DALL-E ERROR] {e}")
        return _fallback_gradient(output_path=output_path)


def generate_carousel_bgs(visual_topic, seed_text, context_title="", context_desc=""):
    """
    캐러셀용 3장 이미지 생성
    같은 토픽이지만 서로 다른 변형으로 생성
    """
    paths = []
    variants = SCENE_VARIANTS.get(visual_topic, SCENE_VARIANTS["market_general"])

    for i in range(3):
        # 카드별로 다른 변형 선택
        variant = variants[i % len(variants)]
        prompt = COMMON_BASE + f"\n\nSCENE:\n{variant}"

        output_path = f"bg_c{i}.jpg"

        try:
            result = client.images.generate(
                model=IMAGE_MODEL,
                prompt=prompt,
                size="1024x1536",
                quality=IMAGE_QUALITY,
            )
            image_b64 = result.data[0].b64_json
            image_bytes = base64.b64decode(image_b64)
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            print(f"[DALL-E] carousel bg {i} saved: {output_path}")
            paths.append(output_path)

        except Exception as e:
            print(f"[DALL-E carousel ERROR] card {i}: {e}")
            _fallback_gradient(output_path=output_path)
            paths.append(output_path)

    return paths
