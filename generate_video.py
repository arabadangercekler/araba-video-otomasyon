import os
import time
import asyncio
import random
import re
import datetime
import requests
import google.generativeai as genai
import edge_tts
from moviepy import (
    ImageClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips, ColorClip, vfx
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
BMW 200 bin kilometre sonra bozulur mu sanıyorsun?
Sana büyük bir sır vereyim: Düzenli bakımlı BMW'ler 400 bin kilometreyi rahat görüyor.
Asıl sorun geç yağ değişimi ve soğuk motora basılan gaz.
Bakımı yapılan araçta zincir sorunu bile geç çıkar.
Bu iddia tamamen yalan.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "kisin": """
Kışın arabayı dakikalarca boşta ısıtmazsan motorun bozulacağını mı sanıyorsun?
Sana büyük bir sır vereyim: Bu kural tam otuz yıl önce bitti.
Eski model arabalarda evet, beklemek gerekiyordu.
Ama şimdiki arabalar öyle değil.
Arabayı sabah çalıştırıp kapının önünde beklersen motora iyilik değil kötülük yapıyorsun.
Motor durduğu yerde çok geç ısınır, boş yere benzin yakar.
Doğrusu çok basit.
Arabayı çalıştır, kemerini tak, aynaları kontrol et.
Yirmi otuz saniye bekle ve hemen yola çık.
Sadece araba ısınana kadar gaza sonuna kadar basma.
Motor hareket ettikçe daha hızlı ve sağlıklı ısınır.
Bu videoyu hemen babana gönder de o da gerçeği öğrensin.
""",
    "turbo": """
Turbo motorlar daha çabuk bozulur mu sanıyorsun?
Sana büyük bir sır vereyim: Yağ soğutması düzgün yapılırsa turbo uzun ömürlü oluyor.
Motoru stop etmeden önce bir dakika rölantide beklemek önemli.
Ucuz yağ ve ihmal asıl suçlu.
Bu iddia tamamen yalan.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "dizel": """
Dizel motorlar benzinliye göre daha dayanıklı mı sanıyorsun?
Sana büyük bir sır vereyim: Eski dizeller gerçekten uzun yaşardı.
Yeni dizellerde ekstra sistemler var, bakım ister.
Bakım yapılmazsa masrafı benzinliden fazla çıkabiliyor.
Dayanıklılık aracın kullanımına bağlı.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "elektrikli": """
Elektrikli arabaların bataryası 5 yılda biter mi sanıyorsun?
Sana büyük bir sır vereyim: Üreticiler genelde 8 yıl veya 160 bin kilometre garanti veriyor.
Gerçek hayatta çoğu batarya 10-15 yıl dayanıyor.
Sık hızlı şarj ömrü biraz kısaltabiliyor.
5 yılda biter demek abartı. Bu iddia tamamen yalan.
Elektrikli araba düşünen birine gönder, o da bilsin.
""",
    "otomatik": """
Otomatik vitesli arabalar daha çabuk bozulur mu sanıyorsun?
Sana büyük bir sır vereyim: Eski otomatikler bakım isterdi, yeniler daha dayanıklı.
Yağ değişimi yapılmazsa sorun çıkar.
Doğru kullanımda otomatik vites uzun yaşar.
Bu iddia tamamen yalan.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "oktan": """
Yüksek oktanlı benzin motoru temizler mi sanıyorsun?
Sana büyük bir sır vereyim: Oktan sayısı vuruntuyu önler, motoru temizlemez.
Motorun istediği oktanın üstüne çıkmak güç artırmaz.
Temizlik için özel katkı gerekir, pahalı benzin değil.
Bu iddia tamamen yalan.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "yeni": """
Yeni araba almak eski arabadan daha kârlı mı sanıyorsun?
Sana büyük bir sır vereyim: İlk 3 yılda yeni araba değer kaybı yüksektir.
Bakımlı 2-3 yaşındaki araç çoğu zaman daha mantıklı.
Sigorta ve vergi de yeni arabada daha pahalı olabilir.
Her zaman yeni almak kârlı değil.
Yeni araba almayı düşünen birine hemen gönder, o da bilsin.
"""
}

