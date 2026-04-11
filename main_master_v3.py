import json, os, re
from datetime import datetime, timedelta, timezone
import news as news_module
from polymarket import get_polymarket_markets
from rank_card_v3 import create_rank_set
from reels_packager import build_content_pack
from reels_maker_final import build_reel
from content_dispatcher import send_media_group, send_message, send_video, send_image
try:
    from card_v3 import create_breaking_image
except Exception:
    create_breaking_image=None
try:
    from instagram_v2 import upload_instagram
except Exception:
    upload_instagram=None

REGULAR_STATE_FILE="regular_rank_state.json"
BREAKING_STATE_FILE="breaking_state.json"
NEWS_POLL_STATE_FILE="news_poll_state.json"
OUT_DIR="output_rank"
REGULAR_POST_MINUTE_WINDOW=90
BREAKING_COOLDOWN_MINUTES=720
BREAKING_NEWS_MIN_SCORE=88
BREAKING_POLY_MIN_SCORE=92
USE_INSTAGRAM_FOR_BREAKING=(os.getenv("USE_INSTAGRAM_FOR_BREAKING","false").lower()=="true")
FORCE_REGULAR_NOW=(os.getenv("FORCE_REGULAR_NOW","false").lower()=="true")

def now_kst(): return datetime.now(timezone.utc)+timedelta(hours=9)
def load_json_file(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except: return default
def save_json_file(path, data):
    with open(path,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)

def current_regular_slot():
    now=now_kst(); total=now.hour*60+now.minute
    if 8*60 <= total < 8*60+REGULAR_POST_MINUTE_WINDOW: return "morning"
    if 19*60 <= total < 19*60+REGULAR_POST_MINUTE_WINDOW: return "evening"
    return None

def should_run_regular_post(): return FORCE_REGULAR_NOW or current_regular_slot() is not None
def load_regular_state(): return load_json_file(REGULAR_STATE_FILE, {"last_morning_date":"","last_evening_date":"","last_force_ts":""})
def save_regular_state(data): save_json_file(REGULAR_STATE_FILE,data)
def already_sent_regular():
    if FORCE_REGULAR_NOW: return False
    state=load_regular_state(); today=now_kst().strftime("%Y-%m-%d"); slot=current_regular_slot()
    if slot=="morning": return state.get("last_morning_date")==today
    if slot=="evening": return state.get("last_evening_date")==today
    return False
def mark_regular_sent():
    state=load_regular_state(); today=now_kst().strftime("%Y-%m-%d"); slot=current_regular_slot()
    if FORCE_REGULAR_NOW: state["last_force_ts"]=now_kst().isoformat(timespec="seconds")
    elif slot=="morning": state["last_morning_date"]=today
    elif slot=="evening": state["last_evening_date"]=today
    save_regular_state(state)
def load_breaking_state(): return load_json_file(BREAKING_STATE_FILE, {"items":[]})
def save_breaking_state(state):
    state["items"]=state.get("items",[])[-100:]
    save_json_file(BREAKING_STATE_FILE,state)
def was_recent_breaking(key):
    state=load_breaking_state(); cutoff=now_kst()-timedelta(minutes=BREAKING_COOLDOWN_MINUTES)
    for item in reversed(state.get("items",[])):
        if item.get("key")!=key: continue
        try:
            ts=datetime.fromisoformat(item["ts"])
            if ts >= cutoff: return True
        except: continue
    return False
def mark_breaking_posted(key,title):
    state=load_breaking_state()
    state["items"].append({"key":key,"title":title,"ts":now_kst().isoformat(timespec="seconds")})
    save_breaking_state(state)
def _contains(text,words):
    t=str(text).lower(); return any(w in t for w in words)
def _clean(text,limit=18):
    text=re.sub(r"\s+"," ",str(text).strip()); return text[:limit].strip()
def parse_datetime_safe(value):
    if not value: return None
    text=str(value).strip()
    try:
        dt=datetime.fromisoformat(text.replace("Z","+00:00")) if text.endswith("Z") else datetime.fromisoformat(text)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt
    except: return None
def regular_window_bounds():
    now=now_kst(); slot=current_regular_slot()
    if slot=="morning":
        end_kst=now.replace(hour=8,minute=0,second=0,microsecond=0)
        start_kst=(end_kst-timedelta(days=1)).replace(hour=19,minute=0,second=0,microsecond=0)
        return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)
    if slot=="evening":
        end_kst=now.replace(hour=19,minute=0,second=0,microsecond=0)
        start_kst=now.replace(hour=8,minute=0,second=0,microsecond=0)
        return start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc)
    return None,None
