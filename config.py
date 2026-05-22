from os import getenv
from dotenv import load_dotenv

load_dotenv()

# ========== MODULE-LEVEL VARIABLES (for direct import) ==========
API_URL = getenv("SHRUTI_API_URL", "https://api.shrutibots.site")
API_KEY = getenv("SHRUTI_API_KEY", "ShrutiBotsguDA4JWhgxUcQYiwkfmg")

# ========== CONFIG CLASS (for other parts of your bot) ==========
class Config:
    def __init__(self):
        self.API_ID = int(getenv("API_ID", 0))
        self.API_HASH = getenv("API_HASH")

        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.MONGO_URL = getenv("MONGO_URL")

        self.LOGGER_ID = int(getenv("LOGGER_ID", 0))
        self.OWNER_ID = int(getenv("OWNER_ID", 0))

        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", 240)) * 60   # 4 hours
        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", 100))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", 100))

        self.SESSION1 = getenv("SESSION", None)
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/UnhealedNotes")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/DevilsHeavenMF")

        # Use the module-level variables
        self.API_URL = API_URL
        self.API_KEY = API_KEY

        self.AUTO_LEAVE: bool = getenv("AUTO_LEAVE", "False").lower() == "true"
        self.AUTO_END: bool = getenv("AUTO_END", "False").lower() == "true"
    
        self.THUMB_GEN: bool = getenv("THUMB_GEN", "True").lower() == "true"
        self.VIDEO_PLAY: bool = getenv("VIDEO_PLAY", "True").lower() == "true"

        self.LANG_CODE = getenv("LANG_CODE", "en")

        self.COOKIES_URL = [
            url for url in getenv("COOKIES_URL", "").split(" ")
            if url and "batbin.me" in url
        ]
        self.DEFAULT_THUMB = getenv("DEFAULT_THUMB", "https://te.legra.ph/file/3e40a408286d4eda24191.jpg")
        self.PING_IMG = getenv("PING_IMG", "https://graph.org/file/5a4ab4d41f53c49c58c96-72c3a68a254b13ba08.jpg")
        self.START_IMG = getenv("START_IMG", "https://graph.org/file/02f22d5f4ebb4c23492bc-916ac01b0bcd80384c.jpg")

    def check(self):
        missing = [
            var
            for var in ["API_ID", "API_HASH", "BOT_TOKEN", "MONGO_URL", "LOGGER_ID", "OWNER_ID", "SESSION1"]
            if not getattr(self, var)
        ]
        if missing:
            raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")
