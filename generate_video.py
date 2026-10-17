import os
import time
import asyncio
import requests
import google.generativeai as genai
import edge_tts
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# === AYARLAR ===
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
PIXABAY_KEY = os.environ["PIXABAY_API_KEY"]
MODEL_NAME = "gemini-3.8-flash"
VOICE = "tr-TR-EmelNeural"

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

def download_car_images(count=8):
    images = []
    url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q=car+automobile&image_type=photo&orientation=vertical&per_page={count}&safesearch=true"
    
    try:
        r = requests.get(url, timeout=15)
        data = r.json()
        hits = data.get("hits", [])
        
        for i, hit in enumerate(hits[:count]):
            img_url = hit["largeImageURL"]
            img_data = requests.get(img_url, timeout=10).content
            filename = f"img_{i}.jpg"
            with open(filename, "wb") as f:
                f.write(img_data)
            images.append(filename)
            print(f"Görsel indirildi: {i+1}")
    except Exception as e:
        print(f"Görsel indirme hatası: {e}")
    
    return images

def create_video(audio_file, image_files, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    clip_duration = duration / max(len(image_files), 1)

    clips = []
    for img in image_files:
        try:
            clip = (ImageClip(img)
                    .with_duration(clip_duration)
                    .resized(height=1280))
            clips.append(clip)
        except:
            continue

    if not clips:
        raise Exception("Hiç görsel yüklenemedi")

    video = concatenate_videoclips(clips, method="compose")
    video = video.with_audio(audio)
    video = video.with_duration(duration)
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

    print("3. Araba görselleri indiriliyor...")
    images = download_car_images(8)

    if not images:
        print("Görsel indirilemedi.")
        return

    print("4. Shorts videosu oluşturuluyor...")
    create_video("ses.mp3", images)
    print("Shorts hazır: video.mp4")

if __name__ == "__main__":
    main()
