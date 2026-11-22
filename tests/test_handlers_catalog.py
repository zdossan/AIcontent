"""bot.handlers - каталог және тегін бөлімдер."""

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


async def test_drama_card_escapes_html_in_title(fake_bot, db):
    """Атауда < белгісі болса Telegram хабарламаны қабылдамай қалады."""
    from tests.conftest import make_callback

    d = store.create_drama("Тең <емес>", "Сипаттама & тағы", 490, 26, 6)
    store.bind_channel(d.bind_code, -100123)
    await handlers.cb_drama(make_callback(7, f"drama:{d.id}"), fake_bot)
    text = fake_bot.last_text()
    assert "&lt;емес&gt;" in text and "&amp;" in text
