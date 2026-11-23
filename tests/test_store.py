"""bot.store - SQLite қоймасы."""

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
    assert store.to_local(None) == "-"


def test_old_database_gets_client_name_column(tmp_path):
    """Бұрыннан бар базаға жаңа баған қосылуы керек - деректер жоғалмай."""
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript(store.SCHEMA.replace(
        "    client_name  TEXT,\n", ""))
    old.execute("INSERT INTO dramas (title, price_kzt, total_episodes,"
                " free_episodes, bind_code, created_at)"
                " VALUES ('Ескі', 490, 26, 6, 'OLD123', '2026-11-01 10:00:00')")
    old.execute("INSERT INTO purchases (tg_id, drama_id, invoice_id, amount,"
                " created_at) VALUES (7, 1, 'qr_old', 490, '2026-11-01 10:00:00')")
    old.commit()
    old.close()

    store.init_db(path)
    purchase = store.mark_paid("qr_old")
    assert purchase.client_name is None
    store.close()


def test_mark_paid_stores_kaspi_client_name(db, drama):
    store.create_purchase(7, drama.id, "qr_1", 490)
    purchase = store.mark_paid("qr_1", client_name="ДОСАН Ж.")
    assert purchase.client_name == "ДОСАН Ж."


def test_view_progress_keeps_the_furthest_episode(db, drama):
    store.mark_viewed(7, drama.id, 3)
    store.mark_viewed(7, drama.id, 6)
    store.mark_viewed(7, drama.id, 2)
    assert store.max_viewed(7, drama.id) == 6


def test_finished_free_counts_only_those_who_reached_the_last_free(db, drama):
    store.mark_viewed(7, drama.id, 6)
    store.mark_viewed(8, drama.id, 5)
    store.mark_viewed(9, drama.id, 6)
    assert store.finished_free_count() == 2
