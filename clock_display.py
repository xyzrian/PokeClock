#!/usr/bin/env python3

from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from astral import LocationInfo, Observer
from astral.sun import sun
from PIL import Image, ImageSequence
from zoneinfo import ZoneInfo
import datetime
import time
import os
import sys

# CONFIGURATION

city = LocationInfo("Vancouver", "Canada", "America/Vancouver", 49.2827, -123.1207)

options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = 'adafruit-hat-pwm'
options.brightness = 30

CLOUDY = True
CLOUD_DRIFT_RANGE = 5
CLOUD_DRIFT_SPEED = 0.25
TARGET_FPS = 60

DAY_SKY = (135, 206, 235)
HORIZON_ORANGE = (255, 165, 79)
NIGHT_SKY = (25, 25, 60)
NIGHT_BOTTOM = (70, 130, 180)

# HARDWARE INITIALIZATION

matrix = RGBMatrix(options=options)
canvas = matrix.CreateFrameCanvas()

font = graphics.Font()
font_path = "/home/dezel/6x10.bdf"
if not os.path.exists(font_path):
    raise FileNotFoundError(f"Font not found at {font_path}")
font.LoadFont(font_path)

# IMAGE LOADING

def load_image_if_exists(path, mode="RGBA"):
    if os.path.exists(path):
        return Image.open(path).convert(mode)
    return None

sun_img = load_image_if_exists("/home/dezel/led_images/sun_resized.png")
moon_img = load_image_if_exists("/home/dezel/led_images/moon_resized.png")
trees_img = load_image_if_exists("/home/dezel/led_images/trees_led.png")
rocks_img = load_image_if_exists("/home/dezel/led_images/rocks_led.png")
clouds_img = load_image_if_exists("/home/dezel/led_images/clouds2.png")

def load_gif_frames(path, target_height):
    frames = []
    if os.path.exists(path):
        try:
            gif = Image.open(path)
            for frame in ImageSequence.Iterator(gif):
                f = frame.convert("RGBA")
                if f.height != target_height:
                    scale = target_height / f.height
                    new_w = max(1, int(f.width * scale))
                    f = f.resize((new_w, target_height), Image.Resampling.LANCZOS)
                frames.append(f.copy())
        except Exception as e:
            print(f"Error loading {path}: {e}")
    return frames

hooh_frames = load_gif_frames("/home/dezel/led_images/ho-oh_short.gif", target_height=15)
lugia_frames = load_gif_frames("/home/dezel/led_images/lugia_short.gif", target_height=15)
trainer_frames = load_gif_frames("/home/dezel/led_images/red_pika_flipped.gif", target_height=14)
ray_frames = load_gif_frames("/home/dezel/led_images/ray_led.gif", target_height=32)
haunter_frames = load_gif_frames("/home/dezel/led_images/haunter.gif", target_height=24)

# RENDERING FUNCTIONS

def interpolate_color(c1, c2, factor):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * factor) for i in range(3))

def draw_sky_gradient(canvas, factor_day=1.0):
    height = canvas.height
    width = canvas.width
    
    row_colors = []
    for y in range(height):
        vertical_factor = y / max(1, height - 1)
        
        if 0.0 < factor_day < 1.0:
            top_color = interpolate_color(NIGHT_SKY, DAY_SKY, factor_day)
            bottom_color = interpolate_color(NIGHT_BOTTOM, HORIZON_ORANGE, factor_day)
            color = interpolate_color(top_color, bottom_color, vertical_factor)
        elif factor_day >= 1.0:
            color = interpolate_color(DAY_SKY, HORIZON_ORANGE, vertical_factor)
        else:
            color = interpolate_color(NIGHT_SKY, NIGHT_BOTTOM, vertical_factor)
        
        row_colors.append(color)
    
    for y in range(height):
        color = row_colors[y]
        for x in range(width):
            canvas.SetPixel(x, y, *color)

def draw_image_on_canvas(canvas, image, x_offset=0, y_offset=0):
    if image is None:
        return
    
    width, height = image.size
    has_alpha = image.mode == "RGBA"
    pixels = image.load()
    
    x_start = max(0, -x_offset)
    x_end = min(width, canvas.width - x_offset)
    y_start = max(0, -y_offset)
    y_end = min(height, canvas.height - y_offset)
    
    for y in range(y_start, y_end):
        canvas_y = y + y_offset
        for x in range(x_start, x_end):
            if has_alpha:
                r, g, b, a = pixels[x, y]
                if a < 10:
                    continue
            else:
                r, g, b = pixels[x, y]
            canvas_x = x + x_offset
            canvas.SetPixel(canvas_x, canvas_y, r, g, b)

def calculate_vertical_position(image_height, canvas_height, progress):
    if image_height is None:
        return 0
    progress = max(0.0, min(1.0, progress))
    start_top = canvas_height - image_height
    end_top = 0
    return int(start_top + (end_top - start_top) * progress)