def pick_topic():
    used_file = "used_topics.txt"
    used = []
    if os.path.exists(used_file):
        with open(used_file, "r", encoding="utf-8") as f:
            used = [x.strip() for x in f.readlines() if x.strip()]
    available = [t for t in TOPICS if t not in used]
    if not available:
        used = []
        available = TOPICS.copy()
    topic = random.choice(available)
    used.append(topic)
    with open(used_file, "w", encoding="utf-8") as f:
        f.write("\n".join(used[-20:]))
    return topic

def pick_fallback(topic):
    t = topic.lower()
    if "bmw" in t: return FALLBACKS["bmw"].strip()
    if "turbo" in t: return FALLBACKS["turbo"].strip()
    if "dizel" in t: return FALLBACKS["dizel"].strip()
    if "elektrikli" in t or "batarya" in t: return FALLBACKS["elektrikli"].strip()
    if "otomatik" in t: return FALLBACKS["otomatik"].strip()
    if "oktan" in t or "benzin" in t: return FALLBACKS["oktan"].strip()
    if "kışın" in t or "isıtmadan" in t: return FALLBACKS["kisin"].strip()
    if "yeni araba" in t: return FALLBACKS["yeni"].strip()
    return FALLBACKS["oktan"].strip()

def clean_for_speech(text):
    text = re.sub(r'\bkm\b', 'kilometre', text, flags=re.IGNORECASE)
    text = re.sub(r'\bKM\b', 'kilometre', text)
    text = re.sub(r'(\d+)\s*bin\s*km', r'\1 bin kilometre', text, flags=re.IGNORECASE)
    text = text.replace("  ", " ")
    return text

def generate_script(topic):
    try:
        response = model.generate_content(f"""
Sen Türk YouTube Shorts için samimi bir araba kanalı sunucususun.
Konu: {topic}

ZORUNLU TARZ:
1. İlk cümle: İzleyiciye "sanıyorsun?" diye biten güçlü bir soru.
2. İkinci cümle: "Sana büyük bir sır vereyim:" veya "Sana bir sır vereyim:" ile başlasın.
3. Kısa cümleler. Konuşur gibi yaz. Teknik kelime yok.
4. "km" yazma, "kilometre" yaz.
5. Son cümle mutlaka konuya uygun bir gönder çağrısı olsun.
   Örnekler:
   - Kış / ısıtma konusuysa: "Bu videoyu hemen babana gönder de o da gerçeği öğrensin."
   - Yeni araba konusuysa: "Yeni araba almayı düşünen birine hemen gönder, o da bilsin."
   - BMW / turbo / dizel gibiyse: "Bunu bilmeyen birine gönder, o da gerçeği öğrensin."
   Konuya uymayan genel "babana gönder" deme.
6. 50-55 saniye. Sadece konuşma metni. Türkçe.
""")
        text = response.text.strip()
        if text and len(text) > 40:
            print("Gemini senaryosu alındı")
            return clean_for_speech(text)
    except Exception as e:
        print(f"Gemini hatası: {e}")
    print("Yedek senaryo (konuya uygun)")
    return clean_for_speech(pick_fallback(topic))

async def text_to_speech(text, output_file):
    # Soru işaretlerini koru (tonlama için). Sadece normal noktaları yumuşat.
    clean = text.replace(". ", ", ")
    communicate = edge_tts.Communicate(clean, VOICE, rate="+10%", pitch="-6Hz")
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

