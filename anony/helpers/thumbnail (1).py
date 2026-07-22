# thumbnail.py
# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# Enhanced Apple Music‑style thumbnail generator.

import asyncio
import math
import os
import re
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from anony import config
from anony.helpers import Track


# ──────────────────────────────────────────────────────────────────────────
#  Fonts
# ──────────────────────────────────────────────────────────────────────────
# Put your real font files here: <this folder>/fonts/Raleway-Bold.ttf and
# <this folder>/fonts/Inter-Light.ttf. This is the #1 reason the two
# screenshots don't match — if these files aren't found, PIL silently falls
# back to a system font (or its tiny built-in bitmap font) with completely
# different character widths, so every trim/centering calculation that was
# tuned against Raleway/Inter comes out wrong.
FONTS_DIR = Path(__file__).resolve().parent / "fonts"


# ──────────────────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────────────────

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


def clean_channel_name(channel_name: str) -> str:
    """
    Clean a YouTube channel/label name for display as the "artist" line —
    the same way Apple/YouTube Music show the uploading label for movie
    songs (e.g. "Think Music India - Topic" -> "Think Music India").

    NOTE: earlier versions of this file tried to be clever and, whenever the
    channel name contained a word like "music" or "records", replaced the
    channel name entirely with a fragment split out of the video title
    (song.title.split('|')[2]). That's why "Think Music India" (which
    contains "Music") was getting swapped out for a truncated slice of the
    title like "Pradeep Ranganathan" -> "PRADE". Splitting an arbitrary
    title on "|" is too fragile to trust, and it actively fights the
    reference design, which just shows the cleaned channel name. That logic
    has been removed — this now only strips the common suffixes.
    """
    if not channel_name:
        return ""
    name = re.sub(r"(?i)\s*-\s*topic\s*$", "", channel_name)
    name = re.sub(r"(?i)\s*-?\s*official.*$", "", name)
    name = re.sub(r"(?i)\s*vevo\s*$", "", name)
    name = name.strip()
    return name or channel_name.strip()


def camel_to_words(name: str) -> str:
    """'EnnavaleMusicBot' -> 'Ennavale Music Bot' — used only for the pill
    label so a CamelCase bot name reads like the reference's "Jerry Bots"
    instead of running together as one long word."""
    return re.sub(r"(?<!^)(?=[A-Z])", " ", name).strip()


def safe_load_font(filename, size, bold=False):
    """
    Load `filename` from FONTS_DIR. If it isn't there, fall back to a
    matching-weight system font instead of a random mix of bold/regular
    paths, and print a clear warning so a missing font is easy to spot
    instead of silently producing mismatched text metrics.
    """
    candidates = [FONTS_DIR / filename]

    system_bold = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    system_regular = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    candidates += [Path(p) for p in (system_bold if bold else system_regular)]

    for path in candidates:
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            continue

    print(
        f"[thumbnail] WARNING: couldn't load '{filename}' (or any fallback) "
        f"at size {size}. Using PIL's built-in default font instead — text "
        f"sizing/trimming will look different from the reference design "
        f"until you add the real .ttf files under: {FONTS_DIR}"
    )
    return ImageFont.load_default()


# ──────────────────────────────────────────────────────────────────────────
#  Icon drawing helpers (kept separate so the layout code stays readable)
# ──────────────────────────────────────────────────────────────────────────

def draw_chevron_pair(draw, cx, cy, scale, color, direction=1, width=6):
    """
    Draws a double-chevron 'rewind'/'fast-forward' icon (⏪ / ⏩) centered
    at (cx, cy). direction = -1 for previous/rewind, 1 for next/forward.
    """
    tri_w = 26 * scale
    tri_h = 30 * scale
    gap = 4 * scale

    def triangle(offset_x):
        if direction == 1:
            x0 = cx + offset_x
            pts = [(x0, cy - tri_h), (x0, cy + tri_h), (x0 + tri_w, cy)]
        else:
            x0 = cx - offset_x
            pts = [(x0, cy - tri_h), (x0, cy + tri_h), (x0 - tri_w, cy)]
        draw.polygon(pts, fill=color)

    triangle(-(tri_w + gap) if direction == 1 else (tri_w + gap))
    triangle(0)


def draw_pause_icon(draw, cx, cy, scale, color):
    """Two rounded vertical bars – the pause icon."""
    bar_w = 11 * scale
    bar_h = 46 * scale
    gap = 9 * scale
    radius = 4 * scale
    draw.rounded_rectangle(
        (cx - gap - bar_w, cy - bar_h / 2, cx - gap, cy + bar_h / 2),
        radius=radius, fill=color
    )
    draw.rounded_rectangle(
        (cx + gap, cy - bar_h / 2, cx + gap + bar_w, cy + bar_h / 2),
        radius=radius, fill=color
    )


