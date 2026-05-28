# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic (V2 – High Quality Audio Edition)

import re
import asyncio
import json
import aiohttp
import aiofiles
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class NexGenApi:
    """Primary & Secondary API handler with fallback support."""
    
    def __init__(
            self,
            # Primary API (YTProxy)
            ytproxy_url: str,
            yt_api_key: str,
            # Secondary API (Shruti)
            shruti_api_url: str,
            shruti_api_key: str,
            retries: int = 3,
            timeout: int = 40,
        ):
        # Primary API config
        self.ytproxy_url = ytproxy_url
        self.yt_api_key = yt_api_key
        
        # Secondary API config
        self.shruti_api_url = shruti_api_url
        self.shruti_api_key = shruti_api_key
        
        self.chunk_limit = 128 * 1024
        self.dl_cache = {}
        self.v_cache = {}
        self.retries = retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: aiohttp.ClientSession | None = None
        self.headers = {"Accept": "application/json"}
        
        # Track which API is working
        self.primary_available = bool(ytproxy_url and yt_api_key)
        self.secondary_available = bool(shruti_api_url and shruti_api_key)

    async def get_session(self) -> None:
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def close_session(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None

    def _create_requests_session(self):
        """Create a requests session with retry logic."""
        session = requests.Session()
        retries = Retry(total=3, backoff_factor=0.1)
        session.mount('http://', HTTPAdapter(max_retries=retries))
        session.mount('https://', HTTPAdapter(max_retries=retries))
        return session

    async def save_file(self, vid_id: str, url: str, video: bool = False, ext: str = None) -> str | None:
        """Save downloaded file from URL."""
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None

                file_name = None
                cd = resp.headers.get("Content-Disposition")
                if cd:
                    match = re.search(r'filename="?(.+?)"?$', cd)
                    if match:
                        file_name = match.group(1)
                
                if not file_name:
                    if ext:
                        file_name = f"{vid_id}.{ext}"
                    else:
                        file_name = vid_id + (".mp4" if video else ".mp3")

                fname = f"downloads/{file_name}"
                async with aiofiles.open(fname, "wb") as f:
                    async for chunk in resp.content.iter_chunked(self.chunk_limit):
                        if chunk:
                            await f.write(chunk)

                if video:
                    self.v_cache[vid_id] = fname
                else:
                    self.dl_cache[vid_id] = fname

                return fname
        except Exception:
            pass
        return None

    # ================================================================
    # PRIMARY API – YTProxy (xBit / similar)
    # ================================================================
    async def _download_primary(self, vid_id: str, video: bool = False) -> str | None:
        """Download using primary YTProxy API."""
        if not self.primary_available:
            return None

        headers = {
            "x-api-key": self.yt_api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            # Get video/audio info from YTProxy
            async with self.session.get(
                f"{self.ytproxy_url}/info/{vid_id}",
                headers=headers,
                timeout=60
            ) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                
                if data.get('status') != 'success':
                    return None
                
                # Get download URL
                dl_url = data.get('video_url') if video else data.get('audio_url')
                if not dl_url:
                    return None
                
                # Determine file extension
                ext = "mp4" if video else "mp3"
                
                # Download file
                return await self.save_file(vid_id, dl_url, video, ext)
                
        except Exception as e:
            return None

    # ================================================================
    # SECONDARY API – Shruti
    # ================================================================
    async def _download_secondary(self, vid_id: str, video: bool = False) -> str | None:
        """Download using secondary Shruti API."""
        if not self.secondary_available:
            return None

        if video:
            endp = f"{self.shruti_api_url}/download?url={vid_id}&type=video&api_key={self.shruti_api_key}"
        else:
            endp = f"{self.shruti_api_url}/download?url={vid_id}&type=audio&api_key={self.shruti_api_key}"

        for _ in range(self.retries):
            try:
                async with self.session.get(endp, headers=self.headers) as resp:
                    content_type = resp.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        data = await resp.json()
                        if resp.status != 200:
                            return None
                        
                        status = data.get("status")
                        dl_link = data.get("link") or data.get("url")
                        
                        if (status == "done" or dl_link) and dl_link:
                            return await self.save_file(vid_id, dl_link, video)
                        elif status == "downloading":
                            await asyncio.sleep(4)
                            continue
                        else:
                            break
                    else:
                        # Direct file download
                        if resp.status == 200:
                            ext = "mp4" if video else "mp3"
                            return await self.save_file(vid_id, str(resp.url), video, ext)
                        else:
                            return None
            except Exception:
                break
        return None

    # ================================================================
    # MAIN DOWNLOAD WITH FALLBACK
    # ================================================================
    async def download(self, vid_id: str, video: bool = False) -> str | None:
        """
        Download with fallback chain:
          1. Primary API (YTProxy)
          2. Secondary API (Shruti) – if primary fails
        """
        # Check cache
        if video and vid_id in self.v_cache:
            return self.v_cache[vid_id]
        elif not video and vid_id in self.dl_cache:
            return self.dl_cache[vid_id]

        await self.get_session()

        # --- Attempt 1: Primary API ---
        try:
            result = await self._download_primary(vid_id, video)
            if result:
                return result
        except Exception:
            pass

        # --- Attempt 2: Secondary API (Fallback) ---
        try:
            result = await self._download_secondary(vid_id, video)
            if result:
                return result
        except Exception:
            pass

        return None
