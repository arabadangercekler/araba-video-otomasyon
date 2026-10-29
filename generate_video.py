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

async def text_to_speech_with_timing(text, output_file):
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    word_timings = []
    with open(output_file, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                word_timings.append({
                    "text": chunk["text"],
                    "start": chunk["offset"] / 10_000_000,
                    "duration": max(chunk["duration"] / 10_000_000, 0.08)
                })
    print(f"Ses OK | Kelime: {len(word_timings)}")
    return word_timings

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
        font_size=40,
        color="white",
        stroke_color="black",
        stroke_width=7,
        method="caption",
        size=(800, None),
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )
    return txt.with_duration(duration).with_position(("center", 220))

def make_sub(text, start, dur):
    txt = TextClip(
        text=text,
        font_size=36,
        color="white",
        stroke_color="black",
        stroke_width=6,
        method="label",
        font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    )
    # Güvenli konum (kesilmesin)
    return txt.with_start(start).with_duration(max(dur, 0.15)).with_position(("center", 1150))

def create_subtitles(script, total_duration, word_timings):
    clips = []

    if word_timings and len(word_timings) > 5:
        print("Gerçek zamanlama (2-3 kelime grup)")
        i = 0
        while i < len(word_timings):
            group = word_timings[i:i+2]
            text = " ".join(w["text"] for w in group)
            start = group[0]["start"]
            if i + 2 < len(word_timings):
                end = word_timings[i + 2]["start"]
            else:
                end = total_duration
            dur = max(end - start, 0.18)
            clips.append(make_sub(text, start, dur))
            i += 2
        return clips

    print("Yedek zamanlama")
    words = [w for w in re.findall(r'\S+', script) if w.strip()]
    groups = [" ".join(words[i:i+2]) for i in range(0, len(words), 2)]
    total_chars = sum(len(g) for g in groups) or 1
    current = 0.0
    for g in groups:
        share = len(g) / total_chars
        dur = max(share * total_duration, 0.2)
        clips.append(make_sub(g, current, dur))
        current += dur
    return clips

def create_video(script, audio_file, images, word_timings, output="video.mp4"):
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

    subs = create_subtitles(script, duration, word_timings)
    print(f"Altyazı: {len(subs)} grup")

    final = CompositeVideoClip(
        [video, create_hook(2.5)] + subs,
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
    word_timings = asyncio.run(text_to_speech_with_timing(script, "ses.mp3"))

    print("3. Görsel...")
    images = download_images(8)
    if len(images) < 3:
        print("Görsel yetersiz")
        return

    print("4. Video...")
    create_video(script, "ses.mp3", images, word_timings)

if __name__ == "__main__":
    main()
