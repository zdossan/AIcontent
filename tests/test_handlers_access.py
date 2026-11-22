"""bot.handlers — сатып алынған сериалдар және төлем түймесі."""

from bot import handlers, store
from tests.conftest import make_callback


async def test_my_dramas_lists_only_paid(fake_bot, db, drama, paid_user):
    other = store.create_drama("Басқа сериал", "", 490, 10, 3)
    store.bind_channel(other.bind_code, -100999)
    await handlers.cb_my_dramas(make_callback(paid_user, "my"), fake_bot)
    labels = [b.text for row in fake_bot.last_markup().inline_keyboard for b in row]
    assert labels == ["Тең емес", "⬅️ Артқа"]


async def test_my_dramas_without_purchases(fake_bot, db, drama):
    await handlers.cb_my_dramas(make_callback(7, "my"), fake_bot)
    assert fake_bot.last_text() == "Әзірге сатып алынған сериал жоқ. 🎬"


async def test_access_button_sends_new_invite(fake_bot, db, drama, paid_user):
    await handlers.cb_access(make_callback(paid_user, f"access:{drama.id}"), fake_bot)
    assert fake_bot.calls["create_chat_invite_link"]


async def test_pay_button_starts_payment(fake_bot, db, drama, fake_arzan):
    await handlers.cb_pay(make_callback(7, f"pay:{drama.id}"), fake_bot)
    assert len(fake_arzan.created_links) == 1
