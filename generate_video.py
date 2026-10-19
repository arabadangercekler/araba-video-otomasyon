import os
import time
import asyncio
import random
import requests
import google.generativeai as genai
import edge_tts
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# === AYARLAR ===
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
PIXABAY_KEY = os.environ["PIXABAY_API_KEY"]
MODEL_NAME = "gemini-3.8-flash"
VOICE = "tr-TR-EmelNeural"

# Shorts boyutu
W, H = 1080, 1920

model = genai.GenerativeModel(MODEL_NAME)

def generate_script(topic):
    prompt = f"""
Sen profesyonel bir Türk YouTube Shorts senaristisin.
Konu: {topic}

Sadece 40-50 saniyelik çok güçlü bir Shorts senaryosu yaz.

Kurallar:
- İlk 3 saniyede izleyiciyi kilitle
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

def download_car_images(count=10):
    images = []
    query = "BMW+car+OR+BMW+vehicle"
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
    """Zoom + hafif sağa/sola kaydırma"""
    clip = ImageClip(img_path)
    
    # Ekranı tamamen dolduracak şekilde büyüt
    clip = clip.resized(height=H * 1.15)  # biraz büyük tut ki kaydırma payı olsun
    
    # Rastgele yön: sağa veya sola
    direction = random.choice([-1, 1])
    
    def position(t):
        # Yavaş zoom
        progress = t / duration
        # Hafif yatay kaydırma
        x = direction * 40 * progress
        y = -30 * progress   # hafif yukarı da kaydır
        return (x, y)
    
    clip = clip.with_position(position)
    clip = clip.with_duration(duration)
    
    # Son boyuta kırp
    clip = clip.cropped(width=W, height=H, x_center=clip.w/2, y_center=clip.h/2)
    return clip

def create_video(audio_file, image_files, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    clip_duration = duration / max(len(image_files), 1)

    clips = []
    for img in image_files:
        try:
            clip = make_ken_burns_clip(img, clip_duration)
            clips.append(clip)
        except Exception as e:
            print(f"Clip hatası: {e}")
            continue

    if not clips:
        raise Exception("Hiç görsel yüklenemedi")

    video = concatenate_videoclips(clips, method="compose")
    video = video.with_audio(audio)
    video = video.with_duration(duration)
    video = video.resized((W, H))  # kesin 9:16
    video.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
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
    images = download_car_images(10)

    if not images:
        print("Görsel indirilemedi.")
        return

    print("4. Shorts videosu oluşturuluyor...")
    create_video("ses.mp3", images)
    print("Shorts hazır: video.mp4")

if __name__ == "__main__":
    main()
