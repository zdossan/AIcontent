"""Жабық арнадағы посттардан бөлімдер каталогын жинау.

Иесі видеоны арнаға жүктейді, тақырыпқа бөлім нөмірін жазады - бот
қалғанын өзі істейді. Арнаны сериалға байлау: арнада /bind <КОД>.
"""

from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message

from bot import store

log = logging.getLogger(__name__)

router = Router(name="catalog")

NUMBER_RE = re.compile(r"\d+")


def parse_episode_number(caption: str | None) -> int | None:
    """Тақырыптағы бірінші санды бөлім нөмірі деп аламыз.

    «3», «3-бөлім», «Тең емес 7-бөлім» - бәрі жарайды.
    """
    if not caption:
        return None
    match = NUMBER_RE.search(caption)
    return int(match.group()) if match else None


# Арна да, топ та жарайды: иесі қайсысын ашса да бот жұмыс істеуі керек.
GROUP_TYPES = {"channel", "group", "supergroup"}


@router.channel_post(F.video)
async def handle_channel_post(message: Message) -> None:
    """Арнаға түскен видеоны каталогқа жазу."""
    if message.video is None:
        return

    drama = store.drama_by_channel(message.chat.id)
    if drama is None:
        log.warning("Байланбаған арнадан пост келді: chat=%s", message.chat.id)
        return

    number = parse_episode_number(message.caption)
    if number is None:
        number = store.next_episode_number(drama.id)
        log.warning("Тақырыпта нөмір жоқ - %s-бөлім деп жазылды (сериал %s)",
                    number, drama.id)

    store.add_episode(drama.id, number, message.message_id)
    log.info("Бөлім жазылды: сериал=%s нөмір=%s message_id=%s",
             drama.id, number, message.message_id)


@router.channel_post(F.text.startswith("/bind"))
async def handle_bind(message: Message, bot=None) -> None:
    """Арнаны (немесе топты) сериалға байлау: /bind ABC123."""
    if message.chat.type not in GROUP_TYPES:
        return

    parts = (message.text or "").split()
    if len(parts) < 2:
        log.warning("Байлау коды көрсетілмеген: chat=%s", message.chat.id)
        return

    drama = store.bind_channel(parts[1], message.chat.id)
    if drama is None:
        log.warning("Байлау сәтсіз, код белгісіз: %r", parts[1])
        return

    log.info("Арна %s «%s» сериалына байланды", message.chat.id, drama.title)
    if bot is None:
        return
    try:
        # Код арнада көрініп тұрмауы үшін өшіреміз.
        await bot.delete_message(chat_id=message.chat.id,
                                 message_id=message.message_id)
    except TelegramAPIError as err:
        log.warning("Байлау хабарламасы өшірілмеді: %s", err)


@router.channel_post()
async def log_channel_post(message: Message) -> None:
    """Басқа хендлерге түспеген арна посттарын логқа жазу.

    «Бот арнадан ештеңе алмай жатыр ма, әлде пост жарамсыз ба?» деген
    сұрақты тек осы лог арқылы айыруға болады.
    """
    log.info("Арна посты: chat=%s (%s), тақырып=%r, видео=%s",
             message.chat.id, message.chat.title,
             message.caption or message.text, message.video is not None)


@router.message(F.chat.type.in_(GROUP_TYPES), F.text.startswith("/bind"))
async def handle_group_bind(message: Message, bot=None) -> None:
    """Топта жазылған /bind - арнадағымен бірдей өңделеді."""
    await handle_bind(message, bot)


@router.message(F.chat.type.in_(GROUP_TYPES), F.video)
async def handle_group_post(message: Message) -> None:
    """Топқа жүктелген видео - арнадағымен бірдей каталогқа түседі."""
    if message.chat.type not in GROUP_TYPES:
        return
    await handle_channel_post(message)


@router.message()
async def log_message(message: Message) -> None:
    """Ешбір хендлерге түспеген хабарламаны логқа жазу.

    Баптау кезінде «команда қай чатқа жазылды?» дегенді осыдан көреміз.
    """
    log.info("Өңделмеген хабарлама: chat=%s type=%s title=%r мәтін=%r видео=%s",
             message.chat.id, message.chat.type, message.chat.title,
             message.text or message.caption, message.video is not None)
