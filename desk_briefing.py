"""
자돈남 DESK 형식 텔레그램 브리핑 (① 헤드 · ② 해석 · ③ 볼 것).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import news as news_module

_WEEKDAY_KO = "월화수목금토일"
_DISCLAIMER = (
    "※ 정리용 · 투자 권유 아님 · 레버·청산·슬리피지·거래소·규제 리스크 전제."
)


def now_kst() -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=9)


def _short(s: str, n: int) -> str:
    t = re.sub(r"\s+", " ", str(s or "").strip())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _desk_brand() -> str:
    return (os.getenv("DESK_BRIEFING_BRAND") or "자돈남 DESK").strip() or "자돈남 DESK"


def _format_kst_header(dt: Optional[datetime] = None) -> str:
    dt = dt or now_kst()
    wd = _WEEKDAY_KO[dt.weekday()]
    date_part = f"{dt.month}/{dt.day}({wd})"
    time_part = f"{dt.hour:02d}:{dt.minute:02d} KST"
    score = min(10, max(6, int(os.getenv("DESK_SCORE_DEFAULT") or "10")))
    return (
        f"{_desk_brand()} · 🇰🇷 한국 · {date_part} · {time_part}\n"
        f"〔{score}/10〕"
    )


def _related_tags(market_data: Dict[str, Any], articles: List[Dict[str, Any]]) -> List[str]:
    tags: List[str] = []
    blob = " ".join(
        f"{a.get('title', '')} {a.get('description', '')}" for a in (articles or [])[:6]
    ).lower()
    rules = [
        (("kospi", "코스피", "증시", "코스닥"), "KOSPI"),
        (("환율", "원달러", "usdkrw", "dollar", "fx"), "환율"),
        (("외국인", "foreign"), "외국인"),
        (("반도체", "nvidia", "삼성", "하이닉스", "sox"), "반도체"),
        (("유가", "wti", "oil", "crude"), "유가"),
        (("금리", "fed", "cpi", "국채", "yield"), "금리"),
        (("bitcoin", "btc", "비트"), "비트코인"),
    ]
    for keys, label in rules:
        if any(k in blob for k in keys) and label not in tags:
            tags.append(label)
    q = (market_data or {}).get("quotes", {})
    if isinstance(q, dict):
        if "KOSPI" in q and "KOSPI" not in tags:
            tags.append("KOSPI")
        if "USDKRW" in q and "환율" not in tags:
            tags.append("환율")
    return tags[:5] or ["KOSPI", "환율", "외국인"]


def _openai_desk_sections(
    articles: List[Dict[str, Any]], market_data: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not key or (os.getenv("CARD_HEADLINE_OPENAI") or "auto").strip().lower() == "false":
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None

    lines_in: List[str] = []
    for i, a in enumerate((articles or [])[:8], 1):
        t = news_module.clean_spaces(a.get("title", "") or "")
        d = news_module.clean_spaces(a.get("description", "") or "")[:200]
        src = news_module.article_source_name(a)
        lines_in.append(f"{i}. [{src}] {t}\n   {d}")

    q = (market_data or {}).get("quotes", {})
    snap = []
    if isinstance(q, dict):
        for sym in ("KOSPI", "KOSDAQ", "NQ_FUT", "WTI", "USDKRW", "US10Y"):
            row = q.get(sym, {})
            if isinstance(row, dict) and row.get("chg_pct") is not None:
                snap.append(f"{sym} {row.get('chg_pct')}%")

    client = OpenAI(api_key=key)
    model = (os.getenv("OPENAI_HEADLINE_MODEL") or "gpt-4o-mini").strip()
    sys = (
        "You write a Korean market desk note for Telegram. ALL output MUST be in Korean "
        "(한국어 only — no English sentences in bullets). Style: 자돈남 DESK — tight, "
        "readable, semi-formal wire tone. Use 美 韓 日 where natural. "
        'Output JSON only: {"head_lead":"...","head_bullets":["..."],"interpretation":"...","watch":"..."}. '
        "head_lead: one strong headline line (max ~55 chars). "
        "head_bullets: 3-4 sub-bullets, each max ~48 chars, can split one story across bullets. "
        "interpretation: one bullet starting with what matters for Korea (max ~72 chars). "
        "watch: one bullet listing what to monitor today (max ~72 chars)."
    )
    user = "NEWS:\n" + "\n".join(lines_in) + "\n\nQUOTES:\n" + ", ".join(snap)
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.25,
            max_tokens=520,
        )
        return json.loads((r.choices[0].message.content or "").strip())
    except Exception as e:
        print(f"[desk_briefing] openai failed: {repr(e)}")
        return None


def _fallback_desk_sections(
    articles: List[Dict[str, Any]], market_data: Dict[str, Any]
) -> Dict[str, Any]:
    titles = [
        news_module.clean_spaces(a.get("title", "") or "")
        for a in (articles or [])[:5]
        if news_module.clean_spaces(a.get("title", "") or "")
    ]
    lead = _short(titles[0] if titles else "글로벌 시장 변수 점검", 56)
    bullets = [_short(t, 50) for t in titles[1:4]]
    while len(bullets) < 3 and titles:
        for t in titles:
            s = _short(t, 50)
            if s not in bullets and s != lead:
                bullets.append(s)
            if len(bullets) >= 3:
                break

    blob = " ".join(titles).lower()
    if any(k in blob for k in ("semiconductor", "nvidia", "반도체", "ai")):
        interp = "美·반도체·AI 변수는 월요 코스피 갭·외국인·삼성·하이닉 선물부터 확인."
    elif any(k in blob for k in ("oil", "유가", "crude")):
        interp = "유가·에너지 흐름이 환율·인플레 기대와 함께 한국 수출·정유 섹터에 전달되는지 본다."
    else:
        interp = "해외 증시·금리·환율이 동시에 움직이는지, 한국장 시초가·수급부터 맞춘다."

    watch = "한국장: 코스피·환율·외국인 + NQ·SOX·삼성·하닉 갭·선물 동시."
    return {
        "head_lead": lead,
        "head_bullets": bullets[:4],
        "interpretation": interp,
        "watch": watch,
    }


def build_desk_briefing_text(
    *,
    articles: List[Dict[str, Any]],
    market_data: Optional[Dict[str, Any]] = None,
    lead_article: Optional[Dict[str, Any]] = None,
    dt: Optional[datetime] = None,
) -> str:
    arts = list(articles or [])
    if lead_article and lead_article not in arts:
        arts = [lead_article] + arts
    md = market_data if isinstance(market_data, dict) else {}

    data = _openai_desk_sections(arts, md) or _fallback_desk_sections(arts, md)
    lead = (data.get("head_lead") or "").strip()
    bullets = [str(b).strip() for b in (data.get("head_bullets") or []) if str(b).strip()]
    interp = (data.get("interpretation") or "").strip()
    watch = (data.get("watch") or "").strip()

    head_lines = [f"· {lead}"] if lead else []
    for b in bullets[:4]:
        head_lines.append(f"· {b}")

    parts = [
        _format_kst_header(dt),
        "",
        "① 헤드",
        *head_lines,
        "",
        "② 해석",
        f"· {interp}" if interp else "· 시장 연관 변수는 수급·환율·선물 포지션부터 확인.",
        "",
        "③ 볼 것",
        f"· {watch}" if watch else "· 코스피·환율·외국인·미국 선물·대형주 갭 동시.",
    ]

    src_art = lead_article or (arts[0] if arts else None)
    url = str((src_art or {}).get("url") or "").strip()
    src_name = news_module.article_source_name(src_art) if src_art else ""
    if url:
        parts.extend(["", f"🔗 {url}"])
    if src_name:
        parts.append(f"출처: {src_name}")
    rel = _related_tags(md, arts)
    if rel:
        parts.append(f"관련: {' · '.join(rel)}")
    parts.extend(["", _DISCLAIMER])
    text = "\n".join(parts).strip()
    if len(text) > 4090:
        text = text[:4087] + "…"
    return text
