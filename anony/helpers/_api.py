# anony/helpers/_api.py
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
        url = f"{self.api_url}/youtube/jobStatus"
        params = {"api_key": self.api_key, "job_id": job_id}
        logger.info(f"ArcApi: Polling job {job_id}")
        for attempt in range(self.retries):
            try:
                async with self.session.get(url, params=params, headers=self.headers) as resp:
                    data = await resp.json()
                    logger.info(f"ArcApi: Poll attempt {attempt+1}: status={resp.status}, data={data}")
                    if resp.status != 200:
                        await asyncio.sleep(3)
                        continue
                    status = data.get("status", "")
                    if status != "success":
                        await asyncio.sleep(3)
                        continue
                    job = data.get("job", {})
                    if isinstance(job, dict) and job.get("status") == "done":
                        result = job.get("result", {})
                        pub_url = result.get("public_url") if isinstance(result, dict) else None
                        if pub_url:
                            logger.info(f"ArcApi: Poll success, public_url={pub_url}")
                            return pub_url
            except Exception as e:
                logger.warning(f"ArcApi: Poll exception: {e}")
                await asyncio.sleep(3)
        logger.warning(f"ArcApi: Poll exhausted for job {job_id}")
        return None

    async def _get_download_link(self, vid_id: str, video: bool) -> str | None:
        url = f"{self.api_url}/youtube/v2/download"
        params = {
            "api_key": self.api_key,
            "query": vid_id,
            "isVideo": str(video).lower(),
        }
        logger.info(f"ArcApi: Requesting {url} with params {params}")
        for attempt in range(self.retries):
            try:
                async with self.session.get(url, params=params, headers=self.headers) as resp:
                    # Attempt to read JSON, but also log raw text if it fails
                    try:
                        data = await resp.json()
                    except Exception:
                        text = await resp.text()
                        logger.error(f"ArcApi: Invalid JSON response (status {resp.status}): {text}")
                        await asyncio.sleep(2)
                        continue

                    logger.info(f"ArcApi: Attempt {attempt+1} -> status={resp.status}, data={data}")

                    if resp.status != 200:
                        await asyncio.sleep(2)
                        continue

                    # Direct public_url or similar
                    for key in ("public_url", "download_url", "link"):
                        val = data.get(key)
                        if isinstance(val, str) and val.strip():
                            candidate = self._normalize_url(val.strip())
                            if "processing" not in candidate.lower() and "queued" not in candidate.lower():
                                logger.info(f"ArcApi: Found direct URL: {candidate}")
                                return candidate

                    # Job object
                    job = data.get("job", {})
                    if isinstance(job, dict):
                        result = job.get("result", {})
                        if isinstance(result, dict):
                            pub_url = result.get("public_url")
                            if pub_url:
                                pub_url = self._normalize_url(pub_url)
                                logger.info(f"ArcApi: URL from job.result: {pub_url}")
                                return pub_url
                        job_id = job.get("id")
                        job_status = job.get("status", "")
                        if job_id and job_status in ("queued", "processing"):
                            pub_url = await self._poll_job(job_id)
                            if pub_url:
                                return pub_url

                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"ArcApi: Request exception: {e}")
                await asyncio.sleep(2)
        return None

    def _normalize_url(self, url: str) -> str:
        if url.startswith("http://") or url.startswith("https://"):
            return url
        if url.startswith("/"):
            return self.api_url + url
        return f"{self.api_url}/{url}"

    async def save_file(self, vid_id: str, url: str, video: bool = False) -> str | None:
        logger.info(f"ArcApi: Downloading file from {url}")
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    logger.warning(f"ArcApi: File download HTTP {resp.status}")
                    return None

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

                if video:
                    self.v_cache[vid_id] = fname
                else:
                    self.dl_cache[vid_id] = fname
                logger.info(f"ArcApi: File saved: {fname}")
                return fname
        except Exception as e:
            logger.warning(f"ArcApi: save_file error: {e}")
        return None

    async def download(self, vid_id: str, video: bool = False) -> str | None:
        if video and vid_id in self.v_cache:
            return self.v_cache[vid_id]
        elif not video and vid_id in self.dl_cache:
            return self.dl_cache[vid_id]

        await self.get_session()
        dl_link = await self._get_download_link(vid_id, video)
        if not dl_link:
            return None

        return await self.save_file(vid_id, dl_link, video)
