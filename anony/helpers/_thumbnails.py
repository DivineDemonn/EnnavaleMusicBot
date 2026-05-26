import os
import re
import aiofiles
import aiohttp
from PIL import (
    Image, ImageDraw, ImageEnhance,
    ImageFilter, ImageFont, ImageOps
)
from py_yt import VideosSearch
import math
import traceback

from config import Config
from anony.core.dir import CACHE_DIR

config = Config()
YOUTUBE_IMG_URL = config.YOUTUBE_IMG_URL

# ================= BASIC CONFIGURATION =================
os.makedirs(CACHE_DIR, exist_ok=True)
CANVAS_SIZE = (1280, 720)

WHITE = (255, 255, 255, 255)
BLACK = (0, 0, 0, 255)
GRAY_TEXT = (200, 200, 200, 255)
DARK_OVERLAY = (0, 0, 0, 80)

# ================= CRASH-PROOF HELPER FUNCTIONS =================
def get_text_width(draw, text, font):
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
    if get_text_width(draw, text, font) <= max_width:
        return text
    while get_text_width(draw, text + "…", font) > max_width and len(text) > 0:
        text = text[:-1]
    return text + "…"

def apply_rounded_corners(image, radius):
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, image.size[0], image.size[1]), radius, fill=255)
    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.paste(image, (0, 0), mask)
    return result

