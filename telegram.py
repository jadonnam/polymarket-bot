import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_image(image_path, caption=""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

    print("TOKEN RAW:", repr(TELEGRAM_BOT_TOKEN))
    print("CHAT_ID:", repr(TELEGRAM_CHAT_ID))
    print("URL:", url)

    with open(image_path, "rb") as f:
        res = requests.post(
            url,
            files={"photo": f},
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption
            }
        )

    print("STATUS:", res.status_code)
    print("RESPONSE:", res.text)