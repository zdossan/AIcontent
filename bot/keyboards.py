"""Инлайн пернетақталар."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot import texts
from bot.store import Drama


def catalog_kb(dramas: list[Drama], paid_ids: set[int]) -> InlineKeyboardMarkup:
    """Сериалдар тізімі. Сатып алынғандар ✅ белгісімен."""
    rows = [
        [InlineKeyboardButton(
            text=f"{d.title} ✅" if d.id in paid_ids else d.title,
            callback_data=f"drama:{d.id}")]
        for d in dramas
    ]
    rows.append([InlineKeyboardButton(text=texts.BTN_MY, callback_data="my")])
    rows.append([InlineKeyboardButton(text=texts.BTN_HELP, callback_data="help")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def drama_kb(drama: Drama, is_paid: bool) -> InlineKeyboardMarkup:
    """Сериал картасы: тегін көру, төлеу, артқа."""
    rows = [[InlineKeyboardButton(text=texts.BTN_FREE,
                                  callback_data=f"free:{drama.id}")]]
    if not is_paid:
        rows.append([InlineKeyboardButton(
            text=texts.BTN_PAY.format(price=drama.price_kzt),
            callback_data=f"pay:{drama.id}")])
    rows.append([InlineKeyboardButton(text=texts.BTN_BACK, callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def pay_kb(drama: Drama) -> InlineKeyboardMarkup:
    """Тегін бөлімдерден кейінгі төлем түймесі."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_PAY.format(price=drama.price_kzt),
                              callback_data=f"pay:{drama.id}")],
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data="back")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data="back")]])


def kaspi_kb(url: str) -> InlineKeyboardMarkup:
    """Kaspi төлем сілтемесі."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_PAY_NOW, url=url)]])


def new_link_kb(drama_id: int) -> InlineKeyboardMarkup:
    """Сілтеме ескіргенде - жаңасын сұрау."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_NEW_LINK,
                              callback_data=f"pay:{drama_id}")],
        [InlineKeyboardButton(text=texts.BTN_BACK, callback_data="back")]])


def retry_kb(drama_id: int) -> InlineKeyboardMarkup:
    """Сілтеме жасалмағанда - қайталау."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts.BTN_RETRY,
                              callback_data=f"access:{drama_id}")]])


def my_dramas_kb(dramas: list[Drama]) -> InlineKeyboardMarkup:
    """Сатып алынған сериалдар - әрқайсысына жаңа сілтеме."""
    rows = [[InlineKeyboardButton(text=d.title, callback_data=f"access:{d.id}")]
            for d in dramas]
    rows.append([InlineKeyboardButton(text=texts.BTN_BACK, callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def episode_kb(drama: Drama, number: int) -> InlineKeyboardMarkup:
    """Бөлімнің астындағы навигация.

    Соңғы тегін бөлімнен кейін «алдыға» орнына төлем түймесі тұрады.
    """
    nav = []
    if number > 1:
        nav.append(InlineKeyboardButton(text=texts.BTN_PREV,
                                        callback_data=f"ep:{drama.id}:{number - 1}"))
    if number < drama.free_episodes:
        nav.append(InlineKeyboardButton(text=texts.BTN_NEXT,
                                        callback_data=f"ep:{drama.id}:{number + 1}"))

    rows = [nav] if nav else []
    if number >= drama.free_episodes:
        rows.append([InlineKeyboardButton(
            text=texts.BTN_PAY.format(price=drama.price_kzt),
            callback_data=f"pay:{drama.id}")])
    rows.append([InlineKeyboardButton(text=texts.BTN_MENU, callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
