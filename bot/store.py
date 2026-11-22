"""SQLite қоймасы: сериалдар, бөлімдер, қолданушылар, төлемдер.

sqlite3 синхронды жұмыс істейді. Хендлерлер бұл функцияларды
asyncio.to_thread арқылы шақырады, ал жазу құлыппен қорғалған.
"""

from __future__ import annotations

import logging
import random
import sqlite3
import string
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

TZ = ZoneInfo("Asia/Almaty")
BIND_CODE_ALPHABET = string.ascii_uppercase + string.digits
BIND_CODE_LEN = 6

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS dramas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT    NOT NULL,
    description    TEXT    NOT NULL DEFAULT '',
    channel_id     INTEGER,
    price_kzt      INTEGER NOT NULL,
    total_episodes INTEGER NOT NULL,
    free_episodes  INTEGER NOT NULL,
    bind_code      TEXT    NOT NULL UNIQUE,
    is_active      INTEGER NOT NULL DEFAULT 1,
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS episodes (
    drama_id   INTEGER NOT NULL REFERENCES dramas(id),
    number     INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    PRIMARY KEY (drama_id, number)
);

CREATE TABLE IF NOT EXISTS users (
    tg_id      INTEGER PRIMARY KEY,
    username   TEXT,
    first_name TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id        INTEGER NOT NULL,
    drama_id     INTEGER NOT NULL REFERENCES dramas(id),
    invoice_id   TEXT    NOT NULL UNIQUE,
    amount       INTEGER NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending',
    created_at   TEXT    NOT NULL,
    paid_at      TEXT,
    invites_sent INTEGER NOT NULL DEFAULT 0
);

-- Бір адам бір сериалды екі рет сатып ала алмайды.
CREATE UNIQUE INDEX IF NOT EXISTS purchases_paid_once
    ON purchases (tg_id, drama_id) WHERE status = 'paid';

CREATE INDEX IF NOT EXISTS purchases_status ON purchases (status);
"""


@dataclass(slots=True)
class Drama:
    id: int
    title: str
    description: str
    channel_id: int | None
    price_kzt: int
    total_episodes: int
    free_episodes: int
    bind_code: str
    is_active: bool
    created_at: str


@dataclass(slots=True)
class Episode:
    drama_id: int
    number: int
    message_id: int


@dataclass(slots=True)
class Purchase:
    id: int
    tg_id: int
    drama_id: int
    invoice_id: str
    amount: int
    status: str
    created_at: str
    paid_at: str | None
    invites_sent: int

    @property
    def is_paid(self) -> bool:
        return self.status == "paid"


def _now() -> str:
    """UTC, SQLite-тің datetime() пішімінде.

    Уақыт белдеуі жазылмайды: әйтпесе жолдарды салыстыру («соңғы N минут»)
    жалған нәтиже береді. Көрсету алдында to_local() арқылы аударамыз.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def to_local(stamp: str | None) -> str:
    """Қоймадағы UTC уақытын Алматы уақытына аудару."""
    if not stamp:
        return "-"
    naive = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S")
    return naive.replace(tzinfo=timezone.utc).astimezone(TZ).strftime("%d.%m.%Y %H:%M")


