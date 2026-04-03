import os
import time
import threading
import requests
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

last_data = {}

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def get_markets():
    url = "https://gamma-api.polymarket.com/markets?limit=50&active=true"
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

def send(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHANNEL_ID,
        "text": msg
    })

def check():
    global last_data
    send("봇 살아있음 테스트")
    markets = get_markets()

    for m in markets:
        mid = m.get("id")
        q = m.get("question", "N/A")
        prob = get_prob(m)

        if not mid or prob is None:
            continue

        if mid in last_data:
            prev = last_data[mid]
            diff = abs(prob - prev)

            if diff >= 10:
                msg = f"""🚨 확률 급변

{q}

📊 {prev:.1f}% → {prob:.1f}%
(변화 {diff:.1f}%)

지금 돈 몰리는 중
"""
                send(msg)

        last_data[mid] = prob

def bot_loop():
    print("봇 시작")

    while True:
        check()
        time.sleep(60)

if __name__ == "__main__":
    thread = threading.Thread(target=bot_loop)
    thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
