"""bot.payments — Arzan Pay клиенті. Нақты API шақырылмайды, жергілікті
жалған сервер көтеріледі."""

import pytest

from bot import payments


async def test_create_payment_link_returns_kaspi_url(fake_arzan):
    fake_arzan.reply("/v1/payment-links", {
        "id": "qr_9f2c", "payment_url": "https://pay.kaspi.kz/pay/XXXX",
        "amount": "490.00", "expires_at": "2026-11-22T14:15:00.000Z"})
    link = await payments.create_payment_link(
        amount=490, description="Тең емес", external_order_id="d1-u7-abc")
    assert (link.id, link.url) == ("qr_9f2c", "https://pay.kaspi.kz/pay/XXXX")


async def test_check_many_maps_ids_to_statuses(fake_arzan):
    fake_arzan.reply("/v1/invoices/status/check", {"data": [
        {"id": "qr_a", "ok": True, "payment": {"status": "paid"}},
        {"id": "qr_b", "ok": False, "error": "payment_not_found"}]})
    assert await payments.check_many(["qr_a", "qr_b"]) == {"qr_a": "paid"}


async def test_check_many_without_ids_skips_request(fake_arzan):
    assert await payments.check_many([]) == {}
    assert fake_arzan.requests == []


async def test_http_error_raises_arzan_error(fake_arzan):
    fake_arzan.reply("/v1/payment-links",
                     {"error": "no_balance", "message": "жеткіліксіз"}, status=402)
    with pytest.raises(payments.ArzanError) as err:
        await payments.create_payment_link(
            amount=490, description="x", external_order_id="y")
    assert err.value.code == "no_balance"


def test_invoice_expired_is_final_but_not_paid():
    inv = payments.Invoice(id="qr_a", status="expired", amount="490.00")
    assert inv.is_final and not inv.is_paid


def test_invoice_paid_is_final():
    inv = payments.Invoice(id="qr_a", status="paid", amount="490.00")
    assert inv.is_final and inv.is_paid
