# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import re

from pyrogram import enums, types

from anony import app


class Utilities:
    def __init__(self):
        pass

    # =========================
    # FORMAT ETA
    # =========================
    def format_eta(self, seconds: int) -> str:

        seconds = int(seconds)

        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if days > 0:
            return f"{days}d {hours}h {minutes}m"

        elif hours > 0:
            return f"{hours}h {minutes}m {secs}s"

        elif minutes > 0:
            return f"{minutes}m {secs}s"

        else:
            return f"{secs}s"

    # =========================
    # FORMAT FILE SIZE
    # =========================
    def format_size(self, bytes: int) -> str:

        bytes = float(bytes)

        kb = 1024
        mb = kb * 1024
        gb = mb * 1024
        tb = gb * 1024

        if bytes >= tb:
            return f"{bytes / tb:.2f} TB"

        elif bytes >= gb:
            return f"{bytes / gb:.2f} GB"

        elif bytes >= mb:
            return f"{bytes / mb:.2f} MB"

        elif bytes >= kb:
            return f"{bytes / kb:.2f} KB"

        else:
            return f"{bytes:.2f} B"

    # =========================
    # TIME TO SECONDS
    # =========================
    def to_seconds(self, time: str) -> int:

        try:
            parts = list(map(int, time.strip().split(":")))

            if len(parts) == 3:
                h, m, s = parts
                return h * 3600 + m * 60 + s

            elif len(parts) == 2:
                m, s = parts
                return m * 60 + s

            elif len(parts) == 1:
                return parts[0]

        except Exception:
            return 0

        return 0

    # =========================
    # GET URL
    # =========================
    def get_url(self, message_1: types.Message) -> str | None:

        link = None
        messages = [message_1]

        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:

            entities = message.entities or message.caption_entities or []

            for entity in entities:

                if entity.type == enums.MessageEntityType.TEXT_LINK:
                    link = entity.url
                    break

                elif entity.type == enums.MessageEntityType.URL:

                    text = message.text or message.caption

                    if not text:
                        continue

                    link = text[
                        entity.offset : entity.offset + entity.length
                    ]

                    break

            if link:
                break

        if link:
            return (
                link.split("&si")[0]
                .split("?si")[0]
                .strip()
            )

        return None

    # =========================
    # EXTRACT USER
    # =========================
    async def extract_user(
        self,
        msg: types.Message,
    ) -> types.User | None:

        if msg.reply_to_message:
            return msg.reply_to_message.from_user

        if msg.entities:
            for e in msg.entities:

                if e.type == enums.MessageEntityType.TEXT_MENTION:
                    return e.user

        if msg.text:
            try:

                # Username
                if m := re.search(r"@(\w{5,32})", msg.text):
                    return await app.get_users(m.group(0))

                # User ID
                if m := re.search(r"\b\d{5,15}\b", msg.text):
                    return await app.get_users(int(m.group(0)))

            except Exception:
                pass

        return None

    # =========================
    # PLAY LOG
    # =========================
    async def play_log(
        self,
        m: types.Message,
        link: str,
        title: str,
        duration: str,
    ) -> None:

        if m.chat.id == app.logger:
            return

        _text = m.lang["play_log"].format(
            app.name,
            m.chat.id,
            m.chat.title,
            m.from_user.id,
            m.from_user.mention,
            link,
            title,
            duration,
        )

        await app.send_message(
            chat_id=app.logger,
            text=_text,
            disable_web_page_preview=True,
        )

    # =========================
    # SEND LOG
    # =========================
    async def send_log(
        self,
        m: types.Message,
        chat: bool = False,
    ) -> None:

        if chat:

            user = m.from_user

            return await app.send_message(
                chat_id=app.logger,
                text=m.lang["log_chat"].format(
                    m.chat.id,
                    m.chat.title,
                    user.id if user else 0,
                    user.mention if user else "Anonymous",
                ),
            )

        await app.send_message(
            chat_id=app.logger,
            text=m.lang["log_user"].format(
                m.from_user.id,
                f"@{m.from_user.username}"
                if m.from_user.username
                else "No Username",
                m.from_user.mention,
            ),
        )