def draw_time_text(canvas, font, time_str):
    outline_color = graphics.Color(40, 40, 40)
    main_color = graphics.Color(255, 255, 255)
    
    text_x = (canvas.width - len(time_str) * 6) // 2
    text_y = (canvas.height // 2) + (font.height // 2) - 1
    
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            graphics.DrawText(canvas, font, text_x + dx, text_y + dy, outline_color, time_str)
    
    graphics.DrawText(canvas, font, text_x, text_y, main_color, time_str)

# ANIMATION CLASSES

class HorizontalAnimation:
    def __init__(self, frames, direction='left', duration=5.0, fps=6, y_offset=0):
        self.frames = frames
        self.direction = direction
        self.duration = duration
        self.fps = fps
        self.y_offset = y_offset
        self.start_time = None
        self.active = False
        
        self.width = frames[0].width if frames else 0
        self.height = frames[0].height if frames else 0
    
    def start(self):
        if self.frames:
            self.start_time = time.time()
            self.active = True
    
    def update_and_draw(self, canvas):
        if not self.active or self.start_time is None or not self.frames:
            return False
        
        elapsed = time.time() - self.start_time
        
        if elapsed > self.duration:
            self.active = False
            return False
        
        progress = elapsed / self.duration
        
        if self.direction == 'left':
            start_x = canvas.width
            end_x = -self.width
        else:
            start_x = -self.width
            end_x = canvas.width
        
        x_pos = int(start_x + (end_x - start_x) * progress)
        
        frame_idx = int(elapsed * self.fps) % len(self.frames)
        
        y_pos = self.y_offset
        
        draw_image_on_canvas(canvas, self.frames[frame_idx], x_offset=x_pos, y_offset=y_pos)
        return True

class HaunterAnimation:
    def __init__(self, frames, slide_duration=2.0, hold_duration=3.0, fps=8):
        self.frames = frames
        self.slide_duration = slide_duration
        self.hold_duration = hold_duration
        self.total_duration = slide_duration * 2 + hold_duration
        self.fps = fps
        self.start_time = None
        self.active = False
        
        self.width = frames[0].width if frames else 0
        self.height = frames[0].height if frames else 0
    
    def start(self):
        if self.frames:
            self.start_time = time.time()
            self.active = True
    
    def update_and_draw(self, canvas):
        if not self.active or self.start_time is None or not self.frames:
            return False
        
        elapsed = time.time() - self.start_time
        
        if elapsed > self.total_duration:
            self.active = False
            return False
        
        if elapsed < self.slide_duration:
            progress = elapsed / self.slide_duration
            start_x = canvas.width
            end_x = canvas.width - self.width
            x_pos = int(start_x + (end_x - start_x) * progress)
        elif elapsed < self.slide_duration + self.hold_duration:
            x_pos = canvas.width - self.width
        else:
            slide_out_elapsed = elapsed - self.slide_duration - self.hold_duration
            progress = slide_out_elapsed / self.slide_duration
            start_x = canvas.width - self.width
            end_x = canvas.width
            x_pos = int(start_x + (end_x - start_x) * progress)
        
        frame_idx = int(elapsed * self.fps) % len(self.frames)
        y_pos = (canvas.height - self.height) // 2
        
        draw_image_on_canvas(canvas, self.frames[frame_idx], x_offset=x_pos, y_offset=y_pos)
        return True

# MAIN LOOP

def main():
    global canvas
    
    tz = ZoneInfo(city.timezone)
    observer = Observer(latitude=city.latitude, longitude=city.longitude)
    
    prev_minute = None
    hooh_anim = HorizontalAnimation(hooh_frames, direction='left', duration=5.0, fps=6, y_offset=1)
    lugia_anim = HorizontalAnimation(lugia_frames, direction='left', duration=5.0, fps=6, y_offset=17)
    trainer_anim = HorizontalAnimation(trainer_frames, direction='right', duration=7.0, fps=6, y_offset=18)
    ray_anim = HorizontalAnimation(ray_frames, direction='left', duration=7.0, fps=6, y_offset=0)
    haunter_anim = HaunterAnimation(haunter_frames, slide_duration=2.0, hold_duration=3.0, fps=8)
    
    hooh_anim.start()
    
    cloud_offset = 0
    cloud_drift_direction = 1
    FRAME_TIME = 1.0 / TARGET_FPS
    
    while True:
        frame_start = time.time()
        now = datetime.datetime.now(tz)
        
        try:
            s_today = sun(observer, date=now.date(), tzinfo=tz)
            sunrise_today = s_today['sunrise']
            sunset_today = s_today['sunset']
            
            yesterday = (now - datetime.timedelta(days=1)).date()
            tomorrow = (now + datetime.timedelta(days=1)).date()
            s_yesterday = sun(observer, date=yesterday, tzinfo=tz)
            s_tomorrow = sun(observer, date=tomorrow, tzinfo=tz)
            sunset_yesterday = s_yesterday['sunset']
            sunrise_tomorrow = s_tomorrow['sunrise']
            
        except Exception:
            sunrise_today = now.replace(hour=6, minute=0, second=0, microsecond=0)
            sunset_today = now.replace(hour=18, minute=0, second=0, microsecond=0)
            yesterday = now - datetime.timedelta(days=1)
            tomorrow = now + datetime.timedelta(days=1)
            sunset_yesterday = yesterday.replace(hour=18, minute=0, second=0, microsecond=0)
            sunrise_tomorrow = tomorrow.replace(hour=6, minute=0, second=0, microsecond=0)
        
        sunrise_transition_end = sunrise_today + datetime.timedelta(minutes=30)
        sunset_transition_end = sunset_today + datetime.timedelta(minutes=30)
        
        if now < sunrise_today:
            moon_rise_start = sunset_yesterday + datetime.timedelta(minutes=30)
            moon_rise_end = sunset_yesterday + datetime.timedelta(minutes=60)
            moon_set_start = sunrise_today - datetime.timedelta(minutes=30)
            moon_set_end = sunrise_today
        else:
            moon_rise_start = sunset_today + datetime.timedelta(minutes=30)
            moon_rise_end = sunset_today + datetime.timedelta(minutes=60)
            moon_set_start = sunrise_tomorrow - datetime.timedelta(minutes=30)
            moon_set_end = sunrise_tomorrow
        
        if sunrise_today <= now <= sunrise_transition_end:
            sun_progress = (now - sunrise_today).total_seconds() / 1800.0
        elif sunrise_transition_end < now < sunset_today:
            sun_progress = 1.0
        elif sunset_today <= now <= sunset_transition_end:
            sun_progress = 1.0 - (now - sunset_today).total_seconds() / 1800.0
        else:
            sun_progress = 0.0
        
        if moon_rise_start <= now <= moon_rise_end:
            moon_progress = (now - moon_rise_start).total_seconds() / 1800.0
        elif moon_rise_end < now < moon_set_start:
            moon_progress = 1.0
        elif moon_set_start <= now <= moon_set_end:
            moon_progress = 1.0 - (now - moon_set_start).total_seconds() / 1800.0
        else:
            moon_progress = 0.0
        
        canvas.Clear()
        
        draw_sky_gradient(canvas, factor_day=sun_progress)
        
        if sun_progress > 0.0 and sun_img:
            sun_y = calculate_vertical_position(sun_img.height, canvas.height, sun_progress)
            sun_x = (canvas.width - sun_img.width) // 2
            draw_image_on_canvas(canvas, sun_img, x_offset=sun_x, y_offset=sun_y)
        
        if moon_progress > 0.0 and moon_img:
            moon_y = calculate_vertical_position(moon_img.height, canvas.height, moon_progress)
            moon_x = (canvas.width - moon_img.width) // 2
            draw_image_on_canvas(canvas, moon_img, x_offset=moon_x, y_offset=moon_y)
        
        if sun_progress > 0.0:
            draw_image_on_canvas(canvas, trees_img)
        else:
            draw_image_on_canvas(canvas, rocks_img)
        
        if CLOUDY and clouds_img and sun_progress > 0.0:
            draw_image_on_canvas(canvas, clouds_img, x_offset=int(cloud_offset))
        
        time_str = now.strftime("%H:%M")
        draw_time_text(canvas, font, time_str)
        
        current_minute = now.minute
        if prev_minute is None:
            prev_minute = current_minute
        elif current_minute != prev_minute:
            prev_minute = current_minute
            if not hooh_anim.active:
                hooh_anim.start()
                lugia_anim.start_time = None
                trainer_anim.start_time = None
                ray_anim.start_time = None
                haunter_anim.start_time = None
        
        hooh_active = hooh_anim.update_and_draw(canvas)
        
        if not hooh_active and not lugia_anim.active and lugia_anim.start_time is None:
            if hooh_anim.start_time is not None:
                lugia_anim.start()
        
        lugia_active = lugia_anim.update_and_draw(canvas)
        
        if not lugia_active and not trainer_anim.active and trainer_anim.start_time is None:
            if lugia_anim.start_time is not None:
                trainer_anim.start()
        
        trainer_active = trainer_anim.update_and_draw(canvas)
        
        if not trainer_active and not ray_anim.active and ray_anim.start_time is None:
            if trainer_anim.start_time is not None:
                ray_anim.start()
        
        ray_anim.update_and_draw(canvas)
        
        if moon_progress > 0.0:
            if not haunter_anim.active and haunter_anim.start_time is None:
                haunter_anim.start()
            haunter_anim.update_and_draw(canvas)
            
        canvas = matrix.SwapOnVSync(canvas)  
        
        if CLOUDY and clouds_img and sun_progress > 0.0:
            cloud_offset += CLOUD_DRIFT_SPEED * cloud_drift_direction
            
            if cloud_offset >= CLOUD_DRIFT_RANGE:
                cloud_drift_direction = -1
            elif cloud_offset <= -CLOUD_DRIFT_RANGE:
                cloud_drift_direction = 1
        
        frame_end = time.time()
        frame_duration = frame_end - frame_start
        sleep_time = max(0, FRAME_TIME - frame_duration)
        if sleep_time > 0:
            time.sleep(sleep_time)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
