"""bot.sheets - сатылымдарды Google кестесіне жазу."""

import pytest

from bot import sheets, store


def test_sale_row_has_all_columns(db, drama):
    store.create_purchase(7, drama.id, "qr_1", 490)
    purchase = store.mark_paid("qr_1")
    row = sheets.sale_row(purchase, drama, username="aigerim",
                          first_name="Әйгерім")
    assert row == [
        store.to_local(purchase.paid_at), "Тең емес", 490, "Әйгерім",
        "@aigerim", 7, "paid", "qr_1", store.to_local(purchase.created_at),
    ]


def test_sale_row_without_username(db, drama):
    store.create_purchase(7, drama.id, "qr_1", 490)
    purchase = store.mark_paid("qr_1")
    row = sheets.sale_row(purchase, drama, username=None, first_name=None)
    assert row[3] == "" and row[4] == ""


def test_disabled_without_sheet_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    assert sheets.is_enabled() is False


async def test_append_is_silent_when_disabled(db, drama, monkeypatch):
    """Баптау жоқ болса - қате емес, жай ештеңе істемейді."""
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    store.create_purchase(7, drama.id, "qr_1", 490)
    purchase = store.mark_paid("qr_1")
    assert await sheets.append_sale(purchase, drama, None, None) is False


async def test_sheets_failure_does_not_block_access(fake_bot, db, drama,
                                                    paid_user, monkeypatch):
    """Кесте істен шықса да сатып алушы сілтемесін алуы керек."""
    from bot import billing

    async def boom(*args, **kwargs):
        raise RuntimeError("Google дауылы")

    monkeypatch.setattr(sheets, "append_sale", boom)
    assert await billing.grant_access(fake_bot, 7, paid_user, drama) is True


async def test_paid_invoice_is_written_to_sheet(fake_bot, db, drama,
                                                fake_arzan, monkeypatch):
    """Төлем өткенде жол кестеге кетуі керек."""
    from bot import billing

    written = []

    async def capture(purchase, drama_, username, first_name):
        written.append((purchase.invoice_id, drama_.title, username))
        return True

    monkeypatch.setattr(sheets, "append_sale", capture)
    store.upsert_user(7, "aigerim", "Әйгерім")
    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.invoice_status = "paid"
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert written == [("qr_1", "Тең емес", "aigerim")]
