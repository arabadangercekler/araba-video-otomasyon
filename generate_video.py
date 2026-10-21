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
    concatenate_videoclips
)

# ===================== AYARLAR =====================
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
PIXABAY_KEY = os.environ["PIXABAY_API_KEY"]
MODEL_NAME = "gemini-3.8-flash"
VOICE = "tr-TR-EmelNeural"
W, H = 1080, 1920

model = genai.GenerativeModel(MODEL_NAME)

# ===================== SENARYO =====================
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

# ===================== SES =====================
async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate="+12%"
    )
    await communicate.save(output_file)
    print("Ses oluşturuldu")

# ===================== GÖRSEL =====================
def extract_keywords(sentence):
    s = sentence.lower()
    base = ["BMW", "car"]

    if any(w in s for w in ["yağ", "oil"]):
        base += ["engine"]
    elif any(w in s for w in ["silindir", "motor"]):
        base += ["engine", "motor"]
    elif any(w in s for w in ["duman", "smoke"]):
        base += ["exhaust"]
    elif any(w in s for w in ["km", "kilometre", "milyon"]):
        base += ["dashboard"]
    else:
        base += ["vehicle"]

    return "+".join(base[:3])

def download_image(query, index):
    url = (
        f"https://pixabay.com/api/?key={PIXABAY_KEY}"
        f"&q={query}&image_type=photo&orientation=vertical"
        f"&per_page=8&safesearch=true"
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

# ===================== HAREKET (DÜZELTİLMİŞ) =====================
def make_moving_clip(img_path, duration):
    clip = ImageClip(img_path)
    clip = clip.resized(height=int(H * 1.2))

    def zoom(t):
        # Yavaş ve belirgin zoom
        return 1.0 + 0.22 * (t / max(duration, 0.1))

    clip = clip.resized(zoom)
    clip = clip.with_duration(duration)
    clip = clip.cropped(width=W, height=H, x_center=clip.w/2, y_center=clip.h/2)
    return clip

# ===================== YAZILAR =====================
def create_hook(duration=2.6):
    txt = TextClip(
        text="BMW 200.000 KM SONRA\nBOZULUR MU?",
        font_size=56,
        color="white",
        stroke_color="black",
        stroke_width=4,
        method="caption",
        size=(W - 70, None)
    )
    return txt.with_duration(duration).with_position("center")

def create_subtitles(sentences, total_duration):
    if not sentences:
        return []
    dur = total_duration / len(sentences)
    clips = []

    for i, sentence in enumerate(sentences):
        short = sentence if len(sentence) < 48 else sentence[:45] + "..."
        wrapped = textwrap.fill(short, width=20)

        txt = TextClip(
            text=wrapped,
            font_size=38,
            color="white",
            stroke_color="black",
            stroke_width=3,
            method="caption",
            size=(W - 80, None)
        )
        txt = txt.with_start(i * dur).with_duration(max(dur * 0.8, 0.6))
        txt = txt.with_position(("center", H - 380))
        clips.append(txt)

    return clips

def split_sentences(script):
    parts = re.split(r'(?<=[.!?])\s+', script)
    return [p.strip() for p in parts if len(p.strip()) > 6] or [script]

# ===================== VİDEO =====================
def create_video(script, audio_file, images, sentences, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration

    while len(images) < len(sentences):
        images.append(random.choice(images))
    images = images[:len(sentences)]

    clip_dur = duration / len(images)
    img_clips = []

    for img in images:
        try:
            img_clips.append(make_moving_clip(img, clip_dur))
        except Exception as e:
            print(f"Clip hatası: {e}")

    if not img_clips:
        raise Exception("Görsel klipler oluşmadı")

    video = concatenate_videoclips(img_clips, method="compose")
    video = video.with_audio(audio).with_duration(duration)

    final = CompositeVideoClip(
        [video, create_hook(2.6)] + create_subtitles(sentences, duration),
        size=(W, H)
    ).with_duration(duration)

    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    return output

# ===================== ANA =====================
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
