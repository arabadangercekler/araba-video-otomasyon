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

FALLBACKS = {
    "bmw": """
BMW 200 bin kilometre sonra bozulur mu? Birçok kişi serviste bunu duyuyor.
N57 dizel motorlar düzenli bakımlıysa 400 bin kilometreyi rahat görüyor.
Asıl sorun geç yağ değişimi ve soğuk motora basılan gaz.
Zincir germe sorunları da bakımsız araçlarda çıkıyor.
Bu iddia tamamen yalan.
""",
    "turbo": """
Turbo motorlar daha çabuk bozulur mu? Birçok kişi bundan korkuyor.
Aslında turbo, yağ soğutması düzgün yapılırsa uzun ömürlü oluyor.
Motoru stop etmeden önce 1 dakika rölantide beklemek önemli.
Ucuz yağ ve ihmal edilen yağ değişimi asıl suçlu.
Bu iddia tamamen yalan.
""",
    "dizel": """
Dizel motorlar benzinliye göre daha dayanıklı mı?
Eski dizeller yüksek tork ve uzun ömürle biliniyordu.
Yeni dizellerde partikül filtresi ve adblue sistemleri ekstra bakım istiyor.
Bakım aksarsa benzinliden daha pahalıya patlayabiliyor.
Bu tamamen aracın kullanımına bağlı. Bu gerçek.
""",
    "elektrikli": """
Elektrikli arabaların bataryası 5 yılda biter mi?
Üreticiler genelde 8 yıl veya 160 bin km garanti veriyor.
Gerçek hayatta çoğu batarya 10-15 yıl dayanıyor.
Hızlı şarjın sık kullanımı ömrü biraz kısaltabiliyor.
5 yılda biter demek abartı. Bu iddia tamamen yalan.
""",
    "otomatik": """
Otomatik vitesli arabalar daha çabuk bozulur mu?
Eski otomatikler bakım isterdi ama yeni şanzımanlar daha dayanıklı.
Yağ değişimi yapılmazsa sorun çıkar, bu da manuelde de olur.
Doğru kullanımda otomatik vites uzun yaşar.
Bu iddia tamamen yalan.
""",
    "default": """
Arabalar hakkında duyduğunuz bazı bilgiler yanlış.
Somut verilere bakmak lazım, genel laflara değil.
Bakım ve kullanım şekli her şeyden önemli.
Bu iddia tamamen yalan.
"""
}

def pick_fallback(topic):
    t = topic.lower()
    if "bmw" in t:
        return FALLBACKS["bmw"].strip()
    if "turbo" in t:
        return FALLBACKS["turbo"].strip()
    if "dizel" in t:
        return FALLBACKS["dizel"].strip()
    if "elektrikli" in t or "batarya" in t:
        return FALLBACKS["elektrikli"].strip()
    if "otomatik" in t:
        return FALLBACKS["otomatik"].strip()
    return FALLBACKS["default"].strip()

def generate_script(topic):
    try:
        response = model.generate_content(f"""
Sen profesyonel Türk YouTube Shorts senaristisin.
Konu: {topic}
55-65 saniyelik senaryo yaz. En az 6-7 cümle olsun.
İlk cümle dikkat çekici soru olsun.
Somut bilgi ver (motor tipi, km, sistem adı gibi).
ASLA şunu deme: "iyi bakarsan uzun sürer", "kaliteli yağ koy", "düzenli bakım yap".
Herkesin bildiği genel laflar yasak.
En sonda net söyle: "Bu iddia tamamen yalan." veya "Bu gerçek."
Çok basit kelimeler. Sadece konuşma metni. Türkçe.
""")
        text = response.text.strip()
        if text and len(text) > 40:
            print("Gemini senaryosu alındı")
            return text
    except Exception as e:
        print(f"Gemini hatası: {e}")
    print("Yedek senaryo (konuya uygun)")
    return pick_fallback(topic)

