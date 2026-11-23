"""Төлемді бастап, аяқтамағандарға еске салу."""

import pytest

from bot import admin, reminder, store, texts
from tests.conftest import ADMIN_ID, make_callback, make_message


@pytest.fixture(autouse=True)
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", str(ADMIN_ID))


def test_targets_are_those_who_started_but_did_not_pay(db, drama):
    store.create_purchase(1, drama.id, "qr_1", 490)          # бастады, төлемеді
    store.create_purchase(2, drama.id, "qr_2", 490)
    store.mark_paid("qr_2")                                   # төледі
    store.upsert_user(3, None, None)                          # тек /start басты
    assert [t.tg_id for t in reminder.targets(drama.id)] == [1]


def test_target_who_paid_another_drama_still_counts(db, drama):
    other = store.create_drama("Басқа", "", 990, 10, 3)
    store.create_purchase(1, other.id, "qr_o", 990)
    store.mark_paid("qr_o")
    store.create_purchase(1, drama.id, "qr_1", 490)
    assert [t.tg_id for t in reminder.targets(drama.id)] == [1]


async def test_reminder_is_sent_once_per_person(fake_bot, db, drama):
    store.create_purchase(1, drama.id, "qr_1", 490)
    assert await reminder.send_all(fake_bot, drama) == 1
    assert await reminder.send_all(fake_bot, drama) == 0


async def test_reminder_text_is_exactly_as_approved(fake_bot, db, drama):
    store.create_purchase(1, drama.id, "qr_1", 490)
    await reminder.send_all(fake_bot, drama)
    assert fake_bot.last_text() == (
        "Төлем жасағыңыз келген екен, бірақ жасамапсыз.\n\n"
        "Тең емес сериалының 1-26 бөлімдері жабық топта\n\n"
        "Қазір 2990 тг орнына, доступты 490тг ала аласыз\n\n"
        "Сұрақтар болса: @tech_supportZZ, +77014031734"
    )


async def test_reminder_has_pay_and_offer_buttons(fake_bot, db, drama):
    store.create_purchase(1, drama.id, "qr_1", 490)
    await reminder.send_all(fake_bot, drama)
    labels = [b.text for row in fake_bot.last_markup().inline_keyboard for b in row]
    assert labels == [texts.BTN_REMINDER_PAY, texts.BTN_OFFER]


async def test_blocked_user_does_not_stop_the_rest(fake_bot, db, drama):
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import SendMessage

    store.create_purchase(1, drama.id, "qr_1", 490)
    store.create_purchase(2, drama.id, "qr_2", 490)
    calls = {"n": 0}
    original = fake_bot.send_message

    async def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TelegramForbiddenError(method=SendMessage(chat_id=1, text="x"),
                                         message="bot was blocked")
        await original(**kwargs)

    fake_bot.send_message = flaky
    assert await reminder.send_all(fake_bot, drama) == 1


async def test_command_asks_for_confirmation_first(fake_bot, db, drama):
    store.create_purchase(1, drama.id, "qr_1", 490)
    await admin.cmd_reminder(make_message(ADMIN_ID, "/eske_salu"), fake_bot)
    assert "send_message" in fake_bot.calls
    assert "1" in fake_bot.last_text()
    assert fake_bot.last_markup() is not None


async def test_non_admin_cannot_start_a_broadcast(fake_bot, db, drama):
    await admin.cmd_reminder(make_message(999, "/eske_salu"), fake_bot)
    assert "send_message" not in fake_bot.calls
