import os
from instagrapi import Client

USERNAME = os.getenv("INSTAGRAM_USERNAME")
PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

def upload_instagram(image_path, caption):
    cl = Client()
    cl.login(USERNAME, PASSWORD)
    cl.photo_upload(image_path, caption)
    print("[인스타 업로드 완료]")
