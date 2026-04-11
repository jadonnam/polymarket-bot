import os
from pathlib import Path
from typing import Optional

from instagrapi import Client

USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()
SESSION_PATH = os.getenv("INSTAGRAM_SESSION_PATH", "instagram_session.json").strip()

HASHTAGS = "#비트코인 #코인 #경제 #투자 #재테크 #주식 #환율 #금리 #돈흐름 #경제뉴스"


def _session_candidates() -> list[str]:
    candidates = []
    if SESSION_PATH:
        candidates.append(SESSION_PATH)
    candidates.extend([
        "instagram_session.json",
        "instagram_session(1).json",
    ])
    out = []
    seen = set()
    for path in candidates:
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


def _existing_session_path() -> Optional[str]:
    for path in _session_candidates():
        if os.path.exists(path):
            return path
    return None


def _save_session(cl: Client) -> str:
    path = SESSION_PATH or "instagram_session.json"
    parent = Path(path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    cl.dump_settings(path)
    return path


def login_with_session(cl: Client) -> str:
    session_path = _existing_session_path()
    if session_path:
        print(f"[인스타] 세션 로드: {session_path}")
        cl.load_settings(session_path)
        try:
            cl.get_timeline_feed()
            print("[인스타] 세션 로그인 성공")
            return session_path
        except Exception as e:
            print(f"[인스타] 세션 만료 → 재로그인 시도: {repr(e)}")

    if not USERNAME or not PASSWORD:
        raise RuntimeError("INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD 없음")

    cl.login(USERNAME, PASSWORD)
    saved = _save_session(cl)
    print(f"[인스타] 재로그인 후 세션 저장 완료: {saved}")
    return saved


def _build_caption(caption: str) -> str:
    caption = (caption or "").strip()
    if caption:
        return caption + "\n\n" + HASHTAGS
    return HASHTAGS


def upload_instagram(image_path: str, caption: str):
    if not os.path.exists(image_path):
        raise RuntimeError(f"이미지 파일 없음: {image_path}")

    cl = Client()
    try:
        session_path = login_with_session(cl)
    except Exception as e:
        print(f"[인스타 로그인 실패] {repr(e)}")
        return None

    try:
        final_caption = _build_caption(caption)
        print(f"[인스타 업로드] {image_path}")
        media = cl.photo_upload(image_path, final_caption)
        print(f"[인스타 업로드 성공] media_pk={getattr(media, 'pk', None)}")
        cl.dump_settings(session_path)
        return media
    except Exception as e:
        print(f"[인스타 업로드 실패] {repr(e)}")
        return None


def upload_reel(video_path: str, caption: str):
    if not os.path.exists(video_path):
        raise RuntimeError(f"영상 파일 없음: {video_path}")

    cl = Client()
    try:
        session_path = login_with_session(cl)
    except Exception as e:
        print(f"[인스타 로그인 실패] {repr(e)}")
        return None

    try:
        final_caption = _build_caption(caption)
        print(f"[인스타 릴스 업로드] {video_path}")
        media = cl.clip_upload(video_path, final_caption)
        print(f"[인스타 릴스 업로드 성공] media_pk={getattr(media, 'pk', None)}")
        cl.dump_settings(session_path)
        return media
    except Exception as e:
        print(f"[인스타 릴스 업로드 실패] {repr(e)}")
        return None