def draw_speaker(draw, x, y, scale, color, waves=0):
    """
    Draws a speaker icon at (x, y) — x is the left edge.
    waves: 0 = muted/plain, 1 = one arc, 2 = two arcs (loud).
    """
    body_h = 18 * scale
    draw.polygon(
        [
            (x, y - 4 * scale), (x + 7 * scale, y - 4 * scale),
            (x + 15 * scale, y - body_h), (x + 15 * scale, y + body_h),
            (x + 7 * scale, y + 4 * scale), (x, y + 4 * scale),
        ],
        fill=color,
    )
    if waves >= 1:
        draw.arc(
            (x + 17 * scale, y - 7 * scale, x + 27 * scale, y + 7 * scale),
            -55, 55, fill=color, width=max(2, int(2 * scale))
        )
    if waves >= 2:
        draw.arc(
            (x + 21 * scale, y - 13 * scale, x + 36 * scale, y + 13 * scale),
            -55, 55, fill=color, width=max(2, int(2 * scale))
        )


def draw_comment_icon(draw, cx, cy, scale, color):
    """Speech-bubble-with-quotes icon."""
    w, h = 34 * scale, 26 * scale
    box = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    draw.rounded_rectangle(box, radius=7 * scale, outline=color, width=max(2, int(2.5 * scale)))
    tail_x = cx - w * 0.15
    tail_y = cy + h / 2
    draw.polygon(
        [
            (tail_x, tail_y), (tail_x + 10 * scale, tail_y),
            (tail_x, tail_y + 10 * scale),
        ],
        fill=color,
    )
    # two little quote marks
    qw, qh = 4 * scale, 7 * scale
    q1x = cx - 8 * scale
    q2x = cx + 3 * scale
    qy = cy - qh / 2
    draw.rectangle((q1x, qy, q1x + qw, qy + qh), fill=color)
    draw.rectangle((q2x, qy, q2x + qw, qy + qh), fill=color)


def draw_queue_icon(draw, cx, cy, scale, color):
    """Three horizontal lines, each prefixed with a small dot (playlist icon)."""
    line_w = 30 * scale
    dot_r = 2.4 * scale
    left = cx - (line_w + 10 * scale) / 2
    for i, dy in enumerate((-9 * scale, 0, 9 * scale)):
        yy = cy + dy
        draw.ellipse((left, yy - dot_r, left + dot_r * 2, yy + dot_r), fill=color)
        line_start = left + dot_r * 2 + 6 * scale
        draw.rounded_rectangle(
            (line_start, yy - 1.6 * scale, line_start + line_w, yy + 1.6 * scale),
            radius=1.5 * scale, fill=color
        )


# ──────────────────────────────────────────────────────────────────────────
#  Thumbnail generator
# ──────────────────────────────────────────────────────────────────────────

