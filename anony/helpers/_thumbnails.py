# thumbnail.py
# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# Clean Apple Music‑style player card with bot name pill.

import os
import re
import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from anony import config
from anony.helpers import Track


# ---------- Helper functions ----------

def get_text_width(draw, text, font):
    """Safely get text width across different PIL versions."""
    try:
        return draw.textlength(text, font=font)
    except AttributeError:
        pass
    try:
        return font.getlength(text)
    except AttributeError:
        pass
    try:
        return font.getsize(text)[0]
    except AttributeError:
        pass
    try:
        return draw.textbbox((0, 0), text, font=font)[2]
    except Exception:
        return len(text) * 15


def trim_text(draw, text, font, max_width):
    """Trim text to fit within max_width, adding ellipsis if needed."""
    if get_text_width(draw, text, font) <= max_width:
        return text
    while get_text_width(draw, text + "…", font) > max_width and len(text) > 0:
        text = text[:-1]
    return text + "…"


def apply_rounded_corners(image, radius):
    """Apply rounded corners to an image."""
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, image.size[0], image.size[1]), radius, fill=255)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    return result


def get_real_artist(title, channel_name):
    """Extract real artist name from title when channel is a label."""
    c_name = re.sub(r"(?i)\s*-\s*topic", "", channel_name)
    c_name = re.sub(r"(?i)\s*official.*", "", c_name)
    c_name = re.sub(r"(?i)\s*vevo", "", c_name)
    c_name = c_name.strip()

    lower_channel = c_name.lower()
    labels = ['music', 'records', 'entertainment', 'series', 'studio',
              'company', 'audio', 'video', 'network', 't-series', 'lahari', 'aditya']
    is_label = any(word in lower_channel for word in labels)

    if is_label:
        for sep in ['|', '-']:
            if sep in title:
                parts = [p.strip() for p in title.split(sep)]
                if len(parts) >= 3:
                    return parts[2]
                elif len(parts) >= 2:
                    return parts[1]
    return c_name


