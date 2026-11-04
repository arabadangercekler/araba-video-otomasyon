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

FALLBACKS = {
    "bmw": """
BMW 200 bin kilometre sonra bozulur mu sanıyorsun?
Sana büyük bir sır vereyim: Bakımlı bir BMW 400 bin kilometreyi rahat görüyor.
Asıl bitiren şey soğuk motora basılan gaz ve geç yağ değişimi.
Zincir gergisi ihmal edilirse sorun çıkıyor, motor kendiliğinden ölmez.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "kisin": """
Kışın arabayı dakikalarca boşta ısıtmazsan motorun bozulacağını mı sanıyorsun?
Sana büyük bir sır vereyim: Bu kural tam otuz yıl önce bitti.
Eski model arabalarda evet, beklemek gerekiyordu.
Ama şimdiki arabalar öyle değil.
Arabayı sabah çalıştırıp kapının önünde beklersen motora iyilik değil kötülük yapıyorsun.
Motor durduğu yerde çok geç ısınır, boş yere benzin yakar ve parçaları daha çok aşınır.
Peki doğrusu ne? Çok basit.
Arabayı çalıştır, kemerini tak, aynaları kontrol et.
Yirmi otuz saniye bekle ve hemen yola çık.
Sadece araba ısınana kadar gaza sonuna kadar basma, sakin sür.
Motor hareket ettikçe daha hızlı ve sağlıklı ısınır.
O soğukta boş yere titreme devri bitti.
Bu videoyu hemen babana gönder de o da gerçeği öğrensin.
""",
    "turbo": """
Turbo motorlar daha çabuk bozulur mu sanıyorsun?
Sana büyük bir sır vereyim: Turbo’yu bitiren şey motor değil, stop sonrası hemen kapatmak.
Yağ hâlâ sıcarken pompa durursa turbo yatakları kuru kalır.
Stop etmeden önce 30-60 saniye rölanti yeter, ömrü ciddi uzatır.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "dizel": """
Dizel motorlar benzinliye göre her zaman daha dayanıklı mı sanıyorsun?
Sana büyük bir sır vereyim: Eski dizeller evet, yenilerde durum değişti.
Partikül filtresi ve AdBlue sistemi bakımsız kalırsa masraf benzinliyi geçer.
Kısa mesafe kullanan dizelde filtre tıkanması çok sık görülüyor.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "elektrikli": """
Elektrikli arabaların bataryası 5 yılda biter mi sanıyorsun?
Sana büyük bir sır vereyim: Üreticiler genelde 8 yıl veya 160 bin kilometre garanti veriyor.
Gerçek kullanımda çoğu batarya 10-15 yılı görüyor.
Asıl ömrü kısaltan şey sürekli yüzde yüze kadar hızlı şarj.
Elektrikli araba düşünen birine gönder, o da bilsin.
""",
    "otomatik": """
Otomatik vitesli arabalar daha çabuk bozulur mu sanıyorsun?
Sana büyük bir sır vereyim: Yeni otomatik vitesler doğru yağla 300 bin kilometreyi geçebiliyor.
Asıl sorun “ömür boyu yağ” yalanı. 60-80 bin kilometrede yağ değişmezse vites sistemi yoruluyor.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "oktan": """
Yüksek oktanlı benzin motoru temizler mi sanıyorsun?
Sana büyük bir sır vereyim: Oktan sadece vuruntuyu önler, temizlik yapmaz.
Motorun istediği oktanın üstüne çıkmak güç de artırmaz.
Temizlik için ayrı katkı gerekir, pahalı pompa benzininden değil.
Bunu bilmeyen birine gönder, o da gerçeği öğrensin.
""",
    "yeni": """
Yeni araba almak her zaman daha kârlı mı sanıyorsun?
Sana büyük bir sır vereyim: İlk 3 yılda yeni araba değerinin büyük kısmını kaybeder.
Bakımlı 2-3 yaşındaki araç çoğu zaman cebine daha az zarar eder.
Sigorta ve vergi de yeni modelde genelde daha yüksek çıkar.
Yeni araba almayı düşünen birine hemen gönder, o da bilsin.
"""
}

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

