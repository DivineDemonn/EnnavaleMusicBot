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
from anony import logger


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
        
        logger.info(f"API Status - Primary (YTProxy): {'✓ Available' if self.primary_available else '✗ Not configured'}")
        logger.info(f"API Status - Secondary (Shruti): {'✓ Available' if self.secondary_available else '✗ Not configured'}")

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
                    logger.warning(f"Save file failed: HTTP {resp.status}")
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

                logger.info(f"✓ File saved: {fname}")
                return fname
        except Exception as e:
            logger.error(f"Save file error: {e}")
        return None

    # ================================================================
    # PRIMARY API – YTProxy (xBit / similar)
    # ================================================================
    async def _download_primary(self, vid_id: str, video: bool = False) -> str | None:
        """Download using primary YTProxy API."""
        if not self.primary_available:
            logger.warning("⏭ Primary API not configured, skipping...")
            return None

        logger.info(f"🔵 [PRIMARY] Trying YTProxy API for {vid_id}...")
        
        headers = {
            "x-api-key": self.yt_api_key,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            api_url = f"{self.ytproxy_url}/info/{vid_id}"
            logger.info(f"🔵 [PRIMARY] Requesting: {api_url}")
            
            async with self.session.get(api_url, headers=headers, timeout=60) as resp:
                logger.info(f"🔵 [PRIMARY] Response status: {resp.status}")
                
                if resp.status != 200:
                    logger.warning(f"🔵 [PRIMARY] Failed: HTTP {resp.status}")
                    return None
                
                data = await resp.json()
                logger.info(f"🔵 [PRIMARY] Response data status: {data.get('status')}")
                
                if data.get('status') != 'success':
                    logger.warning(f"🔵 [PRIMARY] API error: {data.get('message', 'Unknown')}")
                    return None
                
                # Get download URL
                dl_url = data.get('video_url') if video else data.get('audio_url')
                if not dl_url:
                    logger.warning("🔵 [PRIMARY] No download URL in response")
                    return None
                
                logger.info(f"🔵 [PRIMARY] Download URL obtained, downloading...")
                
                # Determine file extension
                ext = "mp4" if video else "mp3"
                
                # Download file
                result = await self.save_file(vid_id, dl_url, video, ext)
                if result:
                    logger.info(f"✅ [PRIMARY] Successfully downloaded via YTProxy: {vid_id}")
                return result
                
        except asyncio.TimeoutError:
            logger.error("🔵 [PRIMARY] Timeout error")
        except aiohttp.ClientError as e:
            logger.error(f"🔵 [PRIMARY] Network error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"🔵 [PRIMARY] Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"🔵 [PRIMARY] Unexpected error: {type(e).__name__}: {e}")
        
        return None

    # ================================================================
    # SECONDARY API – Shruti
    # ================================================================
    async def _download_secondary(self, vid_id: str, video: bool = False) -> str | None:
        """Download using secondary Shruti API."""
        if not self.secondary_available:
            logger.warning("⏭ Secondary API not configured, skipping...")
            return None

        logger.info(f"🟠 [SECONDARY] Trying Shruti API for {vid_id}...")

        if video:
            endp = f"{self.shruti_api_url}/download?url={vid_id}&type=video&api_key={self.shruti_api_key}"
        else:
            endp = f"{self.shruti_api_url}/download?url={vid_id}&type=audio&api_key={self.shruti_api_key}"

        for attempt in range(self.retries):
            try:
                logger.info(f"🟠 [SECONDARY] Attempt {attempt + 1}/{self.retries}")
                
                async with self.session.get(endp, headers=self.headers) as resp:
                    content_type = resp.headers.get('Content-Type', '')
                    logger.info(f"🟠 [SECONDARY] Content-Type: {content_type}")
                    
                    if 'application/json' in content_type:
                        data = await resp.json()
                        logger.info(f"🟠 [SECONDARY] Response: {data}")
                        
                        if resp.status != 200:
                            logger.warning(f"🟠 [SECONDARY] HTTP {resp.status}")
                            return None
                        
                        status = data.get("status")
                        dl_link = data.get("link") or data.get("url")
                        
                        if (status == "done" or dl_link) and dl_link:
                            logger.info(f"🟠 [SECONDARY] Download link obtained")
                            result = await self.save_file(vid_id, dl_link, video)
                            if result:
                                logger.info(f"✅ [SECONDARY] Successfully downloaded via Shruti: {vid_id}")
                            return result
                        elif status == "downloading":
                            logger.info("🟠 [SECONDARY] Video still processing, waiting...")
                            await asyncio.sleep(4)
                            continue
                        else:
                            logger.warning(f"🟠 [SECONDARY] Unknown status: {status}")
                            break
                    else:
                        # Direct file download
                        if resp.status == 200:
                            logger.info("🟠 [SECONDARY] Direct file download")
                            ext = "mp4" if video else "mp3"
                            result = await self.save_file(vid_id, str(resp.url), video, ext)
                            if result:
                                logger.info(f"✅ [SECONDARY] Successfully downloaded via Shruti: {vid_id}")
                            return result
                        else:
                            logger.warning(f"🟠 [SECONDARY] HTTP {resp.status}")
                            return None
            except asyncio.TimeoutError:
                logger.error(f"🟠 [SECONDARY] Timeout on attempt {attempt + 1}")
            except Exception as e:
                logger.error(f"🟠 [SECONDARY] Error on attempt {attempt + 1}: {type(e).__name__}: {e}")
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
            logger.info(f"📦 Cache hit (video): {vid_id}")
            return self.v_cache[vid_id]
        elif not video and vid_id in self.dl_cache:
            logger.info(f"📦 Cache hit (audio): {vid_id}")
            return self.dl_cache[vid_id]

        await self.get_session()

        # --- Attempt 1: Primary API ---
        try:
            result = await self._download_primary(vid_id, video)
            if result:
                return result
            logger.warning("⚠️ Primary API failed, falling back to Secondary API...")
        except Exception as e:
            logger.error(f"Primary API exception: {e}")

        # --- Attempt 2: Secondary API (Fallback) ---
        try:
            result = await self._download_secondary(vid_id, video)
            if result:
                return result
            logger.warning("⚠️ Secondary API also failed")
        except Exception as e:
            logger.error(f"Secondary API exception: {e}")

        return None
