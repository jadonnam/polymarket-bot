"""
인스타 카드뉴스(4:5) — 이슈 기사 → OpenAI 카피 → 텔레그램에
「이미지 AI에 바로 붙여넣을 완성 프롬프트」+ 인스타 캡션 전송.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import news as news_module

_WEEKDAY_KO = "월화수목금토일"
_DISCLAIMER = (
    "※ 정리용 · 투자 권유 아님 · 레버·청산·슬리피지·거래소·규제 리스크 전제."
)

FINISHED_CARD_IMAGE_TEMPLATE = """Create ONE finished Korean financial Instagram news card, 1080×1350px, 4:5 vertical (BoA / Korean brokerage style).

━━━ COPY THESE KOREAN LINES VERBATIM (do NOT replace with other news) ━━━
Line 1: 「{line1}」
Line 2: 「{line2}」

━━━ BACKGROUND must match the Korean headline story (same event) ━━━
{visual_scene}

━━━ FORBIDDEN background (unless headline is about NYSE/listings) ━━━
New York Stock Exchange building, Wall Street street canyon, giant US flag on exchange facade, generic traders with tablets.

━━━ LAYOUT ━━━
Photorealistic editorial photo, upper 58% = background. Bottom 42%: smooth black gradient (~95% black at bottom).
White Korean Gothic text bottom-left (48px left, 72px bottom margin), line1 bold larger, line2 smaller, 1px soft shadow only.
No charts, candlesticks, logos, watermarks, English text in image."""


@dataclass
class InstagramCardPack:
    line1: str
    line2: str
    caption: str
    topic: str
    visual_scene_en: str

# desk_briefing 경로용 (텔레그램 프롬프트 전송과 별개)
_DESK_REF = """① 헤드 · ② 해석 · ③ 볼 것 — 한국어 데스크 노트."""

SYSTEM_PROMPT = f"""You are a Korean market editor.

Output JSON only:
{{
  "card_line1": "...",
  "card_line2": "...",
  "head_lead": "...",
  "head_bullets": ["...", "..."],
  "interpretation": "...",
  "watch": "..."
}}

