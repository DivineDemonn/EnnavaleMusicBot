import asyncio
import re
import aiohttp
import aiofiles
from anony import logger, config


class ArcApi:
    def __init__(self):
        self.base_url = config.ARC_API_URL.rstrip("/")
        self.api_key = config.ARC_API_KEY
        self.timeout = aiohttp.ClientTimeout(total=40)
        self.chunk_limit = 128 * 1024
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=self.timeout)

    async def _save_file(self, url: str, file_name: str) -> str | None:
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None
                fname = f"downloads/{file_name}"
                async with aiofiles.open(fname, "wb") as f:
                    async for chunk in resp.content.iter_chunked(self.chunk_limit):
                        if chunk:
                            await f.write(chunk)
                return fname
        except Exception as e:
            logger.error("ArcApi download save failed: %s", e)
            return None

    async def _poll_job(self, job_id: str, video: bool) -> str | None:
        retries = 15
        sleep_duration = 4
        req_url = f"{self.base_url}/youtube/jobStatus"
        params = {"api_key": self.api_key, "job_id": job_id}

        for _ in range(retries):
            try:
                async with self.session.get(req_url, params=params) as resp:
                    data = await resp.json()
            except Exception:
                await asyncio.sleep(sleep_duration)
                continue

            if data.get("status") != "success":
                await asyncio.sleep(sleep_duration)
                continue

            job = data.get("job", {})
            if job.get("status") != "done":
                await asyncio.sleep(sleep_duration)
                continue

            result = job.get("result", {})
            public_url = result.get("public_url")
            if public_url:
                ext = "mp4" if video else "mp3"
                return await self._save_file(public_url, f"{job_id}.{ext}")
            break
        return None

    async def download(self, video_id: str, video: bool = False) -> str | None:
        if not self.api_key:
            return None
        await self._get_session()

        query = video_id
        req_url = f"{self.base_url}/youtube/v2/download"
        params = {
            "api_key": self.api_key,
            "query": query,
            "isVideo": str(video).lower(),
        }

        try:
            async with self.session.get(req_url, params=params) as resp:
                data = await resp.json()
        except Exception as e:
            logger.error("ArcApi request failed: %s", e)
            return None

        # Immediate download URL?
        candidate = None
        job = data.get("job", {})
        if isinstance(job, dict):
            candidate = job.get("result", {}).get("public_url")
        if not candidate:
            result = data.get("result", {})
            if isinstance(result, dict):
                candidate = result.get("public_url")
        if not candidate:
            candidate = data.get("public_url")

        if candidate and "processing" not in candidate.lower() and "queued" not in candidate.lower():
            # Normalise URL (relative -> absolute)
            if not candidate.startswith("http"):
                candidate = self.base_url + candidate if candidate.startswith("/") else f"{self.base_url}/{candidate}"
            ext = "mp4" if video else "mp3"
            return await self._save_file(candidate, f"{video_id}.{ext}")

        # Job polling if status is queued/processing
        status = data.get("status", "").lower()
        if status in ("queued", "processing"):
            job_id = data.get("job_id") or (job.get("id") if isinstance(job, dict) else None)
            if job_id:
                return await self._poll_job(job_id, video)

        return None
