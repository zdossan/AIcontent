"""Төлем циклі: Kaspi сілтемесі → күту → жабық арнаға қолжетімділік.

Ең маңызды ереже: ақша түскен соң адам міндетті түрде қолжетімділік алуы
керек. Сондықтан алдымен төлем базаға жазылады, содан кейін ғана сілтеме
жасалады — сілтеме сәтсіз болса да, сатып алу сақталып қалады.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from aiogram.exceptions import TelegramAPIError

from bot import access, config, keyboards, payments, store, texts
from bot.store import Drama

log = logging.getLogger(__name__)

# Arzan сілтемесі ~3 минут жарайды.
POLL_INTERVAL_SEC = 3
POLL_TIMEOUT_SEC = 200

# Бір сериалға бір адамға берілетін сілтеме саны.
MAX_INVITES = 5

# Фондағы күту тапсырмалары. Сілтеме сақталмаса, Python оларды
# қоқысқа жинап жіберуі мүмкін — сонда төлем бақылаусыз қалады.
_TASKS: set[asyncio.Task] = set()

# (tg_id, drama_id) -> (url, invoice_id, қашан ескіреді)
LINK_CACHE: dict[tuple[int, int], tuple[str, str, float]] = {}
LINK_TTL_SEC = 150


def _spawn(coro) -> asyncio.Task:
    """Фондағы тапсырманы сілтемесін сақтай отырып қосу."""
    task = asyncio.create_task(coro)
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task


async def shutdown() -> None:
    """Бот тоқтағанда күтудегі тапсырмаларды тоқтату."""
    for task in list(_TASKS):
        task.cancel()
    if _TASKS:
        await asyncio.gather(*_TASKS, return_exceptions=True)


def admin_chat_ids() -> set[int]:
    return config.admin_ids()


async def notify_admins(bot, text: str) -> None:
    """Админдерге хабарлау. Жеткізілмесе — тек логқа."""
    for admin_id in admin_chat_ids():
        try:
            await bot.send_message(chat_id=admin_id, text=text)
        except TelegramAPIError as err:
            log.warning("Админге хабарлама жетпеді (%s): %s", admin_id, err)


async def _say(bot, chat_id: int, text: str, markup=None) -> bool:
    """Қолданушыға жазу. Бот бұғатталған болса False."""
    try:
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
    except TelegramAPIError as err:
        log.warning("Қолданушыға хабарлама жетпеді (%s): %s", chat_id, err)
        return False
    return True


async def start_payment(bot, chat_id: int, tg_id: int, drama: Drama) -> None:
    """Төлемді бастау. Бұрын төлеген болса — бірден қолжетімділік."""
    if store.paid_purchase(tg_id, drama.id) is not None:
        await grant_access(bot, chat_id, tg_id, drama)
        return

    loop = asyncio.get_running_loop()
    cached = LINK_CACHE.get((tg_id, drama.id))
    if cached and cached[2] > loop.time():
        url, invoice_id = cached[0], cached[1]
    else:
        order_id = f"d{drama.id}-u{tg_id}-{uuid.uuid4().hex[:8]}"
        try:
            link = await payments.create_payment_link(
                amount=drama.price_kzt,
                description=drama.title,
                external_order_id=order_id,
            )
        except Exception:
            log.exception("Төлем сілтемесі жасалмады (user=%s, сериал=%s)",
                          tg_id, drama.id)
            await _say(bot, chat_id, texts.PAY_FAILED, keyboards.back_kb())
            return

        url, invoice_id = link.url, link.id
        LINK_CACHE[(tg_id, drama.id)] = (url, invoice_id, loop.time() + LINK_TTL_SEC)
        store.create_purchase(tg_id, drama.id, invoice_id, drama.price_kzt)
        _spawn(watch_invoice(bot, chat_id, tg_id, drama.id, invoice_id))

    await _say(bot, chat_id,
               texts.PAY_LINK.format(title=drama.title, price=drama.price_kzt),
               keyboards.kaspi_kb(url))


async def watch_invoice(bot, chat_id: int, tg_id: int, drama_id: int,
                        invoice_id: str) -> None:
    """Төлемді күту. Arzan webhook орнына — қарапайым сұрау циклі."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + POLL_TIMEOUT_SEC

    while loop.time() < deadline:
        await asyncio.sleep(POLL_INTERVAL_SEC)
        try:
            invoice = await payments.get_invoice(invoice_id)
        except Exception:
            # Желі қатесі күтуді тоқтатпайды.
            log.warning("Шот күйін сұрау сәтсіз (%s)", invoice_id)
            continue

        if not invoice.is_final:
            continue

        LINK_CACHE.pop((tg_id, drama_id), None)
        if invoice.is_paid:
            await _on_paid(bot, chat_id, tg_id, drama_id, invoice_id)
        else:
            log.info("Төлем өтпеді: user=%s шот=%s (%s)",
                     tg_id, invoice_id, invoice.status)
            store.mark_status(invoice_id, invoice.status)
            await _say(bot, chat_id, texts.LINK_EXPIRED,
                       keyboards.new_link_kb(drama_id))
        return

    log.info("Күту уақыты бітті: шот=%s (user=%s)", invoice_id, tg_id)
    LINK_CACHE.pop((tg_id, drama_id), None)
    store.mark_status(invoice_id, "expired")
    await _say(bot, chat_id, texts.LINK_EXPIRED, keyboards.new_link_kb(drama_id))


