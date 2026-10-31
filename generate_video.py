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
from PIL import Image, ImageDraw, ImageFont
import numpy as np

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
Bakım yapılırsa uzun ömürlü olur. Bu iddia tamamen yalan.
"""

TOPICS = [
    "BMW arabalar 200 bin km sonra sürekli arıza yapar yalanı",
    "Dizel motorlar benzinliye göre daha dayanıklı mı gerçek mi",
    "Yeni araba almak eski arabadan daha kârlı mı yalanı",
    "Otomatik vitesli arabalar daha çabuk bozulur yalanı",
    "Yüksek oktanlı benzin motoru temizler gerçek mi",
    "Kışın arabayı ısıtmadan sürmek motoru bozar yalanı",
    "Elektrikli arabalar 5 yılda bataryası biter yalanı",
    "Turbo motorlar bakımsızlığa daha dayanıksız gerçek mi",
]

def generate_script(topic):
    try:
        response = model.generate_content(f"""
Sen profesyonel Türk YouTube Shorts senaristisin.
Konu: {topic}
55-65 saniyelik senaryo yaz. En az 6-7 cümle olsun.
İlk 5 saniyede kanca olsun.
Somut bilgi ver.
En sonda net söyle: "Bu iddia tamamen yalan." veya "Bu gerçek."
Çok basit kelimeler kullan. Herkesin anlayacağı günlük dil.
Sadece konuşma metni. Türkçe.
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
    clean = text.replace(". ", ", ").replace("! ", ", ").replace("? ", ", ")
    communicate = edge_tts.Communicate(clean, VOICE, rate="+12%", pitch="-3Hz")
    await communicate.save(output_file)
    print("Ses oluşturuldu")

def download_images(topic, count=8):
    images = []
    queries = [
        "BMW car",
        "BMW sedan",
        "BMW engine",
        "BMW motor",
        "BMW dashboard",
        "BMW rear light"
    ]
    for q in queries:
        if len(images) >= count:
            break
        url = (
            f"https://pixabay.com/api/?key={PIXABAY_KEY}"
            f"&q={q.replace(' ', '+')}&image_type=photo&orientation=vertical"
            f"&per_page=8&safesearch=true"
        )
        try:
            r = requests.get(url, timeout=12)
            hits = r.json().get("hits", [])
            for hit in hits:
                if len(images) >= count:
                    break
                tags = (hit.get("tags") or "").lower()
                if any(x in tags for x in ["people", "person", "man", "woman", "portrait", "building", "architecture", "abstract"]):
                    continue
                if "bmw" not in tags and "car" not in tags and "auto" not in tags and "vehicle" not in tags:
                    continue
                img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                if not img_url:
                    continue
                data = requests.get(img_url, timeout=10).content
                filename = f"img_{len(images)}.jpg"
                with open(filename, "wb") as f:
                    f.write(data)
                images.append(filename)
                print(f"Görsel {len(images)}: {q}")
        except Exception as e:
            print(f"Görsel hatası ({q}): {e}")

    if len(images) < 3:
        print("Yedek arama...")
        url = (
            f"https://pixabay.com/api/?key={PIXABAY_KEY}"
            f"&q=BMW+car&image_type=photo&orientation=vertical"
            f"&per_page={count}&safesearch=true"
        )
        try:
            r = requests.get(url, timeout=12)
            for i, hit in enumerate(r.json().get("hits", [])[:count]):
                img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                if not img_url:
                    continue
                data = requests.get(img_url, timeout=10).content
                filename = f"img_{i}.jpg"
                with open(filename, "wb") as f:
                    f.write(data)
                images.append(filename)
        except Exception as e:
            print(f"Yedek hata: {e}")
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

def create_hook(script, duration=5.5):
    first = script.strip().split("?")[0] + "?" if "?" in script else script.strip().split(".")[0]
    first = first.strip()
    if len(first) > 55:
        words = first.split()
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    else:
        lines = [first]

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    widths, heights = [], []
    for line in lines:
        bbox = d.textbbox((0, 0), line, font=font)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])
    tw = max(widths) + 50
    th = sum(heights) + 50

    img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    y = 10
    for i, line in enumerate(lines):
        x = (tw - widths[i]) // 2
        for dx, dy in [(-3,-3),(-3,3),(3,-3),(3,3),(-3,0),(3,0),(0,-3),(0,3)]:
            draw.text((x+dx, y+dy), line, font=font, fill=(0, 0, 0, 255))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 255))
        y += heights[i] + 10

    arr = np.array(img)
    clip = ImageClip(arr).with_duration(duration)
    return clip.with_position((50, 200))

def create_result_text(script, total_duration):
    low = script.lower()
    if "gerçek" in low:
        word, color = "GERÇEK", (0, 200, 0)
    else:
        word, color = "YALAN", (220, 30, 30)

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 105)
    dummy = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), word, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    img = Image.new("RGBA", (tw + 80, th + 80), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for dx, dy in [(-5,-5),(-5,5),(5,-5),(5,5),(-5,0),(5,0),(0,-5),(0,5)]:
        draw.text((40+dx, 40+dy), word, font=font, fill=(0, 0, 0, 255))
    draw.text((40, 40), word, font=font, fill=color + (255,))
    img = img.rotate(12, expand=True, fillcolor=(0, 0, 0, 0))

    arr = np.array(img)
    clip = ImageClip(arr).with_duration(2.0)
    start = max(total_duration - 2.0, 0)
    return clip.with_start(start).with_position(("center", 560))

def create_subtitles(script, total_duration):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if len(s.strip()) > 3]
    if not sentences:
        sentences = [script]

    filtered = []
    for s in sentences:
        low = s.lower()
        if "bu iddia tamamen yalan" in low or "bu bir yalan" in low or "bu gerçek" in low:
            continue
        if low.strip() in ["yalan.", "yalan", "gerçek.", "gerçek"]:
            continue
        filtered.append(s)
    sentences = filtered if filtered else sentences

    total_chars = sum(len(s) for s in sentences) or 1
    clips = []
    current = 0.0

    for s in sentences:
        share = len(s) / total_chars
        dur = max(share * total_duration * 0.90, 1.3)
        words = s.split()
        if len(words) <= 5:
            display = s
        else:
            mid = len(words) // 2
            display = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])

        txt = TextClip(
            text=display,
            font_size=26,
            color="white",
            stroke_color="black",
            stroke_width=5,
            method="caption",
            size=(780, None),
            font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        )
        txt = txt.with_start(current).with_duration(dur)
        txt = txt.with_position(("center", 980))
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

    layers = [video, create_hook(script, 5.5)] + create_subtitles(script, duration)
    layers.append(create_result_text(script, duration))

    final = CompositeVideoClip(layers, size=(W, H)).with_duration(duration).resized((W, H))
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    print("Bitti")
    return output

def main():
    topic = random.choice(TOPICS)
    print(f"Konu: {topic}")

    print("1. Senaryo...")
    script = generate_script(topic)

    print("2. Ses...")
    asyncio.run(text_to_speech(script, "ses.mp3"))

    print("3. Görsel...")
    images = download_images(topic, 8)
    if len(images) < 3:
        print("Görsel yetersiz")
        return

    print("4. Video...")
    create_video(script, "ses.mp3", images)

if __name__ == "__main__":
    main()
