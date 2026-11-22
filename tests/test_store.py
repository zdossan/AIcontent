"""bot.store — SQLite қоймасы."""

from bot import store


def test_bind_channel_activates_drama(db):
    d = store.create_drama("Тең емес", "сипаттама", 490, 26, 6)
    assert store.active_dramas() == []
    bound = store.bind_channel(d.bind_code, -1001234567890)
    assert bound.id == d.id
    assert [x.id for x in store.active_dramas()] == [d.id]


def test_bind_channel_unknown_code_returns_none(db):
    assert store.bind_channel("NOPE", -100123) is None


def test_mark_paid_is_idempotent(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_1", 490)
    first = store.mark_paid("qr_1")
    second = store.mark_paid("qr_1")
    assert first.status == "paid" and first.paid_at
    assert second.paid_at == first.paid_at


def test_add_episode_upserts_by_number(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.add_episode(d.id, 1, 100)
    store.add_episode(d.id, 1, 200)
    assert [(e.number, e.message_id) for e in store.episodes(d.id)] == [(1, 200)]


def test_paid_drama_ids(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_1", 490)
    assert store.paid_drama_ids(7) == set()
    store.mark_paid("qr_1")
    assert store.paid_drama_ids(7) == {d.id}


def test_pending_purchases_finds_fresh_purchase(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_1", 490)
    assert [p.invoice_id for p in store.pending_purchases(60)] == ["qr_1"]


def test_pending_purchases_ignores_paid(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_1", 490)
    store.mark_paid("qr_1")
    assert store.pending_purchases(60) == []


def test_pending_purchases_ignores_old_purchase(db):
    """3 сағат бұрынғы төлем «соңғы 60 минут» сүзгісіне түспеуі керек."""
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_old", 490)
    store._db().execute(
        "UPDATE purchases SET created_at = datetime('now', '-180 minutes')"
        " WHERE invoice_id = 'qr_old'")
    assert store.pending_purchases(60) == []


def test_created_at_is_comparable_with_sqlite_now(db):
    """created_at SQLite-тің datetime('now') пішімімен салыстырылуы керек.

    Әйтпесе «соңғы N минут» сүзгісі жалған нәтиже береді.
    """
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_1", 490)
    row = store._db().execute(
        "SELECT created_at >= datetime('now', '-5 minutes') AS fresh,"
        " created_at <= datetime('now', '+5 minutes') AS not_future"
        " FROM purchases WHERE invoice_id = 'qr_1'"
    ).fetchone()
    assert (row["fresh"], row["not_future"]) == (1, 1)


def test_to_local_renders_almaty_time():
    assert store.to_local("2026-11-22 09:30:00") == "22.11.2026 14:30"


def test_to_local_handles_missing_stamp():
    assert store.to_local(None) == "—"
