"""
레퍼런스(자돈남 DESK + BoA 카드 2줄) 한 번의 프롬프트로 생성 → 텔레그램 전송.
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

# 사용자 레퍼런스 — 출력 형식은 이것과 동일 구조
REFERENCE_DESK_EXAMPLE = """자돈남 DESK · 🇰🇷 한국 · 5/17(일) · 21:47 KST
〔10/10〕

① 헤드
· '검은 금요일' 이어 美도 내리막 … 韓 증시 '단기 조정'일까, '폭락 전조'일까
· '검은 금요일' 이어 美도 내리막
· 韓 증시 '단기 조정'일까, '폭락 전조'일까 美국채 ‘고금리 발작’
· 짐 싸는 외국인, 코스피 8000 발목 잡을까 '팔천피' 안착 재도전

② 해석
· 美 반도체 급락은 월요인 코스피 갭·외국인·삼성·하닉 선물 포지션부터 확인.

③ 볼 것
· 한국장: 코스피·환율·외국인 + NQ·SOX·삼성·하닉 갭·선물 동시."""

REFERENCE_CARD_EXAMPLE = """카드 이미지(인스타 4:5) 하단 큰 흰 글씨 2줄만:
뱅크오브아메리카,
반도체 다음은 소재주가 시장을 이끌 것"""

SYSTEM_PROMPT = f"""You are the editor of 「자돈남 DESK」 Korean market Telegram.

Your job: read English/Korean news inputs and output JSON for (1) DESK message body sections and (2) card image two lines.

STRICT RULES:
- ALL user-facing text in Korean (한국어). No English sentences in bullets.
- Tone: concise wire / desk note. Use 美 韓 日 欧 where natural.
- Match the REFERENCE layout exactly (section titles ① 헤드 ② 해석 ③ 볼 것, bullets start with ·).
- head_lead can use … between clauses like the reference.
- head_bullets: 3–4 items; first bullet may be the long combined headline.
- interpretation / watch: each ONE line, no bullet prefix in JSON (added in code).
- card_line1: short subject + comma at end when natural (max ~28 chars).
- card_line2: supporting line (max ~55 chars).

REFERENCE DESK:
{REFERENCE_DESK_EXAMPLE}

REFERENCE CARD:
{REFERENCE_CARD_EXAMPLE}

Output JSON only:
{{
  "card_line1": "...",
  "card_line2": "...",
  "head_lead": "...",
  "head_bullets": ["...", "..."],
  "interpretation": "...",
  "watch": "..."
}}"""


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


def _quotes_block(market_data: Dict[str, Any]) -> str:
    q = (market_data or {}).get("quotes", {})
    if not isinstance(q, dict):
        return ""
    parts: List[str] = []
    for sym in ("KOSPI", "KOSDAQ", "NQ_FUT", "WTI", "USDKRW", "US10Y"):
        row = q.get(sym, {})
        if isinstance(row, dict) and row.get("chg_pct") is not None:
            parts.append(f"{sym} {row.get('chg_pct')}%")
    return ", ".join(parts)


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
    """TELEGRAM_SEND_REFERENCE_PROMPT=true 시 프롬프트 스냅샷용."""
    return SYSTEM_PROMPT