def article_in_window(article):
    start_utc,end_utc=regular_window_bounds()
    if not start_utc or not end_utc: return True
    dt=parse_datetime_safe(article.get("publishedAt"))
    if dt is None: return True
    return start_utc <= dt <= end_utc
def can_poll_news_for_breaking():
    state=load_json_file(NEWS_POLL_STATE_FILE, {"last_hour_key":""})
    hour_key=now_kst().strftime("%Y-%m-%d-%H")
    if state.get("last_hour_key")==hour_key: return False
    state["last_hour_key"]=hour_key
    save_json_file(NEWS_POLL_STATE_FILE,state)
    return True
def _news_label(title):
    t=str(title)
    if _contains(t,["strait of hormuz","hormuz","호르무즈"]): return "호르무즈 변수 확대"
    if _contains(t,["환율","달러","usd","fx","won"]): return "환율 변동성 확대"
    if _contains(t,["유가","oil","wti","crude","brent"]): return "유가 상방 압력"
    if _contains(t,["bitcoin","btc","비트"]): return "비트코인 강세 유지"
    if _contains(t,["ethereum","eth","이더"]): return "이더 강세 유지"
    if _contains(t,["금리","fed","cpi","inflation","yield"]): return "금리 완화 기대"
    if _contains(t,["trump","트럼프","tariff","관세"]): return "트럼프 변수 확대"
    if _contains(t,["iran","israel","war","attack","전쟁","이란","이스라엘","공습"]): return "지정학 리스크 확대"
    if _contains(t,["gold","금값","금"]): return "안전자산 선호"
    return _clean(t,16)
def _news_score(article):
    title=article.get("title","") or ""; desc=article.get("description","") or ""; text=f"{title} {desc}".lower(); score=25
    if _contains(text,["환율","usd","fx","달러","won"]): score+=24
    if _contains(text,["oil","wti","crude","brent","유가"]): score+=26
    if _contains(text,["war","attack","missile","전쟁","공습","이란","israel","iran"]): score+=22
    if _contains(text,["fed","cpi","inflation","yield","금리","물가"]): score+=22
    if _contains(text,["bitcoin","btc","eth","ethereum","비트","코인"]): score+=18
    if _contains(text,["trump","관세","tariff"]): score+=16
    if re.search(r"\d",text): score+=8
    if article_in_window(article): score+=6
    return min(score,100)
def fetch_news_articles(hours_back=36, limit=40):
    try:
        return news_module.fetch_news(limit=limit, hours_back=hours_back) or []
    except TypeError:
        try: return news_module.fetch_news() or []
        except: return []
    except: return []
def build_news_rank_items():
    articles=fetch_news_articles(hours_back=36, limit=40)
    if not articles:
        return [{"label":"유가 상방 압력","score":82},{"label":"휴전 기대 확대","score":78},{"label":"비트코인 강세 유지","score":75},{"label":"달러 강세 유지","score":72},{"label":"금리 완화 기대","score":69}]
    scored=[{"label":_news_label(a.get("title","")),"score":_news_score(a),"title":a.get("title","")} for a in articles]
    scored.sort(key=lambda x:x["score"], reverse=True)
    out=[]; seen=set()
    for item in scored:
        if item["label"] in seen: continue
        seen.add(item["label"]); out.append({"label":item["label"],"score":item["score"]})
        if len(out)==5: break
    fillers=[{"label":"유가 상방 압력","score":80},{"label":"휴전 기대 확대","score":77},{"label":"비트코인 강세 유지","score":74},{"label":"달러 강세 유지","score":71},{"label":"금리 완화 기대","score":68}]
    while len(out)<5: out.append(fillers[len(out)])
    return out[:5]
def _poly_label(question):
    q=str(question)
    if _contains(q,["wti","oil","crude","brent","유가"]): return "유가 상단 도전"
    if _contains(q,["ceasefire","휴전"]): return "휴전 베팅 확대"
    if _contains(q,["hormuz","호르무즈"]): return "호르무즈 정상화 기대"
    if _contains(q,["trump","트럼프"]): return "트럼프 변수 확대"
    if _contains(q,["bitcoin","btc","비트"]): return "비트코인 상단 테스트"
    if _contains(q,["gold","금"]): return "금 선호 확대"
    if _contains(q,["fed","cpi","inflation","금리"]): return "금리 방향 베팅"
    return _clean(q,16)
