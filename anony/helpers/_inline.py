# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

from pyrogram import types
from pyrogram.enums import ButtonStyle

from anony import app, config, lang
from anony.core.lang import lang_codes


class Inline:
    def __init__(self):
        self.ikm = types.InlineKeyboardMarkup
        self.ikb = types.InlineKeyboardButton

    # ==========================================
    # COMMON BUTTON
    # ==========================================

    def button(
        self,
        text: str,
        callback_data: str = None,
        url: str = None,
        copy_text: str = None,
        style=ButtonStyle.PRIMARY,
    ):
        return self.ikb(
            text=text,
            callback_data=callback_data,
            url=url,
            copy_text=copy_text,
            style=style,
        )

    # ==========================================
    # CANCEL DOWNLOAD
    # ==========================================

    def cancel_dl(self, text) -> types.InlineKeyboardMarkup:

        return self.ikm(
            [
                [
                    self.button(
                        text=text,
                        callback_data="cancel_dl",
                        style=ButtonStyle.DANGER,
                    )
                ]
            ]
        )

    # ==========================================
    # PLAYER CONTROLS
    # ==========================================

    def controls(
        self,
        chat_id: int,
        status: str = None,
        timer: str = None,
        remove: bool = False,
    ) -> types.InlineKeyboardMarkup:

        keyboard = []

        if status:
            keyboard.append(
                [
                    self.button(
                        text=status,
                        callback_data=f"controls status {chat_id}",
                        style=ButtonStyle.PRIMARY,
                    )
                ]
            )

        elif timer:
            keyboard.append(
                [
                    self.button(
                        text=timer,
                        callback_data=f"controls status {chat_id}",
                        style=ButtonStyle.PRIMARY,
                    )
                ]
            )

        if not remove:
            keyboard.append(
                [
                    self.button(
                        text="▷",
                        callback_data=f"controls resume {chat_id}",
                        style=ButtonStyle.SUCCESS,
                    ),
                    self.button(
                        text="II",
                        callback_data=f"controls pause {chat_id}",
                        style=ButtonStyle.PRIMARY,
                    ),
                    self.button(
                        text="⥁",
                        callback_data=f"controls replay {chat_id}",
                        style=ButtonStyle.PRIMARY,
                    ),
                    self.button(
                        text="‣‣I",
                        callback_data=f"controls skip {chat_id}",
                        style=ButtonStyle.PRIMARY,
                    ),
                    self.button(
                        text="▢",
                        callback_data=f"controls stop {chat_id}",
                        style=ButtonStyle.DANGER,
                    ),
                ]
            )

        return self.ikm(keyboard)

    # ==========================================
    # HELP MENU
    # ==========================================

    def help_markup(
        self,
        _lang: dict,
        back: bool = False,
    ) -> types.InlineKeyboardMarkup:

        if back:

            rows = [
                [
                    self.button(
                        text=_lang.get("back", "Back"),
                        callback_data="help back",
                        style=ButtonStyle.PRIMARY,
                    ),
                    self.button(
                        text=_lang.get("close", "Close"),
                        callback_data="help close",
                        style=ButtonStyle.DANGER,
                    ),
                ]
            ]

        else:

            cbs = [
                "admins",
                "auth",
                "blist",
                "lang",
                "ping",
                "play",
                "queue",
                "stats",
                "sudo",
            ]

            buttons = []

            for i, cb in enumerate(cbs):

                buttons.append(
                    self.button(
                        text=_lang.get(f"help_{i}", cb.title()),
                        callback_data=f"help {cb}",
                        style=ButtonStyle.PRIMARY,
                    )
                )

            rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]

        return self.ikm(rows)

    # ==========================================
    # LANGUAGE MENU
    # ==========================================

    def lang_markup(
        self,
        _lang: str,
    ) -> types.InlineKeyboardMarkup:

        langs = lang.get_languages()

        buttons = []

        for code, name in langs.items():

            buttons.append(
                self.button(
                    text=f"{name} ({code}) {'✔️' if code == _lang else ''}",
                    callback_data=f"lang_change {code}",
                    style=(
                        ButtonStyle.SUCCESS
                        if code == _lang
                        else ButtonStyle.PRIMARY
                    ),
                )
            )

        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]

        return self.ikm(rows)

    # ==========================================
    # PING BUTTON
    # ==========================================

    def ping_markup(self, text: str) -> types.InlineKeyboardMarkup:

        return self.ikm(
            [
                [
                    self.button(
                        text=text,
                        url=config.SUPPORT_CHAT,
                        style=ButtonStyle.SUCCESS,
                    )
                ]
            ]
        )

    # ==========================================
    # PLAY QUEUED
    # ==========================================

    def play_queued(
        self,
        chat_id: int,
        item_id: str,
        _text: str,
    ) -> types.InlineKeyboardMarkup:

        return self.ikm(
            [
                [
                    self.button(
                        text=_text,
                        callback_data=f"controls force {chat_id} {item_id}",
                        style=ButtonStyle.SUCCESS,
                    )
                ]
            ]
        )

    # ==========================================
    # QUEUE MARKUP
    # ==========================================

    def queue_markup(
        self,
        chat_id: int,
        _text: str,
        playing: bool,
    ) -> types.InlineKeyboardMarkup:

        action = "pause" if playing else "resume"

        return self.ikm(
            [
                [
                    self.button(
                        text=_text,
                        callback_data=f"controls {action} {chat_id} q",
                        style=ButtonStyle.PRIMARY,
                    )
                ]
            ]
        )

    # ==========================================
    # SETTINGS MENU
    # ==========================================

    def settings_markup(
        self,
        lang: dict,
        admin_only: bool,
        cmd_delete: bool,
        language: str,
        chat_id: int,
    ) -> types.InlineKeyboardMarkup:

        return self.ikm(
            [
                [
                    self.button(
                        text=f"{lang.get('play_mode', 'Play Mode')} ➜",
                        callback_data="settings",
                    ),
                    self.button(
                        text=str(admin_only),
                        callback_data="settings play",
                        style=ButtonStyle.SUCCESS,
                    ),
                ],
                [
                    self.button(
                        text=f"{lang.get('cmd_delete', 'Delete Cmd')} ➜",
                        callback_data="settings",
                    ),
                    self.button(
                        text=str(cmd_delete),
                        callback_data="settings delete",
                        style=ButtonStyle.SUCCESS,
                    ),
                ],
                [
                    self.button(
                        text=f"{lang.get('language', 'Language')} ➜",
                        callback_data="settings",
                    ),
                    self.button(
                        text=lang_codes.get(language, "English"),
                        callback_data="language",
                        style=ButtonStyle.SUCCESS,
                    ),
                ],
            ]
        )

    # ==========================================
    # START BUTTONS
    # ==========================================

    def start_key(
        self,
        lang: dict,
        private: bool = False,
    ) -> types.InlineKeyboardMarkup:

        rows = [
            [
                self.button(
                    text=lang.get("add_me", "Add Me"),
                    url=f"https://t.me/{app.username}?startgroup=true",
                    style=ButtonStyle.SUCCESS,
                )
            ],
            [
                self.button(
                    text=lang.get("help", "Help"),
                    callback_data="help",
                    style=ButtonStyle.PRIMARY,
                )
            ],
            [
                self.button(
                    text=lang.get("support", "Support"),
                    url=config.SUPPORT_CHAT,
                    style=ButtonStyle.PRIMARY,
                ),
                self.button(
                    text=lang.get("channel", "Channel"),
                    url=config.SUPPORT_CHANNEL,
                    style=ButtonStyle.PRIMARY,
                ),
            ],
        ]

        if private:

            rows.append(
                [
                    self.button(
                        text=lang.get("Owner", "Owner"),
                        url="https://wenb-330f3d7a3da4.herokuapp.com",
                        style=ButtonStyle.DANGER,
                    )
                ]
            )

        else:

            rows.append(
                [
                    self.button(
                        text=lang.get("language", "Language"),
                        callback_data="language",
                        style=ButtonStyle.SUCCESS,
                    )
                ]
            )

        return self.ikm(rows)

    # ==========================================
    # YOUTUBE BUTTONS
    # ==========================================

    def yt_key(self, link: str) -> types.InlineKeyboardMarkup:

        return self.ikm(
            [
                [
                    self.button(
                        text="❐",
                        copy_text=link,
                        style=ButtonStyle.SUCCESS,
                    ),
                    self.button(
                        text="Youtube",
                        url=link,
                        style=ButtonStyle.DANGER,
                    ),
                ],
            ]
        )
