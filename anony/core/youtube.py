# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path
import shutil

from py_yt import Playlist, VideosSearch

from anony import config, logger
from anony.helpers import ArcApi, Track, utils


class YouTube:
    def __init__(self):
        self.api = None
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "anony/cookies"
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )
        self.iregex = re.compile(
            r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)"
            r"(?!/(watch\?v=[A-Za-z0-9_-]{11}|shorts/[A-Za-z0-9_-]{11}"
            r"|playlist\?list=PL[A-Za-z0-9_-]+|[A-Za-z0-9_-]{11}))\S*"
        )

        if config.ARC_API_URL and config.ARC_API_KEY:
            self.api = ArcApi(
                config.ARC_API_URL,
                config.ARC_API_KEY
            )
            logger.info("ArcApi enabled for YouTube downloads.")
        else:
            logger.info("ArcApi not configured – falling back to yt-dlp only.")

        # Check for ffmpeg (required for audio enhancement)
        self.ffmpeg_available = shutil.which("ffmpeg") is not None
        if not self.ffmpeg_available:
            logger.warning("ffmpeg not found – audio enhancement will be skipped.")

    def get_cookies(self):
        if not self.checked:
            for file in os.listdir(self.cookie_dir):
                if file.endswith(".txt"):
                    self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        async with aiohttp.ClientSession() as session:
            for url in urls:
                name = url.split("/")[-1]
                link = "https://batbin.me/raw/" + name
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(f"{self.cookie_dir}/{name}.txt", "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        try:
            _search = VideosSearch(query, limit=1, with_live=False)
            results = await _search.next()
        except Exception:
            return None
        if results and results["result"]:
            data = results["result"][0]
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except Exception:
            pass
        return tracks

    # ------------------------------------------------------------------
    # AUDIO ENHANCEMENT (BASS + LOUDNESS + STEREO)
    # ------------------------------------------------------------------
    async def _enhance_audio(self, input_path: str, output_path: str,
                             target_bitrate: str = "96k") -> bool:
        """
        Apply ffmpeg filters:
          - loudnorm (EBU R128)
          - bass boost equalizer
          - stereo widening
          - encode to Opus in Ogg container
        Returns True on success.
        """
        if not self.ffmpeg_available:
            logger.warning("ffmpeg missing – cannot enhance audio.")
            return False

        filter_chain = (
            "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true,"
            "equalizer=f=60:width_type=o:width=2:g=6,"
            "equalizer=f=150:width_type=o:width=2:g=3,"
            "stereotools=slev=0.4:lev=0.4"
        )
        cmd = [
            "ffmpeg",
            "-y",                          # overwrite output
            "-i", input_path,
            "-af", filter_chain,
            "-c:a", "libopus",
            "-b:a", target_bitrate,
            "-vbr", "on",
            "-compression_level", "10",
            "-f", "ogg",                   # Ogg container for Telegram
            output_path
        ]
        logger.info(f"Enhancing audio: {' '.join(cmd)}")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                err_msg = stderr.decode()[:200] if stderr else ""
                logger.error(f"ffmpeg failed: {err_msg}")
                return False
            logger.info("Audio enhancement completed successfully.")
            return True
        except Exception as e:
            logger.error(f"ffmpeg error: {e}")
            return False

    # ------------------------------------------------------------------
    # MAIN DOWNLOAD WITH QUALITY & ENHANCEMENT
    # ------------------------------------------------------------------
    async def download(self, video_id: str, video: bool = False,
                       quality: str = "high") -> str | None:
        """
        Download a track/video.
        quality:
          - "high"   : original high bitrate, full enhancement
          - "medium" : 96k Opus, fast download + enhancement
          - "low"    : 64k Opus, smallest file, instant feel (2-3 MB song)
        """
        # ---------- 1) ArcApi ----------
        if self.api:
            if file_path := await self.api.download(video_id, video):
                # If it's audio, enhance it
                if not video and self.ffmpeg_available:
                    enhanced_path = f"downloads/{video_id}_e.ogg"
                    # Choose bitrate based on quality
                    bitrate = "96k" if quality == "medium" else "64k" if quality == "low" else "128k"
                    if await self._enhance_audio(file_path, enhanced_path, bitrate):
                        # Replace the original with the enhanced version
                        os.replace(enhanced_path, file_path)
                return file_path

        # ---------- 2) yt-dlp fallback ----------
        url = self.base + video_id
        # Build the format string according to quality
        if video:
            ext = "mp4"
            fmt = "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)"
            out_ext = "mp4"
        else:
            ext = "webm"
            if quality == "low":
                fmt = "bestaudio[ext=webm][acodec=opus][abr<=64]"
            elif quality == "medium":
                fmt = "bestaudio[ext=webm][acodec=opus][abr<=96]"
            else:  # high
                fmt = "bestaudio[ext=webm][acodec=opus]"
            out_ext = "webm"  # temporary, will be replaced by .ogg after enhancement

        filename = f"downloads/{video_id}.{out_ext}"

        if Path(filename).exists():
            return filename

        cookie = self.get_cookies()
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": cookie,
        }

        if video:
            ydl_opts = {
                **base_opts,
                "format": fmt,
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": fmt,
            }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
                    return None
                except Exception as ex:
                    logger.warning("yt-dlp download failed: %s", ex)
                    return None
            return filename

        result = await asyncio.to_thread(_download)
        if not result:
            return None

        # Post‑process audio
        if not video and self.ffmpeg_available:
            enhanced_ogg = f"downloads/{video_id}_enhanced.ogg"
            bitrate = {"low": "64k", "medium": "96k", "high": "128k"}.get(quality, "96k")
            if await self._enhance_audio(result, enhanced_ogg, bitrate):
                # Replace the old webm with the enhanced ogg
                os.replace(enhanced_ogg, result)
        return result
