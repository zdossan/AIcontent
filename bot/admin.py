"""Иесіне арналған командалар: сериал қосу, бөлімдерді тексеру, есеп.

Админ емес адам бұл командаларға жауап алмайды — бот үндемейді.
"""

from __future__ import annotations

import csv
import html
import io
import logging

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, Message

from bot import config, store, texts

log = logging.getLogger(__name__)

router = Router(name="admin")


class NewDrama(StatesGroup):
    title = State()
    description = State()
    price = State()
    total = State()
    free = State()


def is_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in config.admin_ids())


@router.message(Command("жаңа", "new"))
async def cmd_new(message: Message, bot, state: FSMContext) -> None:
    """Жаңа сериал қосу диалогын бастау."""
    if not is_admin(message):
        return
    await state.set_state(NewDrama.title)
    await bot.send_message(chat_id=message.chat.id, text=texts.NEW_ASK_TITLE)


@router.message(StateFilter(NewDrama))
async def handle_new_step(message: Message, bot, state: FSMContext) -> None:
    """Диалогтың кез келген қадамы."""
    if not is_admin(message):
        return

    current = await state.get_state()
    answer = (message.text or "").strip()

    async def say(text: str) -> None:
        await bot.send_message(chat_id=message.chat.id, text=text)

    # Диалог ортасында команда жазса — шығамыз, әйтпесе иесі тұрып қалады.
    if answer.startswith("/"):
        await state.clear()
        await say(texts.NEW_CANCELLED)
        return

    if current == NewDrama.title.state:
        await state.update_data(title=answer)
        await state.set_state(NewDrama.description)
        await say(texts.NEW_ASK_DESCRIPTION)
        return

    if current == NewDrama.description.state:
        await state.update_data(description=answer)
        await state.set_state(NewDrama.price)
        await say(texts.NEW_ASK_PRICE)
        return

    if not answer.isdigit():
        await say(texts.NEW_NOT_A_NUMBER)
        return

    value = int(answer)

    if current == NewDrama.price.state:
        await state.update_data(price=value)
        await state.set_state(NewDrama.total)
        await say(texts.NEW_ASK_TOTAL)
        return

    if current == NewDrama.total.state:
        await state.update_data(total=value)
        await state.set_state(NewDrama.free)
        await say(texts.NEW_ASK_FREE)
        return

    data = await state.get_data()
    if value > data["total"]:
        await say(texts.NEW_FREE_TOO_BIG)
        return

    drama = store.create_drama(data["title"], data["description"],
                               data["price"], data["total"], value)
    await state.clear()
    await say(texts.NEW_DONE.format(title=html.escape(drama.title), code=drama.bind_code))


@router.message(Command("bolimder"))
async def cmd_bolimder(message: Message, bot) -> None:
    """Қай бөлімдер жүктелген, қайсысы жетіспейді."""
    if not is_admin(message):
        return

    dramas = store.all_dramas()
    if not dramas:
        await bot.send_message(chat_id=message.chat.id, text=texts.ADMIN_NO_DRAMAS)
        return

    lines = []
    for drama in dramas:
        numbers = {e.number for e in store.episodes(drama.id)}
        channel = "байланған" if drama.channel_id else "арна жоқ"
        lines.append(f"🎬 <b>{html.escape(drama.title)}</b> ({channel}, коды {drama.bind_code})")
        if not numbers:
            lines.append("   бөлім жүктелмеген")
            continue
        missing = [n for n in range(1, drama.total_episodes + 1) if n not in numbers]
        lines.append(f"   жүктелген: {len(numbers)}/{drama.total_episodes}")
        if missing:
            lines.append("   жетіспейді: " + ", ".join(str(n) for n in missing))
    await bot.send_message(chat_id=message.chat.id, text="\n".join(lines))


@router.message(Command("stats"))
async def cmd_stats(message: Message, bot) -> None:
    """Сатылымдар мен түсім."""
    if not is_admin(message):
        return

    summary = store.sales_summary()
    if not summary:
        await bot.send_message(chat_id=message.chat.id, text=texts.ADMIN_NO_SALES)
        return

    lines = ["💰 <b>Сатылымдар</b>", ""]
    total = 0
    for title, count, amount in summary:
        lines.append(f"{html.escape(title)}: {count} сатылым — {amount} ₸")
        total += amount
    lines.append("")
    lines.append(f"Барлығы: {total} ₸")
    await bot.send_message(chat_id=message.chat.id, text="\n".join(lines))


@router.message(Command("export"))
async def cmd_export(message: Message, bot) -> None:
    """Барлық төлемдерді CSV етіп жіберу."""
    if not is_admin(message):
        return

    rows = store.export_rows()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Жасалған", "Төленген", "Сериал", "Сома", "Статус",
                     "telegram id", "username", "Аты", "Шот"])
    for row in rows:
        writer.writerow([
            store.to_local(row["created_at"]), store.to_local(row["paid_at"]),
            row["title"], row["amount"], row["status"], row["tg_id"],
            row["username"] or "", row["first_name"] or "", row["invoice_id"],
        ])
    document = BufferedInputFile(buffer.getvalue().encode("utf-8-sig"),
                                 filename="tolemder.csv")
    await bot.send_document(chat_id=message.chat.id, document=document)
