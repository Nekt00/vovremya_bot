from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonCommands,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from medication_reminder.telegram.ui import (
    ADD,
    BACK,
    CALENDAR,
    DONE,
    HISTORY,
    MEDICATION,
    PRIMARY_STYLE,
    SETS,
    SETTINGS,
    SUCCESS_STYLE,
)

TIMEZONE_PRESETS: tuple[str, ...] = (
    "Europe/Moscow",
    "Europe/Kaliningrad",
    "Asia/Yekaterinburg",
    "Asia/Novosibirsk",
    "Asia/Vladivostok",
)

TODAY_BUTTON = f"{CALENDAR} Сегодня"
ADD_BUTTON = f"{ADD} Добавить"
REGIMENS_BUTTON = f"{MEDICATION} Курсы"
HISTORY_BUTTON = f"{HISTORY} История"
SETS_BUTTON = f"{SETS} Наборы"
SETTINGS_BUTTON = f"{SETTINGS} Настройки"
FAMILY_BUTTON = "👨‍👩‍👧 Семья"


def bot_menu_button(mini_app_url: str | None) -> MenuButtonWebApp | MenuButtonCommands:
    if mini_app_url is None:
        return MenuButtonCommands()
    return MenuButtonWebApp(
        text="Открыть Вовремя",
        web_app=WebAppInfo(url=mini_app_url),
    )


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=TODAY_BUTTON, style=PRIMARY_STYLE)],
        [KeyboardButton(text=REGIMENS_BUTTON), KeyboardButton(text=ADD_BUTTON)],
        [KeyboardButton(text=SETS_BUTTON), KeyboardButton(text=HISTORY_BUTTON)],
        [KeyboardButton(text=FAMILY_BUTTON), KeyboardButton(text=SETTINGS_BUTTON)],
    ]
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )


def timezone_keyboard(mini_app_url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=timezone, callback_data=f"tz:{timezone}")]
        for timezone in TIMEZONE_PRESETS
    ]
    if mini_app_url is not None:
        rows.insert(
            0,
            [
                InlineKeyboardButton(
                    text="📍 Определить автоматически",
                    web_app=WebAppInfo(url=mini_app_url),
                )
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_keyboard(*, repeat_minutes: int, enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "🔕 Выключить напоминания" if enabled else "🔔 Включить напоминания"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌍 Изменить часовой пояс", callback_data="settings:tz")],
            [
                InlineKeyboardButton(
                    text=f"{f'{DONE} ' if repeat_minutes == value else ''}{value} мин",
                    callback_data=f"settings:repeat:{value}",
                    style=PRIMARY_STYLE if repeat_minutes == value else None,
                )
                for value in (15, 30, 60)
            ],
            [
                InlineKeyboardButton(
                    text=toggle_text,
                    callback_data=f"settings:enabled:{0 if enabled else 1}",
                    style=None if enabled else SUCCESS_STYLE,
                )
            ],
            [InlineKeyboardButton(text=f"{BACK} В главное меню", callback_data="nav:today")],
        ]
    )
