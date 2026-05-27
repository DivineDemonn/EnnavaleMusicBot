# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import math
import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

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
    """Apply rounded corners to an image with anti-aliasing."""
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, image.size[0], image.size[1]), radius, fill=255)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    return result


def create_glass_effect(size, radius=30, opacity=30):
    """Create a glassmorphism effect overlay."""
    glass = Image.new("RGBA", size, (255, 255, 255, opacity))
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius, fill=255)
    result = Image.new("RGBA", size, (0, 0, 0, 0))
    result.paste(glass, (0, 0), mask)
    return result


def create_gradient(size, color1, color2, vertical=True):
    """Create a gradient image."""
    gradient = Image.new("RGBA", size, (0, 0, 0, 0))
    for i in range(size[1] if vertical else size[0]):
        ratio = i / (size[1] if vertical else size[0])
        r = int(color1[0] + (color2[0] - color1[0]) * ratio)
        g = int(color1[1] + (color2[1] - color1[1]) * ratio)
        b = int(color1[2] + (color2[2] - color1[2]) * ratio)
        a = int(color1[3] + (color2[3] - color1[3]) * ratio) if len(color1) > 3 else 255
        
        if vertical:
            draw = ImageDraw.Draw(gradient)
            draw.line((0, i, size[0], i), fill=(r, g, b, a))
        else:
            draw = ImageDraw.Draw(gradient)
            draw.line((i, 0, i, size[1]), fill=(r, g, b, a))
    return gradient


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


def draw_glowing_text(draw, position, text, font, color, glow_color=None, glow_radius=3):
    """Draw text with a glow effect."""
    if glow_color is None:
        glow_color = (*color[:3], 100)
    
    # Draw glow
    for offset_x in range(-glow_radius, glow_radius + 1):
        for offset_y in range(-glow_radius, glow_radius + 1):
            if offset_x != 0 or offset_y != 0:
                draw.text(
                    (position[0] + offset_x, position[1] + offset_y),
                    text, font=font, fill=glow_color
                )
    
    # Draw main text
    draw.text(position, text, font=font, fill=color)


