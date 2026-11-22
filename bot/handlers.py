"""Қолданушы хендлерлері: каталог, сериал картасы, тегін бөлімдер."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot import keyboards, store, texts
from bot.store import Drama

log = logging.getLogger(__name__)

router = Router(name="handlers")


async def show_catalog(bot, chat_id: int, tg_id: int) -> None:
    """Сериалдар тізімін көрсету."""
    dramas = store.active_dramas()
    if not dramas:
        await bot.send_message(chat_id, texts.NO_DRAMAS)
        return
    await bot.send_message(chat_id, texts.START_GREETING,
                           reply_markup=keyboards.catalog_kb(
                               dramas, store.paid_drama_ids(tg_id)))


@router.message(CommandStart())
async def cmd_start(message: Message, bot) -> None:
    user = message.from_user
    store.upsert_user(user.id, user.username, user.first_name)
    await show_catalog(bot, message.chat.id, user.id)


@router.callback_query(F.data == "back")
async def cb_back(callback: CallbackQuery, bot) -> None:
    await callback.answer()
    await show_catalog(bot, callback.message.chat.id, callback.from_user.id)


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery, bot) -> None:
    await callback.answer()
    await bot.send_message(callback.message.chat.id, texts.HELP,
                           reply_markup=keyboards.back_kb())


@router.callback_query(F.data.startswith("drama:"))
async def cb_drama(callback: CallbackQuery, bot) -> None:
    """Сериал картасы."""
    await callback.answer()
    drama = store.get_drama(int(callback.data.split(":")[1]))
    if drama is None:
        await show_catalog(bot, callback.message.chat.id, callback.from_user.id)
        return

    is_paid = store.paid_purchase(callback.from_user.id, drama.id) is not None
    await bot.send_message(
        callback.message.chat.id,
        texts.DRAMA_CARD.format(title=drama.title, description=drama.description,
                                total=drama.total_episodes,
                                free=drama.free_episodes, price=drama.price_kzt),
        reply_markup=keyboards.drama_kb(drama, is_paid),
    )


@router.callback_query(F.data.startswith("free:"))
async def cb_free(callback: CallbackQuery, bot) -> None:
    """Тегін бөлімдерді жіберу."""
    await callback.answer()
    drama = store.get_drama(int(callback.data.split(":")[1]))
    if drama is None:
        return

    chat_id = callback.message.chat.id
    sent = await send_free_episodes(bot, chat_id, drama)
    if sent == 0:
        await bot.send_message(chat_id, texts.EPISODES_SOON,
                               reply_markup=keyboards.back_kb())
        return

    await bot.send_message(
        chat_id,
        texts.FREE_DONE.format(total=drama.total_episodes, price=drama.price_kzt),
        reply_markup=keyboards.pay_kb(drama),
    )


async def send_free_episodes(bot, chat_id: int, drama: Drama) -> int:
    """Алғашқы бөлімдерді жабық арнадан көшіріп жіберу.

    protect_content=True — видеоны әрі қарай жіберуге болмайды.
    Қоймада жоқ бөлімдер аттап кетіледі, жіберілген саны қайтарылады.
    """
    sent = 0
    for episode in store.episodes(drama.id):
        if episode.number > drama.free_episodes:
            break
        try:
            await bot.copy_message(
                chat_id=chat_id,
                from_chat_id=drama.channel_id,
                message_id=episode.message_id,
                protect_content=True,
            )
        except TelegramAPIError as err:
            log.error("Бөлім жіберілмеді (сериал=%s, бөлім=%s): %s",
                      drama.id, episode.number, err)
            continue
        sent += 1
    return sent