async def _on_paid(bot, chat_id: int, tg_id: int, drama_id: int,
                   invoice_id: str) -> None:
    """Ақша түсті: алдымен базаға, сосын сілтеме."""
    log.info("Төлем өтті: user=%s шот=%s", tg_id, invoice_id)
    store.mark_paid(invoice_id)
    drama = store.get_drama(drama_id)
    if drama is None:
        log.error("Төленген сериал табылмады: %s", drama_id)
        return
    await grant_access(bot, chat_id, tg_id, drama)


async def grant_access(bot, chat_id: int, tg_id: int, drama: Drama) -> bool:
    """Жабық арнаға жеке сілтеме беру.

    False қайтарады: сілтеме лимиті бітсе немесе Telegram сілтеме бермесе.
    Сатып алудың өзі ешқашан жойылмайды.
    """
    purchase = store.paid_purchase(tg_id, drama.id)
    if purchase is None:
        log.error("Төлемсіз қолжетімділік сұралды: user=%s сериал=%s",
                  tg_id, drama.id)
        return False

    if await access.is_member(bot, drama.channel_id, tg_id):
        await _say(bot, chat_id, texts.ALREADY_MEMBER.format(title=drama.title),
                   keyboards.back_kb())
        return True

    if purchase.invites_sent >= MAX_INVITES:
        log.warning("Сілтеме лимиті: user=%s сериал=%s", tg_id, drama.id)
        await _say(bot, chat_id, texts.INVITE_LIMIT, keyboards.back_kb())
        return False

    url = await access.personal_invite(bot, drama.channel_id, tg_id)
    if url is None:
        await notify_admins(bot, texts.ADMIN_INVITE_FAILED.format(
            tg_id=tg_id, title=drama.title))
        await _say(bot, chat_id, texts.INVITE_FAILED,
                   keyboards.retry_kb(drama.id))
        return False

    store.bump_invites(purchase.id)
    await _say(bot, chat_id,
               texts.PAID_WITH_LINK.format(title=drama.title, url=url))
    return True


async def recover_pending(bot) -> int:
    """Бот өшіп тұрғанда өткен төлемдерді қуып жету.

    Қайтаратыны — қолжетімділік берілген төлем саны.
    """
    pending = store.pending_purchases(60)
    if not pending:
        return 0

    try:
        statuses = await payments.check_many([p.invoice_id for p in pending])
    except Exception:
        log.exception("Күтудегі төлемдерді тексеру сәтсіз")
        return 0

    recovered = 0
    for purchase in pending:
        if statuses.get(purchase.invoice_id) != "paid":
            continue
        log.info("Қайта қосылғаннан кейін төлем табылды: %s", purchase.invoice_id)
        store.mark_paid(purchase.invoice_id)
        drama = store.get_drama(purchase.drama_id)
        if drama is not None:
            await grant_access(bot, purchase.tg_id, purchase.tg_id, drama)
        recovered += 1
    return recovered
