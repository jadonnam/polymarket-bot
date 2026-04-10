import os
from instagrapi import Client

USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()
SESSION_PATH = os.getenv("INSTAGRAM_SESSION_PATH", "instagram_session.json").strip()


def login_with_session(cl: Client):
    if not os.path.exists(SESSION_PATH):
        raise RuntimeError("❌ instagram_session.json 없음 (먼저 로컬에서 생성해야 함)")

    print(f"[인스타] 세션 로드: {SESSION_PATH}")
    cl.load_settings(SESSION_PATH)

    try:
        # 🔥 여기 중요: 로그인 시도 안하고 세션만 검증
        cl.get_timeline_feed()
        print("[인스타] 세션 로그인 성공")
    except Exception as e:
        print(f"[인스타] 세션 만료 → 재로그인 시도: {e}")

        # ⚠️ 재로그인은 실패할 수 있음 (IP 문제)
        cl.login(USERNAME, PASSWORD)
        cl.dump_settings(SESSION_PATH)
        print("[인스타] 재로그인 후 세션 저장 완료")


def upload_instagram(image_path, caption):
    if not USERNAME or not PASSWORD:
        raise RuntimeError("INSTAGRAM_USERNAME / PASSWORD 없음")

    if not os.path.exists(image_path):
        raise RuntimeError(f"이미지 없음: {image_path}")

    cl = Client()

    try:
        login_with_session(cl)
    except Exception as e:
        print(f"[인스타 로그인 실패] {repr(e)}")
        return

    try:
        print(f"[인스타 업로드] {image_path}")
        media = cl.photo_upload(image_path, caption)
        print(f"[인스타 업로드 성공] media_pk={getattr(media, 'pk', None)}")

        # 최신 세션 저장
        cl.dump_settings(SESSION_PATH)

    except Exception as e:
        print(f"[인스타 업로드 실패] {repr(e)}")