Card lines: Korean Instagram 4:5 card style (max ~28 / ~55 chars).
{_DESK_REF}
"""


@dataclass
class ReferencePack:
    card_line1: str
    card_line2: str
    head_lead: str
    head_bullets: List[str]
    interpretation: str
    watch: str
    raw_json: Dict[str, Any]


def now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def _desk_brand() -> str:
    return (os.getenv("DESK_BRIEFING_BRAND") or "자돈남 DESK").strip() or "자돈남 DESK"


def _format_header(dt: Optional[datetime] = None) -> str:
    dt = dt or now_kst()
    wd = _WEEKDAY_KO[dt.weekday()]
    score = min(10, max(6, int(os.getenv("DESK_SCORE_DEFAULT") or "10")))
    return (
        f"{_desk_brand()} · 🇰🇷 한국 · {dt.month}/{dt.day}({wd}) · "
        f"{dt.hour:02d}:{dt.minute:02d} KST\n〔{score}/10〕"
    )


def _news_block(articles: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for i, a in enumerate((articles or [])[:8], 1):
        t = news_module.clean_spaces(a.get("title", "") or "")
        d = news_module.clean_spaces(a.get("description", "") or "")[:220]
        src = news_module.article_source_name(a)
        lines.append(f"{i}. [{src}] {t}\n   {d}")
    return "\n".join(lines) or "(no articles)"


_QUOTE_LABELS = {
    "KOSPI": "코스피",
    "KOSDAQ": "코스닥",
    "NQ_FUT": "나스닥선물",
    "WTI": "WTI유",
    "USDKRW": "원·달러",
    "US10Y": "美10년국채",
    "BTC": "비트코인",
    "GOLD": "금",
}


def _quotes_block(market_data: Dict[str, Any]) -> str:
    q = (market_data or {}).get("quotes", {})
    if not isinstance(q, dict):
        return ""
    parts: List[str] = []
    for sym in ("KOSPI", "KOSDAQ", "NQ_FUT", "WTI", "USDKRW", "US10Y", "BTC", "GOLD"):
        row = q.get(sym, {})
        if not isinstance(row, dict):
            continue
        chg = row.get("chg_pct")
        if chg is None:
            continue
        label = _QUOTE_LABELS.get(sym, sym)
        sign = "+" if float(chg) > 0 else ""
        parts.append(f"{label} {sign}{chg}%")
    return " · ".join(parts)


def _related_tags(market_data: Dict[str, Any], articles: List[Dict[str, Any]]) -> List[str]:
    blob = " ".join(
        f"{a.get('title', '')} {a.get('description', '')}" for a in (articles or [])[:6]
    ).lower()
    tags: List[str] = []
    rules = [
        (("kospi", "코스피", "증시"), "KOSPI"),
        (("환율", "원달러", "usdkrw"), "환율"),
        (("외국인",), "외국인"),
        (("반도체", "nvidia", "삼성", "하이닉"), "반도체"),
        (("유가", "oil", "wti", "opec"), "유가"),
        (("금리", "fed", "cpi", "국채"), "금리"),
    ]
    for keys, label in rules:
        if any(k in blob for k in keys) and label not in tags:
            tags.append(label)
    return tags[:5] or ["KOSPI", "환율", "외국인"]


def generate_reference_pack(
    articles: List[Dict[str, Any]],
    *,
    market_data: Optional[Dict[str, Any]] = None,
    lead_article: Optional[Dict[str, Any]] = None,
) -> ReferencePack:
    """OPENAI_API_KEY 필수(권장). 레퍼런스 프롬프트 1회 호출."""
    md = market_data if isinstance(market_data, dict) else {}
    arts = list(articles or [])
    if lead_article and lead_article not in arts:
        arts = [lead_article] + arts

    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return _fallback_pack(arts, lead_article)

    try:
        from openai import OpenAI
    except Exception as e:
        print(f"[reference_pipeline] openai import failed: {repr(e)}")
        return _fallback_pack(arts, lead_article)

    model = (os.getenv("OPENAI_HEADLINE_MODEL") or "gpt-4o-mini").strip()
    user = (
        "LEAD ARTICLE:\n"
        + news_module.clean_spaces((lead_article or arts[0] if arts else {}).get("title", "") or "")
        + "\n\nALL NEWS:\n"
        + _news_block(arts)
        + "\n\nMARKET:\n"
        + _quotes_block(md)
    )
    try:
        client = OpenAI(api_key=key)
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=700,
        )
        d = json.loads((r.choices[0].message.content or "").strip())
        print("[reference_pipeline] openai reference pack ok")
    except Exception as e:
        print(f"[reference_pipeline] openai failed: {repr(e)}")
        return _fallback_pack(arts, lead_article)

    return _pack_from_dict(d)


def _pack_from_dict(d: Dict[str, Any]) -> ReferencePack:
    bullets = [str(b).strip() for b in (d.get("head_bullets") or []) if str(b).strip()]
    c1 = str(d.get("card_line1") or "").strip()
    if c1 and not c1.endswith((",", "，")) and len(c1) < 32:
        c1 = c1 + ","
    return ReferencePack(
        card_line1=c1[:90],
        card_line2=str(d.get("card_line2") or "").strip()[:140],
        head_lead=str(d.get("head_lead") or "").strip()[:120],
        head_bullets=bullets[:4],
        interpretation=str(d.get("interpretation") or "").strip()[:120],
        watch=str(d.get("watch") or "").strip()[:120],
        raw_json=d,
    )


def _fallback_pack(
    articles: List[Dict[str, Any]], lead_article: Optional[Dict[str, Any]]
) -> ReferencePack:
    lead = lead_article or (articles[0] if articles else {})
    title = news_module.clean_spaces(lead.get("title", "") or "")[:80]
    return ReferencePack(
        card_line1=(title[:26] + ",") if title else "시장 이슈,",
        card_line2="변수·수급·환율 흐름을 함께 확인",
        head_lead=title or "글로벌 시장 변수 점검",
        head_bullets=[
            news_module.clean_spaces(a.get("title", "") or "")[:48]
            for a in articles[1:4]
            if news_module.clean_spaces(a.get("title", "") or "")
        ],
        interpretation="한국장은 시초가 갭·외국인·환율·선물 포지션부터 확인.",
        watch="코스피·환율·외국인·NQ·반도체 대형주 동시.",
        raw_json={},
    )


def sanitize_card_korean(text: str) -> str:
    """이미지 AI·LLM 흔한 오타 보정 (코스파→코스피 등)."""
    t = str(text or "").strip()
    if not t:
        return t
    fixes = (
        ("코스파", "코스피"),
        ("코스피피", "코스피"),
        ("코스닥", "코스닥"),
        ("나스닥크", "나스닥"),
    )
    for bad, good in fixes:
        t = t.replace(bad, good)
    return t


def apply_pack_to_article(
    article: Dict[str, Any], pack: Any
) -> Dict[str, Any]:
    a = dict(article)
    if isinstance(pack, InstagramCardPack):
        a["_ko_line1"] = sanitize_card_korean(pack.line1)
        a["_ko_line2"] = sanitize_card_korean(pack.line2)
        a["_instagram_caption"] = pack.caption
        a["_card_topic"] = pack.topic
    else:
        a["_ko_line1"] = sanitize_card_korean(pack.card_line1)
        a["_ko_line2"] = sanitize_card_korean(pack.card_line2)
    return a


def format_desk_telegram_message(
    pack: ReferencePack,
    *,
    articles: List[Dict[str, Any]],
    lead_article: Optional[Dict[str, Any]] = None,
    market_data: Optional[Dict[str, Any]] = None,
    dt: Optional[datetime] = None,
) -> str:
    head_lines = [f"· {pack.head_lead}"] if pack.head_lead else []
    for b in pack.head_bullets:
        head_lines.append(f"· {b}")

    parts = [
        _format_header(dt),
        "",
        "① 헤드",
        *head_lines,
        "",
        "② 해석",
        f"· {pack.interpretation}" if pack.interpretation else "· 한국장 영향은 수급·환율부터 확인.",
        "",
        "③ 볼 것",
        f"· {pack.watch}" if pack.watch else "· 코스피·환율·외국인·미국 선물 동시.",
    ]

    src = lead_article or ((articles or [None])[0])
    url = str((src or {}).get("url") or "").strip()
    src_name = news_module.article_source_name(src) if src else ""
    if url:
        parts.extend(["", f"🔗 {url}"])
    if src_name:
        parts.append(f"출처: {src_name}")
    rel = _related_tags(market_data or {}, articles)
    if rel:
        parts.append(f"관련: {' · '.join(rel)}")
    parts.extend(["", _DISCLAIMER])
    text = "\n".join(parts).strip()
    if len(text) > 4090:
        text = text[:4087] + "…"
    return text


def get_system_prompt_for_debug() -> str:
    return SYSTEM_PROMPT


def collect_articles_for_prompt(
    articles: List[Dict[str, Any]],
    lead_article: Dict[str, Any],
    *,
    max_items: int = 10,
) -> List[Dict[str, Any]]:
    """리드 + 풀에서 점수 상위 기사를 묶어 프롬프트 입력을 풍부하게."""
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    def _add(a: Optional[Dict[str, Any]]) -> None:
        if not a or len(out) >= max_items:
            return
        k = news_module.dedup_key(a)
        if not k or k in seen:
            return
        seen.add(k)
        out.append(a)

    _add(lead_article)
    pool = list(articles or [])
    scored: List[tuple] = []
    for a in pool:
        k = news_module.dedup_key(a)
        if not k or k in seen:
            continue
        try:
            sc = float(news_module.score_article(a))
        except Exception:
            sc = 0.0
        scored.append((sc, a))
    scored.sort(key=lambda x: x[0], reverse=True)
    for _, a in scored:
        _add(a)
        if len(out) >= max_items:
            break
    return out


def infer_instagram_card_topic(article: Dict[str, Any]) -> tuple[str, str]:
    """주제 라벨(한국어) + 배경 장면(영문, 이미지 AI용)."""
    blob = " ".join(
        [
            news_module.clean_spaces(article.get("title", "") or ""),
            news_module.clean_spaces(article.get("description", "") or ""),
        ]
    ).lower()
    rules: List[tuple] = [
        (
            (
                "iran",
                "tehran",
                "hormuz",
                "ceasefire",
                "nuclear",
                "이란",
                "휴전",
                "핵",
                "u.s.-iran",
                "us-iran",
                "diplomat",
            ),
            "미·이란",
            "US and Iran diplomats at negotiation table or summit handshake, Middle East or neutral "
            "conference room, subdued flags, serious tone — NOT New York Stock Exchange, NOT Wall Street",
        ),
        (
            ("iran", "hormuz", "opec", "oil", "gas", "crude", "wti", "유가", "정유", "휘발유", "energy"),
            "에너지·유가",
            "offshore oil rig or Strait of Hormuz tankers at dramatic dusk, orange sky and dark sea, "
            "refinery lights bokeh in distance — NOT stock exchange building",
        ),
        (
            ("assassination", "shooting", "shot", "gunman", "총격", "피격"),
            "속보",
            "breaking news press scene or secure government building exterior, dramatic lighting, "
            "no stock exchange facade",
        ),
        (
            ("trump", "white house", "president trump"),
            "트럼프·정치",
            "White House exterior or presidential motorcade, Capitol press stakeout — NOT NYSE facade",
        ),
        (
            ("bitcoin", "btc", "crypto", "warsh", "fed chair", "fed chairman", "powell"),
            "연준·비트코인",
            "Federal Reserve building or Fed press room, subtle finance motif — NOT NYSE flag facade",
        ),
        (
            ("fed", "cpi", "rate", "yield", "bond", "금리", "국채", "인플레", "treasury"),
            "금리·매크로",
            "Federal Reserve press conference or US Treasury hearing room — NOT generic NYSE building",
        ),
        (
            ("nvidia", "semiconductor", "ai", "chip", "반도체", "삼성", "하이닉스"),
            "반도체·AI",
            "semiconductor fab cleanroom or Silicon Valley tech campus, editorial photo",
        ),
        (
            ("kospi", "kosdaq", "코스피", "코스닥", "외국인", "증시", "stock market"),
            "한국 증시",
            "Seoul financial district and Korea Exchange exterior, no index chart screenshot",
        ),
        (
            ("dollar", "won", "fx", "환율", "원달러"),
            "환율",
            "currency exchange trading desk, US dollar and Korean won imagery",
        ),
        (
            ("war", "military", "missile", "전쟁", "공습"),
            "지정학",
            "conflict zone skyline or military/diplomatic briefing, restrained — NOT stock exchange",
        ),
        (
            ("biden", "대통령", "관세", "tariff", "policy"),
            "정치·정책",
            "US Capitol or White House policy briefing, no NYSE",
        ),
    ]
    for keys, label, visual_en in rules:
        if any(k in blob for k in keys):
            return label, visual_en
    return "글로벌 시장", "global financial markets editorial scene, photorealistic, no charts"


def _story_blob(
    line1: str, line2: str, article: Optional[Dict[str, Any]] = None
) -> str:
    parts = [line1, line2]
    if article:
        parts.append(news_module.clean_spaces(article.get("title", "") or ""))
        parts.append(
            news_module.clean_spaces(article.get("description", "") or "")[:400]
        )
    return " ".join(parts).lower()


def _visual_scene_for_story(blob: str, fallback: str) -> str:
    """카피·기사 키워드와 맞는 배경(영문)."""
    if any(
        k in blob
        for k in (
            "iran",
            "이란",
            "휴전",
            "핵",
            "hormuz",
            "tehran",
            "ceasefire",
            "nuclear",
            "diplomat",
        )
    ):
        return (
            "US and Iran diplomats negotiating, formal meeting table or summit handshake, "
            "Middle East diplomatic setting, serious mood, upper area clear for text — "
            "absolutely NOT New York Stock Exchange or Wall Street trading floor"
        )
    if any(k in blob for k in ("trump", "트럼프", "assassination", "shooting", "총격")):
        return (
            "White House or Capitol breaking-news scene, security perimeter, press lights — "
            "NOT stock exchange building with US flag"
        )
    if any(k in blob for k in ("oil", "유가", "wti", "crude", "opec", "정유")):
        return (
            "oil tankers or refinery at dusk, energy crisis mood — NOT NYSE or trading floor"
        )
    if any(k in blob for k in ("fed", "연준", "금리", "cpi", "powell")):
        return (
            "Federal Reserve press conference room or chair podium — NOT NYSE facade"
        )
    if any(k in blob for k in ("kospi", "코스피", "코스닥", "증시")):
        return "Seoul Exchange or Yeouido financial district skyline, no chart screenshot"
    return fallback


def _visual_mismatch(visual: str, blob: str) -> bool:
    v = visual.lower()
    nyse_cues = (
        "stock exchange",
        "nyse",
        "wall street",
        "american flag on",
        "exchange facade",
        "trading floor",
    )
    iran_story = any(
        k in blob for k in ("iran", "이란", "휴전", "핵", "hormuz", "ceasefire", "nuclear")
    )
    trump_story = any(k in blob for k in ("trump", "트럼프", "연준", "fed", "금리"))
    if iran_story and any(c in v for c in nyse_cues):
        return True
    if iran_story and "iran" not in v and "diplomat" not in v and "middle east" not in v:
        if any(c in v for c in nyse_cues + ("federal reserve", "white house")):
            return True
    if trump_story and not iran_story and any(c in v for c in nyse_cues):
        return True
    return False


def align_pack_to_story(
    pack: InstagramCardPack, lead_article: Dict[str, Any]
) -> InstagramCardPack:
    """한글 카피·배경·기사 주제 일치."""
    blob = _story_blob(pack.line1, pack.line2, lead_article)
    topic, vis_default = infer_instagram_card_topic(lead_article)
    vis = pack.visual_scene_en.strip()
    if _visual_mismatch(vis, blob):
        vis = _visual_scene_for_story(blob, vis_default)
        print("[reference_pipeline] visual_scene realigned to match headline")
    elif len(vis) < 60:
        vis = _visual_scene_for_story(blob, vis_default)
    pack.topic = topic
    pack.visual_scene_en = vis[:500]
    return pack


def build_finished_card_image_prompt(line1: str, line2: str, visual_scene_en: str) -> str:
    return FINISHED_CARD_IMAGE_TEMPLATE.format(
        visual_scene=visual_scene_en.strip(),
        line1=line1.strip(),
        line2=line2.strip(),
    )


def _openai_instagram_card_pack(
    lead_article: Dict[str, Any],
    *,
    topic: str,
    visual_scene_en: str,
    quotes: str,
) -> Optional[InstagramCardPack]:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None

    title = news_module.clean_spaces(lead_article.get("title", "") or "")
    desc = news_module.clean_spaces(lead_article.get("description", "") or "")[:900]
    model = (os.getenv("OPENAI_HEADLINE_MODEL") or "gpt-4o-mini").strip()
    sys = (
        "You create Korean Instagram financial news cards (1080x1350, BoA/broker style). "
        "Output JSON only: "
        '{"line1":"...","line2":"...","caption":"...","visual_scene_en":"..."}. '
        "line1: Korean hook headline max ~24 chars — strong, scroll-stopping, comma at end when natural. "
        "For assassination/shooting/breaking: urgent but factual (속보 톤). "
        "line2: Korean punch line max ~48 chars — why it matters now, not index laundry list. "
        "Spell 코스피 never 코스파. "
        "Spell indices correctly: 코스피 (never 코스파), 코스닥. "
        "caption: 2-3 Korean sentences, neutral, for Instagram post. "
        "visual_scene_en: 2 English sentences for BACKGROUND ONLY — must depict the SAME event as line1/line2. "
        "If story is US-Iran/ceasefire/nuclear: diplomats, negotiation, Middle East — NEVER NYSE or Wall Street. "
        "If story is Trump/Fed: White House or Fed — NEVER NYSE flag facade. "
        "Facts must match TITLE/BODY only."
    )
    user = f"TOPIC:{topic}\nQUOTES:{quotes or 'n/a'}\nTITLE:\n{title}\n\nBODY:\n{desc}\n"
    try:
        client = OpenAI(api_key=key)
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.25,
            max_tokens=420,
        )
        d = json.loads((r.choices[0].message.content or "").strip())
        l1 = str(d.get("line1") or "").strip()
        l2 = str(d.get("line2") or "").strip()
        cap = str(d.get("caption") or "").strip()
        vis = str(d.get("visual_scene_en") or visual_scene_en).strip()
        if len(vis) < 80:
            vis = f"{vis} Cinematic editorial photo, 35mm, upper area uncluttered for headline overlay."
        if len(l1) < 4:
            return None
        if l1 and not l1.endswith((",", "，")) and len(l1) < 30:
            l1 = l1 + ","
        print("[reference_pipeline] openai instagram card pack ok")
        pack = InstagramCardPack(
            line1=sanitize_card_korean(l1[:90]),
            line2=sanitize_card_korean(l2[:140]),
            caption=sanitize_card_korean(cap[:600] or l2),
            topic=topic,
            visual_scene_en=vis[:500],
        )
        return align_pack_to_story(pack, lead_article)
    except Exception as e:
        print(f"[reference_pipeline] openai card pack failed: {repr(e)}")
        return None


def generate_instagram_card_pack(
    lead_article: Dict[str, Any],
    *,
    market_data: Optional[Dict[str, Any]] = None,
) -> InstagramCardPack:
    topic, visual_en = infer_instagram_card_topic(lead_article)
    quotes = _quotes_block(market_data or {})

    pack = _openai_instagram_card_pack(
        lead_article, topic=topic, visual_scene_en=visual_en, quotes=quotes
    )
    if pack:
        return pack

    try:
        from telegram_single_card import _try_openai_korean_card_lines

        ko = _try_openai_korean_card_lines(lead_article)
    except Exception:
        ko = None

    if ko:
        l1, l2 = ko
        pack = InstagramCardPack(
            line1=sanitize_card_korean(l1),
            line2=sanitize_card_korean(l2),
            caption=sanitize_card_korean(l2),
            topic=topic,
            visual_scene_en=visual_en,
        )
        return align_pack_to_story(pack, lead_article)

    title = news_module.clean_spaces(lead_article.get("title", "") or "")[:80]
    pack = InstagramCardPack(
        line1="시장 변수 점검,",
        line2=sanitize_card_korean(title or "글로벌 뉴스 흐름 확인"),
        caption="관련 뉴스에 따르면 시장 변수를 점검할 필요가 있습니다.",
        topic=topic,
        visual_scene_en=visual_en,
    )
    return align_pack_to_story(pack, lead_article)


def build_instagram_hashtags(
    pack: InstagramCardPack,
    lead_article: Dict[str, Any],
    *,
    max_tags: int = 4,
) -> str:
    """인스타 해시태그 4개 이하."""
    blob = " ".join(
        [
            pack.topic,
            pack.line1,
            pack.line2,
            news_module.clean_spaces(lead_article.get("title", "") or ""),
        ]
    ).lower()
    tags: List[str] = []
    rules = [
        (("trump", "트럼프", "총격", "assassination", "shooting"), "#트럼프"),
        (("iran", "이란", "hormuz", "oil", "유가", "wti"), "#유가"),
        (("fed", "연준", "금리", "cpi"), "#연준"),
        (("bitcoin", "btc", "비트"), "#비트코인"),
        (("war", "전쟁", "attack", "지정학"), "#국제정세"),
        (("kospi", "코스피", "증시", "stock"), "#코스피"),
        (("semiconductor", "반도체", "nvidia"), "#반도체"),
    ]
    for keys, tag in rules:
        if any(k in blob for k in keys) and tag not in tags:
            tags.append(tag)
    if not tags:
        tags.append("#시장이슈")
    if "#속보" not in tags and news_module.is_viral_breaking(lead_article):
        tags.insert(0, "#속보")
    return " ".join(tags[:max_tags])


def build_telegram_delivery_messages(
    pack: InstagramCardPack,
    *,
    lead_article: Dict[str, Any],
    market_data: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """텔레그램 2통: ① 이미지 프롬프트 ② 캡션+해시태그."""
    _ = market_data
    lead_url = str(lead_article.get("url") or "").strip()
    lead_src = news_module.article_source_name(lead_article)
    image_prompt = build_finished_card_image_prompt(
        pack.line1, pack.line2, pack.visual_scene_en
    )
    cap_lines = [
        "━━ 생성 확인 (이미지가 다르면 재시도) ━━",
        f"1줄: {pack.line1}",
        f"2줄: {pack.line2}",
        f"주제: {pack.topic}",
        "※ 한글·배경이 위와 다르면 ChatGPT가 프롬프트를 무시한 것 → 같은 프롬프트 재생성",
        "",
        pack.caption.strip(),
        "",
        build_instagram_hashtags(pack, lead_article),
    ]
    if lead_src:
        cap_lines.extend(["", f"출처: {lead_src}"])
    if lead_url:
        cap_lines.append(lead_url)
    cap_lines.extend(["", _DISCLAIMER])
    return [
        image_prompt.strip(),
        "\n".join(cap_lines).strip(),
    ]


def build_reference_telegram_prompt(
    articles: List[Dict[str, Any]],
    *,
    lead_article: Dict[str, Any],
    market_data: Optional[Dict[str, Any]] = None,
) -> str:
    """레거시 — 한 메시지로 합침 (권장: build_telegram_delivery_messages)."""
    pack = generate_instagram_card_pack(lead_article, market_data=market_data)
    return "\n\n---\n\n".join(
        build_telegram_delivery_messages(pack, lead_article=lead_article, market_data=market_data)
    )


def split_telegram_prompt_chunks(text: str, limit: int = 4090) -> List[str]:
    """텔레그램 메시지 길이 제한 분할."""
    t = (text or "").strip()
    if len(t) <= limit:
        return [t]
    raw: List[str] = []
    rest = t
    while rest:
        if len(rest) <= limit:
            raw.append(rest)
            break
        cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = limit
        raw.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    total = len(raw)
    out: List[str] = []
    for i, body in enumerate(raw, 1):
        prefix = f"[{i}/{total}]\n"
        room = limit - len(prefix)
        if len(body) > room:
            body = body[: max(0, room - 1)] + "…"
        out.append(prefix + body)
    return out
