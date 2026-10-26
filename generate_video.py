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

def generate_script(topic):
    prompt = f"""
Sen profesyonel bir Türk YouTube Shorts senaristisin.
Konu: {topic}

40-50 saniyelik güçlü bir Shorts senaryosu yaz.

Kurallar:
- İlk 3 saniyede güçlü kanca
- Net ve anlaşılır konuş
- Sonunda net "Mit" veya "Gerçek" de
- Sadece konuşma metnini yaz
- Türkçe
- Maksimum 100 kelime
"""
    for i in range(4):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text and len(text) > 30:
                return text
        except Exception as e:
            print(f"Senaryo hatası ({i+1}): {e}")
            time.sleep(12)
    return None

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    await communicate.save(output_file)
    print("Ses oluşturuldu")

def download_images(count=8):
    images = []
    query = "BMW+car"
    url = (
        f"https://pixabay.com/api/?key={PIXABAY_KEY}"
        f"&q={query}&image_type=photo&orientation=vertical"
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

def make_clip(img_path, duration):
    bg = ColorClip(size=(W, H), color=(0, 0, 0)).with_duration(duration)
    clip = ImageClip(img_path)

    if clip.w / clip.h > W / H:
        clip = clip.resized(height=H)
    else:
        clip = clip.resized(width=W)

    clip = clip.resized(1.2)

    def zoom(t):
        return 1.0 + 0.10 * (t / max(duration, 0.1))

    clip = clip.resized(zoom).with_duration(duration)
    clip = clip.with_position("center")
    clip = clip.cropped(width=W, height=H, x_center=clip.w/2, y_center=clip.h/2)

    final = CompositeVideoClip([bg, clip], size=(W, H)).with_duration(duration)
    return final.resized((W, H))

def create_hook(duration=2.5):
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
        txt = txt.with_position(("center", H - 300))
    )
    return txt.with_duration(duration).with_position(("center", 200))

def create_subtitles(script, total_duration):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if len(s.strip()) > 5]
    if not sentences:
        return []
    dur = total_duration / len(sentences)
    clips = []
    for i, sentence in enumerate(sentences):
        short = sentence if len(sentence) < 36 else sentence[:33] + "..."
        wrapped = textwrap.fill(short, width=16)
        txt = TextClip(
            text=wrapped,
            font_size=26,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(W - 140, None),
            font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        txt = txt.with_start(i * dur).with_duration(max(dur * 0.85, 0.7))
        txt = txt.with_position(("center", H - 320))
        clips.append(txt)
    return clips

def create_video(script, audio_file, images, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration

    while len(images) < 6:
        images.append(random.choice(images))
    images = images[:8]

    clip_dur = duration / len(images)
    img_clips = [make_clip(img, clip_dur) for img in images]

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
    if not script:
        print("Senaryo yok")
        return

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
