"""
인스타 카드뉴스(4:5) 생성용 프롬프트 조립.
텔레그램에는 카드 제작 프롬프트만 전송(서버 OpenAI 호출 없음).
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

# 대한민국 인스타 금융·시사 카드뉴스 레퍼런스 (BoA/증권사형 4:5)
REFERENCE_INSTAGRAM_CARD = """[완성 카드 = 배경 + 그라데이션 + 한글 2줄이 한 장에 있어야 함]
· 1080×1350 (4:5). 상단~중앙: 주제 실사 배경. 차트·캔들·표 캡처 금지
· 하단 35~40%: 검정→투명 그라데이션(반드시 합성)
· 그라데이션 위: 흰색 굵은 한글 2줄, 좌측 정렬, 크게(1줄 > 2줄)
· 로고·워터마크·영문 헤드라인 본문 없음

[카피]
뱅크오브아메리카,
반도체 다음은 소재주가 시장을 이끌 것

[잘못된 결과]
배경 사진만 있고 한글·그라데이션이 없음 → 실패. 【2】완성 프롬프트 사용."""

# ChatGPT·DALL·E 등 이미지 AI용 원샷 템플릿 (【1】 확정 후 【1】 문구를 그대로 넣음)
FINISHED_CARD_IMAGE_TEMPLATE = """Create a finished Instagram financial news card, 1080x1350, 4:5 vertical.
Background: {visual_scene}. Photorealistic editorial news photo, cinematic lighting.
Bottom 38% of the image: smooth black-to-transparent gradient overlay (must be visible).
On top of the gradient, render LARGE bold white Korean sans-serif text, left-aligned, bottom area:
Line 1 (bigger): 「{line1}」
Line 2 (smaller): 「{line2}」
The Korean text must be sharp, readable, and part of the image — not omitted.
Style: Korean brokerage / BoA-style news card. No charts, candlesticks, logos, watermarks, English headlines."""

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


def apply_pack_to_article(article: Dict[str, Any], pack: ReferencePack) -> Dict[str, Any]:
    a = dict(article)
    a["_ko_line1"] = pack.card_line1
    a["_ko_line2"] = pack.card_line2
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
    """주제 라벨 + 배경 연출 힌트 (한국 인스타 카드뉴스용)."""
    blob = " ".join(
        [
            news_module.clean_spaces(article.get("title", "") or ""),
            news_module.clean_spaces(article.get("description", "") or ""),
        ]
    ).lower()
    rules: List[tuple] = [
        (
            ("iran", "hormuz", "opec", "oil", "gas", "crude", "wti", "유가", "정유", "휘발유"),
            "에너지·유가",
            "중동 정유·유조선·주유소·호르무즈 해역 실사, 차트 금지",
        ),
        (
            ("fed", "cpi", "rate", "yield", "bond", "금리", "국채", "인플레"),
            "금리·매크로",
            "연준·국채·금리 발표 현장, 뉴욕 금융가 실사",
        ),
        (
            ("nvidia", "semiconductor", "ai", "chip", "반도체", "삼성", "하이닉스"),
            "반도체·AI",
            "팹·웨이퍼·데이터센터·실리콘 밸리 실사, 녹색 차트 금지",
        ),
        (
            ("kospi", "kosdaq", "코스피", "코스닥", "외국인", "증시", "stock market"),
            "한국 증시",
            "여의도·거래소 전경·증권가 실사, 지수 차트 캡처 금지",
        ),
        (
            ("dollar", "won", "fx", "환율", "원달러"),
            "환율",
            "달러·원화·외환 거래 연상 실사",
        ),
        (
            ("bitcoin", "btc", "crypto", "비트"),
            "가상자산",
            "비트코인·거래소 연상, 가격 차트 스크린샷 금지",
        ),
        (
            ("war", "military", "missile", "전쟁", "공습", "휴전"),
            "지정학",
            "전쟁·외교 현장 실사, 과도한 폭력 묘사 자제",
        ),
        (
            ("trump", "biden", "white house", "대통령", "관세"),
            "정치·정책",
            "백악관·국회·관세·무역 연상 실사",
        ),
    ]
    for keys, label, visual in rules:
        if any(k in blob for k in keys):
            return label, visual
    return "글로벌 시장", "뉴스 주제에 맞는 산업·현장 실사, 차트·표 캡처 금지"


def build_reference_telegram_prompt(
    articles: List[Dict[str, Any]],
    *,
    lead_article: Dict[str, Any],
    market_data: Optional[Dict[str, Any]] = None,
) -> str:
    """텔레그램용 — 인스타 카드뉴스(4:5) 제작 프롬프트만 (한국형, 주제 맞춤)."""
    md = market_data if isinstance(market_data, dict) else {}
    arts = collect_articles_for_prompt(articles, lead_article, max_items=8)

    lead_title = news_module.clean_spaces(lead_article.get("title", "") or "")
    lead_desc = news_module.clean_spaces(lead_article.get("description", "") or "")[:500]
    lead_url = str(lead_article.get("url") or "").strip()
    lead_src = news_module.article_source_name(lead_article)

    topic, visual_hint = infer_instagram_card_topic(lead_article)
    quotes = _quotes_block(md)
    related_count = max(0, len(arts) - 1)
    related_block = _news_block(arts[1:] if len(arts) > 1 else [])
    if not related_block.strip():
        related_block = "(추가 기사 없음 — 리드 기사만 반영)"

    lines = [
        "📱 인스타 카드뉴스 · 생성 프롬프트",
        "",
        "⚠️ ChatGPT 이미지/DALL·E에 넣을 때",
        "· 【2】완성(원샷)만 사용 → 한글 2줄+그라데이션 포함된 **완성 카드**",
        "· 【3】배경만은 Canva·피그마 합성용. 이걸로 생성하면 글자 없는 사진만 나옴(지금 겪은 현상)",
        "",
        f"주제: {topic} · 배경 연출: {visual_hint}",
        "",
        "역할: 한국 금융 인스타 카드뉴스. 아래 기사 → 출력 【1】~【4】만.",
        "",
        "━━ 규격 ━━",
        REFERENCE_INSTAGRAM_CARD.strip(),
        "",
        "━━ 출력 순서 (설명·JSON 금지) ━━",
        "",
        "【1】카드 하단 한글 2줄 (확정 카피)",
        "1줄:",
        "2줄:",
        "",
        "【2】★ 완성 카드 이미지 프롬프트 (영문, ChatGPT 이미지에 이것만 붙여넣기)",
        "· 【1】의 1·2줄을 아래 템플릿 {line1} {line2}에 **한글 그대로** 넣을 것",
        "· 반드시 gradient + Korean text on image. 배경만 만들지 말 것.",
        "· 템플릿:",
        FINISHED_CARD_IMAGE_TEMPLATE.replace("{visual_scene}", visual_hint),
        "",
        "【3】(선택) 배경만 — Canva 합성용. 이미지 AI 최종 업로드용 아님",
        "· photorealistic, 4:5, no text, no chart …",
        "",
        "【4】인스타 캡션 (한국어 2~3문장 + 출처)",
        "",
        "【5】(선택) 캐러셀 2·3장 카피",
        "",
        "금지: DESK·①②③·배경만을 최종물로 제출·차트 배경",
        "",
        "━━ 리드 기사 (이 이슈의 중심) ━━",
        lead_title,
        lead_desc,
    ]
    if lead_src or lead_url:
        lines.append(f"출처: {lead_src}" + (f" · {lead_url}" if lead_url else ""))
    lines.extend(
        [
            "",
            f"━━ 참고 뉴스 ({related_count}건) ━━",
            related_block,
        ]
    )
    if quotes:
        lines.extend(["", "━━ 참고 시세 (카피에 숫자 넣을 때만) ━━", quotes])
    lines.extend(["", _DISCLAIMER])
    return "\n".join(lines).strip()


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
