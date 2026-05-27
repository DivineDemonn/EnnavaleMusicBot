# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import os
import re
import aiohttp
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)

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


class Thumbnail:
    def __init__(self):
        self.rect = (500, 500)
        self.fill = (255, 255, 255, 255)
        self.mask = Image.new("L", self.rect, 0)
        self.session: aiohttp.ClientSession | None = None
        
        # Modern design fonts
        self.font_title = safe_load_font("anony/helpers/Raleway-Bold.ttf", 46)
        self.font_artist = safe_load_font("anony/helpers/Inter-Light.ttf", 26)
        self.font_time = safe_load_font("anony/helpers/Inter-Light.ttf", 16)
        self.font_pill = safe_load_font("anony/helpers/Raleway-Bold.ttf", 16)

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

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)
            
            # Open thumbnail as album art
            album_art = Image.open(temp).convert("RGBA")

            # --- 1. BLURRED BACKGROUND ---
            canvas = Image.new("RGBA", size, (0, 0, 0, 255))
            bg_blurred = album_art.resize(size, Image.LANCZOS)
            bg_blurred = bg_blurred.filter(ImageFilter.GaussianBlur(15))
            canvas.paste(bg_blurred, (0, 0))

            # Dark overlay for contrast
            overlay = Image.new("RGBA", size, (0, 0, 0, 80))
            canvas = Image.alpha_composite(canvas, overlay)

            # Shapes layer for translucent elements
            shapes_layer = Image.new("RGBA", size, (0, 0, 0, 0))
            draw_shapes = ImageDraw.Draw(shapes_layer)
            draw = ImageDraw.Draw(canvas)

            # --- 2. LEFT PANEL: ALBUM ART ---
            cover_size = 500
            cover_x = 80
            cover_y = 110

            cover = album_art.resize((cover_size, cover_size), Image.LANCZOS)
            cover = apply_rounded_corners(cover, 35)

            # Shadow behind cover
            shadow = Image.new("RGBA", (cover_size + 40, cover_size + 40), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (20, 20, cover_size + 20, cover_size + 20), 40, fill=(0, 0, 0, 120)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(20))
            canvas.alpha_composite(shadow, (cover_x - 20, cover_y - 20))
            canvas.paste(cover, (cover_x, cover_y), cover)

            # --- 3. RIGHT PANEL: CONTENT ---
            rx = 640
            bar_w = 560
            white = (255, 255, 255, 255)
            gray_text = (200, 200, 200, 255)
            black = (0, 0, 0, 255)

            # Title
            title_text = trim_text(draw, song.title, self.font_title, 430)
            draw.text((rx, 140), title_text, font=self.font_title, fill=white)

            # Top Right Buttons (Star & Dots)
            circ_y = 145
            circ_size = 40
            draw_shapes.ellipse(
                (1090, circ_y, 1090 + circ_size, circ_y + circ_size),
                fill=(255, 255, 255, 70)
            )
            draw_shapes.ellipse(
                (1140, circ_y, 1140 + circ_size, circ_y + circ_size),
                fill=(255, 255, 255, 70)
            )

            # Star icon
            draw.polygon(
                [(1110, 155), (1113, 161), (1120, 162), (1115, 166),
                 (1117, 173), (1110, 169), (1103, 173), (1105, 166),
                 (1100, 162), (1107, 161)],
                outline=white, width=2
            )
            # Three dots
            draw.ellipse((1158, 155, 1162, 159), fill=white)
            draw.ellipse((1158, 163, 1162, 167), fill=white)
            draw.ellipse((1158, 171, 1162, 175), fill=white)

            # Artist name
            artist = get_real_artist(song.title, song.channel_name).upper()
            artist_text = trim_text(draw, artist, self.font_artist, bar_w)
            draw.text((rx, 205), artist_text, font=self.font_artist, fill=gray_text)

            # --- 4. PROGRESS BAR & BRAND PILL ---
            bar_y = 300

            # Empty track background
            draw_shapes.rounded_rectangle(
                (rx, bar_y, rx + bar_w, bar_y + 8), radius=4,
                fill=(255, 255, 255, 70)
            )

            # Brand pill
            pill_text = "ANONX"
            pill_tw = get_text_width(draw, pill_text, self.font_pill)
            pill_cx = rx + (bar_w // 2)
            time_y = 325

            draw_shapes.rounded_rectangle(
                (pill_cx - pill_tw // 2 - 16, time_y - 4,
                 pill_cx + pill_tw // 2 + 16, time_y + 26),
                radius=15, fill=(255, 255, 255, 120)
            )

            # Composite shapes layer
            canvas = Image.alpha_composite(canvas, shapes_layer)
            draw = ImageDraw.Draw(canvas)

            # Filled progress (25%)
            filled_w = int(bar_w * 0.25)
            draw.rounded_rectangle(
                (rx, bar_y, rx + filled_w, bar_y + 8), radius=4, fill=white
            )

            # Circular handle
            draw.ellipse(
                (rx + filled_w - 8, bar_y - 4, rx + filled_w + 8, bar_y + 12),
                fill=white
            )

            # Timestamps
            draw.text((rx, time_y), "0:01", font=self.font_time, fill=white)
            dur_w = get_text_width(draw, song.duration or "LIVE", self.font_time)
            draw.text(
                (rx + bar_w - dur_w, time_y),
                f"-{song.duration}" if song.duration else "-LIVE",
                font=self.font_time, fill=white
            )

            # Pill text
            draw.text(
                (pill_cx - pill_tw // 2, time_y + 2),
                pill_text, font=self.font_pill, fill=black
            )

            # --- 5. PLAYBACK CONTROLS ---
            cy = 480
            cx = rx + (bar_w // 2)

            # Pause button
            p_w = 10
            p_h = 44
            p_space = 8
            draw.rounded_rectangle(
                (cx - p_space - p_w, cy - p_h // 2, cx - p_space, cy + p_h // 2),
                radius=3, fill=white
            )
            draw.rounded_rectangle(
                (cx + p_space, cy - p_h // 2, cx + p_space + p_w, cy + p_h // 2),
                radius=3, fill=white
            )

            # Previous button
            px = cx - 130
            tri_h = 22
            draw.polygon(
                [(px - 2, cy), (px + 22, cy - tri_h), (px + 22, cy + tri_h)],
                fill=white
            )
            draw.polygon(
                [(px - 26, cy), (px - 2, cy - tri_h), (px - 2, cy + tri_h)],
                fill=white
            )
            draw.rectangle((px - 32, cy - tri_h, px - 28, cy + tri_h), fill=white)

            # Next button
            nx = cx + 130
            draw.polygon(
                [(nx + 2, cy - tri_h), (nx + 2, cy + tri_h), (nx + 26, cy)],
                fill=white
            )
            draw.polygon(
                [(nx - 22, cy - tri_h), (nx - 22, cy + tri_h), (nx + 2, cy)],
                fill=white
            )
            draw.rectangle((nx + 28, cy - tri_h, nx + 32, cy + tri_h), fill=white)

            # --- 6. VOLUME BAR ---
            vol_y = 560
            vol_len = 400
            vol_x_start = cx - (vol_len // 2)

            # Speaker icon
            sx = vol_x_start
            draw.polygon(
                [(sx, vol_y - 5), (sx + 6, vol_y - 5),
                 (sx + 14, vol_y - 12), (sx + 14, vol_y + 12),
                 (sx + 6, vol_y + 5), (sx, vol_y + 5)],
                fill=white
            )
            draw.arc(
                (sx + 16, vol_y - 6, sx + 26, vol_y + 6),
                270, 90, fill=white, width=2
            )
            draw.arc(
                (sx + 20, vol_y - 12, sx + 34, vol_y + 12),
                270, 90, fill=white, width=2
            )

            # Volume bar
            draw.rounded_rectangle(
                (sx + 45, vol_y - 3, sx + vol_len, vol_y + 3),
                radius=3, fill=white
            )

            # --- 7. BOTTOM UI ---
            bot_y = 620
            cx_chat = cx - 40
            draw.rounded_rectangle(
                (cx_chat, bot_y - 14, cx_chat + 32, bot_y + 10),
                radius=5, outline=white, width=3
            )
            draw.polygon(
                [(cx_chat + 10, bot_y + 10), (cx_chat + 16, bot_y + 10),
                 (cx_chat + 10, bot_y + 18)],
                fill=white
            )
            draw.rectangle((cx_chat + 8, bot_y - 5, cx_chat + 11, bot_y + 2), fill=white)
            draw.rectangle((cx_chat + 14, bot_y - 5, cx_chat + 17, bot_y + 2), fill=white)

            # Queue icon
            lx = cx + 40
            ly = bot_y - 12
            for i in range(3):
                y_off = ly + i * 10
                draw.ellipse((lx, y_off, lx + 4, y_off + 4), fill=white)
                draw.rectangle((lx + 10, y_off + 1, lx + 36, y_off + 3), fill=white)

            # --- 8. SAVE ---
            image = canvas
            image.save(output, quality=100)
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
