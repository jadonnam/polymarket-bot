import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, concatenate_videoclips

W,H=1080,1920
BASE_DIR=os.path.dirname(__file__)
FONT_DIR=os.path.join(BASE_DIR,"fonts")
BOLD_PATH=os.path.join(FONT_DIR,"Pretendard-Bold.ttf")
REG_PATH=os.path.join(FONT_DIR,"Pretendard-Regular.ttf")

def _font(size,bold=False):
    path=BOLD_PATH if bold else REG_PATH
    return ImageFont.truetype(path,size) if os.path.exists(path) else ImageFont.load_default()

def _text_image(text,out_path,small=False):
    img=Image.new("RGB",(W,H),(8,12,18))
    draw=ImageDraw.Draw(img)
    title_font=_font(88 if not small else 76, True)
    sub_font=_font(34, False)
    bbox=draw.textbbox((0,0),text,font=title_font)
    x=(W-(bbox[2]-bbox[0]))//2
    draw.text((x,820), text, fill=(244,246,248), font=title_font)
    sub="전체 흐름은 피드에서 확인" if small else "지금 시장이 먼저 반응한 흐름"
    sb=draw.textbbox((0,0),sub,font=sub_font)
    draw.text(((W-(sb[2]-sb[0]))//2,960), sub, fill=(150,158,170), font=sub_font)
    img.save(out_path, quality=95)

def _prep(path,duration):
    clip=ImageClip(path).set_duration(duration)
    clip=clip.resize(height=H)
    if clip.w < W: clip=clip.resize(width=W)
    clip=clip.crop(x_center=clip.w/2,y_center=clip.h/2,width=W,height=H)
    clip=clip.resize(lambda t: 1 + 0.04*(t/duration))
    return clip

def build_reel(news_path="output_rank/rank_news.jpg", poly_path="output_rank/rank_poly.jpg", market_path="output_rank/rank_market.jpg", hook_text="지금 돈 흐름 바뀌었다", out_path="output_rank/reel_output.mp4"):
    Path("output_rank").mkdir(exist_ok=True)
    intro="output_rank/_reel_intro.jpg"; outro="output_rank/_reel_outro.jpg"
    _text_image(hook_text, intro, False); _text_image("전체 흐름은 피드에서 확인", outro, True)
    clips=[_prep(intro,2.6), _prep(news_path,3.8), _prep(poly_path,3.8), _prep(market_path,3.8), _prep(outro,2.4)]
    final=concatenate_videoclips(clips, method="compose")
    final.write_videofile(out_path, fps=30, codec="libx264", audio=False)
    return out_path