async def text_to_speech(text, output_file):
    clean = text.replace(". ", ", ").replace("! ", ", ").replace("? ", ", ")
    communicate = edge_tts.Communicate(clean, VOICE, rate="+12%", pitch="-3Hz")
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
    print(f"Ses OK | {len(word_timings)} kelime")
    return word_timings

def download_images(topic, count=8):
    images = []
    t = topic.lower()

    if "elektrikli" in t or "batarya" in t:
        queries = ["electric car", "EV car", "electric vehicle", "car battery"]
    elif "dizel" in t:
        queries = ["diesel engine", "diesel car", "car engine"]
    elif "otomatik vites" in t:
        queries = ["automatic transmission", "car gear stick", "car interior"]
    elif "turbo" in t:
        queries = ["turbo engine", "car turbo", "car engine bay"]
    elif "bmw" in t:
        queries = ["BMW car", "BMW sedan", "BMW engine", "BMW rear"]
    else:
        queries = ["car exterior", "sedan car", "car engine", "car dashboard"]

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
                if ("elektrikli" in t or "batarya" in t) and "bmw" in tags:
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
            f"&q=car&image_type=photo&orientation=vertical"
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

def create_hook(topic, duration=5.5):
    t = topic.lower()
    if "bmw" in t and "200" in t:
        lines = ["BMW 200 BIN KM SONRA", "BOZULUR MU?"]
    elif "otomatik vites" in t:
        lines = ["OTOMATIK VITES", "BOZULUR MU?"]
    elif "dizel" in t:
        lines = ["DIZEL MOTOR", "DAHA DAYANIKLI MI?"]
    elif "elektrikli" in t or "batarya" in t:
        lines = ["ELEKTRIKLI ARABA", "BATARYASI BITER MI?"]
    elif "turbo" in t:
        lines = ["TURBO MOTOR", "DAHA CABUK BOZULUR MU?"]
    elif "oktan" in t or "benzin" in t:
        lines = ["YUKSEK OKTANLI BENZIN", "MOTORU TEMIZLER MI?"]
    elif "isıtmadan" in t or "kışın" in t:
        lines = ["KISIN ARABAYI", "ISITMADAN SURMEK ZARARLI MI?"]
    elif "yeni araba" in t:
        lines = ["YENI ARABA ALMAK", "DAHA KARLI MI?"]
    else:
        words = topic.split()
        lines = [" ".join(words[:3]).upper(), " ".join(words[3:6]).upper() + "?"]

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
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
    tail = script.lower()[-80:]
    if "yalan" in tail:
        word, color = "YALAN", (220, 30, 30)
    elif "bu gerçek" in tail or tail.strip().endswith("gerçek.") or tail.strip().endswith("gerçek"):
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

def create_subtitles(script, total_duration, word_timings):
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

    clips = []

    if word_timings and len(word_timings) > 5:
        idx = 0
        for s in sentences:
            s_words = s.split()
            n = max(len(s_words), 1)
            if idx >= len(word_timings):
                break
            start = word_timings[idx]["start"]
            end_idx = min(idx + n - 1, len(word_timings) - 1)
            end = word_timings[end_idx]["start"] + word_timings[end_idx]["duration"]
            dur = max(end - start, 1.2)
            idx += n

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
            txt = txt.with_start(start).with_duration(dur)
            txt = txt.with_position(("center", 980))
            clips.append(txt)
        return clips

    total_chars = sum(len(s) for s in sentences) or 1
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

def create_video(script, audio_file, images, topic, word_timings, output="video.mp4"):
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

    layers = [video, create_hook(topic, 5.5)] + create_subtitles(script, duration, word_timings)
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
    word_timings = asyncio.run(text_to_speech(script, "ses.mp3"))

    print("3. Görsel...")
    images = download_images(topic, 8)
    if len(images) < 3:
        print("Görsel yetersiz")
        return

    print("4. Video...")
    create_video(script, "ses.mp3", images, topic, word_timings)

if __name__ == "__main__":
    main()
