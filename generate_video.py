import os
import time
import asyncio
import random
import re
import textwrap
import requests
import google.generativeai as genai
import edge_tts
from moviepy import (
    ImageClip, AudioFileClip, TextClip, CompositeVideoClip,
    concatenate_videoclips
)

# ===================== AYARLAR =====================
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
PIXABAY_KEY = os.environ["PIXABAY_API_KEY"]
MODEL_NAME = "gemini-3.8-flash"
VOICE = "tr-TR-EmelNeural"
W, H = 1080, 1920

model = genai.GenerativeModel(MODEL_NAME)

# ===================== SENARYO =====================
def generate_script(topic):
    prompt = f"""
Sen profesyonel bir Türk YouTube Shorts senaristisin.
Konu: {topic}

40-50 saniyelik çok güçlü bir Shorts senaryosu yaz.

Kurallar:
- İlk 3 saniyede izleyiciyi kilitleyen güçlü bir kanca olsun
- Merak uyandır, net ve anlaşılır konuş
- Sonunda net "Mit" veya "Gerçek" de
- Sadece konuşma metnini yaz, başka bir şey ekleme
- Türkçe yaz
- Maksimum 120 kelime
"""
    for i in range(5):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            if text and len(text) > 30:
                return text
        except Exception as e:
            print(f"Senaryo hatası (deneme {i+1}): {e}")
            time.sleep(18)
    return None

# ===================== SES =====================
async def text_to_speech(text, output_file):
    # Biraz daha canlı tempo
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%")
    await communicate.save(output_file)

# ===================== GÖRSEL ARAMA =====================
def extract_keywords(sentence):
    """Cümleden basit arama kelimeleri çıkar"""
    sentence = sentence.lower()
    
    # Temel kelimeler
    base = ["BMW", "car"]
    
    if any(w in sentence for w in ["duman", "smoke", "beyaz"]):
        base += ["engine", "smoke", "exhaust"]
    elif any(w in sentence for w in ["motor", "engine", "arıza", "bozul"]):
        base += ["engine", "motor"]
    elif any(w in sentence for w in ["devir", "gösterge", "hız"]):
        base += ["dashboard", "speedometer"]
    elif any(w in sentence for w in ["yağ", "oil"]):
        base += ["oil", "engine"]
    elif any(w in sentence for w in ["fren", "brake"]):
        base += ["brake", "wheel"]
    elif any(w in sentence for w in ["lastik", "teker"]):
        base += ["tire", "wheel"]
    else:
        base += ["vehicle", "automobile"]
    
    return "+".join(base[:4])

def download_image_for_query(query, index):
    """Tek bir sorgu için görsel indir"""
    url = (
        f"https://pixabay.com/api/?key={PIXABAY_KEY}"
        f"&q={query}&image_type=photo&orientation=vertical"
        f"&per_page=5&safesearch=true"
    )
    try:
        r = requests.get(url, timeout=12)
        data = r.json()
        hits = data.get("hits", [])
        if not hits:
            return None
        
        # Rastgele birini seç
        hit = random.choice(hits)
        img_url = hit.get("largeImageURL") or hit.get("webformatURL")
        if not img_url:
            return None
        
        img_data = requests.get(img_url, timeout=10).content
        filename = f"img_{index}.jpg"
        with open(filename, "wb") as f:
            f.write(img_data)
        return filename
    except Exception as e:
        print(f"Görsel hatası ({query}): {e}")
        return None

def download_images_for_sentences(sentences):
    """Her cümle için görsel indirmeye çalış"""
    images = []
    for i, sentence in enumerate(sentences):
        query = extract_keywords(sentence)
        print(f"Cümle {i+1} aranıyor: {query}")
        img = download_image_for_query(query, i)
        
        if img:
            images.append(img)
        else:
            # Yedek: genel BMW
            img = download_image_for_query("BMW+car", i)
            if img:
                images.append(img)
    
    return images

