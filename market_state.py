import json
import os
from datetime import datetime

STATE_FILE = "market_state.json"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(data):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_market_snapshot(question):
    state = load_state()
    return state.get(question)

def update_market_snapshot(question, volume, yes_price):
    state = load_state()
    state[question] = {
        "volume": float(volume) if volume is not None else 0.0,
        "yes_price": float(yes_price) if yes_price is not None else 0.0,
        "updated_at": datetime.now().isoformat()
    }
    save_state(state)

def detect_surge(question, volume, yes_price):
    prev = get_market_snapshot(question)

    try:
        volume = float(volume)
    except:
        volume = 0.0

    try:
        yes_price = float(yes_price)
    except:
        yes_price = 0.0

    if not prev:
        return False

    prev_volume = float(prev.get("volume", 0.0))
    prev_yes_price = float(prev.get("yes_price", 0.0))

    volume_diff = volume - prev_volume
    price_diff = abs(yes_price - prev_yes_price)

    if volume_diff >= 300000:
        return True

    if prev_volume > 0 and (volume / prev_volume) >= 1.8:
        return True

    if price_diff >= 0.12:
        return True

    return False