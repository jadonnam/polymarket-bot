BOT_TOKEN = "8605896650:AAECzR130hjNPSks1In-kiCaRggasAHG1lc"
CHAT_ID = "-1003659436382"

import requests

def send_image(image_path):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN 또는 CHAT_ID가 비어있음")

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"

    with open(image_path, "rb") as f:
        files = {"photo": f}
        data = {"chat_id": CHAT_ID}
        res = requests.post(url, files=files, data=data)

    print("텔레그램 응답:", res.status_code, res.text)