"""Жария оферта ботта қолжетімді ме."""

from bot import handlers, offer, texts
from tests.conftest import make_callback


def labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


def test_offer_file_exists():
    """PDF репозиторийде жатуы керек - бот оны жібереді."""
    assert offer.path().is_file()


async def test_pay_keyboard_has_offer_button(db, drama):
    from bot import keyboards

    assert texts.BTN_OFFER in labels(keyboards.pay_kb(drama))


async def test_drama_card_has_offer_button(db, drama):
    from bot import keyboards

    assert texts.BTN_OFFER in labels(keyboards.drama_kb(drama, is_paid=False))


async def test_paid_user_sees_no_offer_button(db, drama):
    """Төлеп қойған адамға оферта түймесі керек емес."""
    from bot import keyboards

    assert texts.BTN_OFFER not in labels(keyboards.drama_kb(drama, is_paid=True))


async def test_offer_button_sends_document(fake_bot, db, drama):
    await handlers.cb_offer(make_callback(7, "offer"), fake_bot)
    assert fake_bot.calls["send_document"]


async def test_payment_message_mentions_offer():
    """Төлем экранында офертамен келісу туралы ескерту болуы керек."""
    text = texts.PAY_LINK.format(title="Тең емес", price=490)
    assert "оферта" in text.lower()
