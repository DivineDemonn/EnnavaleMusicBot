# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import os
import math
import random
import aiohttp
from PIL import (Image, ImageDraw, ImageEnhance,
                 ImageFilter, ImageFont, ImageOps)

from anony import config
from anony.helpers import Track


class Thumbnail:
    def __init__(self):
        self.rect = (914, 514)
        self.fill = (255, 255, 255)
        self.mask = Image.new("L", self.rect, 0)
        self.font1 = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 30)
        self.font2 = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 30)
        self.session: aiohttp.ClientSession | None = None
        
        # Anime aesthetic settings
        self.CANVAS_SIZE = (1280, 720)
        self.COLORS = {
            "bg_start": (255, 200, 220),
            "bg_mid": (200, 180, 255),
            "bg_end": (160, 210, 255),
            "card_bg": (255, 255, 255, 200),
            "title": (50, 50, 70),
            "artist": (80, 80, 100),
            "secondary": (120, 120, 140),
            "progress_bg": (230, 230, 250),
            "progress_fill_start": (255, 150, 200),
            "progress_fill_end": (200, 150, 255),
            "accent_pink": (255, 120, 180),
            "accent_purple": (180, 120, 255),
            "icon": (80, 60, 120),
            "shadow": (150, 100, 150, 100),
        }
        
        # Card dimensions
        self.CARD_WIDTH = 1100
        self.CARD_HEIGHT = 600
        self.CARD_X = (self.CANVAS_SIZE[0] - self.CARD_WIDTH) // 2
        self.CARD_Y = (self.CANVAS_SIZE[1] - self.CARD_HEIGHT) // 2
        
        # Cover art
        self.COVER_SIZE = 280
        self.COVER_X = self.CARD_X + 60
        self.COVER_Y = self.CARD_Y + (self.CARD_HEIGHT - self.COVER_SIZE) // 2
        
        # Text section
        self.TEXT_START_X = self.COVER_X + self.COVER_SIZE + 70
        self.TEXT_START_Y = self.COVER_Y + 30
        self.TITLE_Y = self.TEXT_START_Y
        self.TITLE_LINE_HEIGHT = 60
        self.ARTIST_Y = self.TITLE_Y + 140
        
        # Progress bar
        self.PROGRESS_Y = self.ARTIST_Y + 100
        self.PROGRESS_WIDTH = 520
        self.PROGRESS_HEIGHT = 6
        self.PROGRESS_X = self.TEXT_START_X
        self.TIME_START_X = self.TEXT_START_X
        self.TIME_END_X = self.TEXT_START_X + self.PROGRESS_WIDTH
        self.TIME_Y = self.PROGRESS_Y - 25
        
        # Control buttons
        self.CONTROL_Y = self.PROGRESS_Y + 70
        self.CONTROL_SPACING = 90

    async def start(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        await self.session.close()

    async def save_thumb(self, output_path: str, url: str) -> str:
        async with self.session.get(url) as resp:
            with open(output_path, "wb") as f:
                f.write(await resp.read())
        return output_path

    def _create_anime_background(self, size):
        """Create dreamy anime-style gradient background"""
        base = Image.new('RGB', size, self.COLORS["bg_start"])
        draw = ImageDraw.Draw(base)
        
        center_x, center_y = size[0] // 2, size[1] // 2
        max_dist = math.sqrt(center_x**2 + center_y**2)
        
        for y in range(size[1]):
            for x in range(size[0]):
                dist = math.sqrt((x - center_x)**2 + (y - center_y)**2)
                ratio = dist / max_dist if max_dist > 0 else 0
                
                if ratio < 0.5:
                    r = int(self.COLORS["bg_mid"][0] * (1 - ratio*2) + self.COLORS["bg_start"][0] * (ratio*2))
                    g = int(self.COLORS["bg_mid"][1] * (1 - ratio*2) + self.COLORS["bg_start"][1] * (ratio*2))
                    b = int(self.COLORS["bg_mid"][2] * (1 - ratio*2) + self.COLORS["bg_start"][2] * (ratio*2))
                else:
                    r = int(self.COLORS["bg_end"][0] * (ratio-0.5)*2 + self.COLORS["bg_mid"][0] * (1-(ratio-0.5)*2))
                    g = int(self.COLORS["bg_end"][1] * (ratio-0.5)*2 + self.COLORS["bg_mid"][1] * (1-(ratio-0.5)*2))
                    b = int(self.COLORS["bg_end"][2] * (ratio-0.5)*2 + self.COLORS["bg_mid"][2] * (1-(ratio-0.5)*2))
                
                draw.point((x, y), fill=(r, g, b))
        
        return base.convert("RGBA")

    def _create_glass_card(self, size, bg_color, corner_radius=30):
        """Create glassmorphism card"""
        card = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle(
            (0, 0, size[0], size[1]),
            radius=corner_radius,
            fill=bg_color
        )
        return card

    def _create_floating_shadow(self, size, radius=30):
        """Create floating shadow effect"""
        shadow = Image.new("RGBA", (size[0] + 40, size[1] + 40), (0, 0, 0, 0))
        draw = ImageDraw.Draw(shadow)
        draw.rounded_rectangle(
            (20, 20, size[0] + 20, size[1] + 20),
            radius=radius,
            fill=self.COLORS["shadow"]
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(20))
        return shadow

    def _create_round_mask(self, size, radius=25):
        """Create rounded corner mask"""
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, size[0], size[1]), radius, fill=255)
        return mask

    def _draw_cherry_blossom(self, draw, x, y, size=20):
        """Draw cherry blossom flower"""
        colors = [(255, 180, 200, 180), (255, 150, 180, 160)]
        
        for i in range(5):
            angle = (i * 72) * math.pi / 180
            petal_x = x + math.cos(angle) * size * 0.6
            petal_y = y + math.sin(angle) * size * 0.6
            
            draw.ellipse(
                (petal_x - size//3, petal_y - size//3,
                 petal_x + size//3, petal_y + size//3),
                fill=colors[i % 2]
            )
        
        draw.ellipse(
            (x - size//5, y - size//5, x + size//5, y + size//5),
            fill=(255, 220, 100, 200)
        )

    def _draw_sparkle(self, draw, x, y, size=8):
        """Draw sparkle effect"""
        draw.line((x - size, y, x + size, y), fill=(255, 255, 255, 200), width=2)
        draw.line((x, y - size, x, y + size), fill=(255, 255, 255, 200), width=2)
        
        draw.ellipse((x - size - 2, y - 2, x - size + 2, y + 2), fill=(255, 255, 255, 200))
        draw.ellipse((x + size - 2, y - 2, x + size + 2, y + 2), fill=(255, 255, 255, 200))
        draw.ellipse((x - 2, y - size - 2, x + 2, y - size + 2), fill=(255, 255, 255, 200))
        draw.ellipse((x - 2, y + size - 2, x + 2, y + size + 2), fill=(255, 255, 255, 200))

    async def generate(self, song: Track, size=(1280, 720)) -> str:
        try:
            temp = f"cache/temp_{song.id}.jpg"
            output = f"cache/{song.id}.png"
            if os.path.exists(output):
                return output

            await self.save_thumb(temp, song.thumbnail)
            
            # Create anime background
            canvas = self._create_anime_background(self.CANVAS_SIZE)
            draw = ImageDraw.Draw(canvas)
            
            # Add cherry blossoms
            for _ in range(8):
                x = random.randint(100, 1180)
                y = random.randint(50, 670)
                self._draw_cherry_blossom(draw, x, y, random.randint(15, 25))
            
            # Add sparkles
            for _ in range(15):
                x = random.randint(0, self.CANVAS_SIZE[0])
                y = random.randint(0, self.CANVAS_SIZE[1])
                self._draw_sparkle(draw, x, y, random.randint(5, 10))
            
            # Create main card
            card = self._create_glass_card(
                (self.CARD_WIDTH, self.CARD_HEIGHT),
                self.COLORS["card_bg"],
                corner_radius=40
            )
            
            # Add floating shadow
            shadow = self._create_floating_shadow((self.CARD_WIDTH, self.CARD_HEIGHT), 40)
            canvas.paste(shadow, (self.CARD_X - 20, self.CARD_Y - 15), shadow)
            
            # Paste main card
            canvas.paste(card, (self.CARD_X, self.CARD_Y), card)
            
            # Process cover art (thumbnail)
            thumb = Image.open(temp).convert("RGBA")
            cover_resized = thumb.resize((self.COVER_SIZE, self.COVER_SIZE), Image.LANCZOS)
            
            # Add shadow for cover
            cover_shadow = Image.new("RGBA", (self.COVER_SIZE + 30, self.COVER_SIZE + 30), (0, 0, 0, 0))
            cover_shadow_draw = ImageDraw.Draw(cover_shadow)
            cover_shadow_draw.rounded_rectangle(
                (15, 15, self.COVER_SIZE + 15, self.COVER_SIZE + 15),
                radius=25,
                fill=(150, 100, 150, 150)
            )
            cover_shadow = cover_shadow.filter(ImageFilter.GaussianBlur(15))
            canvas.paste(cover_shadow, (self.COVER_X - 15, self.COVER_Y - 15), cover_shadow)
            
            # Paste cover with rounded corners
            cover_mask = self._create_round_mask((self.COVER_SIZE, self.COVER_SIZE), radius=25)
            canvas.paste(cover_resized, (self.COVER_X, self.COVER_Y), cover_mask)
            
            # Load fonts for anime design
            try:
                title_font = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 50)
                artist_font = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 34)
                time_font = ImageFont.truetype("anony/helpers/Inter-Light.ttf", 18)
                icon_font = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 40)
                play_font = ImageFont.truetype("anony/helpers/Raleway-Bold.ttf", 50)
            except:
                title_font = artist_font = time_font = icon_font = play_font = self.font1
            
            # Title
            import textwrap
            title_text = song.title[:50] if song.title else "Unknown Title"
            title_lines = textwrap.wrap(title_text, width=25)
            title_y = self.TITLE_Y
            for i, line in enumerate(title_lines[:2]):
                draw.text(
                    (self.TEXT_START_X + 2, title_y + (i * self.TITLE_LINE_HEIGHT) + 2),
                    line,
                    font=title_font,
                    fill=(200, 180, 200, 100)
                )
                draw.text(
                    (self.TEXT_START_X, title_y + (i * self.TITLE_LINE_HEIGHT)),
                    line,
                    font=title_font,
                    fill=self.COLORS["title"]
                )
            
            # Artist/Channel
            artist_text = song.channel_name[:40] if song.channel_name else "Unknown Artist"
            artist_short = textwrap.wrap(artist_text, width=30)[0] if artist_text else "Unknown Artist"
            
            draw.line(
                (self.TEXT_START_X, self.ARTIST_Y - 15, self.TEXT_START_X + 80, self.ARTIST_Y - 15),
                fill=self.COLORS["accent_pink"],
                width=3
            )
            
            draw.text(
                (self.TEXT_START_X, self.ARTIST_Y),
                artist_short,
                font=artist_font,
                fill=self.COLORS["artist"]
            )
            
            # Progress bar background
            draw.rounded_rectangle(
                (self.PROGRESS_X, self.PROGRESS_Y,
                 self.PROGRESS_X + self.PROGRESS_WIDTH, self.PROGRESS_Y + self.PROGRESS_HEIGHT),
                radius=3,
                fill=self.COLORS["progress_bg"]
            )
            
            # Progress fill with gradient
            fill_width = int(self.PROGRESS_WIDTH * 0.55)
            for i in range(fill_width):
                progress_x = self.PROGRESS_X + i
                ratio = i / fill_width if fill_width > 0 else 0
                r = int(self.COLORS["progress_fill_start"][0] * (1 - ratio) + self.COLORS["progress_fill_end"][0] * ratio)
                g = int(self.COLORS["progress_fill_start"][1] * (1 - ratio) + self.COLORS["progress_fill_end"][1] * ratio)
                b = int(self.COLORS["progress_fill_start"][2] * (1 - ratio) + self.COLORS["progress_fill_end"][2] * ratio)
                
                draw.rectangle(
                    (progress_x, self.PROGRESS_Y, progress_x + 1, self.PROGRESS_Y + self.PROGRESS_HEIGHT),
                    fill=(r, g, b)
                )
            
            # Progress knob
            knob_x = self.PROGRESS_X + fill_width
            knob_y = self.PROGRESS_Y + self.PROGRESS_HEIGHT // 2
            knob_radius = 10
            
            draw.ellipse(
                (knob_x - knob_radius, knob_y - knob_radius,
                 knob_x + knob_radius, knob_y + knob_radius),
                fill=self.COLORS["accent_pink"]
            )
            
            draw.ellipse(
                (knob_x - 3, knob_y - 3, knob_x + 3, knob_y + 3),
                fill=(255, 255, 255, 200)
            )
            
            # Time stamps
            draw.text(
                (self.TIME_START_X, self.TIME_Y),
                "0:01",
                font=time_font,
                fill=self.COLORS["secondary"]
            )
            
            draw.text(
                (self.TIME_END_X, self.TIME_Y),
                song.duration if song.duration else "3:45",
                font=time_font,
                fill=self.COLORS["secondary"],
                anchor="ra"
            )
            
            # Control buttons
            center_x = self.CARD_X + (self.CARD_WIDTH // 2)
            
            draw.text(
                (center_x - self.CONTROL_SPACING, self.CONTROL_Y),
                "⏮",
                font=icon_font,
                fill=self.COLORS["icon"],
                anchor="mm"
            )
            
            draw.text(
                (center_x, self.CONTROL_Y),
                "▶",
                font=play_font,
                fill=self.COLORS["icon"],
                anchor="mm"
            )
            
            draw.text(
                (center_x + self.CONTROL_SPACING, self.CONTROL_Y),
                "⏭",
                font=icon_font,
                fill=self.COLORS["icon"],
                anchor="mm"
            )
            
            # View count text at bottom
            view_text = f"{song.channel_name[:25]} | {song.view_count}" if song.view_count else song.channel_name[:40]
            draw.text(
                (self.CARD_X + 60, self.CARD_Y + self.CARD_HEIGHT - 60),
                view_text,
                font=self.font2,
                fill=self.COLORS["secondary"]
            )
            
            # Save output
            if canvas.mode == 'RGBA':
                canvas_rgb = Image.new("RGB", canvas.size, (255, 255, 255))
                canvas_rgb.paste(canvas, mask=canvas.split()[3])
            else:
                canvas_rgb = canvas.copy()
            
            canvas_rgb.save(output, quality=95, optimize=True, format="PNG")
            
            # Cleanup
            canvas_rgb.close()
            canvas.close()
            card.close()
            shadow.close()
            cover_resized.close()
            cover_shadow.close()
            thumb.close()
            
            try:
                os.remove(temp)
            except Exception:
                pass
            
            return output
            
        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            return config.DEFAULT_THUMB
