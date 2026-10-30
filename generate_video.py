import os
import time
import asyncio
import random
import re
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
BMW 200 bin kilometre sonra bozulur mu? Birçok kişi bunu doğru sanıyor. 
Aslında düzenli bakımlı bir BMW 300-400 bin kilometreyi rahat görüyor. 
Asıl sorun ucuz yağ ve ihmal edilen bakımlar. 
Sonuç: Yalan. Bakım yapılırsa uzun ömürlü olur.
"""

def generate_script(topic):
    try:
        response = model.generate_content(f"""
Sen profesyonel Türk YouTube Shorts senaristisin.
Konu: {topic}
40-50 saniyelik senaryo yaz.
İlk 3 saniyede kanca olsun.
Sonunda net Gerçek veya Yalan de.
Basit kelimeler kullan. Sadece konuşma metni. Türkçe. Max 100 kelime.
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
            print(f"Görsel {i+1}")
    except Exception as e:
        print(f"Görsel hatası: {e}")
    return images

def make_clip(img_path, duration, move_type=0):
    bg = ColorClip(size=(W, H), color=(0, 0, 0)).with_duration(duration)
    clip = ImageClip(img_path)
    if clip.w / clip.h > W / H:
        clip = clip.resized(height=int(H * 1.4))
    else:
        clip = clip.resized(width=int(W * 1.4))
    clip = clip.with_duration(duration)
    if move_type == 0:
        def scale(t): return 1.0 + 0.14 * (t / max(duration, 0.1))
    elif move_type == 1:
        def scale(t): return 1.14 - 0.14 * (t / max(duration, 0.1))
    else:
        def scale(t): return 1.0 + 0.08 * (t / max(duration, 0.1))
    clip = clip.resized(scale)
    clip = clip.cropped(width=W, height=H, x_center=clip.w / 2, y_center=clip.h / 2)
    final = CompositeVideoClip([bg, clip.with_position("center")], size=(W, H))
    return final.with_duration(duration).resized((W, H))

def create_hook(duration=2.5):
    txt = TextClip(
        text="BMW 200 BIN KM SONRA\nBOZULUR MU?",
        font_size=38,
        color="white",
        stroke_color="black",
        stroke_width=6,
        method="caption",
        size=(900, None),
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )
    return txt.with_duration(duration).with_position(("center", 260))

def create_subtitles(script, total_duration):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if len(s.strip()) > 3]
    if not sentences:
        sentences = [script]

    total_chars = sum(len(s) for s in sentences) or 1
    clips = []
    current = 0.0

    for s in sentences:
        share = len(s) / total_chars
        dur = max(share * total_duration, 1.3)

        words = s.split()
        if len(words) <= 5:
            display = s
        else:
            mid = len(words) // 2
            display = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])

        txt = TextClip(
            text=display,
            font_size=30,
            color="white",
            stroke_color="black",
            stroke_width=6,
            method="caption",
            size=(820, None),
            font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        )
        txt = txt.with_start(current).with_duration(dur)
        txt = txt.with_position(("center", 1050))
        clips.append(txt)
        current += dur

    return clips

def create_video(script, audio_file, images, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    print(f"Ses: {duration:.1f}s")

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

    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    print("Bitti")
    return output

def main():
    topic = "BMW arabalar 200 bin km sonra sürekli arıza yapar yalanı"

    print("1. Senaryo...")
    script = generate_script(topic)

    print("2. Ses...")
    asyncio.run(text_to_speech(script, "ses.mp3"))

    print("3. Görsel...")
    images = download_images(8)
    if len(images) < 3:
        print("Görsel yetersiz")
        return

    print("4. Video...")
    create_video(script, "ses.mp3", images)

if __name__ == "__main__":
    main()
