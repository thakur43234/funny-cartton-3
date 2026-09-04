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

# ==========================================
# 🟢 1. SETTINGS & FOLDERS 🟢
# ==========================================
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

char_colors = {"Wife": (255, 105, 180), "Husband": (100, 200, 100)}

# ==========================================
# 2. AUDIO GENERATION
# ==========================================
async def download_voices(story_lines):
    print("🎙️ Generating AI Voices...")
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
            
            is_wife = (speaker.lower() == "wife")
            story_data.append({
                "scene": idx + 1,
                "speaker": "Wife" if is_wife else "Husband",
                "text": text,
                "voice": "hi-IN-SwaraNeural" if is_wife else "hi-IN-MadhurNeural",
                "emotion": emotion,
                "camera": camera_cmd,
                "pitch": "+45Hz" if is_wife else "+35Hz",
                "rate": "+25%" if is_wife else "+20%"
            })
    return story_data

# ==========================================
# 4. YOUTUBE UPLOAD
# ==========================================
def upload_to_youtube(video_file):
    print("🌐 YouTube Uploading...")
    token_files = [os.path.join(TOKENS_FOLDER, f) for f in os.listdir(TOKENS_FOLDER) if f.endswith('.json')]
    if not token_files:
        print("❌ Token not found!")
        return False
        
    yt_titles = ["Husband vs Wife 😂 | Funny Joke", "लोटपोट कर देने वाला जोक 🤣", "पति पत्नी की लड़ाई 😆 | Funny Shorts"]
    request_body = {
        "snippet": {
            "title": random.choice(yt_titles), 
            "description": "Trending Husband Wife funny joke! Subscribe for daily comedy shorts! #funny #comedy #shorts #husbandwife", 
            "tags": ["funny", "comedy", "husband wife joke", "hindi jokes", "make joke of"], 
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
        except Exception as e:
            print(f"❌ Upload Error: {e}")
    return False

# ==========================================
# 5. DRAWING & VIRAL ANIMATIONS
# ==========================================
class Character:
    def __init__(self, name, color):
        self.name = name
        self.color = color
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
        
        # Surface for rotation (Falling effect)
        char_surf = pygame.Surface((400, 500), pygame.SRCALPHA)
        cx, cy = 200, 250 

        angle = 0
        y_off = 0
        is_hitting = False
        hit_dir = 1 if not self.flip else -1
        
        face_color = (255, 120, 120) if char_emotion in ["angry", "slap", "punch", "victim"] else (255, 220, 180)

        # 🟢 ACTION ANIMATIONS 🟢
        if action_frame >= 0:
            if char_emotion in ["slap", "punch"]:
                if action_frame < 15: is_hitting = True # हाथ आगे मारना
            elif char_emotion == "victim":
                face_color = (255, 80, 80) # चेहरा लाल
                if action_frame < 10:
                    progress = action_frame / 10.0
                    angle = -90 * progress if self.flip else 90 * progress
                    y_off = 150 * progress
                elif action_frame < 35:
                    angle = -90 if self.flip else 90
                    y_off = 150
                elif action_frame < 50:
                    progress = (action_frame - 35) / 15.0
                    angle = (-90 if self.flip else 90) * (1.0 - progress)
                    y_off = 150 * (1.0 - progress)
            elif char_emotion == "shock":
                if action_frame < 25:
                    y_off = -abs(math.sin(action_frame * 0.8)) * 80 # झटके से उछलना

        # DRAWING 
        pygame.draw.ellipse(surf, (0,0,0,80), (world_x-70, world_y+180, 140, 30)) # Shadow

        # Legs
        pygame.draw.line(char_surf, (20,20,20), (cx - 30, cy + 160), (cx - 30, cy + 190), 12)
        pygame.draw.line(char_surf, (20,20,20), (cx + 30, cy + 160), (cx + 30, cy + 190), 12)
        
        # Body
        pygame.draw.rect(char_surf, self.color, (cx-60, cy, 120, 160), border_radius=30)
        pygame.draw.rect(char_surf, (20,20,20), (cx-60, cy, 120, 160), 6, border_radius=30)

        # Arms
        arm_swing = math.sin(timer * 0.5) * 20 if is_talking else 0
        if char_emotion == "angry" and is_talking: arm_swing = math.sin(timer * 2.0) * 40
        
        if is_hitting:
            # 👊 थप्पड़ मारने वाला हाथ
            pygame.draw.line(char_surf, (20,20,20), (cx, cy + 50), (cx + (140 * hit_dir), cy + 30), 15)
            pygame.draw.circle(char_surf, (255, 220, 180), (cx + (140 * hit_dir), cy + 30), 20) # मुट्ठी
        else:
            pygame.draw.line(char_surf, (20,20,20), (cx - 60, cy + 50), (cx - 90, cy + 90 + arm_swing), 12)
            pygame.draw.line(char_surf, (20,20,20), (cx + 60, cy + 50), (cx + 90, cy + 90 - arm_swing), 12)

        # Head
        head_bounce = math.sin(timer * 1.5) * 5 if is_talking else 0
        head_y = cy - 60 + head_bounce
        pygame.draw.circle(char_surf, face_color, (cx, head_y), 70)
        pygame.draw.circle(char_surf, (20,20,20), (cx, head_y), 70, 6)

        # Eyes & Expressions
        look = -10 if self.flip else 10
        if char_emotion == "victim" and 0 <= action_frame < 50:
            # 😵 चकराती आँखें
            pygame.draw.line(char_surf, (20,20,20), (cx-35+look, head_y-30), (cx-15+look, head_y-10), 6)
            pygame.draw.line(char_surf, (20,20,20), (cx-15+look, head_y-30), (cx-35+look, head_y-10), 6)
            pygame.draw.line(char_surf, (20,20,20), (cx+5+look, head_y-30), (cx+25+look, head_y-10), 6)
            pygame.draw.line(char_surf, (20,20,20), (cx+25+look, head_y-30), (cx+5+look, head_y-10), 6)
        else:
            eye_h = 4 if self.is_blinking else 30
            if char_emotion == "shock": eye_h = 55
            pygame.draw.ellipse(char_surf, (20,20,20), (cx - 30 + look, head_y - 20, 20, eye_h))
            pygame.draw.ellipse(char_surf, (20,20,20), (cx + 10 + look, head_y - 20, 20, eye_h))

        # 💢 Angry Vein & Sad Tear
        if char_emotion in ["angry", "slap", "punch"]:
            pygame.draw.line(char_surf, (20,20,20), (cx - 40 + look, head_y - 35), (cx - 15 + look, head_y - 15), 5)
            pygame.draw.line(char_surf, (20,20,20), (cx + 35 + look, head_y - 35), (cx + 10 + look, head_y - 15), 5)
            pygame.draw.line(char_surf, (200,0,0), (cx + 20, head_y - 55), (cx + 40, head_y - 35), 4)
            pygame.draw.line(char_surf, (200,0,0), (cx + 40, head_y - 55), (cx + 20, head_y - 35), 4)
        if char_emotion in ["sad", "cry"]: 
            pygame.draw.ellipse(char_surf, (0, 191, 255), (cx + 30 + look, head_y - 5, 12, 20))

        # Mouth (Strict Sync)
        if is_talking:
            m_size = abs(math.sin(timer * 1.5)) * 30 + 5
            if char_emotion in ["shock", "slap"]: m_size = 45
            pygame.draw.ellipse(char_surf, (180, 0, 0), (cx - 20 + look, head_y + 25, 40, m_size))
        else:
            pygame.draw.line(char_surf, (20,20,20), (cx - 15 + look, head_y + 35), (cx + 15 + look, head_y + 35), 6)

        # 🟢 Apply Rotation (गिरने का असर)
        if angle != 0:
            rotated_surf = pygame.transform.rotate(char_surf, angle)
            new_rect = rotated_surf.get_rect(center=(world_x, world_y + y_off))
            surf.blit(rotated_surf, new_rect.topleft)
        else:
            surf.blit(char_surf, (world_x - cx, world_y + y_off - cy))


# ==========================================
# 6. MAIN ENGINE (WITH CAMERA PANNING)
# ==========================================
async def main():
    print("🚀 Auto Viral Video Generator Started...")
    current_story = fetch_and_delete_first_joke()
    if not current_story: return
        
    await download_voices(current_story)

    pygame.init()
    # 🟢 Background थोड़ा बड़ा बनाया है ताकि कैमरा खिसक (Pan) सके
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

    chars = {speaker: Character(speaker, color) for speaker, color in char_colors.items()}
    audio_clips = []
    
    for idx, line in enumerate(current_story):
        speech_clip = AudioFileClip(line["audio"]).fx(afx.volumex, 4.0)
        if speech_clip.duration > 0.6: speech_clip = speech_clip.subclip(0, speech_clip.duration - 0.5)
            
        emotion = line.get("emotion", "normal")
        sfx_path = None
        if emotion != "normal":
            mp3_path = os.path.join(SFX_FOLDER, f"{emotion}.mp3")
            wav_path = os.path.join(SFX_FOLDER, f"{emotion}.wav")
            if os.path.exists(mp3_path): sfx_path = mp3_path
            elif os.path.exists(wav_path): sfx_path = wav_path

        if sfx_path:
            sfx_clip = AudioFileClip(sfx_path).fx(afx.volumex, 1.8)
            mixed_audio = CompositeAudioClip([
                speech_clip.set_start(0), 
                sfx_clip.set_start(speech_clip.duration) 
            ])
            line["total_dur"] = speech_clip.duration + max(sfx_clip.duration, 1.8) # Animation time
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(mixed_audio)
        else:
            line["total_dur"] = speech_clip.duration + 0.4 
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(speech_clip)

    print("🎥 Rendering Video Frames...")
    timer = 0
    cam_x = 200 # Initial center offset

    for idx, line in enumerate(current_story):
        speaker = line["speaker"]
        emotion = line.get("emotion", "normal")
        camera_cmd = line.get("camera", "normal") 
        
        frames_to_render = int(line["total_dur"] * FPS)
        speech_frames = int(line["speech_dur"] * FPS)
        
        chars["Wife"].target_pos = [world_w//2 - 180, HEIGHT//2 + 100]; chars["Wife"].flip = False
        chars["Husband"].target_pos = [world_w//2 + 180, HEIGHT//2 + 100]; chars["Husband"].flip = True   

        for f in range(frames_to_render):
            timer += 1
            is_talking_now = f < speech_frames
            action_frame = f - speech_frames
            is_action_time = action_frame >= 0
            
            # 🟢 DYNAMIC CAMERA PANNING (हलचल)
            if is_talking_now:
                target_cam_x = 100 if speaker == "Wife" else 300
            elif is_action_time and emotion in ["slap", "punch"]:
                target_cam_x = 300 if speaker == "Wife" else 100 # पैन टू विक्टिम
            else:
                target_cam_x = 200 # Center
                
            cam_x += (target_cam_x - cam_x) * 0.1 # Smooth Lerp Movement
            
            if loaded_bg: main_surf.blit(loaded_bg, (0, 0))
            else: main_surf.fill((160, 140, 240))
                
            for name, char in chars.items():
                is_talking = (name == speaker and is_talking_now)
                char.update()
                
                char_emotion = "normal"
                if name == speaker: char_emotion = emotion
                elif emotion in ["slap", "punch"] and is_action_time: char_emotion = "victim"
                
                char.draw(main_surf, is_talking, char_emotion, timer, action_frame)

            # 🟢 IMPACT FLASH (स्क्रीन पर सफ़ेद चमक)
            if is_action_time and emotion in ["slap", "punch"] and 0 <= action_frame <= 2:
                main_surf.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)

            # 🟢 CAMERA ZOOM AND SHAKE 
            is_zoomed = "zoom" in camera_cmd and (is_talking_now or is_action_time)
            is_shaking = "shake" in camera_cmd and is_action_time
            
            if is_zoomed or is_shaking:
                zoom_scale = 1.3 if is_zoomed else 1.0
                new_w, new_h = int(world_w * zoom_scale), int(HEIGHT * zoom_scale)
                
                if is_zoomed:
                    zoomed_surf = pygame.transform.smoothscale(main_surf, (new_w, new_h))
                    zoom_offset_x = (new_w - world_w) // 2
                    zoom_offset_y = -200 
                else:
                    zoomed_surf = main_surf
                    zoom_offset_x, zoom_offset_y = 0, 0
                
                if is_shaking:
                    shake_int = 25 if emotion in ["slap", "punch"] else 10
                    zoom_offset_x += random.randint(-shake_int, shake_int)
                    zoom_offset_y += random.randint(-shake_int, shake_int)
                
                # Crop and draw based on Camera Pan
                screen.fill((0,0,0))
                screen.blit(zoomed_surf, (-cam_x - zoom_offset_x, zoom_offset_y))
            else:
                screen.fill((0,0,0))
                screen.blit(main_surf, (-int(cam_x), 0)) # Apply Pan
            
            view = pygame.surfarray.array3d(screen); view = view.transpose([1, 0, 2])
            img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR); video_writer.write(img_bgr)

    # LAUGH TRACK
    laugh_frames = 2 * FPS 
    for f in range(laugh_frames):
        timer += 1
        cam_x += (200 - cam_x) * 0.1 # Pan back to center smoothly
        
        if loaded_bg: main_surf.blit(loaded_bg, (0, 0))
        else: main_surf.fill((160, 140, 240))
        for name, char in chars.items(): char.update(); char.draw(main_surf, False, "normal", timer, -1)
        
        screen.fill((0,0,0)); screen.blit(main_surf, (-int(cam_x), 0))
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
