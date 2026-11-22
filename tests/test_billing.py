"""bot.billing — төлем циклі және қолжетімділік беру."""

import pytest

from bot import billing, store
from tests.conftest import telegram_error


@pytest.fixture(autouse=True)
async def fast_polling(monkeypatch):
    """Тесттер нақты 3 секунд күтпесін әрі фондағы тапсырма қалмасын."""
    monkeypatch.setattr(billing, "POLL_INTERVAL_SEC", 0)
    monkeypatch.setattr(billing, "POLL_TIMEOUT_SEC", 0.2)
    billing.LINK_CACHE.clear()
    yield
    await billing.shutdown()


async def test_second_click_reuses_live_invoice(fake_bot, db, drama, fake_arzan):
    await billing.start_payment(fake_bot, 7, 7, drama)
    await billing.start_payment(fake_bot, 7, 7, drama)
    assert len(fake_arzan.created_links) == 1


async def test_already_paid_skips_payment_and_grants_access(
        fake_bot, db, drama, paid_user, fake_arzan):
    await billing.start_payment(fake_bot, 7, paid_user, drama)
    assert fake_arzan.created_links == []
    assert fake_bot.calls["create_chat_invite_link"]


async def test_paid_invoice_marks_purchase_and_sends_invite(
        fake_bot, db, drama, fake_arzan):
    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.invoice_status = "paid"
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert store.paid_purchase(7, drama.id).status == "paid"
    assert fake_bot.invite_url in fake_bot.last_text()


async def test_purchase_stays_paid_when_invite_fails(
        fake_bot, db, drama, fake_arzan, monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "999")
    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.invoice_status = "paid"
    fake_bot.invite_fails_with = telegram_error("not enough rights")
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert store.paid_purchase(7, drama.id) is not None
    assert any(c["chat_id"] == 999 for c in fake_bot.calls["send_message"])


async def test_blocked_user_keeps_access(fake_bot, db, drama, fake_arzan, monkeypatch):
    from aiogram.exceptions import TelegramForbiddenError
    from aiogram.methods import SendMessage

    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.invoice_status = "paid"
    fake_bot.send_fails_with = TelegramForbiddenError(
        method=SendMessage(chat_id=7, text="x"), message="bot was blocked")
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert store.paid_purchase(7, drama.id) is not None


async def test_expired_invoice_offers_new_link(fake_bot, db, drama, fake_arzan):
    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.invoice_status = "expired"
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert "🔄" in fake_bot.last_markup().inline_keyboard[0][0].text


async def test_recover_pending_grants_access_after_restart(
        fake_bot, db, drama, fake_arzan):
    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.batch = {"qr_1": "paid"}
    assert await billing.recover_pending(fake_bot) == 1
    assert store.paid_purchase(7, drama.id) is not None


async def test_recover_pending_leaves_unpaid_alone(fake_bot, db, drama, fake_arzan):
    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.batch = {"qr_1": "pending"}
    assert await billing.recover_pending(fake_bot) == 0
    assert store.paid_purchase(7, drama.id) is None


async def test_invite_limit_reached(fake_bot, db, drama, paid_user):
    for _ in range(5):
        assert await billing.grant_access(fake_bot, 7, paid_user, drama) is True
    assert await billing.grant_access(fake_bot, 7, paid_user, drama) is False


async def test_member_is_not_sent_another_invite(fake_bot, db, drama, paid_user):
    fake_bot.member_status = "member"
    assert await billing.grant_access(fake_bot, 7, paid_user, drama) is True
    assert "create_chat_invite_link" not in fake_bot.calls