def load_used_topics():
    used_file = "used_topics.txt"
    if os.path.exists(used_file):
        with open(used_file, "r", encoding="utf-8") as f:
            return [x.strip() for x in f.readlines() if x.strip()]
    return []

def save_used_topic(topic):
    used = load_used_topics()
    if topic not in used:
        used.append(topic)
    used = used[-40:]
    with open("used_topics.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(used))

def generate_topic():
    used = load_used_topics()
    used_text = "\n".join(used[-15:]) if used else "Yok"
    try:
        response = model.generate_content(f"""
Türkçe araba YouTube Shorts kanalı için YENİ bir konu üret.
Kurallar:
- Sadece araba ile ilgili olsun
- İnsanların merak ettiği, az bilinen veya yanlış bilinen bir şey olsun
- "Herkesin bildiği genel bilgiler" olmasın
- Daha önce kullanılan konuları KESİNLİKLE kullanma:
{used_text}
Örnek tarz:
- Kışın arabayı ısıtmadan sürmek motoru bozar yalanı
- Turbo motor stop sonrası hemen kapatılırsa ne olur
- Otomatik vites yağının ömür boyu olduğu iddiası
Sadece tek satır konu yaz. Başka hiçbir şey yazma.
""")
        topic = response.text.strip().split("\n")[0].strip()
        if len(topic) > 15 and topic not in used:
            print(f"Yeni konu üretildi: {topic}")
            return topic
    except Exception as e:
        print(f"Konu üretim hatası: {e}")
    backups = [
        "Kışın arabayı ısıtmadan sürmek motoru bozar yalanı",
        "Turbo motor stop sonrası hemen kapatılırsa ne olur",
        "Otomatik vites yağının ömür boyu olduğu iddiası",
        "Yüksek oktanlı benzin motoru temizler mi",
        "Elektrikli araba bataryası 5 yılda biter mi",
        "BMW 200 bin kilometre sonra bozulur mu",
        "Dizel partikül filtresi neden tıkanır",
        "Yeni araba almak her zaman daha kârlı mı",
    ]
    available = [b for b in backups if b not in used]
    topic = random.choice(available) if available else random.choice(backups)
    print(f"Yedek konu: {topic}")
    return topic

def generate_script(topic):
    if random.random() < 0.80:
        print("Samimi yedek senaryo kullanılıyor")
        return clean_for_speech(pick_fallback(topic))
    try:
        response = model.generate_content(f"""
Sen Türk YouTube Shorts için samimi bir araba kanalı sunucususun.
Konu: {topic}
ÖRNEK TARZ:
"Kışın arabayı dakikalarca boşta ısıtmazsan motorun bozulacağını mı sanıyorsun?
Sana büyük bir sır vereyim: Bu kural tam otuz yıl önce bitti.
..."
KURALLAR:
1. İlk cümle "sanıyorsun?" ile bitsin.
2. İkinci cümle "Sana büyük bir sır vereyim:" ile başlasın.
3. Genel laf YASAK.
4. Somut, az bilinen ama herkesin anlayacağı bilgi ver.
5. "kilometre" yaz.
6. Son cümle gönder çağrısı olsun.
7. En az 45 saniye. Sadece konuşma metni.
""")
        text = response.text.strip()
        if text and len(text) > 200:
            bad = ["kaliteli yağ", "düzenli bakım", "iyi bakarsan", "uzun ömürlü", "bakım yaparsan", "özetle", "kısaca", "genel olarak"]
            if any(b in text.lower() for b in bad):
                return clean_for_speech(pick_fallback(topic))
            return clean_for_speech(text)
    except Exception as e:
        print(f"Gemini hatası: {e}")
    return clean_for_speech(pick_fallback(topic))

async def text_to_speech(text, output_file):
    clean = re.sub(r'\.\s+', ', ', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    communicate = edge_tts.Communicate(clean, VOICE, rate="+16%", pitch="-3Hz", volume="+25%")
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

def is_valid_image(filepath):
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) < 5000:
            return False
        with Image.open(filepath) as img:
            img.verify()
        with Image.open(filepath) as img:
            img.load()
            if img.width < 200 or img.height < 200:
                return False
        return True
    except Exception:
        return False

def download_music():
    """Ücretsiz arka plan müziği indir. Olmazsa None döner."""
    # Mixkit ücretsiz, telifsiz parçalar
    urls = [
        "https://assets.mixkit.co/music/preview/mixkit-tech-house-vibes-130.mp3",
        "https://assets.mixkit.co/music/preview/mixkit-hip-hop-02-738.mp3",
        "https://assets.mixkit.co/music/preview/mixkit-driving-ambition-32.mp3",
        "https://assets.mixkit.co/music/preview/mixkit-serene-view-443.mp3",
    ]
    random.shuffle(urls)

    for url in urls:
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200 and len(r.content) > 20000:
                with open("music.mp3", "wb") as f:
                    f.write(r.content)
                print("Müzik indirildi")
                return "music.mp3"
        except Exception as e:
            print(f"Müzik indirme hatası: {e}")
            continue

    print("Müzik alınamadı, sessiz devam")
    return None

def download_images(topic, count=16):
    images = []
    t = topic.lower()
    prefer_tag = None
    if "elektrikli" in t or "batarya" in t:
        queries = ["electric car exterior", "electric sedan", "ev car"]
    elif "dizel" in t:
        queries = ["diesel car", "car engine bay", "sedan car"]
    elif "otomatik" in t:
        queries = ["automatic gear shifter car", "car gear lever", "car interior"]
    elif "turbo" in t:
        queries = ["car turbo engine", "car engine closeup", "engine bay"]
    elif "bmw" in t:
        queries = ["BMW sedan", "BMW 3 series", "BMW 5 series", "BMW car exterior"]
        prefer_tag = "bmw"
    elif "oktan" in t or "benzin" in t:
        queries = ["car gas station", "fuel pump car", "petrol station car"]
    elif "yeni araba" in t:
        queries = ["new sedan car", "modern car exterior", "new car"]
    elif "kışın" in t or "isıtmadan" in t:
        queries = ["car in snow", "snow covered car", "car winter", "sedan snow"]
    else:
        queries = ["sedan car exterior", "modern car", "car side view"]

    exclude = [
        "people", "person", "man", "woman", "portrait", "child", "kid", "baby",
        "face", "human", "crowd", "group", "boy", "girl", "worker", "driver",
        "building", "architecture", "house", "skyscraper", "cityscape", "street",
        "cake", "toy", "miniature", "fondant", "dessert",
        "train", "railway", "locomotive", "metro", "subway", "tram",
        "airplane", "aircraft", "plane", "motorcycle", "bike",
        "gondola", "cable car", "ski lift", "cableway",
        "lamborghini", "ferrari", "porsche", "supercar",
        "lamp", "light", "bulb", "lighting", "chandelier", "lantern",
        "furniture", "room", "indoor", "interior design", "sofa", "chair",
        "table", "desk", "office", "kitchen", "bedroom", "living room"
    ]

    preferred = []
    others = []
    for q in queries:
        if len(preferred) + len(others) >= count * 4:
            break
        url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={q.replace(' ', '+')}&image_type=photo&per_page=30&safesearch=true"
        try:
            r = requests.get(url, timeout=12)
            hits = r.json().get("hits", [])
            for hit in hits:
                tags = (hit.get("tags") or "").lower()
                if any(x in tags for x in exclude):
                    continue
                if not any(x in tags for x in ["car", "auto", "vehicle", "sedan", "bmw", "engine", "motor", "wheel"]):
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
            data = requests.get(img_url, timeout=12).content
            if len(data) < 5000:
                continue
            filename = f"img_{len(images)}.jpg"
            with open(filename, "wb") as f:
                f.write(data)
            if is_valid_image(filename):
                images.append(filename)
                print(f"Görsel {len(images)} OK")
            else:
                try:
                    os.remove(filename)
                except:
                    pass
        except Exception as e:
            print(f"İndirme hatası: {e}")
            continue

    if len(images) < 5:
        fallback_q = "BMW+car" if prefer_tag == "bmw" else ("car+snow" if "kışın" in t or "isıtmadan" in t else "sedan+car")
        url = f"https://pixabay.com/api/?key={PIXABAY_KEY}&q={fallback_q}&image_type=photo&per_page=40&safesearch=true"
        try:
            r = requests.get(url, timeout=12)
            for hit in r.json().get("hits", []):
                if len(images) >= count:
                    break
                tags = (hit.get("tags") or "").lower()
                if any(x in tags for x in exclude):
                    continue
                if not any(x in tags for x in ["car", "auto", "vehicle", "sedan", "bmw"]):
                    continue
                img_url = hit.get("largeImageURL") or hit.get("webformatURL")
                if not img_url:
                    continue
                try:
                    data = requests.get(img_url, timeout=10).content
                    if len(data) < 5000:
                        continue
                    filename = f"img_{len(images)}.jpg"
                    with open(filename, "wb") as f:
                        f.write(data)
                    if is_valid_image(filename):
                        images.append(filename)
                        print(f"Yedek görsel {len(images)} OK")
                    else:
                        try:
                            os.remove(filename)
                        except:
                            pass
                except:
                    continue
        except Exception as e:
            print(f"Yedek arama hatası: {e}")

    print(f"Toplam geçerli görsel: {len(images)}")
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
            txt = TextClip(text=display, font_size=26, color="white", stroke_color="black", stroke_width=5, method="caption", size=(780, None), font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
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
        txt = TextClip(text=display, font_size=26, color="white", stroke_color="black", stroke_width=5, method="caption", size=(780, None), font="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        clips.append(txt.with_start(current).with_duration(dur).with_position(("center", 980)))
        current += dur
    return clips

def create_video(script, audio_file, images, topic, word_timings, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    audio = audio.with_volume_scaled(1.6)
    duration = audio.duration
    print(f"Ses: {duration:.1f}s")
    
            # Arka plan müziği (çok alçak)
    music_path = download_music()
    if music_path and os.path.exists(music_path):
        try:
            music = AudioFileClip(music_path).with_volume_scaled(0.10)
            if music.duration < duration:
                music = music.with_duration(duration)
            else:
                music = music.subclipped(0, duration)
            from moviepy import CompositeAudioClip
            audio = CompositeAudioClip([audio, music])
            print("Arka plan müziği eklendi")
        except Exception as e:
            print(f"Müzik karıştırma hatası: {e}")

    valid_images = [img for img in images if is_valid_image(img)]
    if len(valid_images) < 3:
        print("Yeterli geçerli görsel yok!")
        return

    images = valid_images
    print(f"Kullanılacak görsel sayısı: {len(images)}")

    fade = 0.35
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
        try:
            c = make_clip(images[i], clip_dur, i % 3)
            c = c.with_effects([vfx.CrossFadeIn(fade), vfx.CrossFadeOut(fade)])
            img_clips.append(c)
        except Exception as e:
            print(f"Clip hatası ({images[i]}): {e}")
            continue

    if not img_clips:
        print("Hiç clip oluşturulamadı!")
        return

    video = concatenate_videoclips(img_clips, method="compose", padding=-fade)
    video = video.with_duration(duration).resized((W, H))
    video = video.with_audio(audio)

    layers = [video, create_hook(topic, 5.5)] + create_subtitles(script, duration, word_timings)
    final = CompositeVideoClip(layers, size=(W, H)).with_duration(duration)
    final.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", logger=None)
    print("Bitti")
    return output

def main():
    topic = generate_topic()
    print(f"Konu: {topic}")
    print("1. Senaryo...")
    script = generate_script(topic)
    save_used_topic(topic)
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
