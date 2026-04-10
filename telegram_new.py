
import os
import json
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def _api(method: str) -> str:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 없음")
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"

def send_message(text: str):
    if not CHAT_ID:
        print("[텔레그램] CHAT_ID 없음")
        return
    r = requests.post(_api("sendMessage"), data={"chat_id": CHAT_ID, "text": text}, timeout=30)
    print("[텔레그램 메시지]", r.status_code, r.text[:200])

def send_image(image_path: str, caption: str = ""):
    if not CHAT_ID:
        print("[텔레그램] CHAT_ID 없음")
        return
    with open(image_path, "rb") as f:
        r = requests.post(
            _api("sendPhoto"),
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": f},
            timeout=60
        )
    print("[텔레그램 이미지]", r.status_code, r.text[:200])

def send_media_group(image_paths, caption=""):
    if not CHAT_ID:
        print("[텔레그램] CHAT_ID 없음")
        return

    files = {}
    media = []

    for idx, path in enumerate(image_paths):
        key = f"file{idx}"
        files[key] = open(path, "rb")
        item = {"type": "photo", "media": f"attach://{key}"}
        if idx == 0 and caption:
            item["caption"] = caption
        media.append(item)

    try:
        r = requests.post(
            _api("sendMediaGroup"),
            data={"chat_id": CHAT_ID, "media": json.dumps(media, ensure_ascii=False)},
            files=files,
            timeout=90
        )
        print("[텔레그램 미디어그룹]", r.status_code, r.text[:200])
    finally:
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass
