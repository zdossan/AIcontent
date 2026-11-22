"""bot.handlers — каталог және тегін бөлімдер."""

from bot import handlers, store
from tests.conftest import make_message


async def test_start_lists_active_dramas(fake_bot, db, drama):
    await handlers.cmd_start(make_message(tg_id=7), fake_bot)
    kb = fake_bot.last_markup()
    assert kb.inline_keyboard[0][0].text.startswith("Тең емес")


async def test_start_marks_purchased_drama(fake_bot, db, drama, paid_user):
    await handlers.cmd_start(make_message(tg_id=paid_user), fake_bot)
    assert "✅" in fake_bot.last_markup().inline_keyboard[0][0].text


async def test_start_registers_user(fake_bot, db, drama):
    await handlers.cmd_start(make_message(tg_id=7), fake_bot)
    row = store._db().execute("SELECT username FROM users WHERE tg_id = 7").fetchone()
    assert row["username"] == "ayan"


async def test_start_without_dramas_explains(fake_bot, db):
    await handlers.cmd_start(make_message(tg_id=7), fake_bot)
    assert fake_bot.last_markup() is None


async def test_free_episodes_copied_with_protection(fake_bot, db, drama_with_26_episodes):
    sent = await handlers.send_free_episodes(fake_bot, 7, drama_with_26_episodes)
    assert sent == 6
    calls = fake_bot.calls["copy_message"]
    assert [c["message_id"] for c in calls] == [10, 11, 12, 13, 14, 15]
    assert all(c["protect_content"] is True for c in calls)


async def test_free_episodes_copied_from_channel(fake_bot, db, drama_with_26_episodes):
    await handlers.send_free_episodes(fake_bot, 7, drama_with_26_episodes)
    call = fake_bot.calls["copy_message"][0]
    assert call["from_chat_id"] == drama_with_26_episodes.channel_id
    assert call["chat_id"] == 7


async def test_free_episodes_sends_what_exists(fake_bot, db, drama_with_3_episodes):
    assert await handlers.send_free_episodes(fake_bot, 7, drama_with_3_episodes) == 3


async def test_free_episodes_with_empty_catalog_sends_none(fake_bot, db, drama):
    assert await handlers.send_free_episodes(fake_bot, 7, drama) == 0
    assert "copy_message" not in fake_bot.calls
