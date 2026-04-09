import os
import base64
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

IMAGE_MODEL = "dall-e-3"
IMAGE_QUALITY = "hd"

def generate_bg(prompt, output_path="bg.jpg"):
    result = client.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size="1024x1536",
        quality=IMAGE_QUALITY,
    )

    image_bytes = base64.b64decode(result.data[0].b64_json)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    print(f"[DALL-E] 생성 완료: {output_path}")
    return output_path


def safe_generate_bg(**kwargs):
    prompt = kwargs.get("context_title", "") + "\n" + kwargs.get("context_desc", "")
    return generate_bg(prompt)
