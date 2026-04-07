import json
import os

SENT_FILE = "sent_history.json"
TOPIC_FILE = "topic_history.json"

def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_history():
    return _load_json(SENT_FILE, [])

def save_history(data):
    _save_json(SENT_FILE, data)

def is_duplicate(title):
    history = load_history()
    return title in history

def add_history(title):
    history = load_history()
    history.append(title)
    history = history[-100:]
    save_history(history)

def load_topics():
    return _load_json(TOPIC_FILE, [])

def save_topics(data):
    _save_json(TOPIC_FILE, data)

def is_same_topic(topic):
    if topic in ["general", "sports", "other", "unknown", ""]:
        return False
    topics = load_topics()
    if not topics:
        return False
    return topics[-1] == topic

def add_topic(topic):
    if topic in ["general", "sports", "other", "unknown", ""]:
        return
    topics = load_topics()
    topics.append(topic)
    topics = topics[-30:]
    save_topics(topics)