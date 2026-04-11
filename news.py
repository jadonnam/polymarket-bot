import os, json, re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import requests
API_KEY=(os.getenv("NEWS_API_KEY") or "").strip()
SEARCH_QUERY='("trump" OR "tariff" OR "trade deal" OR "bitcoin" OR "btc" OR "ethereum" OR "eth" OR "oil" OR "wti" OR "crude" OR "brent" OR "gold" OR "fed" OR "inflation" OR "cpi" OR "treasury yield" OR "rate cut" OR "nasdaq" OR "s&p 500" OR "dow" OR "iran" OR "israel" OR "ceasefire" OR "war" OR "hormuz" OR "dollar" OR "fx" OR "won")'
TRUSTED_DOMAINS={"reuters.com","bloomberg.com","cnbc.com","wsj.com","ft.com","apnews.com","bbc.com","finance.yahoo.com","marketwatch.com","investing.com","coindesk.com","theblock.co","yna.co.kr","english.yna.co.kr"}
TRUSTED_SOURCE_NAMES={"Reuters","Bloomberg","CNBC","The Wall Street Journal","WSJ","Financial Times","Associated Press","AP News","BBC News","Yahoo Finance","MarketWatch","Investing.com","CoinDesk","The Block","Yonhap News Agency","연합뉴스"}
MARKET_KEYWORDS=["trump","tariff","trade deal","bitcoin","btc","ethereum","eth","oil","wti","crude","brent","gold","fed","inflation","cpi","yield","rate cut","nasdaq","s&p","dow","ceasefire","iran","israel","war","attack","hormuz","dollar","fx","won","환율","유가","금리","물가","비트","달러","금값"]
HIGH_IMPACT_KEYWORDS=["oil","wti","crude","brent","hormuz","fed","inflation","cpi","yield","dollar","fx","won","tariff","bitcoin","btc","iran","israel","war","attack","ceasefire","gold"]
def clean_spaces(text): return re.sub(r"\s+"," ",str(text or "")).strip()
def normalize_domain(url):
    try: host=urlparse(url).netloc.lower().strip()
    except: return ""
    return host[4:] if host.startswith("www.") else host
def article_domain(a): return normalize_domain(a.get("url",""))
def article_source_name(a):
    src=a.get("source",{})
    return (src.get("name","") if isinstance(src,dict) else str(src or "")).strip()
def domain_is_trusted(d): return bool(d) and any(d==x or d.endswith("."+x) for x in TRUSTED_DOMAINS)
def source_name_is_trusted(n): return (n or "").strip().lower() in {x.lower() for x in TRUSTED_SOURCE_NAMES}
def article_text(a):
    return f"{clean_spaces(a.get('title',''))} {clean_spaces(a.get('description','') or a.get('content',''))}".lower()
def trusted_article(a): return domain_is_trusted(article_domain(a)) or source_name_is_trusted(article_source_name(a))
def published_recent_enough(a,hours=36):
    raw=a.get("publishedAt")
    if not raw: return True
    try:
        text=str(raw)
        dt=datetime.fromisoformat(text.replace("Z","+00:00")) if text.endswith("Z") else datetime.fromisoformat(text)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt >= datetime.now(timezone.utc)-timedelta(hours=hours)
    except: return True
def dedup_key(a):
    title=clean_spaces(a.get("title","")).lower()
    title=re.sub(r"[^a-z0-9가-힣\s]"," ",title)
    return re.sub(r"\s+"," ",title).strip()[:120]
def has_market_impact(a): 
    text=article_text(a); return any(k in text for k in MARKET_KEYWORDS)
def has_high_impact(a):
    text=article_text(a); return any(k in text for k in HIGH_IMPACT_KEYWORDS)
def is_low_quality_text(a):
    title=clean_spaces(a.get("title","")); desc=clean_spaces(a.get("description","") or a.get("content",""))
    return len(title)<18 or len(desc)<40
def score_article(a):
    text=article_text(a); score=0
    if domain_is_trusted(article_domain(a)): score+=40
    if source_name_is_trusted(article_source_name(a)): score+=20
    if re.search(r"\d", text): score+=8
    for k in MARKET_KEYWORDS:
        if k in text: score+=4
    return score
def fetch_news(limit=40,hours_back=36):
    if not API_KEY: return []
    params={"q":SEARCH_QUERY,"language":"en","sortBy":"publishedAt","pageSize":min(max(limit,20),100),"from":(datetime.now(timezone.utc)-timedelta(hours=hours_back)).strftime("%Y-%m-%dT%H:%M:%SZ"),"apiKey":API_KEY}
    try:
        data=requests.get("https://newsapi.org/v2/everything",params=params,timeout=20).json()
    except: return []
    if data.get("status")!="ok":
        print("뉴스 API 응답 이상:", data); return []
    filtered=[]; seen=set()
    for a in data.get("articles",[]) or []:
        if not trusted_article(a) or not has_market_impact(a) or not has_high_impact(a) or is_low_quality_text(a) or not published_recent_enough(a,hours_back): continue
        key=dedup_key(a)
        if not key or key in seen: continue
        seen.add(key); filtered.append(a)
    filtered.sort(key=score_article, reverse=True)
    return filtered[:limit]
def get_news_candidate():
    arts=fetch_news(limit=30,hours_back=12)
    if not arts: return None
    best=arts[0]
    return {"title":best.get("title",""),"description":best.get("description",""),"source":article_source_name(best),"url":best.get("url",""),"publishedAt":best.get("publishedAt","")}
