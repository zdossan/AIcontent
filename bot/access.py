"""Жабық арнаға қолжетімділік: жеке сілтеме және мүшелікті тексеру.

Бот арнада админ болуы керек («Пригласить пользователей» құқығымен).
"""

from __future__ import annotations

import logging
import time

from aiogram.exceptions import TelegramAPIError

log = logging.getLogger(__name__)

# Жеке сілтеменің жарамдылық мерзімі (секунд).
INVITE_TTL_SEC = 24 * 3600

MEMBER_STATUSES = {"member", "administrator", "creator"}


async def personal_invite(bot, channel_id: int, tg_id: int) -> str | None:
    """Бір адамға арналған, бір рет қолданылатын сілтеме.

    Сәтсіз болса None қайтарады — шақырған жақ міндетті түрде өңдеуі керек:
    ақша төленген адам ештеңе алмай қалмауы тиіс.
    """
    try:
        link = await bot.create_chat_invite_link(
            chat_id=channel_id,
            name=f"user {tg_id}",
            member_limit=1,
            expire_date=int(time.time()) + INVITE_TTL_SEC,
        )
    except TelegramAPIError as err:
        log.error("Жеке сілтеме жасалмады (арна=%s, user=%s): %s",
                  channel_id, tg_id, err)
        return None

    log.info("Жеке сілтеме жасалды: арна=%s user=%s", channel_id, tg_id)
    return link.invite_link


async def is_member(bot, channel_id: int, tg_id: int) -> bool:
    """Адам арнада отыр ма? Қате болса False — артық сілтеме беру қауіпсіз."""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=tg_id)
    except TelegramAPIError as err:
        log.warning("Мүшелікті тексеру сәтсіз (арна=%s, user=%s): %s",
                    channel_id, tg_id, err)
        return False
    return member.status in MEMBER_STATUSES