def get_real_artist(title, channel_name):
    c_name = re.sub(r"(?i)\s*-\s*topic", "", channel_name)
    c_name = re.sub(r"(?i)\s*official.*", "", c_name)
    c_name = re.sub(r"(?i)\s*vevo", "", c_name)
    c_name = c_name.strip()
    
    lower_channel = c_name.lower()
    labels = ['music', 'records', 'entertainment', 'series', 'studio', 'company', 'audio', 'video', 'network', 't-series', 'lahari', 'aditya']
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
    """Safely loads a font, automatically falling back to system fonts if the custom ones are missing."""
    fonts_to_try = [
        font_path,
        "anony/assets/font.ttf",
        "anony/assets/font2.ttf",
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
    # Absolute last resort (will be tiny, but prevents crashing)
    return ImageFont.load_default()

# ================= MAIN FUNCTION =================
async def get_thumb(videoid: str) -> str:
    cache_name = f"{videoid}_updated.png"
    cache = os.path.join(CACHE_DIR, cache_name)
    
    if os.path.exists(cache):
        return cache

    # ---------- FETCH YOUTUBE DATA ----------
    try:
        vs = VideosSearch(f"https://www.youtube.com/watch?v={videoid}", limit=1)
        data = (await vs.next())["result"][0]
        
        title = re.sub(r"\s+", " ", data["title"]).strip()
        raw_artist = data["channel"]["name"]
        artist = get_real_artist(title, raw_artist).upper()
        duration = data.get("duration") or "LIVE"
        thumb_url = data["thumbnails"][-1]["url"].split("?")[0]
    except Exception:
        return YOUTUBE_IMG_URL

    # ---------- DOWNLOAD THUMBNAIL ----------
    thumb_file = os.path.join(CACHE_DIR, f"{videoid}.jpg")
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(thumb_url, timeout=10) as r:
                if r.status == 200:
                    async with aiofiles.open(thumb_file, "wb") as f:
                        await f.write(await r.read())
                else:
                    return YOUTUBE_IMG_URL
    except Exception:
        return YOUTUBE_IMG_URL

    # ---------- IMAGE GENERATION ----------
    try:
        if os.path.exists(thumb_file):
            try:
                album_art = Image.open(thumb_file).convert("RGBA")
            except Exception:
                album_art = Image.new("RGBA", (320, 180), (50, 50, 50, 255))
        else:
            album_art = Image.new("RGBA", (320, 180), (50, 50, 50, 255))

        # --- 1. DYNAMIC BLURRED BACKGROUND ---
        canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 255))
        bg_blurred = album_art.resize(CANVAS_SIZE, Image.LANCZOS)
        # Blur significantly reduced to 15 to make background visible
        bg_blurred = bg_blurred.filter(ImageFilter.GaussianBlur(15))
        canvas.paste(bg_blurred, (0, 0))
        
        # Apply dark overlay for perfect contrast
        overlay = Image.new("RGBA", CANVAS_SIZE, DARK_OVERLAY)
        canvas = Image.alpha_composite(canvas, overlay)
        draw = ImageDraw.Draw(canvas)

        # Create a layer specifically for translucent shapes
        shapes_layer = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
        draw_shapes = ImageDraw.Draw(shapes_layer)

        # --- 2. FONTS ---
        title_f = safe_load_font("anony/assets/Montserrat-Bold.ttf", 46)
        artist_f = safe_load_font("anony/assets/Montserrat-Medium.ttf", 26)
        time_f = safe_load_font("anony/assets/Montserrat-SemiBold.ttf", 16)
        pill_f = safe_load_font("anony/assets/Montserrat-SemiBold.ttf", 16)

        # --- 3. LEFT PANEL: ALBUM ART ---
        cover_size = 500
        cover_x = 80
        cover_y = 110
        
        cover = album_art.resize((cover_size, cover_size), Image.LANCZOS)
        cover = apply_rounded_corners(cover, 35)
        
        # Soft shadow behind the cover
        shadow = Image.new("RGBA", (cover_size + 40, cover_size + 40), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle((20, 20, cover_size + 20, cover_size + 20), 40, fill=(0, 0, 0, 120))
        shadow = shadow.filter(ImageFilter.GaussianBlur(20))
        canvas.alpha_composite(shadow, (cover_x - 20, cover_y - 20))
        
        canvas.paste(cover, (cover_x, cover_y), cover)

        # --- 4. RIGHT PANEL: TOP CONTENT ---
        rx = 640
        bar_w = 560
        
        # Title
        title_text = trim_text(draw, title, title_f, 430)
        draw.text((rx, 140), title_text, font=title_f, fill=WHITE)
        
        # Top Right Button Circles (Star and 3 Dots)
        circ_y = 145
        circ_size = 40
        
        # Draw translucent circles on shapes layer
        draw_shapes.ellipse((1090, circ_y, 1090 + circ_size, circ_y + circ_size), fill=(255, 255, 255, 70))
        draw_shapes.ellipse((1140, circ_y, 1140 + circ_size, circ_y + circ_size), fill=(255, 255, 255, 70))
        
        # Draw the inner icons on the main canvas
        draw.polygon([(1110, 155), (1113, 161), (1120, 162), (1115, 166), (1117, 173), (1110, 169), (1103, 173), (1105, 166), (1100, 162), (1107, 161)], outline=WHITE, width=2)
        draw.ellipse((1158, 155, 1162, 159), fill=WHITE)
        draw.ellipse((1158, 163, 1162, 167), fill=WHITE)
        draw.ellipse((1158, 171, 1162, 175), fill=WHITE)

        # Artist
        artist_text = trim_text(draw, artist, artist_f, bar_w)
        draw.text((rx, 205), artist_text, font=artist_f, fill=GRAY_TEXT)

        # --- 5. PROGRESS BAR & PILL ---
        bar_y = 300
        
        # Empty track (translucent white/gray)
        draw_shapes.rounded_rectangle((rx, bar_y, rx + bar_w, bar_y + 8), radius=4, fill=(255, 255, 255, 70))
        
        # NEXT-GEN PILL WITH BLACK TEXT
        pill_text = "NEXT-GEN"
        pill_tw = get_text_width(draw, pill_text, pill_f)
        pill_cx = rx + (bar_w // 2)
        time_y = 325
        
        # Translucent background for pill
        draw_shapes.rounded_rectangle((pill_cx - pill_tw//2 - 16, time_y - 4, pill_cx + pill_tw//2 + 16, time_y + 26), radius=15, fill=(255, 255, 255, 120))
        
        # Composite shapes layer to canvas BEFORE drawing solid white/black stuff
        canvas = Image.alpha_composite(canvas, shapes_layer)
        draw = ImageDraw.Draw(canvas)

        # Filled progress part (25% filled for visual effect)
        filled_w = int(bar_w * 0.25)
        draw.rounded_rectangle((rx, bar_y, rx + filled_w, bar_y + 8), radius=4, fill=WHITE)
        
        # Circular Handle
        draw.ellipse((rx + filled_w - 8, bar_y - 4, rx + filled_w + 8, bar_y + 12), fill=WHITE)

        # Timestamps
        draw.text((rx, time_y), "0:00", font=time_f, fill=WHITE)
        dur_w = get_text_width(draw, str(duration), time_f)
        draw.text((rx + bar_w - dur_w, time_y), f"-{duration}", font=time_f, fill=WHITE)

        # Pill Black Text
        draw.text((pill_cx - pill_tw//2, time_y + 2), pill_text, font=pill_f, fill=BLACK)

        # --- 6. PLAYBACK CONTROLS ---
        cy = 480
        cx = rx + (bar_w // 2)
        
        # Pause (Center)
        p_w = 10
        p_h = 44
        p_space = 8
        draw.rounded_rectangle((cx - p_space - p_w, cy - p_h//2, cx - p_space, cy + p_h//2), radius=3, fill=WHITE)
        draw.rounded_rectangle((cx + p_space, cy - p_h//2, cx + p_space + p_w, cy + p_h//2), radius=3, fill=WHITE)
        
        # Previous ( |< < )
        px = cx - 130
        tri_h = 22
        draw.polygon([(px-2, cy), (px+22, cy-tri_h), (px+22, cy+tri_h)], fill=WHITE)
        draw.polygon([(px-26, cy), (px-2, cy-tri_h), (px-2, cy+tri_h)], fill=WHITE)
        draw.rectangle((px-32, cy-tri_h, px-28, cy+tri_h), fill=WHITE)
        
        # Next ( > >| )
        nx = cx + 130
        draw.polygon([(nx+2, cy-tri_h), (nx+2, cy+tri_h), (nx+26, cy)], fill=WHITE)
        draw.polygon([(nx-22, cy-tri_h), (nx-22, cy+tri_h), (nx+2, cy)], fill=WHITE)
        draw.rectangle((nx+28, cy-tri_h, nx+32, cy+tri_h), fill=WHITE)

        # --- 7. NEW VOLUME POSITION ---
        vol_y = 560
        vol_len = 400 # Restored the longer length!
        vol_x_start = cx - (vol_len // 2)
        
        # Volume/Speaker Icon
        sx = vol_x_start
        draw.polygon([(sx, vol_y-5), (sx+6, vol_y-5), (sx+14, vol_y-12), (sx+14, vol_y+12), (sx+6, vol_y+5), (sx, vol_y+5)], fill=WHITE)
        draw.arc((sx+16, vol_y-6, sx+26, vol_y+6), 270, 90, fill=WHITE, width=2)
        draw.arc((sx+20, vol_y-12, sx+34, vol_y+12), 270, 90, fill=WHITE, width=2)
        
        # Lengthened volume bar
        draw.rounded_rectangle((sx+45, vol_y-3, sx + vol_len, vol_y+3), radius=3, fill=WHITE)
        
        # --- 8. BOTTOM UI (Chat & List moved slightly left for balance) ---
        bot_y = 620
        
        # Chat Bubble Icon
        cx_chat = cx - 40 # Nudged slightly to the left relative to the center
        draw.rounded_rectangle((cx_chat, bot_y-14, cx_chat+32, bot_y+10), radius=5, outline=WHITE, width=3)
        draw.polygon([(cx_chat+10, bot_y+10), (cx_chat+16, bot_y+10), (cx_chat+10, bot_y+18)], fill=WHITE)
        draw.rectangle((cx_chat+8, bot_y-5, cx_chat+11, bot_y+2), fill=WHITE)
        draw.rectangle((cx_chat+14, bot_y-5, cx_chat+17, bot_y+2), fill=WHITE)
        
        # List/Queue Icon
        lx = cx + 40 # Matching distance on the right
        ly = bot_y - 12
        for i in range(3):
            y_off = ly + i * 10
            draw.ellipse((lx, y_off, lx+4, y_off+4), fill=WHITE)
            draw.rectangle((lx+10, y_off+1, lx+36, y_off+3), fill=WHITE)

        # ---------- SAVE ----------
        canvas.save(cache, quality=100, optimize=False, dpi=(300, 300))
        album_art.close()
        canvas.close()
        
    except Exception:
        traceback.print_exc()
        if os.path.exists(thumb_file):
            return thumb_file
        return YOUTUBE_IMG_URL
        
    # ---------- CLEANUP & CACHE LIMITING ----------
    if os.path.exists(thumb_file):
        try:
            os.remove(thumb_file)
        except Exception:
            pass
        
    files = sorted(
        [os.path.join(CACHE_DIR, f) for f in os.listdir(CACHE_DIR)],
        key=os.path.getmtime
    )
    files = [f for f in files if "_updated" in f]
    
    for f in files[:-15]:
        try:
            os.remove(f)
        except Exception:
            pass
    
    return cache

# ================= COMPATIBILITY CLASS =================
class Thumbnail:
    def __init__(self):
        pass

    async def start(self):
        return True

    async def stop(self):
        return True

    async def thumbnail(self, videoid):
        return await get_thumb(videoid)

    async def generate(self, media):
        try:
            videoid = None

            if hasattr(media, "videoid"):
                videoid = media.videoid

            elif hasattr(media, "vidid"):
                videoid = media.vidid

            elif isinstance(media, dict):
                videoid = media.get("videoid") or media.get("vidid")

            if not videoid:
                return YOUTUBE_IMG_URL

            return await get_thumb(videoid)

        except Exception:
            return YOUTUBE_IMG_URL
