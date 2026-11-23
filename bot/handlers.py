"""Қолданушы хендлерлері: каталог, сериал картасы, тегін бөлімдер."""

from __future__ import annotations

import html
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot import billing, keyboards, offer, store, texts
from bot.store import Drama

log = logging.getLogger(__name__)

router = Router(name="handlers")


async def ack(bot, callback: CallbackQuery) -> None:
    """Түймедегі «сағатты» өшіру.

    callback.answer() ботқа байланған объектіні талап етеді, сондықтан
    әдісті боттан тікелей шақырамыз - хендлерлерді тестілеу жеңілдейді.
    """
    try:
        await bot.answer_callback_query(callback_query_id=callback.id)
    except TelegramAPIError as err:
        log.debug("callback жауабы жіберілмеді: %s", err)


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
    await ack(bot, callback)
    await show_catalog(bot, callback.message.chat.id, callback.from_user.id)


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery, bot) -> None:
    await ack(bot, callback)
    await bot.send_message(callback.message.chat.id, texts.HELP,
                           reply_markup=keyboards.back_kb())


@router.callback_query(F.data.startswith("drama:"))
async def cb_drama(callback: CallbackQuery, bot) -> None:
    """Сериал картасы."""
    await ack(bot, callback)
    drama = store.get_drama(int(callback.data.split(":")[1]))
    if drama is None:
        await show_catalog(bot, callback.message.chat.id, callback.from_user.id)
        return

    is_paid = store.paid_purchase(callback.from_user.id, drama.id) is not None
    await bot.send_message(
        callback.message.chat.id,
        texts.DRAMA_CARD.format(title=html.escape(drama.title),
                                description=html.escape(drama.description),
                                total=drama.total_episodes,
                                free=drama.free_episodes, price=drama.price_kzt),
        reply_markup=keyboards.drama_kb(drama, is_paid),
    )


@router.callback_query(F.data.startswith("free:"))
async def cb_free(callback: CallbackQuery, bot) -> None:
    """Тегін көруді бірінші бөлімнен бастау."""
    await ack(bot, callback)
    drama = store.get_drama(int(callback.data.split(":")[1]))
    if drama is None:
        return
    await send_episode(bot, callback.message.chat.id, drama, 1,
                       callback.from_user.id)


@router.callback_query(F.data.startswith("ep:"))
async def cb_episode(callback: CallbackQuery, bot) -> None:
    """«Алдыға» / «Артқа» түймелері.

    Жаңа бөлім жіберілген соң ескісі чаттан өшіріледі - сонда чатта
    әрқашан бір ғана бөлім тұрады.
    """
    await ack(bot, callback)
    _, drama_id, number = callback.data.split(":")
    drama = store.get_drama(int(drama_id))
    if drama is None:
        return

    sent = await send_episode(bot, callback.message.chat.id, drama, int(number),
                              callback.from_user.id)
    if sent:
        await _remove(bot, callback.message.chat.id, callback.message.message_id)


async def _remove(bot, chat_id: int, message_id: int) -> None:
    """Ескі бөлімді өшіру. Өшірілмесе де жұмыс тоқтамайды."""
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramAPIError as err:
        log.debug("Ескі бөлім өшірілмеді: %s", err)


async def send_episode(bot, chat_id: int, drama: Drama, number: int,
                       tg_id: int | None = None) -> bool:
    """Бір бөлімді жабық арнадан көшіріп жіберу.

    Тегін шектен асса - видео жіберілмейді, төлем ұсынылады.
    protect_content=True: видеоны әрі қарай жіберуге болмайды.
    """
    if number > drama.free_episodes:
        await bot.send_message(
            chat_id=chat_id,
            text=texts.FREE_DONE.format(total=drama.total_episodes,
                                        price=drama.price_kzt),
            reply_markup=keyboards.pay_kb(drama),
        )
        return False

    episode = next((e for e in store.episodes(drama.id) if e.number == number), None)
    if episode is None:
        log.warning("Бөлім жүктелмеген: сериал=%s нөмір=%s", drama.id, number)
        await bot.send_message(chat_id=chat_id, text=texts.EPISODE_MISSING,
                               reply_markup=keyboards.back_kb())
        return False

    try:
        await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=drama.channel_id,
            message_id=episode.message_id,
            caption=texts.EPISODE_CAPTION.format(
                title=html.escape(drama.title), number=number,
                total=drama.total_episodes),
            protect_content=True,
            reply_markup=keyboards.episode_kb(drama, number),
        )
    except TelegramAPIError as err:
        log.error("Бөлім жіберілмеді (сериал=%s, бөлім=%s): %s",
                  drama.id, number, err)
        await bot.send_message(chat_id=chat_id, text=texts.EPISODE_MISSING,
                               reply_markup=keyboards.back_kb())
        return False

    # Воронканы өлшеу үшін: адам қай бөлімге дейін жеткені.
    store.mark_viewed(tg_id if tg_id is not None else chat_id, drama.id, number)
    return True


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(callback: CallbackQuery, bot) -> None:
    """Төлемді бастау немесе жаңа сілтеме беру."""
    await ack(bot, callback)
    drama = store.get_drama(int(callback.data.split(":")[1]))
    if drama is None:
        return
    await billing.start_payment(bot, callback.message.chat.id,
                                callback.from_user.id, drama)


@router.callback_query(F.data == "my")
async def cb_my_dramas(callback: CallbackQuery, bot) -> None:
    """Сатып алынған сериалдар тізімі."""
    await ack(bot, callback)
    paid = store.paid_drama_ids(callback.from_user.id)
    dramas = [d for d in store.active_dramas() if d.id in paid]
    if not dramas:
        await bot.send_message(callback.message.chat.id, texts.NO_PURCHASES,
                               reply_markup=keyboards.back_kb())
        return
    await bot.send_message(callback.message.chat.id, texts.MY_DRAMAS,
                           reply_markup=keyboards.my_dramas_kb(dramas))


@router.callback_query(F.data.startswith("access:"))
async def cb_access(callback: CallbackQuery, bot) -> None:
    """Сатып алынған сериалға жаңа сілтеме."""
    await ack(bot, callback)
    drama = store.get_drama(int(callback.data.split(":")[1]))
    if drama is None:
        return
    await billing.grant_access(bot, callback.message.chat.id,
                               callback.from_user.id, drama)


@router.callback_query(F.data == "offer")
async def cb_offer(callback: CallbackQuery, bot) -> None:
    """Жария офертаны PDF түрінде жіберу."""
    await ack(bot, callback)
    try:
        await bot.send_document(chat_id=callback.message.chat.id,
                                document=offer.document(),
                                caption=texts.OFFER_CAPTION)
    except TelegramAPIError as err:
        log.error("Оферта жіберілмеді: %s", err)
