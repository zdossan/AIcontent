"""bot.admin — иесіне арналған командалар."""

import pytest

from bot import admin, store
from tests.conftest import ADMIN_ID, make_message


@pytest.fixture(autouse=True)
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", str(ADMIN_ID))


async def feed(fake_bot, fsm, answers: list[str]) -> None:
    """Диалогты қадам-қадам өткізу."""
    await admin.cmd_new(make_message(ADMIN_ID, "/жаңа"), fake_bot, fsm)
    for answer in answers:
        await admin.handle_new_step(make_message(ADMIN_ID, answer), fake_bot, fsm)


async def test_non_admin_gets_no_answer(fake_bot, db):
    await admin.cmd_stats(make_message(999, "/stats"), fake_bot)
    assert "send_message" not in fake_bot.calls


async def test_new_drama_dialog_creates_drama_and_returns_code(fake_bot, db, fsm):
    await feed(fake_bot, fsm, ["Тең емес", "Сипаттама", "490", "26", "6"])
    d = store.get_drama(1)
    assert (d.title, d.price_kzt, d.total_episodes, d.free_episodes) == (
        "Тең емес", 490, 26, 6)
    assert d.bind_code in fake_bot.last_text()


async def test_new_drama_rejects_non_numeric_price(fake_bot, db, fsm):
    await feed(fake_bot, fsm, ["Тең емес", "Сипаттама", "тегін"])
    assert "сан" in fake_bot.last_text().lower()
    assert store.all_dramas() == []


async def test_new_drama_rejects_free_above_total(fake_bot, db, fsm):
    await feed(fake_bot, fsm, ["Тең емес", "Сипаттама", "490", "26", "30"])
    assert store.all_dramas() == []


async def test_bolimder_reports_missing_episodes(fake_bot, db, drama):
    store.add_episode(drama.id, 1, 10)
    store.add_episode(drama.id, 3, 12)
    await admin.cmd_bolimder(make_message(ADMIN_ID, "/bolimder"), fake_bot)
    assert "2" in fake_bot.last_text()


async def test_stats_shows_sales(fake_bot, db, drama, paid_user):
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert "Тең емес" in text and "490" in text


async def test_export_sends_csv(fake_bot, db, drama, paid_user):
    await admin.cmd_export(make_message(ADMIN_ID, "/export"), fake_bot)
    assert fake_bot.calls["send_document"]


async def test_command_during_dialog_cancels_it(fake_bot, db, fsm):
    """Диалог ортасында /start жазса — иесі тұрып қалмауы керек."""
    await admin.cmd_new(make_message(ADMIN_ID, "/жаңа"), fake_bot, fsm)
    await admin.handle_new_step(make_message(ADMIN_ID, "/start"), fake_bot, fsm)
    assert await fsm.get_state() is None
    assert store.all_dramas() == []
