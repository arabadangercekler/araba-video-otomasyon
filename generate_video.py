import os
import time
import asyncio
import random
import re
import textwrap
import requests
import google.generativeai as genai
import edge_tts
from moviepy import (
    ImageClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip
)

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
PIXABAY_KEY = os.environ["PIXABAY_API_KEY"]
MODEL_NAME = "gemini-3.8-flash"
VOICE = "tr-TR-EmelNeural"
W, H = 1080, 1920

model = genai.GenerativeModel(MODEL_NAME)

FALLBACK_SCRIPT = """
BMW 200 bin kilometre sonra bozulur mu? Çoğu kişi bunu mit sanıyor. 
Aslında düzenli bakımlı bir BMW 300-400 bin kilometreyi rahat görüyor. 
Asıl sorun ucuz yağ ve ihmal edilen bakımlar. 
Sonuç: Mit. Bakım yapılırsa uzun ömürlü.
"""

def generate_script(topic):
    try:
        response = model.generate_content(f"""
Sen profesyonel Türk YouTube Shorts senaristisin.
Konu: {topic}
40-50 saniyelik senaryo yaz. İlk 3 saniyede kanca.
Sonunda Mit veya Gerçek de. Sadece konuşma metni. Türkçe. Max 100 kelime.
""")
        text = response.text.strip()
        if text and len(text) > 30:
            print("Gemini senaryosu alındı")
            return text
    except Exception as e:
        print(f"Gemini hatası: {e}")
    print("Yedek senaryo kullanılıyor")
    return FALLBACK_SCRIPT.strip()

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    await communicate.save(output_file)
    print("Ses oluşturuldu")

def download_images(count=8):
    images = []
    url = (
        f"https://pixabay.com/api/?key={PIXABAY_KEY}"
        f"&q=BMW+car&image_type=photo&orientation=vertical"
        f"&per_page={count}&safesearch=true"
    )
    try:
        r = requests.get(url, timeout=12)
        hits = r.json().get("hits", [])
        for i, hit in enumerate(hits[:count]):
            img_url = hit.get("largeImageURL") or hit.get("webformatURL")
            if not img_url:
                continue
            data = requests.get(img_url, timeout=10).content
            filename = f"img_{i}.jpg"
            with open(filename, "wb") as f:
                f.write(data)
            images.append(filename)
            print(f"Görsel {i+1} indirildi")
    except Exception as e:
        print(f"Görsel hatası: {e}")
    return images

def make_clip(img_path, duration, move_type=0):
    bg = ColorClip(size=(W, H), color=(0, 0, 0)).with_duration(duration)
    clip = ImageClip(img_path)

    # Ekranı rahat dolduracak şekilde büyüt
    if clip.w / clip.h > W / H:
        clip = clip.resized(height=int(H * 1.5))
    else:
        clip = clip.resized(width=int(W * 1.5))

    clip = clip.with_duration(duration)

    # Zoom in veya zoom out
    if move_type == 0:  # yakınlaş
        def scale(t):
            p = t / max(duration, 0.1)
            return 1.0 + 0.20 * p
    elif move_type == 1:  # uzaklaş
        def scale(t):
            p = t / max(duration, 0.1)
            return 1.20 - 0.20 * p
    else:  # hafif yakınlaş
        def scale(t):
            p = t / max(duration, 0.1)
            return 1.0 + 0.12 * p

    clip = clip.resized(scale)

    # Ortadan sabit kırp (taşma olmasın)
    clip = clip.cropped(width=W, height=H, x_center=clip.w / 2, y_center=clip.h / 2)

    final = CompositeVideoClip([bg, clip.with_position("center")], size=(W, H))
    return final.with_duration(duration).resized((W, H))

def create_hook(duration=2.5):
    txt = TextClip(
        text="BMW 200.000 KM SONRA\nBOZULUR MU?",
        font_size=36,
        color="white",
        stroke_color="black",
        stroke_width=3,
        method="caption",
        size=(W - 180, None),
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )
    return txt.with_duration(duration).with_position(("center", 180))

def create_subtitles(script, total_duration):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if len(s.strip()) > 5]
    if not sentences:
        return []
    dur = total_duration / len(sentences)
    clips = []
    for i, sentence in enumerate(sentences):
        short = sentence if len(sentence) < 34 else sentence[:31] + "..."
        wrapped = textwrap.fill(short, width=15)
        txt = TextClip(
            text=wrapped,
            font_size=24,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(W - 160, None),
            font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        txt = txt.with_start(i * dur).with_duration(max(dur * 0.85, 0.7))
        txt = txt.with_position(("center", H - 280))
        clips.append(txt)
    return clips

def create_video(script, audio_file, images, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration

    while len(images) < 6:
        images.append(random.choice(images))
    images = images[:8]

    clip_dur = duration / len(images)
    img_clips = [make_clip(img, clip_dur, i % 3) for i, img in enumerate(images)]

    video = concatenate_videoclips(img_clips, method="compose").resized((W, H))
    video = video.with_audio(audio).with_duration(duration)

    final = CompositeVideoClip(
        [video, create_hook(2.5)] + create_subtitles(script, duration),
        size=(W, H)
    ).with_duration(duration).resized((W, H))

    print(f"Final boyut: {final.w}x{final.h}")
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    return output

def main():
    topic = "BMW arabalar 200 bin km sonra sürekli arıza yapar miti"

    print("1. Senaryo...")
    script = generate_script(topic)

    print("2. Ses...")
    asyncio.run(text_to_speech(script, "ses.mp3"))

    print("3. Görseller...")
    images = download_images(8)
    if len(images) < 3:
        print("Görsel yetersiz")
        return

    print("4. Video...")
    create_video(script, "ses.mp3", images)
    print("Bitti → video.mp4")

if __name__ == "__main__":
    main()
