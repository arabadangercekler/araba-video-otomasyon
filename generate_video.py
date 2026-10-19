import os
import time
import asyncio
import random
import textwrap
import requests
import google.generativeai as genai
import edge_tts
from moviepy import (
    ImageClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip
)

# === AYARLAR ===
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

Sadece 40-50 saniyelik çok güçlü bir Shorts senaryosu yaz.

Kurallar:
- İlk 3 saniyede izleyiciyi kilitleyen güçlü bir kanca olsun
- Çok net ve hızlı anlat
- Sonunda net "Mit" veya "Gerçek" de
- Sadece konuşma metnini yaz
- Türkçe yaz
- Maksimum 130 kelime
"""
    for i in range(5):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text:
                return text
        except Exception as e:
            print(f"Senaryo hatası (deneme {i+1}): {e}")
            time.sleep(20)
    return None

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def download_car_images(count=12):
    images = []
    # Daha sıkı arama - insan olasılığını azalt
    query = "BMW+car+exterior+OR+BMW+vehicle+closeup"
    url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={query}&image_type=photo&orientation=vertical&per_page={count}&safesearch=true"
    
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        hits = data.get("hits", [])
        
        for i, hit in enumerate(hits[:count]):
            img_url = hit.get("largeImageURL") or hit.get("webformatURL")
            if not img_url:
                continue
            img_data = requests.get(img_url, timeout=10).content
            filename = f"img_{i}.jpg"
            with open(filename, "wb") as f:
                f.write(img_data)
            images.append(filename)
            print(f"Görsel indirildi: {i+1}")
    except Exception as e:
        print(f"Görsel indirme hatası: {e}")
    
    return images

def make_ken_burns_clip(img_path, duration):
    clip = ImageClip(img_path)
    clip = clip.resized(height=int(H * 1.2))
    
    direction = random.choice([-1, 1])
    
    def pos(t):
        progress = t / max(duration, 0.1)
        x = direction * 60 * progress
        y = -40 * progress
        return (x, y)
    
    clip = clip.with_position(pos).with_duration(duration)
    clip = clip.cropped(width=W, height=H, x_center=clip.w/2, y_center=clip.h/2)
    return clip

def create_subtitle_clips(script, total_duration):
    """Basit cümle bazlı altyazı"""
    sentences = [s.strip() for s in script.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if not sentences:
        return []
    
    clip_duration = total_duration / len(sentences)
    clips = []
    
    for i, sentence in enumerate(sentences):
        # Uzun cümleleri kırp
        wrapped = textwrap.fill(sentence, width=30)
        
        txt = TextClip(
            text=wrapped,
            font_size=55,
            color="white",
            stroke_color="black",
            stroke_width=3,
            method="caption",
            size=(W - 100, None)
        )
        txt = txt.with_duration(clip_duration - 0.15)
        txt = txt.with_start(i * clip_duration)
        txt = txt.with_position(("center", H - 350))
        clips.append(txt)
    
    return clips

def create_hook_text(duration=3.5):
    """Başta dikkat çekici kanca yazısı"""
    txt = TextClip(
        text="BMW 200.000 KM SONRA\nBOZULUR MU?",
        font_size=70,
        color="white",
        stroke_color="black",
        stroke_width=4,
        method="caption",
        size=(W - 80, None)
    )
    txt = txt.with_duration(duration)
    txt = txt.with_position("center")
    return txt

def create_video(script, audio_file, image_files, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    clip_duration = duration / max(len(image_files), 1)

    # Görsel klipler
    img_clips = []
    for img in image_files:
        try:
            clip = make_ken_burns_clip(img, clip_duration)
            # Hafif geçiş için fade
            clip = clip.with_effects([])  # placeholder
            img_clips.append(clip)
        except Exception as e:
            print(f"Clip hatası: {e}")
            continue

    if not img_clips:
        raise Exception("Hiç görsel yüklenemedi")

    video = concatenate_videoclips(img_clips, method="compose")
    video = video.with_audio(audio).with_duration(duration)

    # Altyazılar + kanca
    subtitles = create_subtitle_clips(script, duration)
    hook = create_hook_text(3.2)

    final = CompositeVideoClip([video, hook] + subtitles, size=(W, H))
    final = final.with_duration(duration)
    
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    return output

def main():
    topic = "BMW arabalar 200 bin km sonra sürekli arıza yapar miti"
    print("1. Shorts senaryosu yazılıyor...")
    script = generate_script(topic)
    
    if not script:
        print("Senaryo oluşturulamadı.")
        return

    print("2. Ses oluşturuluyor...")
    asyncio.run(text_to_speech(script, "ses.mp3"))

    print("3. BMW görselleri indiriliyor...")
    images = download_car_images(12)

    if not images:
        print("Görsel indirilemedi.")
        return

    print("4. Shorts videosu oluşturuluyor...")
    create_video(script, "ses.mp3", images)
    print("Shorts hazır: video.mp4")

if __name__ == "__main__":
    main()
