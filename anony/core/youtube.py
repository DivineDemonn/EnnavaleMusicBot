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
from typing import Optional

from py_yt import Playlist, VideosSearch

from anony import config, logger
from anony.helpers import Track, utils
from anony.helpers.arcapi import ArcApi


class YouTube:
    def __init__(self):
        self.api: Optional[ArcApi] = None
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

        # Initialize Arc API if configured
        if config.ARC_API_URL and config.ARC_API_KEY:
            self.api = ArcApi()
            logger.info("Arc API initialized for YouTube downloads")

    async def download(self, video_id: str, video: bool = False) -> Optional[str]:
        """
        Download YouTube content with fallback strategy:
        1. Try Arc API first (if configured)
        2. Fallback to yt-dlp
        
        Args:
            video_id: YouTube video ID
            video: True for video, False for audio only
            
        Returns:
            Path to downloaded file or None
        """
        # 1. Try Arc API first
        if self.api:
            logger.info(f"Attempting download via Arc API: {video_id}")
            try:
                result = await self.api.download(video_id, video)
                if result:
                    logger.info(f"Successfully downloaded via Arc API: {result}")
                    return result
            except Exception as e:
                logger.warning(f"Arc API download failed: {e}, falling back to yt-dlp")

        # 2. Fallback to yt-dlp
        logger.info(f"Downloading via yt-dlp: {video_id}")
        url = self.base + video_id
        ext = "mp4" if video else "webm"
        filename = f"downloads/{video_id}.{ext}"

        # Return cached file if exists
        if Path(filename).exists():
            logger.info(f"Using cached file: {filename}")
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
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio)",
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[ext=webm][acodec=opus]",
            }

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                return filename
            except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
                logger.warning(f"yt-dlp download error: {e}")
                return None
            except Exception as ex:
                logger.warning("Download failed: %s", ex)
                return None

        return await asyncio.to_thread(_download)

    async def close(self):
        """Clean up resources."""
        if self.api:
            await self.api.close()
