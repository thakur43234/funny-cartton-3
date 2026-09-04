import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import math
import numpy as np
import asyncio
import random
import cv2
import re
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips, CompositeAudioClip
import moviepy.audio.fx.all as afx
import edge_tts
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# =====================================================================
# 🟢 1. EASY CUSTOMIZATION BLOCK 🟢
# =====================================================================
CHANNEL_NAME = "@YourThirdChannel"          # अपने तीसरे चैनल का नाम
TOP_BANNER_TEXT = "Pinku aur Neelu 😂"       # ऊपर दिखने वाला बैनर टेक्स्ट
FONT_PATH = "./NirmalaB.ttf"

# =====================================================================

OUTPUT_FOLDER = "./output"
TEMP_FOLDER = "./temp"
TEXT_FILE_PATH = "./jokes.txt"
BG_FOLDER = "./bgs" 
SFX_FOLDER = "./sfx"       
BGM_FILE = "./bgm.mp3"     
LAUGH_FILE = "./laugh.mp3" 
TOKENS_FOLDER = "./tokens"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(BG_FOLDER, exist_ok=True)
os.makedirs(SFX_FOLDER, exist_ok=True)
os.makedirs(TOKENS_FOLDER, exist_ok=True)

WIDTH, HEIGHT = 720, 1280
FPS = 30

# ==========================================
# 2. AUDIO GENERATION (2 DIFFERENT FUNNY VOICES)
# ==========================================
async def download_voices(story_lines):
    print("🎙️ Generating Character Voices...")
    for i, line in enumerate(story_lines):
        filename = os.path.join(TEMP_FOLDER, f"temp_audio_{i}.mp3")
        line["audio"] = filename
        communicate = edge_tts.Communicate(line["text"], line["voice"], rate=line["rate"], pitch=line["pitch"], volume="+100%")
        await communicate.save(filename)