def download_images(topic, count=16):
    images = []
    t = topic.lower()
    prefer_tag = None

    if "elektrikli" in t or "batarya" in t:
        queries = ["electric car exterior", "electric sedan car", "ev car side view"]
    elif "dizel" in t:
        queries = ["diesel car exterior", "car engine bay", "sedan car side"]
    elif "otomatik" in t:
        queries = ["automatic gear shifter", "car gear lever close", "car interior console"]
    elif "turbo" in t:
        queries = ["car turbo engine", "car engine close up", "engine bay car"]
    elif "bmw" in t:
        queries = ["BMW sedan", "BMW 3 series", "BMW 5 series", "BMW car"]
        prefer_tag = "bmw"
    elif "oktan" in t or "benzin" in t:
        queries = ["car at gas station", "fuel pump car", "petrol nozzle filling car"]
    elif "yeni araba" in t:
        queries = ["new sedan car", "modern car exterior", "car dealership lot"]
    elif "kışın" in t or "isıtmadan" in t:
        queries = ["car in snow outdoor", "snow covered sedan", "winter car road"]
    else:
        queries = ["sedan car exterior", "modern car side view", "automobile exterior"]

    exclude = [
        "people", "person", "man", "woman", "portrait", "child", "kid", "baby",
        "face", "human", "crowd", "group", "boy", "girl", "worker", "driver",
        "building", "architecture", "house", "skyscraper", "cityscape",
        "cake", "toy", "miniature",
        "train", "railway", "locomotive", "metro", "subway", "tram",
        "airplane", "aircraft", "plane", "motorcycle", "bike",
        "lamborghini", "ferrari", "porsche", "supercar"
    ]

    preferred = []
    others = []

    for q in queries:
        if len(preferred) + len(others) >= count * 2:
            break
        url = (
            f"https://pixabay.com/api/?key={PIXABAY_KEY}"
            f"&q={q.replace(' ', '+')}&image_type=photo"
            f"&per_page=25&safesearch=true"
        )
        try:
            r = requests.get(url, timeout=12)
            hits = r.json().get("hits", [])
            for hit in hits:
                tags = (hit.get("tags") or "").lower()
                if any(x in tags for x in exclude):
                    continue
                img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                if not img_url:
                    continue
                if prefer_tag and prefer_tag in tags:
                    preferred.append(img_url)
                else:
                    others.append(img_url)
        except Exception as e:
            print(f"Görsel hatası ({q}): {e}")

    urls = preferred + others
    for img_url in urls:
        if len(images) >= count:
            break
        try:
            data = requests.get(img_url, timeout=10).content
            filename = f"img_{len(images)}.jpg"
            with open(filename, "wb") as f:
                f.write(data)
            images.append(filename)
            print(f"Görsel {len(images)}")
        except:
            continue

    if len(images) < 5:
        fallback_q = "BMW+car" if prefer_tag == "bmw" else "sedan+car"
        url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={fallback_q}&image_type=photo&per_page={count}&safesearch=true"
        try:
            r = requests.get(url, timeout=12)
            for i, hit in enumerate(r.json().get("hits", [])[:count]):
                tags = (hit.get("tags") or "").lower()
                if any(x in tags for x in exclude):
                    continue
                img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                if not img_url: continue
                data = requests.get(img_url, timeout=10).content
                with open(f"img_{i}.jpg", "wb") as f:
                    f.write(data)
                images.append(f"img_{i}.jpg")
        except: pass
    return images

def make_clip(img_path, duration, move_type=0):
    bg = ColorClip(size=(W, H), color=(0, 0, 0)).with_duration(duration)
    clip = ImageClip(img_path)
    if clip.w / clip.h > W / H:
        clip = clip.resized(height=int(H * 1.12))
    else:
        clip = clip.resized(width=int(W * 1.12))
    clip = clip.with_duration(duration)

    if move_type == 0:
        def scale(t): return 1.0 + 0.05 * (t / max(duration, 0.1))
    elif move_type == 1:
        def scale(t): return 1.05 - 0.05 * (t / max(duration, 0.1))
    else:
        def scale(t): return 1.02 + 0.03 * (t / max(duration, 0.1))

    clip = clip.resized(scale)
    clip = clip.cropped(width=W, height=H, x_center=clip.w / 2, y_center=clip.h / 2)
    final = CompositeVideoClip([bg, clip.with_position("center")], size=(W, H))
    return final.with_duration(duration).resized((W, H))

