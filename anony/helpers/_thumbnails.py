# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import math
import random
import textwrap
import aiohttp
from PIL import (
    Image, ImageDraw, ImageEnhance,
    ImageFilter, ImageFont, ImageOps, ImageChops
)

from anony import config
from anony.helpers import Track


class Thumbnail:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None
        
        # Premium Canvas Settings
        self.CANVAS_SIZE = (1280, 720)
        self.BORDER_RADIUS = 28
        
        # Premium Color Palette
        self.COLORS = {
            # Dynamic gradient colors
            "gradient_primary": (29, 185, 84),      # Spotify Green
            "gradient_secondary": (30, 215, 96),    # Light Green
            "gradient_accent": (20, 160, 70),       # Dark Green
            
            # Dark theme colors
            "bg_primary": (18, 18, 18),
            "bg_secondary": (24, 24, 24),
            "bg_card": (30, 30, 30),
            "bg_card_hover": (40, 40, 40),
            
            # Text colors
            "text_primary": (255, 255, 255),
            "text_secondary": (179, 179, 179),
            "text_tertiary": (115, 115, 115),
            
            # Accent colors
            "accent_green": (30, 215, 96),
            "accent_blue": (29, 185, 235),
            "accent_purple": (175, 40, 230),
            "accent_pink": (255, 80, 140),
            "accent_orange": (255, 165, 0),
            
            # UI elements
            "progress_bar_bg": (83, 83, 83),
            "progress_bar_fill": (255, 255, 255),
            "button_active": (255, 255, 255),
            "button_inactive": (179, 179, 179),
            "heart_active": (30, 215, 96),
            "heart_inactive": (255, 255, 255),
            
            # Effects
            "shadow": (0, 0, 0, 80),
            "glow_green": (30, 215, 96, 100),
            "overlay": (0, 0, 0, 40),
        }
        
        # Layout Coordinates
        self._setup_layout()
        
    def _setup_layout(self):
        """Setup all layout coordinates"""
        # Main card
        self.CARD_WIDTH = 1080
        self.CARD_HEIGHT = 520
        self.CARD_X = (self.CANVAS_SIZE[0] - self.CARD_WIDTH) // 2
        self.CARD_Y = (self.CANVAS_SIZE[1] - self.CARD_HEIGHT) // 2
        
        # Album Art
        self.ALBUM_SIZE = 320
        self.ALBUM_X = self.CARD_X + 45
        self.ALBUM_Y = self.CARD_Y + (self.CARD_HEIGHT - self.ALBUM_SIZE) // 2
        
        # Text Section
        self.TEXT_X = self.ALBUM_X + self.ALBUM_SIZE + 50
        self.TEXT_Y = self.ALBUM_Y + 30
        self.TEXT_MAX_WIDTH = 28
        
        # Music Info
        self.TITLE_Y = self.TEXT_Y
        self.ARTIST_Y = self.TITLE_Y + 110
        self.ALBUM_Y = self.ARTIST_Y + 55
        
        # Progress Bar
        self.PROGRESS_Y = self.ALBUM_Y + 70
        self.PROGRESS_WIDTH = 560
        self.PROGRESS_HEIGHT = 4
        self.PROGRESS_X = self.TEXT_X
        
        # Time Labels
        self.TIME_Y = self.PROGRESS_Y - 28
        
        # Controls
        self.CONTROLS_Y = self.PROGRESS_Y + 55
        
        # Footer
        self.FOOTER_Y = self.CARD_Y + self.CARD_HEIGHT - 45

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

    def _create_gradient_background(self, size, color1, color2, angle=135):
        """Create premium gradient background"""
        base = Image.new('RGB', size, color1)
        overlay = Image.new('RGB', size, color2)
        
        # Create gradient mask
        mask = Image.new('L', size)
        draw = ImageDraw.Draw(mask)
        
        rad = math.radians(angle)
        x0, y0 = 0, 0
        x1 = int(size[0] * abs(math.cos(rad)))
        y1 = int(size[1] * abs(math.sin(rad)))
        
        for i in range(size[0] + size[1]):
            alpha = int(255 * (i / (size[0] + size[1])))
            x = int(i * math.cos(rad))
            y = int(i * math.sin(rad))
            draw.line([(x - 100, y - 100), (x + 100, y + 100)], fill=alpha, width=200)
        
        return Image.composite(overlay, base, mask)

    def _create_noise_texture(self, size, opacity=10):
        """Add subtle noise texture for premium feel"""
        noise = Image.new('RGBA', size, (0, 0, 0, 0))
        pixels = noise.load()
        
        for i in range(size[0]):
            for j in range(size[1]):
                if random.random() < 0.1:
                    alpha = random.randint(0, opacity)
                    pixels[i, j] = (255, 255, 255, alpha)
        
        return noise

    def _create_rounded_rectangle_mask(self, size, radius):
        """Create rounded rectangle mask"""
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([0, 0, size[0]-1, size[1]-1], radius, fill=255)
        return mask

    def _draw_glow_effect(self, draw, x, y, radius, color, intensity=30):
        """Draw premium glow effect"""
        for i in range(intensity, 0, -1):
            alpha = int(100 * (i / intensity))
            glow_color = (*color[:3], alpha)
            draw.ellipse(
                [x - radius - i, y - radius - i, x + radius + i, y + radius + i],
                fill=glow_color
            )

    def _draw_progress_bar(self, draw, x, y, width, height, progress=0.55):
        """Draw premium progress bar with dot"""
        # Background
        draw.rounded_rectangle(
            [x, y, x + width, y + height],
            radius=height//2,
            fill=self.COLORS["progress_bar_bg"]
        )
        
        # Progress fill
        fill_width = int(width * progress)
        if fill_width > 0:
            # Gradient fill
            for i in range(fill_width):
                ratio = i / width
                r = int(255 * (1 - ratio * 0.2))
                g = int(255 * (1 - ratio * 0.2))
                b = int(255 * (1 - ratio * 0.2))
                
                draw.rectangle(
                    [x + i, y, x + i + 1, y + height],
                    fill=(r, g, b)
                )
            
            # Rounded end
            draw.ellipse(
                [x + fill_width - height//2, y - height//2,
                 x + fill_width + height//2, y + height + height//2],
                fill=self.COLORS["button_active"]
            )
        
        # Progress dot (knob)
        knob_x = x + fill_width
        knob_y = y + height // 2
        knob_size = 12
        
        # Outer glow
        self._draw_glow_effect(draw, knob_x, knob_y, knob_size, (255, 255, 255), 15)
        
        # Knob
        draw.ellipse(
            [knob_x - knob_size//2, knob_y - knob_size//2,
             knob_x + knob_size//2, knob_y + knob_size//2],
            fill=self.COLORS["button_active"]
        )

    def _draw_music_waveform(self, draw, x, y, width, height, bars=40):
        """Draw animated-looking waveform visualization"""
        bar_width = width // bars
        gap = 2
        
        for i in range(bars):
            bar_height = random.randint(height//4, height)
            bar_x = x + (i * bar_width)
            bar_y = y + (height - bar_height) // 2
            
            # Gradient bar
            for j in range(bar_height):
                ratio = j / bar_height
                color = (
                    int(30 + (255-30) * (1-ratio)),
                    int(185 + (255-185) * (1-ratio)),
                    int(84 + (255-84) * (1-ratio))
                )
                draw.rectangle(
                    [bar_x, bar_y + j, bar_x + bar_width - gap, bar_y + j + 1],
                    fill=color
                )

    def _draw_control_button(self, draw, x, y, symbol, size=24, active=True):
        """Draw premium control button"""
        color = self.COLORS["button_active"] if active else self.COLORS["button_inactive"]
        
        # Button background with hover effect
        if symbol in ["▶", "⏸"]:
            # Main play/pause button
            circle_size = size * 2.5
            draw.ellipse(
                [x - circle_size//2, y - circle_size//2,
                 x + circle_size//2, y + circle_size//2],
                fill=(255, 255, 255) if active else (60, 60, 60)
            )
            
            if symbol == "▶":
                # Play triangle
                triangle_points = [
                    (x - size//3, y - size//2),
                    (x - size//3, y + size//2),
                    (x + size//2, y)
                ]
                draw.polygon(triangle_points, fill=(0, 0, 0) if active else (40, 40, 40))
            else:
                # Pause bars
                bar_width = size // 3
                draw.rectangle([x - size//4, y - size//2, x - size//4 + bar_width, y + size//2],
                             fill=(0, 0, 0))
                draw.rectangle([x + size//4 - bar_width, y - size//2, x + size//4, y + size//2],
                             fill=(0, 0, 0))
        else:
            # Secondary buttons
            try:
                button_font = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", size)
            except:
                button_font = ImageFont.load_default()
            
            # Draw symbol
            bbox = draw.textbbox((0, 0), symbol, font=button_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            draw.text(
                (x - text_width//2, y - text_height//2 - 2),
                symbol,
                font=button_font,
                fill=color
            )

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        """Generate premium Spotify-style thumbnail"""
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            
            if os.path.exists(output):
                return output

            # Download thumbnail
            await self.save_thumb(temp, song.thumbnail)
            
            # Create dark premium background
            canvas = self._create_gradient_background(
                self.CANVAS_SIZE,
                self.COLORS["bg_primary"],
                self.COLORS["bg_secondary"],
                angle=145
            )
            
            # Add subtle noise texture
            noise = self._create_noise_texture(self.CANVAS_SIZE, opacity=8)
            canvas.paste(noise, (0, 0), noise)
            
            draw = ImageDraw.Draw(canvas)
            
            # Load premium fonts
            try:
                title_font = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 44)
                artist_font = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 26)
                album_font = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 20)
                time_font = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 14)
                button_font = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 24)
                small_font = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 16)
            except:
                title_font = ImageFont.load_default()
                artist_font = ImageFont.load_default()
                album_font = ImageFont.load_default()
                time_font = ImageFont.load_default()
                button_font = ImageFont.load_default()
                small_font = ImageFont.load_default()
            
            # Create main card with shadow
            card_shadow = Image.new('RGBA', (self.CARD_WIDTH + 40, self.CARD_HEIGHT + 40), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(card_shadow)
            shadow_draw.rounded_rectangle(
                [20, 20, self.CARD_WIDTH + 20, self.CARD_HEIGHT + 20],
                radius=self.BORDER_RADIUS,
                fill=self.COLORS["shadow"]
            )
            card_shadow = card_shadow.filter(ImageFilter.GaussianBlur(30))
            canvas.paste(card_shadow, (self.CARD_X - 20, self.CARD_Y - 20), card_shadow)
            
            # Create card
            card = Image.new('RGBA', (self.CARD_WIDTH, self.CARD_HEIGHT), (0, 0, 0, 0))
            card_draw = ImageDraw.Draw(card)
            
            # Card gradient
            for y in range(self.CARD_HEIGHT):
                ratio = y / self.CARD_HEIGHT
                r = int(30 + (35 - 30) * ratio)
                g = int(30 + (35 - 30) * ratio)
                b = int(30 + (40 - 30) * ratio)
                
                card_draw.rectangle(
                    [0, y, self.CARD_WIDTH, y + 1],
                    fill=(r, g, b)
                )
            
            # Card border glow
            card_draw.rounded_rectangle(
                [1, 1, self.CARD_WIDTH-1, self.CARD_HEIGHT-1],
                radius=self.BORDER_RADIUS,
                outline=(60, 60, 60, 100),
                width=1
            )
            
            canvas.paste(card, (self.CARD_X, self.CARD_Y), card)
            
            # Process album art with premium effects
            thumb = Image.open(temp).convert("RGBA")
            
            # Create rounded album art
            album_mask = self._create_rounded_rectangle_mask(
                (self.ALBUM_SIZE, self.ALBUM_SIZE),
                radius=20
            )
            
            # Resize and enhance album art
            album_art = thumb.resize((self.ALBUM_SIZE, self.ALBUM_SIZE), Image.LANCZOS)
            
            # Add subtle shadow to album
            album_shadow = Image.new('RGBA', (self.ALBUM_SIZE + 30, self.ALBUM_SIZE + 30), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(album_shadow)
            shadow_draw.rounded_rectangle(
                [15, 15, self.ALBUM_SIZE + 15, self.ALBUM_SIZE + 15],
                radius=20,
                fill=(0, 0, 0, 120)
            )
            album_shadow = album_shadow.filter(ImageFilter.GaussianBlur(15))
            canvas.paste(album_shadow, (self.ALBUM_X - 15, self.ALBUM_Y - 15), album_shadow)
            
            # Paste album art
            canvas.paste(album_art, (self.ALBUM_X, self.ALBUM_Y), album_mask)
            
            # Add subtle overlay gradient on album
            overlay = Image.new('RGBA', (self.ALBUM_SIZE, self.ALBUM_SIZE), (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            for y in range(self.ALBUM_SIZE):
                alpha = int(30 * (y / self.ALBUM_SIZE))
                overlay_draw.rectangle([0, y, self.ALBUM_SIZE, y+1], fill=(0, 0, 0, alpha))
            
            canvas.paste(overlay, (self.ALBUM_X, self.ALBUM_Y), album_mask)
            
            # Draw music info text
            current_y = self.TITLE_Y
            
            # Title with gradient effect
            title = song.title[:50] if song.title else "Unknown Track"
            title_lines = textwrap.wrap(title, width=self.TEXT_MAX_WIDTH)
            
            for i, line in enumerate(title_lines[:2]):
                if line:
                    # Text shadow
                    draw.text(
                        (self.TEXT_X + 2, current_y + 2),
                        line,
                        font=title_font,
                        fill=(0, 0, 0, 100)
                    )
                    
                    # Main text
                    draw.text(
                        (self.TEXT_X, current_y),
                        line,
                        font=title_font,
                        fill=self.COLORS["text_primary"]
                    )
                    
                    current_y += 52
            
            # Artist name
            artist = song.channel_name[:40] if song.channel_name else "Unknown Artist"
            artist_text = textwrap.wrap(artist, width=30)[0]
            
            draw.text(
                (self.TEXT_X, self.ARTIST_Y),
                artist_text,
                font=artist_font,
                fill=self.COLORS["text_secondary"]
            )
            
            # Album/Playlist info
            album_info = f"Album • {song.view_count}" if song.view_count else "Single"
            draw.text(
                (self.TEXT_X, self.ALBUM_Y),
                album_info[:40],
                font=album_font,
                fill=self.COLORS["text_tertiary"]
            )
            
            # Draw waveform visualization
            self._draw_music_waveform(
                draw,
                self.TEXT_X,
                self.ALBUM_Y + 40,
                self.PROGRESS_WIDTH,
                30
            )
            
            # Progress bar
            self._draw_progress_bar(
                draw,
                self.PROGRESS_X,
                self.PROGRESS_Y,
                self.PROGRESS_WIDTH,
                self.PROGRESS_HEIGHT,
                progress=0.55
            )
            
            # Time stamps
            draw.text(
                (self.PROGRESS_X, self.TIME_Y),
                "0:01",
                font=time_font,
                fill=self.COLORS["text_tertiary"]
            )
            
            duration = song.duration if song.duration else "3:45"
            # Calculate right-aligned position
            bbox = draw.textbbox((0, 0), duration, font=time_font)
            time_width = bbox[2] - bbox[0]
            
            draw.text(
                (self.PROGRESS_X + self.PROGRESS_WIDTH - time_width, self.TIME_Y),
                duration,
                font=time_font,
                fill=self.COLORS["text_tertiary"]
            )
            
            # Control buttons
            control_center_x = self.TEXT_X + self.PROGRESS_WIDTH // 2
            
            # Shuffle button
            self._draw_control_button(
                draw,
                control_center_x - 160,
                self.CONTROLS_Y,
                "🔀",
                size=22,
                active=False
            )
            
            # Previous button
            self._draw_control_button(
                draw,
                control_center_x - 80,
                self.CONTROLS_Y,
                "⏮",
                size=22,
                active=True
            )
            
            # Play/Pause button
            self._draw_control_button(
                draw,
                control_center_x,
                self.CONTROLS_Y,
                "▶",
                size=28,
                active=True
            )
            
            # Next button
            self._draw_control_button(
                draw,
                control_center_x + 80,
                self.CONTROLS_Y,
                "⏭",
                size=22,
                active=True
            )
            
            # Repeat button
            self._draw_control_button(
                draw,
                control_center_x + 160,
                self.CONTROLS_Y,
                "🔁",
                size=22,
                active=False
            )
            
            # Heart/Like button (top right)
            heart_x = self.CARD_X + self.CARD_WIDTH - 50
            heart_y = self.CARD_Y + 30
            
            # Heart icon
            self._draw_control_button(
                draw,
                heart_x,
                heart_y,
                "❤️",
                size=22,
                active=True
            )
            
            # Footer with branding
            footer_text = "Spotify Premium"
            bbox = draw.textbbox((0, 0), footer_text, font=small_font)
            footer_width = bbox[2] - bbox[0]
            
            draw.text(
                (self.CARD_X + self.CARD_WIDTH - footer_width - 40, self.FOOTER_Y),
                footer_text,
                font=small_font,
                fill=self.COLORS["accent_green"]
            )
            
            # Spotify logo (left side footer)
            draw.text(
                (self.ALBUM_X, self.FOOTER_Y),
                "🎵",
                font=small_font,
                fill=self.COLORS["text_secondary"]
            )
            
            # Now Playing indicator
            now_playing = "NOW PLAYING"
            bbox = draw.textbbox((0, 0), now_playing, font=small_font)
            np_width = bbox[2] - bbox[0]
            
            # Green dot indicator
            draw.ellipse(
                [self.ALBUM_X + 30, self.FOOTER_Y + 4,
                 self.ALBUM_X + 36, self.FOOTER_Y + 10],
                fill=self.COLORS["accent_green"]
            )
            
            draw.text(
                (self.ALBUM_X + 44, self.FOOTER_Y),
                now_playing,
                font=small_font,
                fill=self.COLORS["text_secondary"]
            )
            
            # Save final image
            if canvas.mode == 'RGBA':
                canvas_rgb = Image.new("RGB", canvas.size, (18, 18, 18))
                canvas_rgb.paste(canvas, mask=canvas.split()[3])
            else:
                canvas_rgb = canvas.copy()
            
            # Save with high quality
            canvas_rgb.save(output, quality=100, optimize=True, format="PNG")
            
            # Cleanup
            canvas_rgb.close()
            canvas.close()
            card.close()
            card_shadow.close()
            album_art.close()
            album_shadow.close()
            overlay.close()
            thumb.close()
            noise.close()
            
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