# ===================== KLİP OLUŞTURMA =====================
def make_ken_burns_clip(img_path, duration):
    clip = ImageClip(img_path)
    clip = clip.resized(height=int(H * 1.22))
    
    direction = random.choice([-1, 1])
    
    def pos(t):
        progress = t / max(duration, 0.1)
        x = direction * 55 * progress
        y = -35 * progress
        return (x, y)
    
    clip = clip.with_position(pos).with_duration(duration)
    clip = clip.cropped(width=W, height=H, x_center=clip.w/2, y_center=clip.h/2)
    return clip

def create_hook(duration=3.2):
    txt = TextClip(
        text="BMW 200.000 KM SONRA\nBOZULUR MU?",
        font_size=64,
        color="white",
        stroke_color="black",
        stroke_width=4,
        method="caption",
        size=(W - 100, None)
    )
    
    def scale(t):
        if t < 0.5:
            return 0.75 + (t / 0.5) * 0.35
        elif t < 1.2:
            return 1.1 - ((t - 0.5) / 0.7) * 0.1
        return 1.0
    
    txt = txt.resized(scale).with_duration(duration).with_position("center")
    return txt

def create_subtitles(sentences, total_duration):
    if not sentences:
        return []
    
    dur = total_duration / len(sentences)
    clips = []
    
    for i, sentence in enumerate(sentences):
        wrapped = textwrap.fill(sentence, width=26)
        txt = TextClip(
            text=wrapped,
            font_size=46,
            color="white",
            stroke_color="black",
            stroke_width=3,
            method="caption",
            size=(W - 110, None)
        )
        txt = txt.with_start(i * dur).with_duration(max(dur * 0.9, 0.8))
        txt = txt.with_position(("center", H - 300))
        clips.append(txt)
    
    return clips

def split_sentences(script):
    # Cümlelere böl
    parts = re.split(r'(?<=[.!?])\s+', script)
    sentences = [p.strip() for p in parts if len(p.strip()) > 8]
    return sentences if sentences else [script]

# ===================== VİDEO =====================
def create_video(script, audio_file, image_files, sentences, output="video.mp4"):
    audio = AudioFileClip(audio_file)
    duration = audio.duration
    
    # Görselleri cümle sayısına göre ayarla
    if len(image_files) < len(sentences):
        # Eksikse tekrarla
        while len(image_files) < len(sentences):
            image_files.append(random.choice(image_files))
    image_files = image_files[:len(sentences)]
    
    clip_duration = duration / max(len(image_files), 1)
    
    img_clips = []
    for img in image_files:
        try:
            clip = make_ken_burns_clip(img, clip_duration)
            img_clips.append(clip)
        except Exception as e:
            print(f"Clip hatası: {e}")
    
    if not img_clips:
        raise Exception("Hiç görsel klipler oluşmadı")
    
    video = concatenate_videoclips(img_clips, method="compose")
    video = video.with_audio(audio).with_duration(duration)
    
    hook = create_hook(3.0)
    subs = create_subtitles(sentences, duration)
    
    final = CompositeVideoClip([video, hook] + subs, size=(W, H))
    final = final.with_duration(duration)
    
    final.write_videofile(
        output,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None
    )
    return output

# ===================== ANA =====================
def main():
    topic = "BMW arabalar 200 bin km sonra sürekli arıza yapar miti"
    
    print("1. Senaryo yazılıyor...")
    script = generate_script(topic)
    if not script:
        print("Senaryo oluşturulamadı.")
        return
    print("Senaryo hazır.")
    
    print("2. Ses oluşturuluyor...")
    asyncio.run(text_to_speech(script, "ses.mp3"))
    
    print("3. Cümleler ayrılıyor...")
    sentences = split_sentences(script)
    print(f"{len(sentences)} cümle bulundu.")
    
    print("4. Cümlelere göre görseller indiriliyor...")
    images = download_images_for_sentences(sentences)
    
    if len(images) < 2:
        print("Yeterli görsel indirilemedi.")
        return
    
    print("5. Video oluşturuluyor...")
    create_video(script, "ses.mp3", images, sentences)
    print("Video hazır: video.mp4")

if __name__ == "__main__":
    main()
