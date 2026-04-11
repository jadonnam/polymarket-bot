import os, json, requests

BOT_TOKEN=(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
CHAT_ID=(os.getenv("TELEGRAM_CHAT_ID") or "").strip()

def _url(method):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

def _check():
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    if not CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID not set")

def send_message(text):
    _check()
    r=requests.post(_url("sendMessage"), data={"chat_id":CHAT_ID,"text":text}, timeout=30)
    r.raise_for_status()
    return r.json()

def send_image(path, caption=""):
    _check()
    with open(path,"rb") as f:
        r=requests.post(_url("sendPhoto"), data={"chat_id":CHAT_ID,"caption":caption}, files={"photo":f}, timeout=60)
    r.raise_for_status()
    return r.json()

def send_video(path, caption=""):
    _check()
    with open(path,"rb") as f:
        r=requests.post(_url("sendVideo"), data={"chat_id":CHAT_ID,"caption":caption,"supports_streaming":"true"}, files={"video":f}, timeout=120)
    r.raise_for_status()
    return r.json()

def send_media_group(paths):
    _check()
    media=[]
    files={}
    for i,p in enumerate(paths):
        key=f"file{i}"
        files[key]=open(p,"rb")
        media.append({"type":"photo","media":f"attach://{key}"})
    try:
        r=requests.post(_url("sendMediaGroup"), data={"chat_id":CHAT_ID,"media":json.dumps(media, ensure_ascii=False)}, files=files, timeout=120)
        r.raise_for_status()
        return r.json()
    finally:
        for f in files.values():
            try: f.close()
            except: pass
