#!/usr/bin/env python3
# refactored code

from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
from astral import LocationInfo, Observer
from astral.sun import sun
from PIL import Image, ImageSequence
from zoneinfo import ZoneInfo
import datetime
import time
import os
import sys


city = LocationInfo("Vancouver", "Canada", "America/Vancouver", 49.2827, -123.1207)

options = RGBMatrixOptions()
options.rows = 32
options.cols = 64
options.chain_length = 1
options.parallel = 1
options.hardware_mapping = "adafruit-hat-pwm"
options.brightness = 30

TARGET_FPS = 60

CLOUDY = True
CLOUD_DRIFT_RANGE = 5
CLOUD_DRIFT_SPEED = 0.25

DAY_SKY = (135, 206, 235)
HORIZON_ORANGE = (255, 165, 79)
NIGHT_SKY = (25, 25, 60)
NIGHT_BOTTOM = (70, 130, 180)


# Initialize hardware and canvas
matrix = RGBMatrix(options=options)
canvas = matrix.CreateFrameCanvas()

font = graphics.Font()
font.LoadFont("/home/dezel/6x10.bdf")

# Load images
def load_image(path):
    return Image.open(path).convert("RGBA") if os.path.exists(path) else None

def load_gif(path, target_height):
    frames = []
    if not os.path.exists(path):
        return frames
    gif = Image.open(path)
    for frame in ImageSequence.Iterator(gif):
        f = frame.convert("RGBA")
        scale = target_height / f.height
        f = f.resize((max(1, int(f.width * scale)), target_height))
        frames.append(f.copy())
    return frames

sun_img = load_image("/home/dezel/led_images/sun_resized.png")
moon_img = load_image("/home/dezel/led_images/moon_resized.png")
trees_img = load_image("/home/dezel/led_images/trees_led.png")
rocks_img = load_image("/home/dezel/led_images/rocks_led.png")
clouds_img = load_image("/home/dezel/led_images/clouds2.png")

hooh_frames = load_gif("/home/dezel/led_images/ho-oh_short.gif", 15)
lugia_frames = load_gif("/home/dezel/led_images/lugia_short.gif", 15)
trainer_frames = load_gif("/home/dezel/led_images/red_pika_flipped.gif", 14)
ray_frames = load_gif("/home/dezel/led_images/ray_led.gif", 32)
haunter_frames = load_gif("/home/dezel/led_images/haunter.gif", 24)


# helper functions for drawing
def interpolate_color(c1, c2, f):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * f) for i in range(3))

def draw_sky_gradient(canvas, factor_day):
    for y in range(canvas.height):
        v = y / max(1, canvas.height - 1)

        if 0.0 < factor_day < 1.0:
            top = interpolate_color(NIGHT_SKY, DAY_SKY, factor_day)
            bottom = interpolate_color(NIGHT_BOTTOM, HORIZON_ORANGE, factor_day)
            color = interpolate_color(top, bottom, v)
        elif factor_day >= 1.0:
            color = interpolate_color(DAY_SKY, HORIZON_ORANGE, v)
        else:
            color = interpolate_color(NIGHT_SKY, NIGHT_BOTTOM, v)

        for x in range(canvas.width):
            canvas.SetPixel(x, y, *color)

def draw_image(canvas, img, x=0, y=0):
    if not img:
        return
    px = img.load()
    for iy in range(img.height):
        for ix in range(img.width):
            r, g, b, a = px[ix, iy]
            if a > 10:
                canvas.SetPixel(x + ix, y + iy, r, g, b)

def draw_time_text(canvas, text):
    outline = graphics.Color(40, 40, 40)
    main = graphics.Color(255, 255, 255)

    x = (canvas.width - len(text) * 6) // 2
    y = canvas.height // 2 + font.height // 2

    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            graphics.DrawText(canvas, font, x + dx, y + dy, outline, text)

    graphics.DrawText(canvas, font, x, y, main, text)

def calculate_vertical_position(img_h, canvas_h, progress):
    progress = max(0.0, min(1.0, progress))
    return int((canvas_h - img_h) * (1 - progress))


# Animation system
class Animation:
    def __init__(self, frames, duration, fps):
        self.frames = frames
        self.duration = duration
        self.fps = fps
        self.start_time = None
        self.active = False

    def start(self):
        if self.frames:
            self.start_time = time.time()
            self.active = True

    def reset(self):
        self.start_time = None
        self.active = False

    def update_and_draw(self, canvas):
        if not self.active or self.start_time is None:
            return False

        elapsed = time.time() - self.start_time
        if elapsed >= self.duration:
            self.reset()
            return False

        self.draw(canvas, elapsed)
        return True

    def draw(self, canvas, elapsed):
        pass