def init_db(path: Path) -> None:
    """Кестелерді жасау. Қайта шақырса ештеңе бұзылмайды."""
    global _conn
    close()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(path, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.executescript(SCHEMA)
    _conn.commit()
    log.info("Дерекқор дайын: %s", path)


def close() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


def _db() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("init_db() шақырылмаған")
    return _conn


def _drama(row: sqlite3.Row) -> Drama:
    return Drama(
        id=row["id"], title=row["title"], description=row["description"],
        channel_id=row["channel_id"], price_kzt=row["price_kzt"],
        total_episodes=row["total_episodes"], free_episodes=row["free_episodes"],
        bind_code=row["bind_code"], is_active=bool(row["is_active"]),
        created_at=row["created_at"],
    )


def _purchase(row: sqlite3.Row) -> Purchase:
    return Purchase(
        id=row["id"], tg_id=row["tg_id"], drama_id=row["drama_id"],
        invoice_id=row["invoice_id"], amount=row["amount"], status=row["status"],
        created_at=row["created_at"], paid_at=row["paid_at"],
        invites_sent=row["invites_sent"],
    )


def _new_bind_code(db: sqlite3.Connection) -> str:
    while True:
        code = "".join(random.choices(BIND_CODE_ALPHABET, k=BIND_CODE_LEN))
        if db.execute("SELECT 1 FROM dramas WHERE bind_code = ?", (code,)).fetchone() is None:
            return code


# --- Сериалдар ---------------------------------------------------------


def create_drama(title: str, description: str, price_kzt: int,
                 total_episodes: int, free_episodes: int) -> Drama:
    db = _db()
    with _lock:
        code = _new_bind_code(db)
        cur = db.execute(
            "INSERT INTO dramas (title, description, price_kzt, total_episodes,"
            " free_episodes, bind_code, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, description, price_kzt, total_episodes, free_episodes, code, _now()),
        )
        db.commit()
    log.info("Сериал жасалды: %r (код %s)", title, code)
    return get_drama(cur.lastrowid)  # type: ignore[arg-type,return-value]


def bind_channel(bind_code: str, channel_id: int) -> Drama | None:
    """Кодты арнаға байлау. Код табылмаса None."""
    db = _db()
    with _lock:
        cur = db.execute(
            "UPDATE dramas SET channel_id = ? WHERE bind_code = ?",
            (channel_id, bind_code.strip().upper()),
        )
        db.commit()
    if cur.rowcount == 0:
        log.warning("Белгісіз байлау коды: %r", bind_code)
        return None
    row = db.execute("SELECT * FROM dramas WHERE bind_code = ?",
                     (bind_code.strip().upper(),)).fetchone()
    log.info("Арна байланды: %s -> сериал %s", channel_id, row["id"])
    return _drama(row)


def active_dramas() -> list[Drama]:
    """Арнасы байланған және өшірілмеген сериалдар."""
    rows = _db().execute(
        "SELECT * FROM dramas WHERE channel_id IS NOT NULL AND is_active = 1"
        " ORDER BY id"
    ).fetchall()
    return [_drama(r) for r in rows]


def all_dramas() -> list[Drama]:
    return [_drama(r) for r in _db().execute("SELECT * FROM dramas ORDER BY id")]


def get_drama(drama_id: int) -> Drama | None:
    row = _db().execute("SELECT * FROM dramas WHERE id = ?", (drama_id,)).fetchone()
    return _drama(row) if row else None


def drama_by_channel(channel_id: int) -> Drama | None:
    row = _db().execute("SELECT * FROM dramas WHERE channel_id = ?",
                        (channel_id,)).fetchone()
    return _drama(row) if row else None


# --- Қолданушылар ------------------------------------------------------


def upsert_user(tg_id: int, username: str | None, first_name: str | None) -> None:
    db = _db()
    with _lock:
        db.execute(
            "INSERT INTO users (tg_id, username, first_name, created_at)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(tg_id) DO UPDATE SET username = excluded.username,"
            " first_name = excluded.first_name",
            (tg_id, username, first_name, _now()),
        )
        db.commit()


# --- Бөлімдер ----------------------------------------------------------


def add_episode(drama_id: int, number: int, message_id: int) -> None:
    db = _db()
    with _lock:
        db.execute(
            "INSERT INTO episodes (drama_id, number, message_id) VALUES (?, ?, ?)"
            " ON CONFLICT(drama_id, number) DO UPDATE SET message_id = excluded.message_id",
            (drama_id, number, message_id),
        )
        db.commit()


def episodes(drama_id: int) -> list[Episode]:
    rows = _db().execute(
        "SELECT drama_id, number, message_id FROM episodes WHERE drama_id = ?"
        " ORDER BY number", (drama_id,)
    ).fetchall()
    return [Episode(r["drama_id"], r["number"], r["message_id"]) for r in rows]


def next_episode_number(drama_id: int) -> int:
    """Тақырыпта нөмір болмаса - келесі бос нөмір."""
    row = _db().execute("SELECT MAX(number) AS m FROM episodes WHERE drama_id = ?",
                        (drama_id,)).fetchone()
    return (row["m"] or 0) + 1


# --- Төлемдер ----------------------------------------------------------


def create_purchase(tg_id: int, drama_id: int, invoice_id: str, amount: int) -> int:
    db = _db()
    with _lock:
        cur = db.execute(
            "INSERT INTO purchases (tg_id, drama_id, invoice_id, amount, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (tg_id, drama_id, invoice_id, amount, _now()),
        )
        db.commit()
    return int(cur.lastrowid)  # type: ignore[arg-type]


def mark_paid(invoice_id: str) -> Purchase | None:
    """Төлемді «paid» деп белгілеу. Екінші рет шақырса paid_at өзгермейді."""
    db = _db()
    with _lock:
        db.execute(
            "UPDATE purchases SET status = 'paid', paid_at = ?"
            " WHERE invoice_id = ? AND status != 'paid'",
            (_now(), invoice_id),
        )
        db.commit()
    row = db.execute("SELECT * FROM purchases WHERE invoice_id = ?",
                     (invoice_id,)).fetchone()
    return _purchase(row) if row else None


def mark_status(invoice_id: str, status: str) -> None:
    """Төленбеген соңғы күйлерді жазу (expired, failed, canceled)."""
    db = _db()
    with _lock:
        db.execute(
            "UPDATE purchases SET status = ? WHERE invoice_id = ? AND status = 'pending'",
            (status, invoice_id),
        )
        db.commit()


def paid_purchase(tg_id: int, drama_id: int) -> Purchase | None:
    row = _db().execute(
        "SELECT * FROM purchases WHERE tg_id = ? AND drama_id = ? AND status = 'paid'",
        (tg_id, drama_id),
    ).fetchone()
    return _purchase(row) if row else None


def paid_drama_ids(tg_id: int) -> set[int]:
    rows = _db().execute(
        "SELECT drama_id FROM purchases WHERE tg_id = ? AND status = 'paid'", (tg_id,)
    ).fetchall()
    return {r["drama_id"] for r in rows}


def pending_purchases(since_minutes: int) -> list[Purchase]:
    """Соңғы N минуттағы аяқталмаған төлемдер - қайта қосылғанда тексеру үшін."""
    rows = _db().execute(
        "SELECT * FROM purchases WHERE status = 'pending'"
        " AND created_at >= datetime('now', ?)",
        (f"-{int(since_minutes)} minutes",),
    ).fetchall()
    return [_purchase(r) for r in rows]


def bump_invites(purchase_id: int) -> int:
    db = _db()
    with _lock:
        db.execute("UPDATE purchases SET invites_sent = invites_sent + 1 WHERE id = ?",
                   (purchase_id,))
        db.commit()
    row = db.execute("SELECT invites_sent FROM purchases WHERE id = ?",
                     (purchase_id,)).fetchone()
    return int(row["invites_sent"]) if row else 0


# --- Есеп --------------------------------------------------------------


def sales_summary() -> list[tuple[str, int, int]]:
    """(сериал атауы, сатылым саны, жалпы сома)."""
    rows = _db().execute(
        "SELECT d.title AS title, COUNT(*) AS cnt, SUM(p.amount) AS total"
        " FROM purchases p JOIN dramas d ON d.id = p.drama_id"
        " WHERE p.status = 'paid' GROUP BY d.id ORDER BY total DESC"
    ).fetchall()
    return [(r["title"], r["cnt"], r["total"]) for r in rows]


def export_rows() -> list[dict]:
    """CSV-ге шығаруға арналған барлық төлемдер."""
    rows = _db().execute(
        "SELECT p.created_at, p.paid_at, d.title, p.amount, p.status,"
        " p.tg_id, u.username, u.first_name, p.invoice_id"
        " FROM purchases p JOIN dramas d ON d.id = p.drama_id"
        " LEFT JOIN users u ON u.tg_id = p.tg_id ORDER BY p.id"
    ).fetchall()
    return [dict(r) for r in rows]
