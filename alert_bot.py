import os
import time
import threading
import requests
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

last_data = {}
last_alert_time = {}

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def get_markets():
    url = "https://gamma-api.polymarket.com/markets?limit=50&active=true&order=volume24hr&ascending=false"
    try:
        res = requests.get(url, timeout=10)
        return res.json()
    except:
        return []

def get_prob(m):
    try:
        return float(m["outcomePrices"][0]) * 100
    except:
        return None

def get_volume(m):
    try:
        return float(m.get("volumeNum", 0))
    except:
        return 0

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHANNEL_ID,
        "text": msg
    })

def can_send(mid):
    now = time.time()
    if mid not in last_alert_time:
        return True
    if now - last_alert_time[mid] > 3600:  # 1시간 제한
        return True
    return False

def mark_sent(mid):
    last_alert_time[mid] = time.time()

def check():
    global last_data

    markets = get_markets()

    for m in markets:
        mid = str(m.get("id"))
        question = m.get("question", "N/A")
        prob = get_prob(m)
        volume = get_volume(m)

        if not mid or prob is None:
            continue

        # 💣 거래량 필터 (중요)
        if volume < 100000:
            continue

        if mid in last_data:
            prev = last_data[mid]
            diff = abs(prob - prev)

            # 💣 급변 조건
            if diff >= 10 and can_send(mid):

                msg = f"""🚨 확률 급변

{question}

📊 {prev:.1f}% → {prob:.1f}%
(변화 {diff:.1f}%)

💰 거래량: ${int(volume):,}

지금 시장 반응 움직이는 중
"""

                send(msg)
                mark_sent(mid)

        last_data[mid] = prob

def bot_loop():
    print("봇 시작")

    send("✅ 폴리마켓 알림 봇 정상 작동 시작")

    while True:
        check()
        time.sleep(60)

if __name__ == "__main__":
    thread = threading.Thread(target=bot_loop)
    thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