def safe_load_font(font_path, size):
    """Safely load a font with fallbacks."""
    fonts_to_try = [
        font_path,
        "anony/helpers/Raleway-Bold.ttf",
        "anony/helpers/Inter-Light.ttf",
        "arial.ttf",
        "DejaVuSans.ttf",
        "FreeSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    for font in fonts_to_try:
        try:
            return ImageFont.truetype(font, size)
        except Exception:
            pass
    return ImageFont.load_default()


def format_time(seconds):
    """Convert seconds to MM:SS or H:MM:SS if needed."""
    if seconds < 0:
        seconds = 0
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def parse_duration(duration_str):
    """Convert '4:01' or '1:02:03' to total seconds."""
    if not duration_str:
        return 0
    parts = duration_str.split(':')
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    elif len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return 0


# ---------- Main Thumbnail class ----------

class Thumbnail:
    """
    Generates a music player card with album art, title, artist,
    progress bar, and a bot name pill.
    """

    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

        # Load fonts (fallback to default if missing)
        self.font_title = safe_load_font("anony/helpers/Raleway-Bold.ttf", 46)
        self.font_artist = safe_load_font("anony/helpers/Inter-Light.ttf", 26)
        self.font_time = safe_load_font("anony/helpers/Inter-Light.ttf", 18)
        self.font_pill = safe_load_font("anony/helpers/Raleway-Bold.ttf", 16)

    async def start(self) -> None:
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    async def _download_thumb(self, url: str, path: str) -> str:
        async with self.session.get(url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(await resp.read())
        return path

    async def generate(
        self,
        song: Track,
        progress: float = 0.25,
        position: int | None = None,
        size=(1280, 720)
    ) -> str:
        """
        Generate the thumbnail image.
        :param song: Track with attributes: id, thumbnail, title, channel_name, duration
        :param progress: float 0..1 (used if position is None)
        :param position: current playback position in seconds (if given, overrides progress)
        :param size: (width, height)
        :return: path to generated PNG
        """
        if self.session is None:
            await self.start()

        temp_path = f"cache/temp_{song.id}.jpg"
        output_path = f"cache/{song.id}.png"

        if os.path.exists(output_path):
            return output_path

        try:
            # Download album art
            await self._download_thumb(song.thumbnail, temp_path)
            album_art = Image.open(temp_path).convert("RGBA")

            # ----- 1. Background -----
            canvas = Image.new("RGBA", size, (0, 0, 0, 255))
            bg_blurred = album_art.resize(size, Image.LANCZOS)
            bg_blurred = bg_blurred.filter(ImageFilter.GaussianBlur(40))
            canvas.paste(bg_blurred, (0, 0))

            # Dark gradient overlay (top to bottom)
            gradient = Image.new("RGBA", size, (0, 0, 0, 0))
            grad_draw = ImageDraw.Draw(gradient)
            for y in range(size[1]):
                alpha = int(140 - 100 * (y / size[1]))
                grad_draw.line([(0, y), (size[0], y)], fill=(0, 0, 0, alpha))
            canvas = Image.alpha_composite(canvas, gradient)

            draw = ImageDraw.Draw(canvas)

            # ----- 2. Album Art (left) -----
            cover_size = 500
            cover_x = 80
            cover_y = 110

            cover = album_art.resize((cover_size, cover_size), Image.LANCZOS)
            cover = apply_rounded_corners(cover, 35)

            # Shadow
            shadow = Image.new("RGBA", (cover_size + 40, cover_size + 40), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (20, 20, cover_size + 20, cover_size + 20), 40, fill=(0, 0, 0, 180)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(25))
            canvas.alpha_composite(shadow, (cover_x - 20, cover_y - 20))
            canvas.paste(cover, (cover_x, cover_y), cover)

            # ----- 3. Text (right side) -----
            rx = 640
            bar_w = 560
            white = (255, 255, 255, 255)
            gray = (200, 200, 200, 255)

            # Title
            title_text = trim_text(draw, song.title, self.font_title, 430)
            draw.text((rx, 140), title_text, font=self.font_title, fill=white)

            # Artist (channel name)
            artist = get_real_artist(song.title, song.channel_name).upper()
            artist_text = trim_text(draw, artist, self.font_artist, bar_w)
            draw.text((rx, 210), artist_text, font=self.font_artist, fill=gray)

            # ----- 4. Progress Bar & Bot Name Pill -----
            bar_y = 290
            time_y = 320

            # Compute current time
            total_sec = parse_duration(song.duration)
            if position is not None:
                current_sec = max(0, min(position, total_sec))
            else:
                current_sec = progress * total_sec if total_sec else 0

            current_str = format_time(current_sec)
            remaining_str = f"-{format_time(total_sec - current_sec)}" if total_sec else "-LIVE"

            # Empty track background
            draw.rounded_rectangle(
                (rx, bar_y, rx + bar_w, bar_y + 8), radius=4,
                fill=(255, 255, 255, 70)
            )

            # Filled progress
            filled_w = int(bar_w * (current_sec / total_sec if total_sec else 0))
            if filled_w > 0:
                draw.rounded_rectangle(
                    (rx, bar_y, rx + filled_w, bar_y + 8), radius=4,
                    fill=white
                )
                # Circular handle
                handle_x = rx + filled_w
                draw.ellipse(
                    (handle_x - 8, bar_y - 4, handle_x + 8, bar_y + 12),
                    fill=white
                )

            # Timestamps
            draw.text((rx, time_y), current_str, font=self.font_time, fill=white)
            rem_w = get_text_width(draw, remaining_str, self.font_time)
            draw.text((rx + bar_w - rem_w, time_y), remaining_str,
                      font=self.font_time, fill=white)

            # Pill with bot name
            pill_text = "EnnavaleMusicBot"
            pill_tw = get_text_width(draw, pill_text, self.font_pill)
            pill_cx = rx + (bar_w // 2)
            # Background pill
            draw.rounded_rectangle(
                (pill_cx - pill_tw // 2 - 16, time_y - 4,
                 pill_cx + pill_tw // 2 + 16, time_y + 26),
                radius=15, fill=(255, 255, 255, 120)
            )
            # Text
            draw.text(
                (pill_cx - pill_tw // 2, time_y + 2),
                pill_text, font=self.font_pill, fill=(0, 0, 0, 255)
            )

            # ----- 5. Save -----
            canvas.save(output_path, quality=100)
            album_art.close()
            canvas.close()

            try:
                os.remove(temp_path)
            except Exception:
                pass

            return output_path

        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            return config.DEFAULT_THUMB
