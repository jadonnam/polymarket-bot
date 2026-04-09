import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_image(image_path, caption=None):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID 환경변수 없음")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    with open(image_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID}
        if caption:
            data["caption"] = caption
        res = requests.post(url, files=files, data=data)

    print("텔레그램 응답:", res.status_code, res.text[:200])
    return res


def send_caption(text):
    """텍스트만 따로 전송"""
    if not BOT_TOKEN or not CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    res = requests.post(url, data=data)
    print("텔레그램 텍스트 응답:", res.status_code)