class HorizontalAnimation(Animation):
    def __init__(self, frames, y, direction, duration, fps):
        super().__init__(frames, duration, fps)
        self.y = y
        self.direction = direction
        self.w = frames[0].width if frames else 0

    def draw(self, canvas, elapsed):
        p = elapsed / self.duration
        if self.direction == "left":
            x = int(canvas.width - p * (canvas.width + self.w))
        else:
            x = int(-self.w + p * (canvas.width + self.w))

        idx = int(elapsed * self.fps) % len(self.frames)
        draw_image(canvas, self.frames[idx], x, self.y)

class HaunterAnimation(Animation):
    def __init__(self, frames):
        super().__init__(frames, 7.0, 8)
        self.w = frames[0].width if frames else 0
        self.h = frames[0].height if frames else 0

    def draw(self, canvas, elapsed):
        if elapsed < 2:
            x = int(canvas.width - (elapsed / 2) * self.w)
        elif elapsed < 5:
            x = canvas.width - self.w
        else:
            x = int(canvas.width - self.w + ((elapsed - 5) / 2) * self.w)

        idx = int(elapsed * self.fps) % len(self.frames)
        y = (canvas.height - self.h) // 2
        draw_image(canvas, self.frames[idx], x, y)

class AnimationChain:
    def __init__(self, animations):
        self.animations = animations
        self.index = 0

    def reset(self):
        for a in self.animations:
            a.reset()
        self.index = 0

    def update_and_draw(self, canvas):
        if self.index >= len(self.animations):
            return False

        anim = self.animations[self.index]
        if not anim.active:
            anim.start()

        if not anim.update_and_draw(canvas):
            self.index += 1

        return True



def main():
    global canvas

    tz = ZoneInfo(city.timezone)
    observer = Observer(city.latitude, city.longitude)

    day_chain = AnimationChain([
        HorizontalAnimation(frames = hooh_frames, y=1, direction="left", duration=5, fps=6),
        HorizontalAnimation(frames = lugia_frames, y=17, direction="left", duration=5, fps=6),
        HorizontalAnimation(frames = trainer_frames, y=18, direction="right", duration=7, fps=6),
        HorizontalAnimation(frames = ray_frames, y=0, direction="left", duration=7, fps=6),
    ])

    haunter = HaunterAnimation(haunter_frames)

    cloud_offset = 0
    cloud_dir = 1
    prev_minute = None

    FRAME_TIME = 1 / TARGET_FPS

    while True:
        start = time.time()
        now = datetime.datetime.now(tz)

        s = sun(observer, date=now.date(), tzinfo=tz)
        sunrise = s["sunrise"]
        sunset = s["sunset"]

        if sunrise <= now <= sunrise + datetime.timedelta(minutes=30):
            sun_progress = (now - sunrise).total_seconds() / 1800
        elif sunrise + datetime.timedelta(minutes=30) < now < sunset:
            sun_progress = 1.0
        elif sunset <= now <= sunset + datetime.timedelta(minutes=30):
            sun_progress = 1.0 - (now - sunset).total_seconds() / 1800
        else:
            sun_progress = 0.0

        canvas.Clear()
        draw_sky_gradient(canvas, sun_progress)

        if sun_progress > 0 and sun_img:
            y = calculate_vertical_position(sun_img.height, canvas.height, sun_progress)
            x = (canvas.width - sun_img.width) // 2
            draw_image(canvas, sun_img, x, y)

        if sun_progress > 0:
            draw_image(canvas, trees_img)
        else:
            draw_image(canvas, rocks_img)

        if CLOUDY and sun_progress > 0 and clouds_img:
            draw_image(canvas, clouds_img, int(cloud_offset), 0)

        draw_time_text(canvas, now.strftime("%H:%M"))

        if prev_minute != now.minute:
            prev_minute = now.minute
            day_chain.reset()

        if sun_progress > 0:
            day_chain.update_and_draw(canvas)
        else:
            if not haunter.active:
                haunter.start()
            haunter.update_and_draw(canvas)

        canvas = matrix.SwapOnVSync(canvas)

        if CLOUDY and sun_progress > 0:
            cloud_offset += CLOUD_DRIFT_SPEED * cloud_dir
            if abs(cloud_offset) >= CLOUD_DRIFT_RANGE:
                cloud_dir *= -1

        sleep = FRAME_TIME - (time.time() - start)
        if sleep > 0:
            time.sleep(sleep)

if __name__ == "__main__":
    main()
