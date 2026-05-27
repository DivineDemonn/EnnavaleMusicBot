# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic (V2 – High Quality Audio Edition)

import os
import re
import random
import asyncio
import aiohttp
from pathlib import Path

import yt_dlp
from py_yt import Playlist, VideosSearch

from anony import config, logger
from anony.helpers import NexGenApi, Track, utils


class YouTube:
    """
    Enhanced YouTube handler with:
      - Forced high-bitrate OPUS stereo audio for Telegram VC.
      - Aggressive retry/network recovery settings.
      - Clean fallback chains (Shruti API -> yt-dlp -> alternative formats).
    """

    def __init__(self):
        self.api = None
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "anony/cookies"
        self.warned = False
        # URL validation patterns (unchanged)
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

        # Connect to Shruti API if provided
        if config.SHRUTI_API_URL and config.SHRUTI_API_KEY:
            self.api = NexGenApi(
                config.SHRUTI_API_URL,
                config.SHRUTI_API_KEY,
                config.SHRUTI_API_URL,  # Using same URL for both audio and video
            )

    # ------------------------------------------------------------------
    # Cookie handling (unchanged, still random & batbin-based)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # URL validation helpers
    # ------------------------------------------------------------------
    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    def invalid(self, url: str) -> bool:
        return bool(re.match(self.iregex, url))

    # ------------------------------------------------------------------
    # Search (single video)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Playlist extraction
    # ------------------------------------------------------------------
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
    # 🔥 UPGRADED DOWNLOADER – High Quality & Network Resilient
    # ------------------------------------------------------------------
    async def download(self, video_id: str, video: bool = False) -> str | None:
        """
        Downloads audio/video with these priorities:
          1. Shruti API (if available)
          2. yt-dlp with high-quality OPUS (crystal stereo)
          3. Fallback to best possible format in case of network issues.
        """
        # --- PATH PREPARATION ---
        ext = "mp4" if video else "webm"  # webm container holds OPUS natively
        filename = f"downloads/{video_id}.{ext}"
        Path("downloads").mkdir(parents=True, exist_ok=True)

        if Path(filename).exists():
            logger.info("Cache hit: %s", filename)
            return filename

        # --- 1st ATTEMPT: Shruti API ---
        if self.api:
            try:
                logger.info("Trying Shruti API for %s", video_id)
                # Ensure session is initialized
                await self.api.get_session()
                file_path = await self.api.download(video_id, video)
                if file_path and Path(file_path).exists():
                    return file_path
            except Exception as e:
                logger.warning("Shruti API failed: %s", e)

        # --- 2nd ATTEMPT: yt-dlp with best OPUS stereo ---
        url = self.base + video_id
        cookie = self.get_cookies()

        # Base options with aggressive retry & network resilience
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": cookie,
            # --- NETWORK RESILIENCE (new) ---
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 5,
            "socket_timeout": 30,
            "file_access_retries": 5,
            "skip_unavailable_fragments": True,
            "ignoreerrors": True,
        }

        if video:
            # Video: limit to 720p, merge into MP4
            ydl_opts = {
                **base_opts,
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)",
                "merge_output_format": "mp4",
            }
        else:
            # 🎵 AUDIO: prefer OPUS in webm, fallback to best audio overall
            #    OPUS delivers stereo and high efficiency for Telegram VC.
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[acodec=opus]/bestaudio",
                # Keep the native container (webm) – no re-encoding
                "postprocessors": [],   # disable any automatic conversion
            }

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except yt_dlp.utils.DownloadError as de:
                logger.error("yt-dlp DownloadError: %s", de)
                return None
            except Exception as ex:
                logger.exception("Unexpected yt-dlp error: %s", ex)
                return None
            return filename

        # Run blocking download in thread (with a generous timeout)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_download),
                timeout=120,  # 2 minutes for large files
            )
            if result and Path(result).exists():
                return result
        except asyncio.TimeoutError:
            logger.error("Download timed out for %s", url)

        # --- 3rd ATTEMPT: last-resort fallback (any best audio) ---
        if not video:
            logger.warning("Primary download failed. Trying fallback format (bestaudio).")
            fallback_opts = {
                **base_opts,
                "format": "bestaudio",  # totally unrestricted
                "postprocessors": [],
            }
            def _fallback():
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    ydl.download([url])
                return filename
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_fallback),
                    timeout=120,
                )
                if result and Path(result).exists():
                    return result
            except Exception as e:
                logger.error("Fallback download also failed: %s", e)

        return None