def create_hook(topic, duration=5.5):
    t = topic.lower()
    if "bmw" in t and "200" in t:
        lines = ["BMW 200 BIN KM SONRA", "BOZULUR MU?"]
    elif "otomatik" in t:
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

    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
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
    return ImageClip(arr).with_duration(duration).with_position((40, 280))

def create_subtitles(script, total_duration, word_timings):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if len(s.strip()) > 2]
    if not sentences:
        sentences = [script]

    clips = []
    if word_timings and len(word_timings) > 3:
        idx = 0
        for i, s in enumerate(sentences):
            n = max(len(s.split()), 1)
            if idx >= len(word_timings):
                start = clips[-1].start + clips[-1].duration if clips else 0
                dur = max(total_duration - start, 1.5)
            else:
                start = word_timings[idx]["start"]
                end_idx = min(idx + n - 1, len(word_timings) - 1)
                end = word_timings[end_idx]["start"] + word_timings[end_idx]["duration"]
                dur = max(end - start, 1.0)
                idx += n

            if i == len(sentences) - 1:
                dur = max(total_duration - start, 1.5)

            words = s.split()
            display = s if len(words) <= 6 else " ".join(words[:len(words)//2]) + "\n" + " ".join(words[len(words)//2:])

            txt = TextClip(
                text=display, font_size=26, color="white",
                stroke_color="black", stroke_width=5, method="caption",
                size=(780, None),
                font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            )
            clips.append(txt.with_start(start).with_duration(dur).with_position(("center", 980)))
        return clips

    total_chars = sum(len(s) for s in sentences) or 1
    current = 0.0
    for i, s in enumerate(sentences):
        dur = max((len(s) / total_chars) * total_duration * 0.95, 1.2)
        if i == len(sentences) - 1:
            dur = max(total_duration - current, 1.5)
        words = s.split()
        display = s if len(words) <= 6 else " ".join(words[:len(words)//2]) + "\n" + " ".join(words[len(words)//2:])
        txt = TextClip(
            text=display, font_size=26, color="white",
            stroke_color="black", stroke_width=5, method="caption",
            size=(780, None),
            font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        )
        clips.append(txt.with_start(current).with_duration(dur).with_position(("center", 980)))
        current += dur
    return clips

def create_video(script, audio_file, images, topic, word_timings, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    print(f"Ses: {duration:.1f}s")

    if not images:
        print("Görsel yok")
        return

    fade = 0.30
    n = max(12, min(len(images) * 2, int(duration / 1.8)))
    unique = list(dict.fromkeys(images))
    images = unique.copy()
    while len(images) < n:
        images.append(random.choice(unique))
    random.shuffle(images)
    images = images[:n]

    clip_dur = duration / n + fade
    img_clips = []
    for i in range(n):
        c = make_clip(images[i], clip_dur, i % 3)
        c = c.with_effects([vfx.CrossFadeIn(fade), vfx.CrossFadeOut(fade)])
        img_clips.append(c)

    video = concatenate_videoclips(img_clips, method="compose", padding=-fade)
    video = video.with_duration(duration).resized((W, H))
    video = video.with_audio(audio)

    layers = [video, create_hook(topic, 5.5)] + create_subtitles(script, duration, word_timings)

    final = CompositeVideoClip(layers, size=(W, H)).with_duration(duration)
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    print("Bitti")
    return output

def main():
    topic = pick_topic()
    print(f"Konu: {topic}")

    print("1. Senaryo...")
    script = generate_script(topic)

    print("2. Ses...")
    word_timings = asyncio.run(text_to_speech(script, "ses.mp3"))

    print("3. Görsel...")
    images = download_images(topic, 16)
    if len(images) < 3:
        print("Görsel yetersiz")
        return

    print("4. Video...")
    create_video(script, "ses.mp3", images, topic, word_timings)

if __name__ == "__main__":
    main()
