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

    async def generate(self, song: Track, size=(1080, 1920)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)
            album_art = Image.open(temp).convert("RGBA")

            # ----- 1. BACKGROUND: blurred album art with dark red gradient -----
            canvas = Image.new("RGBA", size, (0, 0, 0, 255))
            bg = album_art.resize(size, Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(55))
            canvas.paste(bg, (0, 0))

            # Dark overlay
            overlay = Image.new("RGBA", size, (0, 0, 0, 180))
            canvas = Image.alpha_composite(canvas, overlay)

            # Red gradient overlay (diagonal from top‑left to bottom‑right)
            gradient = Image.new("RGBA", size, (0, 0, 0, 0))
            draw_grad = ImageDraw.Draw(gradient)
            for y in range(size[1]):
                alpha = int(120 * (y / size[1]))   # increases toward bottom
                draw_grad.line([(0, y), (size[0], y)], fill=(180, 20, 20, alpha))
            canvas = Image.alpha_composite(canvas, gradient)

            # Vignette (dark edges)
            vignette = Image.new("RGBA", size, (0, 0, 0, 0))
            draw_vig = ImageDraw.Draw(vignette)
            center = (size[0] // 2, size[1] // 2)
            radius = max(size) // 2
            for r in range(radius, 0, -1):
                alpha = int(40 * (1 - r / radius))
                draw_vig.ellipse(
                    (center[0] - r, center[1] - r, center[0] + r, center[1] + r),
                    outline=(0, 0, 0, alpha),
                    width=2
                )
            canvas = Image.alpha_composite(canvas, vignette)

            # ----- 2. GLASS CARD -----
            card_w, card_h = 940, 560
            card_x, card_y = 70, 540
            corner_radius = 60

            # Card shadow
            shadow = Image.new("RGBA", (card_w + 40, card_h + 40), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (20, 20, card_w + 20, card_h + 20),
                corner_radius + 10,
                fill=(0, 0, 0, 160)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(25))
            canvas.alpha_composite(shadow, (card_x - 20, card_y - 20))

            # Card background (glass)
            card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
            draw_card = ImageDraw.Draw(card)
            draw_card.rounded_rectangle(
                (0, 0, card_w, card_h),
                corner_radius,
                fill=(255, 255, 255, 30)   # 12% white
            )

            # Subtle border
            draw_card.rounded_rectangle(
                (2, 2, card_w - 2, card_h - 2),
                corner_radius - 2,
                outline=(255, 255, 255, 50),
                width=2
            )

            # Paste card onto canvas
            canvas.alpha_composite(card, (card_x, card_y))

            # Now draw inside the card using absolute coordinates
            draw = ImageDraw.Draw(canvas)
            # Base coordinates relative to card
            pad = 40
            left = card_x + pad
            right = card_x + card_w - pad
            top = card_y + pad
            bottom = card_y + card_h - pad

            # ----- 3. TOP ROW: album art + "EnnavaleMusicBot" + "Dolby Atmos" -----
            # Small album art
            small_cover_size = 120
            small_cover = album_art.resize((small_cover_size, small_cover_size), Image.LANCZOS)
            small_cover = apply_rounded_corners(small_cover, 20)
            canvas.paste(small_cover, (left, top), small_cover)

            # App name (left of the album art)
            app_name = "🎵 EnnavaleMusicBot"
            app_font = safe_load_font("anony/helpers/Raleway-Bold.ttf", 28)
            app_color = (255, 255, 255, 255)
            draw.text((left + small_cover_size + 15, top + 10), app_name, font=app_font, fill=app_color)

            # Dolby Atmos badge (right-aligned)
            atmos_text = "Dolby Atmos"
            atmos_font = safe_load_font("anony/helpers/Inter-Light.ttf", 20)
            atmos_color = (200, 200, 200, 255)
            atmos_w = get_text_width(draw, atmos_text, atmos_font)
            atmos_x = right - atmos_w
            draw.text((atmos_x, top + 15), atmos_text, font=atmos_font, fill=atmos_color)

            # ----- 4. SONG TITLE & ARTIST -----
            title_y = top + small_cover_size + 35
            title_font = safe_load_font("anony/helpers/Raleway-Bold.ttf", 46)
            title_color = (255, 255, 255, 255)
            max_title_w = right - left
            title_text = trim_text(draw, song.title, title_font, max_title_w)
            draw.text((left, title_y), title_text, font=title_font, fill=title_color)

            artist_y = title_y + 60
            artist_font = safe_load_font("anony/helpers/Inter-Light.ttf", 28)
            artist_color = (200, 200, 200, 255)
            artist_name = get_real_artist(song.title, song.channel_name).upper()
            artist_text = trim_text(draw, artist_name, artist_font, max_title_w)
            draw.text((left, artist_y), artist_text, font=artist_font, fill=artist_color)

            # ----- 5. PROGRESS BAR -----
            bar_y = artist_y + 80
            bar_w = right - left
            bar_h = 6

            # Background track
            draw.rounded_rectangle(
                (left, bar_y, left + bar_w, bar_y + bar_h),
                radius=3,
                fill=(255, 255, 255, 60)
            )

            # Filled progress (example: 30%)
            # You can compute progress from song.duration if you have current position
            progress_ratio = 0.30  # placeholder
            filled_w = int(bar_w * progress_ratio)
            draw.rounded_rectangle(
                (left, bar_y, left + filled_w, bar_y + bar_h),
                radius=3,
                fill=(255, 255, 255, 255)
            )

            # Knob
            knob_r = 12
            knob_x = left + filled_w
            knob_y = bar_y + bar_h // 2
            draw.ellipse(
                (knob_x - knob_r, knob_y - knob_r, knob_x + knob_r, knob_y + knob_r),
                fill=(255, 255, 255, 255),
                outline=(255, 255, 255, 200),
                width=2
            )

            # Timestamps
            time_y = bar_y + 25
            time_font = safe_load_font("anony/helpers/Inter-Light.ttf", 18)
            time_color = (200, 200, 200, 255)

            # Current time (example "0:58")
            current_time = "0:58"
            draw.text((left, time_y), current_time, font=time_font, fill=time_color)

            # Duration (right-aligned)
            duration = song.duration or "LIVE"
            dur_text = f"-{duration}" if duration != "LIVE" else "LIVE"
            dur_w = get_text_width(draw, dur_text, time_font)
            draw.text((right - dur_w, time_y), dur_text, font=time_font, fill=time_color)

            # ----- 6. PLAYBACK CONTROLS -----
            controls_y = time_y + 60
            controls_padding = 30
            total_controls_width = right - left - 2 * controls_padding
            control_icons = ["⇄", "⏮", "⏸", "⏭", "↻"]
            icon_count = len(control_icons)
            spacing = total_controls_width // (icon_count - 1)
            icon_font = safe_load_font("anony/helpers/Raleway-Bold.ttf", 32)
            icon_color = (255, 255, 255, 220)

            for i, icon in enumerate(control_icons):
                x = left + controls_padding + i * spacing
                # center text horizontally
                icon_w = get_text_width(draw, icon, icon_font)
                draw.text((x - icon_w // 2, controls_y), icon, font=icon_font, fill=icon_color)

            # ----- 7. SAVE -----
            canvas.save(output, quality=100)
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
