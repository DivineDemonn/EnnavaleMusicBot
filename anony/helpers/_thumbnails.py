# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import aiohttp
import asyncio
from PIL import (
    Image, ImageDraw, ImageEnhance,
    ImageFilter, ImageFont, ImageOps
)

from anony import config
from anony.helpers import Track


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


def create_glassmorphism(size, radius=20, opacity=40):
    """Create a glassmorphic overlay rectangle."""
    glass = Image.new("RGBA", size, (255, 255, 255, opacity))
    glass = apply_rounded_corners(glass, radius)
    return glass


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
        "anony/helpers/Inter-Medium.ttf",
        "anony/helpers/SF-Pro-Display-Bold.otf",
        "arial.ttf",
        "DejaVuSans.ttf",
        "FreeSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
    ]
    for font in fonts_to_try:
        try:
            return ImageFont.truetype(font, size)
        except Exception:
            pass
    return ImageFont.load_default()


class Thumbnail:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
        
        # Premium typography
        self.font_title = safe_load_font("anony/helpers/Raleway-Bold.ttf", 44)
        self.font_artist = safe_load_font("anony/helpers/Inter-Light.ttf", 28)
        self.font_time = safe_load_font("anony/helpers/Inter-Light.ttf", 18)
        self.font_pill = safe_load_font("anony/helpers/Raleway-Bold.ttf", 17)
        self.font_button = safe_load_font("anony/helpers/Inter-Medium.ttf", 24)

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with self.session.get(url) as resp:
            with open(output_path, "wb") as f:
                f.write(await resp.read())
        return output_path

    def draw_player_controls(self, draw, center_x, y, controls_color):
        """Draw modern music player controls."""
        # Previous button
        prev_x = center_x - 140
        # Left arrow
        draw.polygon(
            [(prev_x + 24, y - 20), (prev_x, y), (prev_x + 24, y + 20)],
            fill=controls_color
        )
        draw.rectangle((prev_x - 8, y - 20, prev_x - 2, y + 20), fill=controls_color)

        # Play/Pause button (showing pause state)
        bar_w = 8
        bar_h = 36
        gap = 12
        draw.rounded_rectangle(
            (center_x - gap - bar_w, y - bar_h // 2, center_x - gap, y + bar_h // 2),
            radius=3, fill=controls_color
        )
        draw.rounded_rectangle(
            (center_x + gap, y - bar_h // 2, center_x + gap + bar_w, y + bar_h // 2),
            radius=3, fill=controls_color
        )

        # Next button
        next_x = center_x + 140
        draw.polygon(
            [(next_x - 16, y - 20), (next_x + 8, y), (next_x - 16, y + 20)],
            fill=controls_color
        )
        draw.rectangle((next_x + 12, y - 20, next_x + 18, y + 20), fill=controls_color)

    def draw_volume_control(self, draw, center_x, y, controls_color):
        """Draw volume slider with speaker icon."""
        vol_width = 320
        vol_start = center_x - vol_width // 2 + 40

        # Speaker icon
        sp_x = vol_start - 30
        draw.polygon(
            [(sp_x, y - 8), (sp_x + 8, y - 8),
             (sp_x + 18, y - 16), (sp_x + 18, y + 16),
             (sp_x + 8, y + 8), (sp_x, y + 8)],
            fill=controls_color
        )
        # Sound waves
        draw.arc(
            (sp_x + 20, y - 10, sp_x + 32, y + 10),
            280, 80, fill=controls_color, width=2
        )
        draw.arc(
            (sp_x + 25, y - 16, sp_x + 41, y + 16),
            280, 80, fill=controls_color, width=2
        )

        # Volume bar background
        draw.rounded_rectangle(
            (vol_start, y - 2, vol_start + vol_width - 30, y + 2),
            radius=2, fill=(255, 255, 255, 40)
        )
        # Volume level (60% filled)
        filled_vol = int((vol_width - 30) * 0.6)
        draw.rounded_rectangle(
            (vol_start, y - 2, vol_start + filled_vol, y + 2),
            radius=2, fill=controls_color
        )
        # Volume handle
        draw.ellipse(
            (vol_start + filled_vol - 6, y - 8, vol_start + filled_vol + 6, y + 8),
            fill=controls_color
        )

    def draw_bottom_controls(self, draw, center_x, y, controls_color):
        """Draw bottom UI elements (lyrics and queue)."""
        # Lyrics icon
        lyrics_x = center_x - 50
        draw.rounded_rectangle(
            (lyrics_x - 4, y - 14, lyrics_x + 28, y + 10),
            radius=6, outline=controls_color, width=2
        )
        # Text lines inside lyrics icon
        draw.rectangle((lyrics_x + 4, y - 8, lyrics_x + 6, y), fill=controls_color)
        draw.rectangle((lyrics_x + 10, y - 8, lyrics_x + 12, y), fill=controls_color)
        draw.rectangle((lyrics_x + 16, y - 8, lyrics_x + 18, y), fill=controls_color)
        # Arrow
        draw.polygon(
            [(lyrics_x + 10, y + 10), (lyrics_x + 16, y + 10), (lyrics_x + 13, y + 18)],
            fill=controls_color
        )

        # Queue icon
        queue_x = center_x + 30
        for i in range(3):
            y_pos = y - 10 + i * 12
            draw.ellipse((queue_x, y_pos, queue_x + 4, y_pos + 4), fill=controls_color)
            draw.rectangle(
                (queue_x + 10, y_pos + 1, queue_x + 36, y_pos + 3),
                fill=controls_color
            )

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)
            
            # Load album art
            album_art = Image.open(temp).convert("RGBA")

            # --- 1. PREMIUM BACKGROUND ---
            canvas = Image.new("RGBA", size, (0, 0, 0, 255))
            
            # Create deeply blurred background
            bg_blurred = album_art.resize(size, Image.LANCZOS)
            bg_blurred = bg_blurred.filter(ImageFilter.GaussianBlur(30))
            
            # Enhance colors for cinematic feel
            enhancer = ImageEnhance.Brightness(bg_blurred)
            bg_blurred = enhancer.enhance(0.7)
            enhancer = ImageEnhance.Color(bg_blurred)
            bg_blurred = enhancer.enhance(1.2)
            
            canvas.paste(bg_blurred, (0, 0))

            # Add subtle gradient overlay for depth
            gradient = Image.new("RGBA", size, (0, 0, 0, 0))
            grad_draw = ImageDraw.Draw(gradient)
            for i in range(size[1]):
                opacity = int(80 * (i / size[1]))
                grad_draw.line([(0, i), (size[0], i)], fill=(0, 0, 0, opacity))
            canvas = Image.alpha_composite(canvas, gradient)

            # --- 2. LEFT PANEL: ALBUM ART WITH SHADOW ---
            cover_size = 500
            cover_x = 80
            cover_y = 110

            # Create shadow
            shadow = Image.new("RGBA", (cover_size + 60, cover_size + 60), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (30, 30, cover_size + 30, cover_size + 30),
                45, fill=(0, 0, 0, 120)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(25))
            canvas.alpha_composite(shadow, (cover_x - 30, cover_y - 30))

            # Album art with rounded corners
            cover = album_art.resize((cover_size, cover_size), Image.LANCZOS)
            cover = apply_rounded_corners(cover, 35)
            
            # Subtle inner shadow effect
            inner_shadow = Image.new("RGBA", (cover_size, cover_size), (0, 0, 0, 0))
            inner_draw = ImageDraw.Draw(inner_shadow)
            inner_draw.rounded_rectangle(
                (0, 0, cover_size, cover_size), 35,
                outline=(0, 0, 0, 30), width=2
            )
            cover = Image.alpha_composite(cover, inner_shadow)
            
            canvas.paste(cover, (cover_x, cover_y), cover)

            # --- 3. RIGHT CONTENT AREA ---
            right_x = 640
            content_width = 560
            center_x = right_x + content_width // 2
            
            draw = ImageDraw.Draw(canvas)
            white = (255, 255, 255, 255)
            light_gray = (220, 220, 220, 255)
            dim_gray = (180, 180, 180, 255)

            # Glassmorphism panel behind text
            glass_panel = create_glassmorphism(
                (content_width + 40, 280), radius=20, opacity=15
            )
            canvas.alpha_composite(glass_panel, (right_x - 20, 100))

            # Song Title
            title_text = trim_text(draw, song.title, self.font_title, content_width - 40)
            draw.text((right_x, 140), title_text, font=self.font_title, fill=white)

            # Artist name
            artist = get_real_artist(song.title, song.channel_name).upper()
            artist_text = trim_text(draw, artist, self.font_artist, content_width - 40)
            draw.text((right_x, 200), artist_text, font=self.font_artist, fill=light_gray)

            # --- 4. PROGRESS BAR WITH BRAND PILL ---
            bar_y = 290
            bar_width = content_width
            bar_height = 6
            
            # Progress bar background
            draw.rounded_rectangle(
                (right_x, bar_y, right_x + bar_width, bar_y + bar_height),
                radius=3, fill=(255, 255, 255, 50)
            )
            
            # Progress filled (30%)
            progress_width = int(bar_width * 0.3)
            draw.rounded_rectangle(
                (right_x, bar_y, right_x + progress_width, bar_y + bar_height),
                radius=3, fill=white
            )
            
            # Progress handle
            handle_radius = 7
            draw.ellipse(
                (right_x + progress_width - handle_radius, bar_y - handle_radius + bar_height//2,
                 right_x + progress_width + handle_radius, bar_y + handle_radius + bar_height//2),
                fill=white
            )

            # Time labels
            time_y = bar_y + 20
            draw.text((right_x, time_y), "1:23", font=self.font_time, fill=dim_gray)
            duration = song.duration or "LIVE"
            dur_width = get_text_width(draw, duration, self.font_time)
            draw.text(
                (right_x + bar_width - dur_width, time_y),
                duration, font=self.font_time, fill=dim_gray
            )

            # Brand pill in center
            pill_text = "ENNAVALEMUSICBOT"
            pill_width = get_text_width(draw, pill_text, self.font_pill)
            pill_padding = 16
            pill_rect = (
                center_x - pill_width // 2 - pill_padding,
                time_y - 6,
                center_x + pill_width // 2 + pill_padding,
                time_y + 28
            )
            draw.rounded_rectangle(pill_rect, radius=14, fill=(255, 255, 255, 150))
            draw.text(
                (center_x - pill_width // 2, time_y + 2),
                pill_text, font=self.font_pill, fill=(0, 0, 0, 255)
            )

            # --- 5. PLAYER CONTROLS ---
            controls_y = 420
            self.draw_player_controls(draw, center_x, controls_y, white)

            # --- 6. VOLUME CONTROL ---
            volume_y = 510
            self.draw_volume_control(draw, center_x, volume_y, white)

            # --- 7. BOTTOM CONTROLS ---
            bottom_y = 600
            self.draw_bottom_controls(draw, center_x, bottom_y, white)

            # --- 8. TOP RIGHT DECORATIVE ELEMENTS ---
            # Favorite button
            fav_x = 1090
            fav_y = 150
            draw.rounded_rectangle(
                (fav_x, fav_y, fav_x + 40, fav_y + 40),
                radius=20, fill=(255, 255, 255, 60)
            )
            # Star shape
            star_cx = fav_x + 20
            star_cy = fav_y + 20
            draw.polygon(
                [(star_cx, star_cy - 8), (star_cx + 2, star_cy - 2),
                 (star_cx + 8, star_cy - 1), (star_cx + 3, star_cy + 2),
                 (star_cx + 5, star_cy + 8), (star_cx, star_cy + 4),
                 (star_cx - 5, star_cy + 8), (star_cx - 3, star_cy + 2),
                 (star_cx - 8, star_cy - 1), (star_cx - 2, star_cy - 2)],
                fill=white
            )

            # Menu button
            menu_x = 1145
            draw.rounded_rectangle(
                (menu_x, fav_y, menu_x + 40, fav_y + 40),
                radius=20, fill=(255, 255, 255, 60)
            )
            for i in range(3):
                dot_y = fav_y + 15 + i * 5
                draw.ellipse((menu_x + 18, dot_y, menu_x + 22, dot_y + 4), fill=white)

            # --- 9. SAVE FINAL IMAGE ---
            canvas.save(output, quality=100, optimize=True)
            
            # Cleanup
            album_art.close()
            canvas.close()
            try:
                os.remove(temp)
            except Exception:
                pass

            return output

        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            return config.DEFAULT_THUMB