def _to_float(v, default=0.0):
    try: return float(v)
    except: return default
def _poly_score(question, volume, yes_price):
    text=str(question).lower(); score=24; v=_to_float(volume,0.0); p=_to_float(yes_price,0.0)
    if v>=20000000: score+=42
    elif v>=10000000: score+=36
    elif v>=5000000: score+=28
    elif v>=1000000: score+=18
    if 0.10<=p<=0.90: score+=14
    if 0.20<=p<=0.80: score+=8
    if _contains(text,["oil","wti","crude","brent","hormuz"]): score+=18
    if _contains(text,["bitcoin","btc","eth","ethereum"]): score+=16
    if _contains(text,["iran","israel","war","attack","ceasefire"]): score+=18
    if _contains(text,["trump","tariff","fed","cpi","yield"]): score+=14
    return min(score,100)
def build_poly_rank_items():
    try: markets=get_polymarket_markets()
    except: markets=[]
    if not markets:
        return [{"label":"유가 상단 도전","score":83},{"label":"휴전 베팅 확대","score":80},{"label":"트럼프 변수 확대","score":76},{"label":"호르무즈 정상화 기대","score":73},{"label":"비트코인 상단 테스트","score":70}]
    scored=[]
    for m in markets:
        q=m.get("question",""); vol=m.get("volume24hr",m.get("volume",0)); yp=m.get("yes_price",m.get("yesPrice",0))
        scored.append({"label":_poly_label(q),"score":_poly_score(q,vol,yp),"question":q})
    scored.sort(key=lambda x:x["score"], reverse=True)
    out=[]; seen=set()
    for item in scored:
        if item["label"] in seen: continue
        seen.add(item["label"]); out.append({"label":item["label"],"score":item["score"]})
        if len(out)==5: break
    fillers=[{"label":"유가 상단 도전","score":82},{"label":"휴전 베팅 확대","score":79},{"label":"트럼프 변수 확대","score":75},{"label":"호르무즈 정상화 기대","score":72},{"label":"비트코인 상단 테스트","score":69}]
    while len(out)<5: out.append(fillers[len(out)])
    return out[:5]
def build_market_rank_items(news_items, poly_items):
    buckets={"유가 상방 압력":0,"환율 변동성 확대":0,"비트코인 강세 유지":0,"금 선호 강화":0,"금리 부담 확대":0}
    for item in news_items+poly_items:
        label,score=item["label"],item["score"]
        if _contains(label,["유가","호르무즈","oil","crude","wti"]): buckets["유가 상방 압력"]+=score
        if _contains(label,["환율","달러","usd","fx"]): buckets["환율 변동성 확대"]+=score
        if _contains(label,["비트","btc","코인","crypto"]): buckets["비트코인 강세 유지"]+=score
        if _contains(label,["금","gold","안전자산"]): buckets["금 선호 강화"]+=score
        if _contains(label,["금리","fed","cpi","yield"]): buckets["금리 부담 확대"]+=score
        if _contains(label,["전쟁","공습","지정학","휴전","이란","이스라엘"]):
            buckets["유가 상방 압력"]+=6; buckets["금 선호 강화"]+=6
    ranked=[]
    for k,v in buckets.items():
        score=min(100,max(55,int(v/2) if v>0 else 55)); ranked.append({"label":k,"score":score})
    ranked.sort(key=lambda x:x["score"], reverse=True)
    return ranked[:5]
def post_regular_rank_cards():
    news_items=build_news_rank_items(); poly_items=build_poly_rank_items(); market_items=build_market_rank_items(news_items,poly_items)
    paths=create_rank_set(news_items,poly_items,market_items,out_dir=OUT_DIR)
    pack=build_content_pack(news_items,poly_items,market_items)
    reel_path=build_reel(news_path=paths[0], poly_path=paths[1], market_path=paths[2], hook_text=pack["reel_hook"], out_path=os.path.join(OUT_DIR,"reel_output.mp4"))
    send_media_group(paths); send_video(reel_path, caption=pack["reel_hook"])
    send_message(f"[커버 문구]\n{pack['cover_text']}\n\n[피드 제목]\n{pack['feed_title']}\n\n[피드 캡션]\n{pack['feed_caption']}\n\n[릴스 훅]\n{pack['reel_hook']}\n\n[릴스 스크립트]\n{pack['reel_script']}\n\n[릴스 캡션]\n{pack['reel_caption']}\n\n[스토리 문구]\n{pack['story_text']}\n\n[해시태그]\n{pack['hashtags']}\n\n[첫 댓글]\n{pack['first_comment']}")
    mark_regular_sent(); print("[정규 업로드합니다]")