# ==========================================
# 3. TEXT PARSING 
# ==========================================
def fetch_and_delete_first_joke():
    if not os.path.exists(TEXT_FILE_PATH): return None
    with open(TEXT_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        
    jokes = [s.strip() for s in content.split("=====") if s.strip()]
    if not jokes: return None
        
    first_joke = jokes[0]
    remaining_jokes = jokes[1:]
    
    with open(TEXT_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("\n=====\n".join(remaining_jokes))
        
    story_data = []
    lines = first_joke.split('\n')
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        match = re.match(r'^(.*?)(?:\s*\((.*?)\))?\s*:\s*(.*)$', line)
        if match:
            speaker = match.group(1).strip()
            bracket_content = match.group(2).strip().lower() if match.group(2) else "normal"
            text = match.group(3).strip()
            
            bracket_parts = [p.strip() for p in bracket_content.split(',')]
            emotion = bracket_parts[0] if len(bracket_parts) > 0 else "normal"
            camera_cmd = bracket_parts[1] if len(bracket_parts) > 1 else "normal"
            
            # 🟢 Pinku = Squeaky फनी आवाज़ | Neelu = बिल्कुल अलग आवाज़
            is_pink = (speaker.lower() == "pinku")
            if is_pink:
                voice = "hi-IN-MadhurNeural"
                pitch = "+60Hz"   # बहुत पतली चूहे जैसी आवाज़
                rate = "+25%"
                speaker_name = "Pinku"
            else:
                voice = "hi-IN-SwaraNeural"
                pitch = "-15Hz"   # थोड़ी भारी, बिल्कुल अलग आवाज़
                rate = "+10%"
                speaker_name = "Neelu"
            
            story_data.append({
                "scene": idx + 1,
                "speaker": speaker_name,
                "text": text,
                "voice": voice,
                "emotion": emotion,
                "camera": camera_cmd,
                "pitch": pitch,
                "rate": rate
            })
    return story_data

# ==========================================
# 4. YOUTUBE UPLOAD
# ==========================================
def upload_to_youtube(video_file):
    print("🌐 YouTube Uploading...")
    token_files = [os.path.join(TOKENS_FOLDER, f) for f in os.listdir(TOKENS_FOLDER) if f.endswith('.json')]
    if not token_files: return False
        
    yt_titles = ["Pinku aur Neelu की मस्ती 😂 | Funny Cartoon", "ये कार्टून देखकर हँसी नहीं रुकेगी 🤣", "Pinku vs Neelu की फनी बातचीत 😆 | Shorts"]
    request_body = {
        "snippet": {
            "title": random.choice(yt_titles), 
            "description": "Pinku aur Neelu ki funny comedy! Subscribe for daily cartoons! #funny #cartoon #comedy #shorts", 
            "tags": ["funny cartoon", "pink panther style", "hindi cartoon comedy", "funny animals", "cartoon joke", "shorts"], 
            "categoryId": "23" 
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }

    for token_path in token_files:
        try:
            creds = Credentials.from_authorized_user_file(token_path, ["https://www.googleapis.com/auth/youtube.upload"])
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, 'w') as tf: tf.write(creds.to_json())
                    
            youtube = build('youtube', 'v3', credentials=creds)
            media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
            response = request.execute()
            print(f"✅ Video LIVE: https://youtu.be/{response['id']}")
            return True
        except Exception as e: print(f"❌ Upload Error: {e}")
    return False

# ==========================================
# 5. DRAWING HELPERS
# ==========================================
def draw_background(surf, bg_img):
    if bg_img: surf.blit(bg_img, (0, 0))
    else: surf.fill((100, 150, 200)) 

def render_text_with_outline(surf, text, font, color, x, y, outline_color=(0,0,0), thickness=3, center_x=False):
    words = text.split(" ")
    lines, current_line = [], ""
    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] < WIDTH - 80: current_line = test_line
        else: lines.append(current_line); current_line = word + " "
    lines.append(current_line)
    
    for i, line in enumerate(lines):
        final_x = x
        if center_x: final_x = (WIDTH - font.size(line)[0]) // 2
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx != 0 or dy != 0:
                    txt_bg = font.render(line, True, outline_color)
                    surf.blit(txt_bg, (final_x + dx, y + i * 55 + dy))
        txt_fg = font.render(line, True, color)
        surf.blit(txt_fg, (final_x, y + i * 55))

# ==========================================
# 🟢 6. CAT CHARACTER CLASS (PANTHER STYLE) 🟢
# ==========================================
class CatCharacter:
    def __init__(self, name, char_type):
        self.name = name
        self.char_type = char_type  # 'pinku' or 'neelu'
        
        if self.char_type == 'pinku':
            self.body_color = (255, 105, 180)    # गुलाबी
            self.belly_color = (255, 190, 220)   # हल्का गुलाबी
            self.eye_iris = (255, 210, 0)        # पीली आँखें
            self.body_w = 100                     # पतला
        else:
            self.body_color = (130, 110, 230)    # बैंगनी
            self.belly_color = (190, 175, 245)   # हल्का बैंगनी
            self.eye_iris = (50, 200, 100)       # हरी आँखें
            self.body_w = 130                     # मोटा (अलग लुक)
            self.stripe_color = (90, 70, 180)    # धारियाँ

        self.pos = np.array([0.0, 0.0])
        self.target_pos = np.array([0.0, 0.0])
        self.blink_timer = 0
        self.is_blinking = False
        self.flip = False

    def update(self):
        self.pos += (self.target_pos - self.pos) * 0.1
        self.blink_timer += 1
        if self.blink_timer > random.randint(80, 150):
            self.is_blinking = True
            if self.blink_timer > 160: self.is_blinking = False; self.blink_timer = 0

    def draw(self, surf, is_talking, char_emotion, timer, action_frame):
        world_x, world_y = int(self.pos[0]), int(self.pos[1])
        char_surf = pygame.Surface((400, 560), pygame.SRCALPHA)
        cx, cy = 200, 240

        angle = 0; y_off = 0; is_hitting = False
        hit_dir = 1 if not self.flip else -1
        
        # 🟢 ACTION ANIMATIONS
        if action_frame >= 0:
            if char_emotion in ["slap", "punch"]:
                if action_frame < 15: is_hitting = True
            elif char_emotion == "victim":
                if action_frame < 10:
                    progress = action_frame / 10.0
                    angle = -90 * progress if self.flip else 90 * progress
                    y_off = 150 * progress
                elif action_frame < 35:
                    angle = -90 if self.flip else 90; y_off = 150
                elif action_frame < 50:
                    progress = (action_frame - 35) / 15.0
                    angle = (-90 if self.flip else 90) * (1.0 - progress)
                    y_off = 150 * (1.0 - progress)
            elif char_emotion in ["shock", "funny"]:
                if action_frame < 25: y_off = -abs(math.sin(action_frame * 0.8)) * 80 

        # Shadow
        pygame.draw.ellipse(surf, (0,0,0,80), (world_x-70, world_y+180, 140, 30))

        # 🟢 लंबी घुंघराली पूंछ (Tail - हलचल के साथ हिलती है)
        back_dir = -1 if not self.flip else 1
        for i in range(18):
            t = i / 17.0
            seg_x = cx + back_dir * (40 + math.sin(t * 2.5 + timer * 0.08) * 14 * t)
            seg_y = (cy + 140) - t * 220
            r = max(4, 13 - int(t * 9))
            pygame.draw.circle(char_surf, self.body_color, (int(seg_x), int(seg_y)), r)

        # Legs & Feet
        pygame.draw.line(char_surf, self.body_color, (cx-25, cy+140), (cx-30, cy+185), 16)
        pygame.draw.line(char_surf, self.body_color, (cx+25, cy+140), (cx+30, cy+185), 16)
        pygame.draw.ellipse(char_surf, self.body_color, (cx-50, cy+180, 42, 20))
        pygame.draw.ellipse(char_surf, self.body_color, (cx+10, cy+180, 42, 20))

        # Body (Tall ellipse)
        pygame.draw.ellipse(char_surf, self.body_color, (cx - self.body_w//2, cy - 20, self.body_w, 175))
        # Belly
        pygame.draw.ellipse(char_surf, self.belly_color, (cx - self.body_w//2 + 22, cy + 15, self.body_w - 44, 105))
        
        # 🟢 Neelu की Body पर धारियाँ (Stripes - Copyright से बचने के लिए)
        if self.char_type == 'neelu':
            for sy in [cy+5, cy+45, cy+85]:
                pygame.draw.line(char_surf, self.stripe_color, (cx - self.body_w//2 + 6, sy), (cx - self.body_w//2 + 26, sy), 6)
                pygame.draw.line(char_surf, self.stripe_color, (cx + self.body_w//2 - 6, sy), (cx + self.body_w//2 - 26, sy), 6)

        # Arms
        arm_swing = math.sin(timer * 0.5) * 20 if is_talking else 0
        if char_emotion == "angry" and is_talking: arm_swing = math.sin(timer * 2.0) * 40
        
        if is_hitting:
            # 🟢 थप्पड़/मुक्का मारने वाला हाथ
            pygame.draw.line(char_surf, self.body_color, (cx, cy + 30), (cx + (135 * hit_dir), cy + 10), 15)
            pygame.draw.circle(char_surf, self.body_color, (int(cx + (135 * hit_dir)), cy + 10), 20)
        else:
            pygame.draw.line(char_surf, self.body_color, (cx - self.body_w//2 + 5, cy + 25), (cx - self.body_w//2 - 25, cy + 85 + arm_swing), 13)
            pygame.draw.line(char_surf, self.body_color, (cx + self.body_w//2 - 5, cy + 25), (cx + self.body_w//2 + 25, cy + 85 - arm_swing), 13)
            pygame.draw.circle(char_surf, self.body_color, (cx - self.body_w//2 - 25, int(cy + 85 + arm_swing)), 14)
            pygame.draw.circle(char_surf, self.body_color, (cx + self.body_w//2 + 25, int(cy + 85 - arm_swing)), 14)

        # 🟢 Head (Ears अलग-अलग स्टाइल के)
        head_bounce = math.sin(timer * 1.5) * 5 if is_talking else 0
        head_y = cy - 80 + head_bounce
        
        if self.char_type == 'pinku':
            # नुकीले कान
            pygame.draw.polygon(char_surf, self.body_color, [(cx-55, head_y-30), (cx-38, head_y-105), (cx-8, head_y-45)])
            pygame.draw.polygon(char_surf, self.body_color, [(cx+55, head_y-30), (cx+38, head_y-105), (cx+8, head_y-45)])
        else:
            # गोल कान
            pygame.draw.circle(char_surf, self.body_color, (cx-50, head_y-55), 26)
            pygame.draw.circle(char_surf, self.body_color, (cx+50, head_y-55), 26)

        pygame.draw.circle(char_surf, self.body_color, (cx, head_y), 68)
        # Muzzle
        pygame.draw.ellipse(char_surf, self.belly_color, (cx-38, head_y-5, 76, 58))

        # 🟢 BIG CARTOON EYES
        look = -10 if self.flip else 10
        eye_r = 24
        if char_emotion == "shock": eye_r = 30

        if char_emotion == "victim" and 0 <= action_frame < 50:
            # 😵 चकराती आँखें (Dizzy X Eyes)
            for ex in [-26, 26]:
                pygame.draw.line(char_surf, (20,20,20), (cx+ex-12+look, head_y-37), (cx+ex+12+look, head_y-13), 5)
                pygame.draw.line(char_surf, (20,20,20), (cx+ex+12+look, head_y-37), (cx+ex-12+look, head_y-13), 5)
        elif self.is_blinking:
            pygame.draw.line(char_surf, (20,20,20), (cx-38+look, head_y-25), (cx-14+look, head_y-25), 5)
            pygame.draw.line(char_surf, (20,20,20), (cx+14+look, head_y-25), (cx+38+look, head_y-25), 5)
        else:
            # White
            pygame.draw.circle(char_surf, (255,255,255), (cx-26, head_y-25), eye_r)
            pygame.draw.circle(char_surf, (255,255,255), (cx+26, head_y-25), eye_r)
            # Iris (रंगीन आँखें)
            pygame.draw.circle(char_surf, self.eye_iris, (cx-26+look//2, head_y-25), int(eye_r*0.55))
            pygame.draw.circle(char_surf, self.eye_iris, (cx+26+look//2, head_y-25), int(eye_r*0.55))
            # Pupil
            pygame.draw.circle(char_surf, (20,20,20), (cx-26+int(look*0.8), head_y-25), 7)
            pygame.draw.circle(char_surf, (20,20,20), (cx+26+int(look*0.8), head_y-25), 7)

        # Nose
        nose_color = (200, 40, 100) if self.char_type == 'pinku' else (50, 60, 170)
        pygame.draw.ellipse(char_surf, nose_color, (cx-11, head_y, 22, 14))

        # 🟢 मूंछें (Whiskers)
        for side in [-1, 1]:
            pygame.draw.line(char_surf, (20,20,20), (cx + side*40, head_y+10), (cx + side*90, head_y+2), 3)
            pygame.draw.line(char_surf, (20,20,20), (cx + side*40, head_y+18), (cx + side*90, head_y+24), 3)

        # Mouth (Perfect Sync)
        if is_talking:
            m_size = abs(math.sin(timer * 1.5)) * 25 + 6
            if char_emotion in ["shock", "slap"]: m_size = 38
            pygame.draw.ellipse(char_surf, (150, 30, 60), (cx-18, head_y+20, 36, m_size))
        else:
            pygame.draw.arc(char_surf, (20,20,20), (cx-20, head_y+8, 40, 30), math.pi*0.15, math.pi*0.85, 4)

        # Apply rotation for falling
        if angle != 0:
            rotated_surf = pygame.transform.rotate(char_surf, angle)
            new_rect = rotated_surf.get_rect(center=(world_x, world_y + y_off))
            surf.blit(rotated_surf, new_rect.topleft)
        else:
            surf.blit(char_surf, (world_x - cx, world_y + y_off - cy))


# ==========================================
# 7. MAIN ENGINE
# ==========================================
async def main():
    print("🚀 Auto Video Generator (Pinku & Neelu) Started...")
    current_story = fetch_and_delete_first_joke()
    if not current_story: return
        
    await download_voices(current_story)

    pygame.init()
    try: 
        hindi_font = pygame.font.Font(FONT_PATH, 45)
        title_font = pygame.font.Font(FONT_PATH, 60)
        watermark_font = pygame.font.Font(FONT_PATH, 35)
    except: 
        hindi_font = pygame.font.SysFont("Arial", 45)
        title_font = pygame.font.SysFont("Arial", 60)
        watermark_font = pygame.font.SysFont("Arial", 35)

    world_w = WIDTH + 400 
    main_surf = pygame.Surface((world_w, HEIGHT))
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    
    loaded_bg = None
    bg_files = [f for f in os.listdir(BG_FOLDER) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if bg_files:
        loaded_bg = pygame.image.load(os.path.join(BG_FOLDER, random.choice(bg_files)))
        loaded_bg = pygame.transform.scale(loaded_bg, (world_w, HEIGHT))

    temp_video_path = os.path.join(TEMP_FOLDER, "temp_video.mp4")
    final_video_path = os.path.join(OUTPUT_FOLDER, "FINAL_UPLOAD.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(temp_video_path, fourcc, FPS, (WIDTH, HEIGHT))

    # 🟢 कैरेक्टर्स इनिशियलाइज़
    chars = {
        "Pinku": CatCharacter("Pinku", "pinku"),
        "Neelu": CatCharacter("Neelu", "neelu")
    }
    
    audio_clips = []
    
    for idx, line in enumerate(current_story):
        speech_clip = AudioFileClip(line["audio"]).fx(afx.volumex, 4.0)
        # 🟢 SILENCE TRIMMER (मुँह 0.0 सेकंड में बंद)
        if speech_clip.duration > 0.6: speech_clip = speech_clip.subclip(0, speech_clip.duration - 0.5)
            
        emotion = line.get("emotion", "normal")
        sfx_path = None
        if emotion != "normal":
            for ext in [".mp3", ".wav"]:
                if os.path.exists(os.path.join(SFX_FOLDER, f"{emotion}{ext}")):
                    sfx_path = os.path.join(SFX_FOLDER, f"{emotion}{ext}"); break

        if sfx_path:
            sfx_clip = AudioFileClip(sfx_path).fx(afx.volumex, 1.8)
            mixed_audio = CompositeAudioClip([speech_clip.set_start(0), sfx_clip.set_start(speech_clip.duration)])
            line["total_dur"] = speech_clip.duration + max(sfx_clip.duration, 1.8) 
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(mixed_audio)
        else:
            line["total_dur"] = speech_clip.duration + 0.4 
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(speech_clip)

    timer = 0; cam_x = 200 

    for idx, line in enumerate(current_story):
        speaker = line["speaker"]
        emotion = line.get("emotion", "normal")
        camera_cmd = line.get("camera", "normal") 
        
        frames_to_render = int(line["total_dur"] * FPS)
        speech_frames = int(line["speech_dur"] * FPS)
        
        chars["Pinku"].target_pos = [world_w//2 - 180, HEIGHT//2 + 100]; chars["Pinku"].flip = False
        chars["Neelu"].target_pos = [world_w//2 + 180, HEIGHT//2 + 100]; chars["Neelu"].flip = True   

        for f in range(frames_to_render):
            timer += 1
            is_talking_now = f < speech_frames
            action_frame = f - speech_frames
            is_action_time = action_frame >= 0
            
            # 🟢 DYNAMIC CAMERA PANNING
            if is_talking_now: target_cam_x = 100 if speaker == "Pinku" else 300
            elif is_action_time and emotion in ["slap", "punch"]: target_cam_x = 300 if speaker == "Pinku" else 100 
            else: target_cam_x = 200 
                
            cam_x += (target_cam_x - cam_x) * 0.1 
            
            if loaded_bg: main_surf.blit(loaded_bg, (0, 0))
            else: main_surf.fill((100, 150, 200))
                
            for name, char in chars.items():
                is_talking = (name == speaker and is_talking_now)
                char.update()
                
                char_emotion = "normal"
                if name == speaker: char_emotion = emotion
                elif emotion in ["slap", "punch"] and is_action_time: char_emotion = "victim"
                
                char.draw(main_surf, is_talking, char_emotion, timer, action_frame)

            # 🟢 IMPACT FLASH
            if is_action_time and emotion in ["slap", "punch"] and 0 <= action_frame <= 2:
                main_surf.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)

            is_zoomed = "zoom" in camera_cmd and (is_talking_now or is_action_time)
            is_shaking = "shake" in camera_cmd and is_action_time
            
            if is_zoomed or is_shaking:
                zoom_scale = 1.3 if is_zoomed else 1.0
                new_w, new_h = int(world_w * zoom_scale), int(HEIGHT * zoom_scale)
                if is_zoomed:
                    zoomed_surf = pygame.transform.smoothscale(main_surf, (new_w, new_h))
                    zoom_offset_x = (new_w - world_w) // 2
                    zoom_offset_y = -200 
                else: zoomed_surf = main_surf; zoom_offset_x, zoom_offset_y = 0, 0
                
                if is_shaking:
                    shake_int = 25 if emotion in ["slap", "punch"] else 10
                    zoom_offset_x += random.randint(-shake_int, shake_int)
                    zoom_offset_y += random.randint(-shake_int, shake_int)
                
                screen.fill((0,0,0)); screen.blit(zoomed_surf, (-cam_x - zoom_offset_x, zoom_offset_y))
            else:
                screen.fill((0,0,0)); screen.blit(main_surf, (-int(cam_x), 0)) 
                
            # 🟢 BANNER + WATERMARK
            watermark_surf = watermark_font.render(CHANNEL_NAME, True, (255, 255, 255))
            watermark_surf.set_alpha(120)
            screen.blit(watermark_surf, (20, 160))
            
            pygame.draw.rect(screen, (255, 200, 0), (0, 40, WIDTH, 90))
            render_text_with_outline(screen, TOP_BANNER_TEXT, title_font, (255, 255, 255), 0, 50, (0,0,0), 5, center_x=True)
            
            view = pygame.surfarray.array3d(screen); view = view.transpose([1, 0, 2])
            img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR); video_writer.write(img_bgr)

    laugh_frames = 2 * FPS 
    for f in range(laugh_frames):
        timer += 1
        cam_x += (200 - cam_x) * 0.1 
        
        if loaded_bg: main_surf.blit(loaded_bg, (0, 0))
        else: main_surf.fill((100, 150, 200))
        for name, char in chars.items(): char.update(); char.draw(main_surf, False, "normal", timer, -1)
        
        screen.fill((0,0,0)); screen.blit(main_surf, (-int(cam_x), 0))
        
        pygame.draw.rect(screen, (255, 200, 0), (0, 40, WIDTH, 90))
        render_text_with_outline(screen, TOP_BANNER_TEXT, title_font, (255, 255, 255), 0, 50, (0,0,0), 5, center_x=True)

        view = pygame.surfarray.array3d(screen); view = view.transpose([1, 0, 2])
        img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR); video_writer.write(img_bgr)

    video_writer.release()
    pygame.quit()

    print("🎧 Merging Audio...")
    final_audio = concatenate_audioclips(audio_clips)
    if os.path.exists(LAUGH_FILE):
        laugh_clip = AudioFileClip(LAUGH_FILE).fx(afx.volumex, 1.2)
        final_audio = concatenate_audioclips([final_audio, laugh_clip.set_start(0).set_duration(laugh_frames / FPS)])

    if os.path.exists(BGM_FILE):
        bgm_clip = AudioFileClip(BGM_FILE).fx(afx.volumex, 0.15).loop(duration=final_audio.duration)
        final_audio = CompositeAudioClip([final_audio, bgm_clip])

    video_clip = VideoFileClip(temp_video_path)
    final_video = video_clip.set_audio(final_audio)
    final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", fps=FPS, preset="ultrafast", logger=None)
    video_clip.close()
    
    upload_to_youtube(final_video_path)

if __name__ == "__main__":
    asyncio.run(main())
