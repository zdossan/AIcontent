"""Төлемді бастап, аяқтамағандарға еске салу хабарламасы.

Әр адамға бір сериал бойынша бір рет қана жіберіледі - журнал
`reminders` кестесінде жүргізіледі. Ботты бұғаттағандар аттап кетіледі.
"""

from __future__ import annotations

import asyncio
import html
import logging
from dataclasses import dataclass

from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from bot import keyboards, store, texts
from bot.store import Drama

log = logging.getLogger(__name__)

# Telegram секундына ~30 хабарламаға рұқсат етеді.
SEND_PAUSE_SEC = 0.05


@dataclass(slots=True)
class Target:
    tg_id: int


def targets(drama_id: int) -> list[Target]:
    """Еске салу керек адамдар."""
    return [Target(tg_id) for tg_id in store.unpaid_starters(drama_id)]


def message_text(drama: Drama) -> str:
    return texts.REMINDER.format(title=html.escape(drama.title),
                                 total=drama.total_episodes,
                                 price=drama.price_kzt)


async def send_all(bot, drama: Drama) -> int:
    """Хабарламаны тарату. Қайтаратыны - нақты жеткен адам саны."""
    text = message_text(drama)
    markup = keyboards.reminder_kb(drama)
    sent = 0

    for target in targets(drama.id):
        try:
            await bot.send_message(chat_id=target.tg_id, text=text,
                                   reply_markup=markup)
        except TelegramRetryAfter as err:
            # Telegram шектеу қойды - күтіп, бір рет қайталаймыз.
            await asyncio.sleep(err.retry_after)
            try:
                await bot.send_message(chat_id=target.tg_id, text=text,
                                       reply_markup=markup)
            except TelegramAPIError as retry_err:
                log.warning("Еске салу жетпеді (user=%s): %s",
                            target.tg_id, retry_err)
                continue
        except TelegramAPIError as err:
            # Бұғаттаған немесе чатты жойған адам - бұл қате емес.
            log.info("Еске салу жетпеді (user=%s): %s", target.tg_id, err)
            continue

        store.mark_reminded(target.tg_id, drama.id)
        sent += 1
        await asyncio.sleep(SEND_PAUSE_SEC)

    log.info("Еске салу таратылды: сериал=%s, жеткені=%s", drama.id, sent)
    return sent
