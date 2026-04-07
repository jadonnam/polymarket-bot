print("🔥 ALERT.PY 실행됨 🔥")
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram(text, image_path=None):
    print("TOKEN RAW:", repr(TELEGRAM_BOT_TOKEN))
    print("CHAT_ID:", repr(TELEGRAM_CHAT_ID))

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    print("URL:", url)

    res = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text
        }
    )

    print("STATUS:", res.status_code)
    print("RESPONSE:", res.text)