import os
from moviepy.editor import (
    ImageClip,
    CompositeVideoClip,
    AudioFileClip,
    concatenate_videoclips,
    TextClip
)

W, H = 1080, 1920

def make_zoom_clip(image_path: str, duration: float):
    clip = ImageClip(image_path).set_duration(duration)
    clip = clip.resize(height=H)
    if clip.w < W:
        clip = clip.resize(width=W)
    clip = clip.crop(x_center=clip.w / 2, y_center=clip.h / 2, width=W, height=H)
    clip = clip.resize(lambda t: 1 + 0.05 * (t / duration))
    return clip.set_position("center")

def make_caption(text: str, duration: float, y: int):
    txt = TextClip(
        text,
        fontsize=72,
        color="white",
        method="caption",
        size=(900, None),
        align="center",
        stroke_color="black",
        stroke_width=2,
    ).set_duration(duration)
    return txt.set_position(("center", y))

def make_scene(image_path: str, caption: str, duration: float):
    bg = make_zoom_clip(image_path, duration)
    cap = make_caption(caption, duration, y=1450)
    return CompositeVideoClip([bg, cap], size=(W, H)).set_duration(duration)

def build_reel(news_path, poly_path, market_path, music_path=None, out_path="reel_output.mp4"):
    captions = [
        "지금 돈 흐름 바뀌었다",
        "오늘 뉴스 1위 이슈",
        "폴리마켓은 이렇게 본다",
        "전체 흐름은 피드에서 확인",
    ]

    scenes = [
        make_scene(news_path, captions[0], 3.5),
        make_scene(poly_path, captions[1], 4.0),
        make_scene(market_path, captions[2], 4.0),
    ]

    end_clip = TextClip(
        captions[3],
        fontsize=80,
        color="white",
        size=(W, H),
        method="caption",
        align="center"
    ).set_duration(3.5)

    final = concatenate_videoclips(scenes + [end_clip], method="compose")

    if music_path and os.path.exists(music_path):
        audio = AudioFileClip(music_path).subclip(0, min(final.duration, AudioFileClip(music_path).duration))
        audio = audio.volumex(0.25)
        final = final.set_audio(audio)

    final.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac")

if __name__ == "__main__":
    build_reel(
        news_path="output_rank/rank_news.jpg",
        poly_path="output_rank/rank_poly.jpg",
        market_path="output_rank/rank_market.jpg",
        music_path=None,
        out_path="reel_output.mp4",
    )
