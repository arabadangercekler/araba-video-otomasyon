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
- Net, tempolu ve anlaşılır konuş
- Sonunda net "Mit" veya "Gerçek" de
- Sadece konuşma metnini yaz
- Türkçe
- Maksimum 110 kelime
"""
    for i in range(5):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text and len(text) > 30:
                return text
        except Exception as e:
            print(f"Senaryo hatası ({i+1}): {e}")
            time.sleep(15)
    return None

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE, rate="+13%")
    await communicate.save(output_file)
    print("Ses oluşturuldu")

def extract_keywords(sentence):
    s = sentence.lower()
    base = ["BMW", "car"]
    if any(w in s for w in ["yağ", "oil", "silindir", "motor"]):
        base += ["engine"]
    elif any(w in s for w in ["duman", "smoke"]):
        base += ["exhaust"]
    elif any(w in s for w in ["km", "kilometre"]):
        base += ["dashboard"]
    else:
        base += ["vehicle"]
    return "+".join(base[:3])

def download_image(query, index):
    url = (
        f"https://pixabay.com/api/?key={PIXABAY_KEY}"
        f"&q={query}&image_type=photo&orientation=vertical"
        f"&per_page=10&safesearch=true"
    )
    try:
        r = requests.get(url, timeout=12)
        hits = r.json().get("hits", [])
        if not hits:
            return None
        hit = random.choice(hits)
        img_url = hit.get("largeImageURL") or hit.get("webformatURL")
        if not img_url:
            return None
        data = requests.get(img_url, timeout=10).content
        filename = f"img_{index}.jpg"
        with open(filename, "wb") as f:
            f.write(data)
        return filename
    except Exception as e:
        print(f"Görsel hatası: {e}")
        return None

def download_images_for_sentences(sentences):
    images = []
    for i, sentence in enumerate(sentences):
        query = extract_keywords(sentence)
        print(f"→ {query}")
        img = download_image(query, i)
        if not img:
            img = download_image("BMW+car", i)
        if img:
            images.append(img)
    return images

def make_moving_clip(img_path, duration, move_type=0):
    bg = ColorClip(size=(W, H), color=(0, 0, 0)).with_duration(duration)

    clip = ImageClip(img_path)

    ratio = clip.w / max(clip.h, 1)
    target = W / H
    if ratio > target:
        clip = clip.resized(height=H)
    else:
        clip = clip.resized(width=W)

    clip = clip.resized(1.35)

    def zoom(t):
        p = t / max(duration, 0.1)
        return 1.0 + 0.12 * p

    clip = clip.resized(zoom).with_duration(duration)

    if move_type == 0:
        def pos(t):
            p = t / max(duration, 0.1)
            return (50 * p, -25 * p)
    elif move_type == 1:
        def pos(t):
            p = t / max(duration, 0.1)
            return (-50 * p, -25 * p)
    else:
        def pos(t):
            p = t / max(duration, 0.1)
            return (0, -40 * p)

    clip = clip.with_position(pos)
    clip = clip.cropped(width=W, height=H, x_center=clip.w/2, y_center=clip.h/2)

    final = CompositeVideoClip([bg, clip], size=(W, H))
    final = final.with_duration(duration)
    final = final.resized((W, H))
    return final

def create_hook(duration=2.5):
    txt = TextClip(
        text="BMW 200.000 KM SONRA\nBOZULUR MU?",
        font_size=42,
        color="white",
        stroke_color="black",
        stroke_width=3,
        method="caption",
        size=(W - 140, None),
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )
    return txt.with_duration(duration).with_position(("center", 220))

def create_subtitles(sentences, total_duration):
    if not sentences:
        return []
    dur = total_duration / len(sentences)
    clips = []
    for i, sentence in enumerate(sentences):
        short = sentence if len(sentence) < 40 else sentence[:37] + "..."
        wrapped = textwrap.fill(short, width=17)
        txt = TextClip(
            text=wrapped,
            font_size=28,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(W - 120, None),
            font="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        )
        txt = txt.with_start(i * dur).with_duration(max(dur * 0.8, 0.6))
        txt = txt.with_position(("center", H - 360))
        clips.append(txt)
    return clips

def split_sentences(script):
    parts = re.split(r'(?<=[.!?])\s+', script)
    return [p.strip() for p in parts if len(p.strip()) > 6] or [script]

def create_video(script, audio_file, images, sentences, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration

    target_count = max(len(sentences) + 2, 8)
    while len(images) < target_count:
        images.append(random.choice(images))
    images = images[:target_count]

    clip_dur = duration / len(images)
    img_clips = []

    for i, img in enumerate(images):
        try:
            clip = make_moving_clip(img, clip_dur, i % 3)
            clip = clip.resized((W, H))
            img_clips.append(clip)
        except Exception as e:
            print(f"Clip hatası: {e}")

    if not img_clips:
        raise Exception("Görsel klipler oluşmadı")

    video = concatenate_videoclips(img_clips, method="compose")
    video = video.resized((W, H))
    video = video.with_audio(audio).with_duration(duration)

    final = CompositeVideoClip(
        [video, create_hook(2.5)] + create_subtitles(sentences, duration),
        size=(W, H)
    )
    final = final.with_duration(duration)
    final = final.resized((W, H))

    print(f"Final boyut: {final.w}x{final.h}")

    final.write_videofile(
        output,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None
    )
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

    print("3. Cümleler...")
    sentences = split_sentences(script)
    print(f"{len(sentences)} cümle")

    print("4. Görseller...")
    images = download_images_for_sentences(sentences)
    if len(images) < 2:
        print("Görsel yetersiz")
        return

    print("5. Video...")
    create_video(script, "ses.mp3", images, sentences)
    print("Bitti → video.mp4")

if __name__ == "__main__":
    main()
