import os
import time
import asyncio
import requests
import google.generativeai as genai
import edge_tts
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

# === AYARLAR ===
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL_NAME = "gemini-3.8-flash"
VOICE = "tr-TR-EmelNeural"  # Geçici olarak çalışan ses (sonra erkek ses ayarlarız)

model = genai.GenerativeModel(MODEL_NAME)

def generate_script(topic):
    prompt = f"""
Sen profesyonel bir Türk YouTube senaristisin.
Konu: {topic}

7-8 dakikalık, izleyiciyi baştan sona tutacak bir "Mit mi Gerçek mi" videosu senaryosu yaz.

Kurallar:
- İlk 5 saniyede çok güçlü bir kanca (hook) olsun
- Merak uyandıran bir dil kullan
- 4-5 ana bilgi ver
- Sonunda net "Mit" veya "Gerçek" damgası vur
- Sadece konuşma metnini yaz, başka bir şey ekleme
- Türkçe yaz
"""
    for i in range(6):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text:
                return text
        except Exception as e:
            print(f"Senaryo hatası (deneme {i+1}): {e}")
            time.sleep(25)
    return None

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(output_file)

def download_images(count=12):
    images = []
    for i in range(count):
        try:
            url = f"https://picsum.photos/1280/720?random={i+10}"
            img_data = requests.get(url, timeout=10).content
            filename = f"img_{i}.jpg"
            with open(filename, "wb") as f:
                f.write(img_data)
            images.append(filename)
        except:
            pass
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
                    .resized(height=720))
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
    print("1. Senaryo yazılıyor...")
    script = generate_script(topic)
    
    if not script:
        print("Senaryo oluşturulamadı, çıkılıyor.")
        return

    print("2. Ses oluşturuluyor...")
    asyncio.run(text_to_speech(script, "ses.mp3"))

    print("3. Görseller indiriliyor...")
    images = download_images(12)

    print("4. Video oluşturuluyor...")
    create_video("ses.mp3", images)
    print("Video hazır: video.mp4")

if __name__ == "__main__":
    main()