def _breaking_news_score(title,desc=""):
    text=f"{title} {desc}".lower(); score=20
    if _contains(text,["breaking","urgent","just in","developing"]): score+=20
    if _contains(text,["war","attack","missile","nuclear","invasion","ceasefire"]): score+=22
    if _contains(text,["trump","fed","bitcoin","oil","gold","tariff","rate"]): score+=18
    if _contains(text,["crash","bankruptcy","default","circuit breaker"]): score+=24
    if re.search(r"\d", text): score+=6
    return min(score,100)
def _breaking_poly_score(question,volume,yes_price):
    score=_poly_score(question,volume,yes_price)
    if _contains(question,["ceasefire","attack","war","hormuz","oil","bitcoin","fed"]): score+=10
    return min(score,100)
def post_breaking():
    if can_poll_news_for_breaking():
        print("[속보] 뉴스 1시간 슬롯 검사")
        articles=fetch_news_articles(hours_back=12, limit=20); best_news=None
        for art in articles[:20]:
            title=art.get("title","") or ""; desc=art.get("description","") or ""; score=_breaking_news_score(title,desc)
            if score < BREAKING_NEWS_MIN_SCORE: continue
            key=f"news::{title.strip()}"
            if was_recent_breaking(key): continue
            if best_news is None or score > best_news["score"]: best_news={"title":title,"score":score,"key":key}
        if best_news and create_breaking_image is not None:
            title=best_news["title"]; img_path="output_breaking_news.png"
            try:
                create_breaking_image(title,out_path=img_path); send_image(img_path,caption=title)
                if USE_INSTAGRAM_FOR_BREAKING and upload_instagram is not None:
                    try: upload_instagram(img_path,title)
                    except: pass
                mark_breaking_posted(best_news["key"],title); print("[속보 업로드 완료 - 뉴스]", title)
            except Exception as e:
                print("[속보 이미지 실패 - 뉴스]", repr(e))
        else:
            print("[속보] 뉴스 후보 없음 또는 점수 미달")
    else:
        print("[속보] 뉴스 검사 스킵 (시간당 1회 제한)")
    try: markets=get_polymarket_markets()
    except: markets=[]
    best_poly=None
    for m in markets[:30]:
        q=m.get("question",""); vol=m.get("volume24hr",m.get("volume",0)); yp=m.get("yes_price",m.get("yesPrice",0)); score=_breaking_poly_score(q,vol,yp)
        if score < BREAKING_POLY_MIN_SCORE: continue
        key=f"poly::{q.strip()}"
        if was_recent_breaking(key): continue
        if best_poly is None or score > best_poly["score"]: best_poly={"title":q,"score":score,"key":key}
    if best_poly and create_breaking_image is not None:
        title=best_poly["title"]; img_path="output_breaking_poly.png"
        try:
            create_breaking_image(title,out_path=img_path); send_image(img_path,caption=title)
            if USE_INSTAGRAM_FOR_BREAKING and upload_instagram is not None:
                try: upload_instagram(img_path,title)
                except: pass
            mark_breaking_posted(best_poly["key"],title); print("[속보 업로드 완료 - 폴리마켓]", title)
        except Exception as e:
            print("[속보 이미지 실패 - 폴리마켓]", repr(e))
    else:
        print("[속보] 폴리 후보 없음 또는 점수 미달")
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    try: post_breaking()
    except Exception as e: print("[속보 처리 오류]", repr(e))
    try:
        if should_run_regular_post():
            if already_sent_regular(): print("[정규 업로드 스킵] 이미 전송됨")
            else: post_regular_rank_cards()
        else: print("[정규 업로드 시간 아님]")
    except Exception as e:
        print("[정규 업로드 오류]", repr(e)); raise
if __name__=="__main__":
    print("FINAL FULL AUTOMATION VERSION LOADED")
    main()