class Thumbnail:
    def __init__(self):
        self.rect = (500, 500)
        self.fill = (255, 255, 255, 255)
        self.mask = Image.new("L", self.rect, 0)
        self.session: aiohttp.ClientSession | None = None
        
        # Premium fonts
        self.font_title = safe_load_font("anony/helpers/Raleway-Bold.ttf", 52)
        self.font_artist = safe_load_font("anony/helpers/Inter-Light.ttf", 24)
        self.font_time = safe_load_font("anony/helpers/Inter-Light.ttf", 15)
        self.font_pill = safe_load_font("anony/helpers/Raleway-Bold.ttf", 15)
        self.font_small = safe_load_font("anony/helpers/Inter-Light.ttf", 13)

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

            # --- 1. ENHANCED BACKGROUND ---
            canvas = Image.new("RGBA", size, (0, 0, 0, 255))
            
            # Resize and blur background
            bg_blurred = album_art.resize(size, Image.LANCZOS)
            bg_blurred = bg_blurred.filter(ImageFilter.GaussianBlur(25))
            
            # Darken the blurred background
            enhancer = ImageEnhance.Brightness(bg_blurred)
            bg_blurred = enhancer.enhance(0.4)
            
            canvas.paste(bg_blurred, (0, 0))

            # Add dark gradient overlay
            gradient_overlay = create_gradient(
                size, (0, 0, 0, 180), (0, 0, 0, 80), vertical=True
            )
            canvas = Image.alpha_composite(canvas, gradient_overlay)

            # Add subtle vignette effect
            vignette = Image.new("RGBA", size, (0, 0, 0, 0))
            vignette_draw = ImageDraw.Draw(vignette)
            for i in range(20):
                alpha = int(200 * (1 - i / 20))
                vignette_draw.rectangle(
                    (i, i, size[0] - i, size[1] - i),
                    outline=(0, 0, 0, alpha), width=2
                )
            canvas = Image.alpha_composite(canvas, vignette)

            # Shapes layer for UI elements
            shapes_layer = Image.new("RGBA", size, (0, 0, 0, 0))
            draw_shapes = ImageDraw.Draw(shapes_layer)
            draw = ImageDraw.Draw(canvas)

            # --- 2. ALBUM ART WITH 3D SHADOW EFFECT ---
            cover_size = 480
            cover_x = 70
            cover_y = (size[1] - cover_size) // 2

            cover = album_art.resize((cover_size, cover_size), Image.LANCZOS)
            
            # Apply subtle color enhancement to cover
            cover_enhancer = ImageEnhance.Contrast(cover)
            cover = cover_enhancer.enhance(1.1)
            cover_enhancer = ImageEnhance.Color(cover)
            cover = cover_enhancer.enhance(1.1)
            
            cover = apply_rounded_corners(cover, 40)

            # Multi-layer shadow for 3D effect
            for shadow_offset, shadow_alpha in [(30, 40), (20, 60), (10, 100)]:
                shadow = Image.new("RGBA", (cover_size + shadow_offset * 2, cover_size + shadow_offset * 2), (0, 0, 0, 0))
                shadow_draw = ImageDraw.Draw(shadow)
                shadow_draw.rounded_rectangle(
                    (shadow_offset, shadow_offset, cover_size + shadow_offset, cover_size + shadow_offset),
                    45, fill=(0, 0, 0, shadow_alpha)
                )
                shadow = shadow.filter(ImageFilter.GaussianBlur(shadow_offset // 2))
                canvas.alpha_composite(
                    shadow, 
                    (cover_x - shadow_offset, cover_y - shadow_offset + 5)
                )

            # Glass border effect around album art
            glass_border = create_glass_effect((cover_size, cover_size), radius=40, opacity=15)
            canvas.paste(cover, (cover_x, cover_y), cover)
            canvas.alpha_composite(glass_border, (cover_x, cover_y))

            # --- 3. RIGHT PANEL CONTENT ---
            rx = 620
            bar_w = 580
            white = (255, 255, 255, 255)
            gray_text = (180, 180, 180, 255)
            accent_color = (29, 185, 84, 255)  # Spotify green
            dark_bg = (18, 18, 18, 200)

            # Glass panel for text background
            glass_panel = create_glass_effect((bar_w + 60, 200), radius=25, opacity=20)
            canvas.alpha_composite(glass_panel, (rx - 30, 100))

            # Now Playing label with accent color
            np_text = "NOW PLAYING"
            np_width = get_text_width(draw, np_text, self.font_small)
            draw.text((rx, 115), np_text, font=self.font_small, fill=accent_color)
            
            # Animated dot indicator
            for i, alpha in enumerate([255, 180, 100]):
                dot_x = rx + np_width + 15 + i * 12
                draw.ellipse(
                    (dot_x, 120, dot_x + 6, 126),
                    fill=(*accent_color[:3], alpha)
                )

            # Title with enhanced styling
            title_text = trim_text(draw, song.title, self.font_title, bar_w - 20)
            draw_glowing_text(
                draw, (rx, 145), title_text, self.font_title, white,
                glow_color=(255, 255, 255, 50), glow_radius=2
            )

            # Artist name with icon
            artist = get_real_artist(song.title, song.channel_name)
            artist_text = trim_text(draw, artist.upper(), self.font_artist, bar_w - 40)
            
            # Verified badge
            badge_x = rx
            badge_y = 215
            draw.ellipse((badge_x, badge_y, badge_x + 16, badge_y + 16), fill=accent_color)
            draw.polygon(
                [(badge_x + 4, badge_y + 8), (badge_x + 7, badge_y + 12),
                 (badge_x + 13, badge_y + 5)],
                fill=white
            )
            
            draw.text((rx + 24, 210), artist_text, font=self.font_artist, fill=gray_text)

            # --- 4. ENHANCED PROGRESS BAR ---
            bar_y = 320
            bar_height = 6
            
            # Progress bar background with glass effect
            draw_shapes.rounded_rectangle(
                (rx, bar_y, rx + bar_w, bar_y + bar_height),
                radius=3, fill=(255, 255, 255, 40)
            )

            # Progress fill with gradient
            progress_pct = 0.32  # Simulated progress
            filled_w = int(bar_w * progress_pct)
            
            # Gradient progress fill
            for i in range(filled_w):
                ratio = i / bar_w
                r = int(accent_color[0] + (accent_color[0] - 50) * ratio)
                g = int(accent_color[1] + (accent_color[1] - 30) * ratio)
                b = int(accent_color[2] + (accent_color[2] - 20) * ratio)
                draw.line(
                    (rx + i, bar_y, rx + i, bar_y + bar_height),
                    fill=(r, g, b, 255), width=1
                )
            
            draw_shapes.rounded_rectangle(
                (rx, bar_y, rx + filled_w, bar_y + bar_height),
                radius=3, fill=accent_color
            )

            # Progress handle with glow
            handle_x = rx + filled_w
            for glow_radius in range(12, 0, -3):
                alpha = int(100 * (1 - glow_radius / 12))
                draw.ellipse(
                    (handle_x - glow_radius, bar_y + bar_height//2 - glow_radius,
                     handle_x + glow_radius, bar_y + bar_height//2 + glow_radius),
                    fill=(*accent_color[:3], alpha)
                )
            
            draw.ellipse(
                (handle_x - 8, bar_y + bar_height//2 - 8,
                 handle_x + 8, bar_y + bar_height//2 + 8),
                fill=white
            )

            # Timestamps
            draw.text((rx, bar_y + 20), "1:24", font=self.font_time, fill=gray_text)
            
            # Duration with remaining time
            duration_text = f"-{song.duration}" if song.duration else "-LIVE"
            dur_w = get_text_width(draw, duration_text, self.font_time)
            draw.text(
                (rx + bar_w - dur_w, bar_y + 20),
                duration_text,
                font=self.font_time, fill=gray_text
            )

            # --- 5. BRAND PILL WITH GLASS EFFECT ---
            pill_y = 380
            pill_text = "ENNAVALEMUSICBOT"
            pill_tw = get_text_width(draw, pill_text, self.font_pill)
            
            # Glass effect pill
            pill_width = pill_tw + 40
            pill_height = 36
            pill_x = rx + (bar_w - pill_width) // 2
            
            pill_glass = create_glass_effect((pill_width, pill_height), radius=18, opacity=40)
            canvas.alpha_composite(pill_glass, (pill_x, pill_y))
            
            # Pill border
            draw.rounded_rectangle(
                (pill_x, pill_y, pill_x + pill_width, pill_y + pill_height),
                radius=18, outline=(255, 255, 255, 60), width=2
            )
            
            # Music note icon in pill
            note_x = pill_x + 15
            draw.ellipse((note_x, pill_y + 14, note_x + 10, pill_y + 24), fill=white)
            draw.line((note_x + 10, pill_y + 14, note_x + 10, pill_y + 2), fill=white, width=3)
            draw.line((note_x + 10, pill_y + 2, note_x + 18, pill_y + 6), fill=white, width=3)
            
            draw.text(
                (pill_x + 35, pill_y + 8),
                pill_text, font=self.font_pill, fill=(255, 255, 255, 255)
            )

            # --- 6. ENHANCED PLAYBACK CONTROLS ---
            controls_y = 480
            cx = rx + (bar_w // 2)

            # Control button background glass
            for btn_x in [cx - 120, cx - 40, cx, cx + 40, cx + 120]:
                btn_glass = create_glass_effect((48, 48), radius=24, opacity=30)
                canvas.alpha_composite(btn_glass, (btn_x - 24, controls_y - 24))

            # Shuffle button
            shuffle_x = cx - 120
            shuffle_y = controls_y
            for i in range(2):
                points = [
                    (shuffle_x - 12 + i * 6, shuffle_y - 8),
                    (shuffle_x - 4 + i * 6, shuffle_y - 8),
                    (shuffle_x + 4 + i * 6, shuffle_y - 2),
                    (shuffle_x + 4 + i * 6, shuffle_y + 2),
                    (shuffle_x - 4 + i * 6, shuffle_y + 8),
                    (shuffle_x - 12 + i * 6, shuffle_y + 8)
                ]
                draw.line(points, fill=white if i == 0 else (255, 255, 255, 150), width=2)

            # Previous button
            prev_x = cx - 40
            draw.polygon(
                [(prev_x - 8, controls_y), (prev_x + 8, controls_y - 14), (prev_x + 8, controls_y + 14)],
                fill=white
            )

            # Play/Pause button with accent color
            play_x = cx
            # Outer ring
            draw.ellipse(
                (play_x - 28, controls_y - 28, play_x + 28, controls_y + 28),
                outline=accent_color, width=3
            )
            # Inner circle
            draw.ellipse(
                (play_x - 22, controls_y - 22, play_x + 22, controls_y + 22),
                fill=accent_color
            )
            # Play triangle
            draw.polygon(
                [(play_x - 6, controls_y - 10), (play_x - 6, controls_y + 10),
                 (play_x + 10, controls_y)],
                fill=white
            )

            # Next button
            next_x = cx + 40
            draw.polygon(
                [(next_x + 8, controls_y), (next_x - 8, controls_y - 14), (next_x - 8, controls_y + 14)],
                fill=white
            )

            # Repeat button
            repeat_x = cx + 120
            repeat_y = controls_y
            draw.arc(
                (repeat_x - 10, repeat_y - 10, repeat_x + 10, repeat_y + 10),
                270, 340, fill=white, width=2
            )
            draw.polygon(
                [(repeat_x + 6, repeat_y - 8), (repeat_x + 6, repeat_y - 4),
                 (repeat_x + 12, repeat_y - 6)],
                fill=white
            )
            # Repeat one indicator
            draw.text((repeat_x - 4, repeat_y - 4), "1", font=self.font_time, fill=white)

            # --- 7. VOLUME CONTROLS ---
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
            
            # Sound waves
            wave_alpha = 200
            draw.arc((sx + 16, vol_y - 8, sx + 28, vol_y + 8), 270, 90, fill=(255, 255, 255, wave_alpha), width=2)
            draw.arc((sx + 22, vol_y - 14, sx + 34, vol_y + 14), 270, 90, fill=(255, 255, 255, wave_alpha-60), width=2)

            # Volume bar background
            draw_shapes.rounded_rectangle(
                (sx + 45, vol_y - 4, sx + vol_len, vol_y + 4),
                radius=2, fill=(255, 255, 255, 40)
            )
            
            # Volume fill
            vol_fill = int(vol_len * 0.7)
            draw_shapes.rounded_rectangle(
                (sx + 45, vol_y - 4, sx + 45 + vol_fill, vol_y + 4),
                radius=2, fill=white
            )
            
            # Volume handle
            vol_handle_x = sx + 45 + vol_fill
            draw.ellipse(
                (vol_handle_x - 6, vol_y - 6, vol_handle_x + 6, vol_y + 6),
                fill=white
            )

            # --- 8. BOTTOM BAR ---
            bot_y = 630
            
            # Bottom glass bar
            bottom_glass = create_glass_effect((bar_w, 50), radius=15, opacity=25)
            canvas.alpha_composite(bottom_glass, (rx, bot_y - 25))
            
            # Lyrics button
            lyrics_x = rx + 20
            draw.text((lyrics_x, bot_y - 10), "🎵 Lyrics", font=self.font_small, fill=gray_text)
            
            # Queue button
            queue_x = rx + bar_w//2 - 30
            draw.text((queue_x, bot_y - 10), "📋 Queue", font=self.font_small, fill=gray_text)
            
            # Like button
            like_x = rx + bar_w - 100
            heart_text = "🤍"
            draw.text((like_x, bot_y - 10), heart_text, font=self.font_small, fill=gray_text)
            
            # Save/Download button
            save_x = rx + bar_w - 50
            draw.text((save_x, bot_y - 10), "💾", font=self.font_small, fill=gray_text)

            # --- 9. QUALITY BADGE ---
            quality_badge = create_glass_effect((50, 24), radius=12, opacity=30)
            canvas.alpha_composite(quality_badge, (1180, 30))
            draw.text((1192, 33), "HD", font=self.font_small, fill=white)
            
            # Logo watermark
            logo_text = "🎵 Music"
            logo_w = get_text_width(draw, logo_text, self.font_small)
            draw.text(
                (rx + bar_w - logo_w, 45),
                logo_text, font=self.font_small, fill=(255, 255, 255, 100)
            )

            # --- 10. FINAL TOUCHES ---
            # Add subtle grain texture
            for _ in range(200):
                x = int(0)
                y = int(0)
                import random
                x = random.randint(0, size[0]-1)
                y = random.randint(0, size[1]-1)
                alpha = random.randint(0, 3)
                draw.point((x, y), fill=(255, 255, 255, alpha))
            
            # Composite all layers
            canvas = Image.alpha_composite(canvas, shapes_layer)

            # --- 11. SAVE ---
            canvas.save(output, quality=100, optimize=True)
            album_art.close()
            canvas.close()

            try:
                os.remove(temp)
            except Exception:
                pass

            return output

        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            import traceback
            traceback.print_exc()
            return config.DEFAULT_THUMB
