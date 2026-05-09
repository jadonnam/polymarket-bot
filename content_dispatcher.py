import json
import os
from typing import Iterable, Optional

import requests

BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
CHAT_ID = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
STORAGE_CHAT_ID = (os.getenv("TELEGRAM_STORAGE_CHAT_ID") or "").strip()
DRY_RUN = (os.getenv("DRY_RUN") or "false").lower() == "true"


def _check() -> None:
    if DRY_RUN:
        return
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    if not CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID not set")


def _url(method: str) -> str:
    return f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"


def _check_storage() -> None:
    if DRY_RUN:
        return
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    if not STORAGE_CHAT_ID:
        raise RuntimeError("TELEGRAM_STORAGE_CHAT_ID not set")


def send_message(text: str) -> None:
    # Legacy information-channel sender (unused in main_instagram.py)
    _check()
    if DRY_RUN:
        print("[DRY_RUN] send_message")
        print(text[:500])
        return
    res = requests.post(
        _url("sendMessage"),
        data={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": "true"},
        timeout=30,
    )
    res.raise_for_status()


def send_image(path: str, caption: str = "") -> None:
    # Legacy information-channel sender (unused in main_instagram.py)
    _check()
    if DRY_RUN:
        print(f"[DRY_RUN] send_image: {path} | {caption[:120]}")
        return
    with open(path, "rb") as f:
        res = requests.post(
            _url("sendPhoto"),
            data={"chat_id": CHAT_ID, "caption": caption},
            files={"photo": f},
            timeout=60,
        )
    res.raise_for_status()


def send_video(path: str, caption: str = "") -> None:
    # Legacy information-channel sender (unused in main_instagram.py)
    _check()
    if DRY_RUN:
        print(f"[DRY_RUN] send_video: {path} | {caption[:120]}")
        return
    with open(path, "rb") as f:
        res = requests.post(
            _url("sendVideo"),
            data={"chat_id": CHAT_ID, "caption": caption, "supports_streaming": "true"},
            files={"video": f},
            timeout=180,
        )
    res.raise_for_status()


def send_storage_video(path: str, caption: str = "") -> None:
    _check_storage()
    if DRY_RUN:
        print(f"[DRY_RUN] send_storage_video: {path} | {caption[:120]}")
        return
    with open(path, "rb") as f:
        res = requests.post(
            _url("sendVideo"),
            data={"chat_id": STORAGE_CHAT_ID, "caption": caption, "supports_streaming": "true"},
            files={"video": f},
            timeout=180,
        )
    res.raise_for_status()


def send_storage_image(path: str, caption: str = "") -> None:
    _check_storage()
    if DRY_RUN:
        print(f"[DRY_RUN] send_storage_image: {path} | {caption[:120]}")
        return
    with open(path, "rb") as f:
        res = requests.post(
            _url("sendPhoto"),
            data={"chat_id": STORAGE_CHAT_ID, "caption": caption},
            files={"photo": f},
            timeout=60,
        )
    res.raise_for_status()


def send_storage_document(path: str, caption: str = "") -> None:
    _check_storage()
    if DRY_RUN:
        print(f"[DRY_RUN] send_storage_document: {path} | {caption[:120]}")
        return
    with open(path, "rb") as f:
        res = requests.post(
            _url("sendDocument"),
            data={"chat_id": STORAGE_CHAT_ID, "caption": caption},
            files={"document": f},
            timeout=120,
        )
    res.raise_for_status()


def send_storage_message(text: str) -> None:
    _check_storage()
    if DRY_RUN:
        print("[DRY_RUN] send_storage_message")
        print(str(text)[:500])
        return
    res = requests.post(
        _url("sendMessage"),
        data={"chat_id": STORAGE_CHAT_ID, "text": text, "disable_web_page_preview": "true"},
        timeout=30,
    )
    res.raise_for_status()


def send_media_group(paths: Iterable[str]) -> None:
    # Legacy information-channel sender (unused in main_instagram.py)
    _check()
    paths = list(paths)
    if DRY_RUN:
        print("[DRY_RUN] send_media_group:", paths)
        return
    files = {}
    media = []
    try:
        for idx, path in enumerate(paths):
            key = f"file{idx}"
            files[key] = open(path, "rb")
            media.append({"type": "photo", "media": f"attach://{key}"})
        res = requests.post(
            _url("sendMediaGroup"),
            data={"chat_id": CHAT_ID, "media": json.dumps(media, ensure_ascii=False)},
            files=files,
            timeout=180,
        )
        res.raise_for_status()
    finally:
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass


def send_storage_media_group(paths: Iterable[str]) -> None:
    _check_storage()
    paths = list(paths)
    if DRY_RUN:
        print("[DRY_RUN] send_storage_media_group:", paths)
        return
    files = {}
    media = []
    try:
        for idx, path in enumerate(paths):
            key = f"file{idx}"
            files[key] = open(path, "rb")
            media.append({"type": "photo", "media": f"attach://{key}"})
        res = requests.post(
            _url("sendMediaGroup"),
            data={"chat_id": STORAGE_CHAT_ID, "media": json.dumps(media, ensure_ascii=False)},
            files=files,
            timeout=180,
        )
        res.raise_for_status()
    finally:
        for f in files.values():
            try:
                f.close()
            except Exception:
                pass
