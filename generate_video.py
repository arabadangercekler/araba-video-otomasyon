import os
import google.generativeai as genai
import edge_tts
import asyncio
import requests
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image
import textwrap

# API anahtarını GitHub Secrets'tan al
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-2.0-flash")

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
    response = model.generate_content(prompt)
    return response.text.strip()

async def text_to_speech(text, output_file):
    communicate = edge_tts.Communicate(text, "tr-TR-AhmetNeural")
    await communicate.save(output_file)

def download_images(query, count=12):
    # Şimdilik basit stok görseller (Pexels yerine geçici çözüm)
    # Daha sonra Pexels API ekleyeceğiz
    images = []
    for i in range(count):
        url = f"https://picsum.photos/1280/720?random={i}"
        img_data = requests.get(url).content
        filename = f"img_{i}.jpg"
        with open(filename, "wb") as f:
            f.write(img_data)
        images.append(filename)
    return images

def create_video(script, audio_file, image_files, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    clip_duration = duration / len(image_files)

    clips = []
    for img in image_files:
        clip = ImageClip(img).set_duration(clip_duration).resize(height=720)
        # Basit zoom efekti
        clip = clip.resize(lambda t: 1 + 0.04 * t)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(audio)
    video = video.set_duration(duration)
    video.write_videofile(output, fps=24, codec="libx264", audio_codec="aac")
    return output

def main():
    topic = "BMW arabalar 200 bin km sonra sürekli arıza yapar miti"
    print("Senaryo yazılıyor...")
    script = generate_script(topic)
    print("Senaryo hazır.")

    print("Ses oluşturuluyor...")
    asyncio.run(text_to_speech(script, "ses.mp3"))

    print("Görseller indiriliyor...")
    images = download_images("car bmw", 12)

    print("Video oluşturuluyor...")
    create_video(script, "ses.mp3", images)
    print("Video hazır: video.mp4")

if __name__ == "__main__":
    main()
