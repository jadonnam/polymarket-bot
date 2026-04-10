import os
from instagrapi import Client

USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()
SESSION_PATH = os.getenv("INSTAGRAM_SESSION_PATH", "instagram_session.json").strip()

HASHTAGS = "#비트코인 #코인 #경제 #투자 #재테크 #주식 #환율 #금리 #돈흐름 #경제뉴스"


def login_with_session(cl: Client):
    if not os.path.exists(SESSION_PATH):
        raise RuntimeError("instagram_session.json 없음")

    print(f"[인스타] 세션 로드: {SESSION_PATH}")
    cl.load_settings(SESSION_PATH)

    try:
        cl.get_timeline_feed()
        print("[인스타] 세션 로그인 성공")
    except Exception as e:
        print(f"[인스타] 세션 만료 → 재로그인 시도: {repr(e)}")
        cl.login(USERNAME, PASSWORD)
        cl.dump_settings(SESSION_PATH)
        print("[인스타] 재로그인 후 세션 저장 완료")


def upload_instagram(image_path, caption):
    if not USERNAME or not PASSWORD:
        raise RuntimeError("INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD 없음")

    if not os.path.exists(image_path):
        raise RuntimeError(f"이미지 파일 없음: {image_path}")

    cl = Client()

    try:
        login_with_session(cl)
    except Exception as e:
        print(f"[인스타 로그인 실패] {repr(e)}")
        return

    try:
        final_caption = caption.strip() + "\n\n" + HASHTAGS

        print(f"[인스타 업로드] {image_path}")
        media = cl.photo_upload(image_path, final_caption)
        print(f"[인스타 업로드 성공] media_pk={getattr(media, 'pk', None)}")

        cl.dump_settings(SESSION_PATH)
        return media

    except Exception as e:
        print(f"[인스타 업로드 실패] {repr(e)}")
        return