class Thumbnail:
    """
    Generates an Apple Music‑style player card for a given track.
    Usage:
        thumb = Thumbnail()
        await thumb.start()
        path = await thumb.generate(track, progress=0.45)
        await thumb.close()
    """

    # Change this to your bot's display name — it shows up as the little
    # pill badge centered under the progress bar. You can write it with
    # spaces ("Jerry Bots") or in CamelCase ("EnnavaleMusicBot") — the pill
    # will automatically add spacing between words either way.
    BOT_NAME = "EnnavaleMusicBot"

    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

        # Load fonts (fallback to a matching-weight system font if missing)
        self.font_title = safe_load_font("Raleway-Bold.ttf", 44, bold=True)
        self.font_artist = safe_load_font("Inter-Light.ttf", 24)
        self.font_time = safe_load_font("Inter-Light.ttf", 17)
        self.font_pill = safe_load_font("Raleway-Bold.ttf", 16, bold=True)

    async def start(self) -> None:
        """Initialize the HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession()

    async def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _download_thumb(self, url: str, path: str) -> str:
        """Download the thumbnail image from URL to local path."""
        async with self.session.get(url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                f.write(await resp.read())
        return path

    async def generate(
        self,
        song: Track,
        progress: float = 0.25,
        size=(1280, 720),
        force: bool = False,
    ) -> str:
        """
        Generate the thumbnail image.

        :param song: Track object with attributes: id, thumbnail, title, channel_name, duration
        :param progress: float between 0 and 1 indicating playback progress
        :param size: (width, height) of the output image
        :param force: regenerate even if cache/{song.id}.png already exists.
            IMPORTANT while you're testing changes to this file: the cache
            below is keyed only on song.id, not on progress/content, so if
            you already generated a thumbnail for a given song once, every
            later call just hands back that same old file — including old
            *broken* renders from before you fixed the code. Pass
            force=True (or delete the file under cache/) whenever you want
            to confirm what the current code actually produces.
        :return: path to the generated PNG file
        """
        if self.session is None:
            await self.start()

        os.makedirs("cache", exist_ok=True)
        temp_path = f"cache/temp_{song.id}.jpg"
        output_path = f"cache/{song.id}.png"

        # Return cached if it exists (see the `force` note above).
        if os.path.exists(output_path) and not force:
            return output_path

        album_art = None
        canvas = None
        try:
            # Download album art
            await self._download_thumb(song.thumbnail, temp_path)
            album_art = Image.open(temp_path).convert("RGBA")

            # --- 1. BLURRED BACKGROUND ---
            canvas = Image.new("RGBA", size, (0, 0, 0, 255))
            bg_crop = ImageOps.fit(album_art, size, Image.LANCZOS)
            bg_blurred = bg_crop.filter(ImageFilter.GaussianBlur(45))
            enhancer = ImageEnhance.Brightness(bg_blurred)
            bg_blurred = enhancer.enhance(0.75)
            canvas.paste(bg_blurred, (0, 0))

            # Dark gradient overlay (top darker, bottom slightly lighter)
            gradient = Image.new("RGBA", size, (0, 0, 0, 0))
            grad_draw = ImageDraw.Draw(gradient)
            for y in range(size[1]):
                alpha = int(130 - 90 * (y / size[1]))
                grad_draw.line([(0, y), (size[0], y)], fill=(0, 0, 0, alpha))
            canvas = Image.alpha_composite(canvas, gradient)

            shapes_layer = Image.new("RGBA", size, (0, 0, 0, 0))
            draw_shapes = ImageDraw.Draw(shapes_layer)
            draw = ImageDraw.Draw(canvas)

            # --- 2. LEFT PANEL: ALBUM ART ---
            cover_size = 520
            cover_x = 90
            cover_y = (size[1] - cover_size) // 2

            cover = ImageOps.fit(album_art, (cover_size, cover_size), Image.LANCZOS)
            cover = apply_rounded_corners(cover, 40)

            # Shadow behind cover (soft drop shadow)
            shadow = Image.new("RGBA", (cover_size + 60, cover_size + 60), (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_draw.rounded_rectangle(
                (30, 30, cover_size + 30, cover_size + 30), 45, fill=(0, 0, 0, 190)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(28))
            canvas.alpha_composite(shadow, (cover_x - 30, cover_y - 30))
            canvas.paste(cover, (cover_x, cover_y), cover)

            # --- 3. RIGHT PANEL: CONTENT ---
            rx = cover_x + cover_size + 100          # 710
            bar_w = size[0] - 105 - rx                # right margin ≈105
            white = (255, 255, 255, 255)
            gray_text = (215, 215, 215, 235)
            black = (25, 25, 25, 255)

            title_y = 128
            artist_y = title_y + 62

            # Title (trim if too long) — leave clearance for the star/dots
            # buttons on the right (they occupy ~146px) so long titles never
            # run underneath them.
            title_text = trim_text(draw, song.title, self.font_title, bar_w - 160)
            draw.text((rx, title_y), title_text, font=self.font_title, fill=white)

            # Top Right Buttons (Star & Dots)
            circ_size = 44
            circ_y = title_y + 2
            star_cx = rx + bar_w - circ_size - 56
            dots_cx = rx + bar_w - circ_size

            draw_shapes.ellipse(
                (star_cx, circ_y, star_cx + circ_size, circ_y + circ_size),
                fill=(255, 255, 255, 65)
            )
            draw_shapes.ellipse(
                (dots_cx, circ_y, dots_cx + circ_size, circ_y + circ_size),
                fill=(255, 255, 255, 65)
            )

            # Star icon
            scx, scy = star_cx + circ_size / 2, circ_y + circ_size / 2
            star_pts = []
            for i in range(10):
                ang = math.pi / 2 + i * math.pi / 5
                r = 12 if i % 2 == 0 else 5
                star_pts.append((scx + r * math.cos(ang), scy - r * math.sin(ang)))
            draw.polygon(star_pts, outline=white, width=2)

            # Three dots
            dcx = dots_cx + circ_size / 2
            dcy = circ_y + circ_size / 2
            for dy in (-9, 0, 9):
                draw.ellipse((dcx - 2.5, dcy + dy - 2.5, dcx + 2.5, dcy + dy + 2.5), fill=white)

            # Artist / channel name — shown as-is (not uppercased) to match
            # the reference design, e.g. "Think Music India" rather than
            # "THINK MUSIC INDIA".
            artist = clean_channel_name(song.channel_name)
            artist_text = trim_text(draw, artist, self.font_artist, bar_w)
            draw.text((rx, artist_y), artist_text, font=self.font_artist, fill=gray_text)

            # --- 4. PROGRESS BAR & BRAND PILL ---
            bar_y = artist_y + 95

            # Empty track background
            draw_shapes.rounded_rectangle(
                (rx, bar_y, rx + bar_w, bar_y + 7), radius=4,
                fill=(255, 255, 255, 70)
            )

            # Brand pill (bot name) — mixed case like "Jerry Bots", not
            # ALL CAPS, and auto-shrinks so it never overflows the bar.
            pill_text = camel_to_words(self.BOT_NAME)
            pill_font = self.font_pill
            pill_tw = get_text_width(draw, pill_text, pill_font)
            max_pill_w = bar_w * 0.55
            if pill_tw > max_pill_w:
                # try progressively smaller sizes of the same font family
                for fallback_size in (14, 12, 11):
                    pill_font = safe_load_font("Raleway-Bold.ttf", fallback_size, bold=True)
                    pill_tw = get_text_width(draw, pill_text, pill_font)
                    if pill_tw <= max_pill_w:
                        break

            pill_cx = rx + (bar_w // 2)
            time_y = bar_y + 24
            pad_x, pad_y = 20, 7

            draw_shapes.rounded_rectangle(
                (pill_cx - pill_tw / 2 - pad_x, time_y - pad_y,
                 pill_cx + pill_tw / 2 + pad_x, time_y + 22 + (pad_y - 6)),
                radius=16, fill=(255, 255, 255, 190)
            )

            # Composite translucent shapes onto canvas
            canvas = Image.alpha_composite(canvas, shapes_layer)
            draw = ImageDraw.Draw(canvas)

            # Filled progress (based on `progress` parameter)
            filled_w = int(bar_w * max(0, min(1, progress)))
            if filled_w > 0:
                draw.rounded_rectangle(
                    (rx, bar_y, rx + filled_w, bar_y + 7), radius=4, fill=white
                )
                handle_x = rx + filled_w
                draw.ellipse(
                    (handle_x - 7, bar_y - 3.5, handle_x + 7, bar_y + 10.5),
                    fill=white
                )

            # Timestamps
            elapsed = getattr(song, "elapsed", None) or "0:00"
            draw.text((rx, time_y), elapsed, font=self.font_time, fill=white)
            dur_text = f"-{song.duration}" if song.duration else "-LIVE"
            dur_w = get_text_width(draw, dur_text, self.font_time)
            draw.text((rx + bar_w - dur_w, time_y), dur_text, font=self.font_time, fill=white)

            # Pill text
            draw.text(
                (pill_cx - pill_tw / 2, time_y - 3),
                pill_text, font=pill_font, fill=black
            )

            # --- 5. PLAYBACK CONTROLS ---
            controls_y = bar_y + 145
            cx = pill_cx

            draw_pause_icon(draw, cx, controls_y, 1.15, white)
            draw_chevron_pair(draw, cx - 145, controls_y, 1.0, white, direction=-1)
            draw_chevron_pair(draw, cx + 145, controls_y, 1.0, white, direction=1)

            # --- 6. VOLUME BAR ---
            vol_y = controls_y + 95
            vol_len = bar_w - 80
            vol_x_start = rx + 40

            draw_speaker(draw, vol_x_start, vol_y, 0.85, white, waves=0)

            bar_left = vol_x_start + 30
            bar_right = vol_x_start + vol_len - 30
            draw.rounded_rectangle(
                (bar_left, vol_y - 3, bar_right, vol_y + 3),
                radius=3, fill=(255, 255, 255, 110)
            )
            # user's own volume level is unknown here — show a sensible default fill
            vol_fill = bar_left + int((bar_right - bar_left) * 0.7)
            draw.rounded_rectangle(
                (bar_left, vol_y - 3, vol_fill, vol_y + 3),
                radius=3, fill=white
            )

            draw_speaker(draw, vol_x_start + vol_len - 34, vol_y, 0.85, white, waves=2)

            # --- 7. BOTTOM UI (comments / queue) ---
            bot_y = vol_y + 68
            draw_comment_icon(draw, cx - 100, bot_y, 1.0, white)
            draw_queue_icon(draw, cx + 100, bot_y, 1.0, white)

            # --- 8. SAVE ---
            canvas = canvas.convert("RGB")
            canvas.save(output_path, quality=100)

            return output_path

        except Exception as e:
            print(f"Thumbnail generation error: {e}")
            # Return a default thumbnail (you can set a fallback image)
            return config.DEFAULT_THUMB

        finally:
            if album_art is not None:
                album_art.close()
            if canvas is not None:
                canvas.close()
            try:
                os.remove(temp_path)
            except Exception:
                pass
