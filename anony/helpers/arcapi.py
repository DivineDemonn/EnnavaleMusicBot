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
        self.max_retries = 15
        self.poll_interval = 4  # seconds

    async def get_session(self):
        """Public method to initialize the session."""
        await self._get_session()

    async def _get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36",
                    "Accept": "application/json",
                }
            )

    async def close(self):
        """Close the session properly."""
        if self.session:
            await self.session.close()
            self.session = None

    async def _save_file(self, url: str, file_name: str) -> str | None:
        """Download and save file from URL."""
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    logger.error(f"ArcApi download failed with status: {resp.status}")
                    return None
                
                fname = f"downloads/{file_name}"
                async with aiofiles.open(fname, "wb") as f:
                    async for chunk in resp.content.iter_chunked(self.chunk_limit):
                        if chunk:
                            await f.write(chunk)
                
                logger.info(f"ArcApi successfully saved: {fname}")
                return fname
        except Exception as e:
            logger.error("ArcApi download save failed: %s", e)
            return None

    async def _poll_job(self, job_id: str, video: bool) -> str | None:
        """Poll job status until completion or timeout."""
        req_url = f"{self.base_url}/youtube/jobStatus"
        params = {"api_key": self.api_key, "job_id": job_id}

        for attempt in range(self.max_retries):
            try:
                async with self.session.get(req_url, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"ArcApi poll attempt {attempt + 1} failed with status: {resp.status}")
                        await asyncio.sleep(self.poll_interval)
                        continue
                    
                    data = await resp.json()
            except Exception as e:
                logger.error(f"ArcApi poll attempt {attempt + 1} error: {e}")
                await asyncio.sleep(self.poll_interval)
                continue

            # Check response structure
            status = data.get("status", "").lower()
            if status != "success":
                logger.warning(f"ArcApi poll: job status not success: {status}")
                await asyncio.sleep(self.poll_interval)
                continue

            # Check job status
            job = data.get("job", {})
            job_status = job.get("status", "").lower()
            
            if job_status == "done":
                result = job.get("result", {})
                public_url = result.get("public_url")
                if public_url:
                    ext = "mp4" if video else "mp3"
                    filename = f"{job_id}.{ext}"
                    return await self._save_file(public_url, filename)
                else:
                    logger.error("ArcApi job done but no public_url found")
                    return None
            elif job_status in ("failed", "error"):
                logger.error(f"ArcApi job failed: {job.get('error', 'Unknown error')}")
                return None
            else:
                # Still processing
                logger.info(f"ArcApi job {job_id} status: {job_status} (attempt {attempt + 1})")
                await asyncio.sleep(self.poll_interval)

        logger.error(f"ArcApi poll timeout after {self.max_retries} attempts")
        return None

    async def _make_request(self, endpoint: str, params: dict) -> dict | None:
        """Make API request with proper error handling."""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            async with self.session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"ArcApi request failed: {resp.status} for {url}")
                    return None
                
                content_type = resp.headers.get("Content-Type", "")
                if "application/json" not in content_type:
                    logger.error(f"ArcApi unexpected content type: {content_type}")
                    return None
                
                return await resp.json()
        except aiohttp.ClientError as e:
            logger.error(f"ArcApi request error: {e}")
            return None
        except Exception as e:
            logger.error(f"ArcApi unexpected error: {e}")
            return None

    async def download(self, video_id: str, video: bool = False) -> str | None:
        """
        Download video/audio using Arc API.
        
        Args:
            video_id: YouTube video ID or URL
            video: True for video download, False for audio only
            
        Returns:
            Path to downloaded file or None if failed
        """
        if not self.api_key or not self.base_url:
            logger.warning("Arc API not configured (missing API key or URL)")
            return None
        
        await self._get_session()

        # Try different endpoint formats to be compatible with various API versions
        endpoints = [
            "youtube/v2/download",
            "youtube/download",
            "download/youtube",
        ]
        
        params = {
            "api_key": self.api_key,
            "query": video_id,
            "isVideo": str(video).lower(),
        }

        for endpoint in endpoints:
            data = await self._make_request(endpoint, params)
            if not data:
                continue

            # Check for immediate download URL
            public_url = None
            job_id = None

            # Try different response formats
            # Format 1: { "status": "success", "result": { "public_url": "..." } }
            if data.get("status") == "success":
                result = data.get("result", {})
                if isinstance(result, dict):
                    public_url = result.get("public_url")
                    if not public_url:
                        # Maybe nested differently
                        public_url = result.get("download_url") or result.get("url")

            # Format 2: { "job": { "result": { "public_url": "..." } } }
            if not public_url:
                job = data.get("job", {})
                if isinstance(job, dict):
                    public_url = job.get("result", {}).get("public_url")
                    job_id = job.get("id") or data.get("job_id")

            # Format 3: Direct URL in response
            if not public_url:
                public_url = data.get("public_url") or data.get("download_url") or data.get("url")

            if public_url:
                # Normalize URL
                if not public_url.startswith("http"):
                    public_url = f"{self.base_url}/{public_url.lstrip('/')}"
                
                ext = "mp4" if video else "mp3"
                filename = f"{video_id}.{ext}"
                result = await self._save_file(public_url, filename)
                if result:
                    return result

            # Check if we need to poll
            status = data.get("status", "").lower()
            job_status = data.get("job", {}).get("status", "").lower()
            
            if status in ("queued", "processing") or job_status in ("queued", "processing"):
                if not job_id:
                    job_id = data.get("job_id") or data.get("id")
                    if not job_id and isinstance(data.get("job"), dict):
                        job_id = data.get("job", {}).get("id")
                
                if job_id:
                    logger.info(f"ArcApi starting poll for job: {job_id}")
                    return await self._poll_job(job_id, video)

        logger.error(f"ArcApi failed to download {video_id} with all endpoints")
        return None

    async def get_info(self, video_id: str) -> dict | None:
        """
        Get video information from Arc API.
        
        Args:
            video_id: YouTube video ID or URL
            
        Returns:
            Dictionary with video information or None
        """
        if not self.api_key:
            return None
        
        await self._get_session()

        endpoints = [
            "youtube/info",
            "youtube/v2/info",
        ]
        
        params = {
            "api_key": self.api_key,
            "query": video_id,
        }

        for endpoint in endpoints:
            data = await self._make_request(endpoint, params)
            if data and data.get("status") == "success":
                return data.get("result") or data
        
        return None
