import os

TELEGRAM_BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
TELEGRAM_CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()

CHECK_INTERVAL = int((os.getenv("CHECK_INTERVAL") or "1800").strip())
