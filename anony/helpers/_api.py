# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import re
import asyncio
import aiohttp
import aiofiles
from anony import logger


class ArcApi:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        retries: int = 10,
        timeout: int = 40,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.chunk_limit = 128 * 1024
        self.dl_cache = {}
        self.v_cache = {}
        self.retries = retries
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: aiohttp.ClientSession | None = None
        self.headers = {"Accept": "application/json"}

    async def get_session(self) -> None:
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def _poll_job(self, job_id: str) -> str | None:
        """Poll /youtube/jobStatus until status is 'done' and return public_url."""
        url = f"{self.api_url}/youtube/jobStatus"
        params = {"api_key": self.api_key, "job_id": job_id}
        for _ in range(self.retries):
            try:
                async with self.session.get(url, params=params, headers=self.headers) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(3)
                        continue
                    data = await resp.json()
            except Exception:
                await asyncio.sleep(3)
                continue

            status = data.get("status", "")
            if status != "success":
                await asyncio.sleep(3)
                continue

            job = data.get("job", {})
            if isinstance(job, dict) and job.get("status") == "done":
                result = job.get("result", {})
                if isinstance(result, dict):
                    pub_url = result.get("public_url")
                    if pub_url:
                        return pub_url
            await asyncio.sleep(3)
        return None

    async def _get_download_link(self, vid_id: str, video: bool) -> str | None:
        """Call the v2 download endpoint and return the final public URL."""
        url = f"{self.api_url}/youtube/v2/download"
        params = {
            "api_key": self.api_key,
            "query": vid_id,
            "isVideo": str(video).lower(),
        }
        for _ in range(self.retries):
            try:
                async with self.session.get(url, params=params, headers=self.headers) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(2)
                        continue
                    data = await resp.json()
            except Exception:
                await asyncio.sleep(2)
                continue

            # Direct public_url in response
            candidate = data.get("public_url")
            if candidate and "processing" not in candidate.lower() and "queued" not in candidate.lower():
                return candidate

            # Check job object
            job = data.get("job", {})
            if isinstance(job, dict):
                result = job.get("result", {})
                if isinstance(result, dict):
                    pub_url = result.get("public_url")
                    if pub_url:
                        return pub_url
                job_id = job.get("id")
                if job_id and job.get("status") in ("queued", "processing"):
                    pub_url = await self._poll_job(job_id)
                    if pub_url:
                        return pub_url

            # Last resort: any public_url anywhere
            for key in ("public_url", "download_url"):
                val = data.get(key)
                if val and "processing" not in val.lower() and "queued" not in val.lower():
                    return val

            await asyncio.sleep(2)
        return None

    async def save_file(self, vid_id: str, url: str, video: bool = False) -> str | None:
        """Download the file from the given URL and return the local path."""
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None

                # Determine filename from headers or fallback
                file_name = None
                cd = resp.headers.get("Content-Disposition")
                if cd:
                    match = re.search(r'filename="?(.+?)"?$', cd)
                    if match:
                        file_name = match.group(1)
                if not file_name:
                    file_name = vid_id + (".mp4" if video else ".mp3")

                fname = f"downloads/{file_name}"
                async with aiofiles.open(fname, "wb") as f:
                    async for chunk in resp.content.iter_chunked(self.chunk_limit):
                        if chunk:
                            await f.write(chunk)

                # Update cache
                if video:
                    self.v_cache[vid_id] = fname
                else:
                    self.dl_cache[vid_id] = fname

                return fname
        except Exception as e:
            logger.warning("ArcApi save_file error: %s", e)
        return None

    async def download(self, vid_id: str, video: bool = False) -> str | None:
        """Main entry point – get download link, then save file."""
        # Check cache first
        if video and vid_id in self.v_cache:
            return self.v_cache[vid_id]
        elif not video and vid_id in self.dl_cache:
            return self.dl_cache[vid_id]

        await self.get_session()
        dl_link = await self._get_download_link(vid_id, video)
        if not dl_link:
            return None

        return await self.save_file(vid_id, dl_link, video)
