# Copyright (c) 2026 CyberPixelPro
# Licensed under the MIT License.
# This file is part of AviaxMusic

import re
import asyncio

import aiohttp
import aiofiles


class NexGenApi:
    def __init__(
            self, api_url: str, api_key: str, video_api_url: str,
            retries: int = 10, timeout: int = 40,
        ):
        self.api_url = api_url
        self.video_api_url = video_api_url
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

    async def save_file(self, vid_id: str, url: str, video: bool = False) -> str | None:
        try:
            async with self.session.get(url) as resp:
                if resp.status != 200:
                    return None

                file_name = None
                cd = resp.headers.get("Content-Disposition")
                if cd:
                    match = re.search(r'filename="?(.+?)"?$', cd)
                    if match: file_name = match.group(1)
                else:
                    file_name = vid_id + (".mp4" if video else ".mp3")

                fname = f"downloads/{file_name}"
                async with aiofiles.open(fname, "wb") as f:
                    async for chunk in resp.content.iter_chunked(self.chunk_limit):
                        if chunk: await f.write(chunk)

                if video: self.v_cache[vid_id] = fname
                else: self.dl_cache[vid_id] = fname

                return fname
        except Exception:
            pass
        return None

    async def download(self, vid_id: str, video: bool = False) -> str | None:
        if video and vid_id in self.v_cache:
            return self.v_cache[vid_id]
        elif not video and vid_id in self.dl_cache:
            return self.dl_cache[vid_id]

        # Shruti API endpoint format
        if video:
            endp = f"{self.video_api_url}/download?url={vid_id}&type=video&api_key={self.api_key}"
        else:
            endp = f"{self.api_url}/download?url={vid_id}&type=audio&api_key={self.api_key}"

        for _ in range(self.retries):
            try:
                async with self.session.get(endp, headers=self.headers) as resp:
                    # Shruti API might return direct download or JSON
                    content_type = resp.headers.get('Content-Type', '')
                    
                    if 'application/json' in content_type:
                        data = await resp.json()
                        if resp.status != 200:
                            return None
                        
                        status = data.get("status")
                        dl_link = data.get("link") or data.get("url")
                        
                        if status == "done" or dl_link:
                            if not dl_link:
                                return None
                            return await self.save_file(vid_id, dl_link, video)
                        elif status == "downloading":
                            await asyncio.sleep(4)
                            continue
                        else:
                            break
                    else:
                        # Direct file download
                        if resp.status == 200:
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
                        else:
                            return None
            except Exception:
                break
        return None
