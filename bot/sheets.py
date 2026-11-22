"""Сатылымдарды Google кестесіне жазу - «тірі» есеп үшін.

Кесте - қосымша ыңғайлылық, негізгі дерекқор емес. Сондықтан мұндағы
кез келген қате жұмысты тоқтатпайды: ақша түскен адам сілтемесін
бәрібір алады, ал қате логқа жазылады.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from bot import store
from bot.store import Drama, Purchase

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADERS = [
    "Төленген уақыты", "Сериал", "Сома", "Kaspi аты-жөні",
    "Telegram аты", "username", "telegram id", "Статус", "Шот",
    "Жасалған уақыты",
]

_lock = asyncio.Lock()


def sheet_id() -> str:
    return os.getenv("GOOGLE_SHEET_ID", "").strip()


def credentials_file() -> Path:
    return Path(os.getenv("GOOGLE_CREDENTIALS_FILE",
                          "google-credentials.json")).expanduser()


def is_enabled() -> bool:
    """Кесте бапталған ба? Бапталмаса бот онсыз да жұмыс істей береді."""
    return bool(sheet_id()) and credentials_file().is_file()


def sale_row(purchase: Purchase, drama: Drama, username: str | None,
             first_name: str | None) -> list:
    """Кестеге жазылатын бір жол."""
    return [
        store.to_local(purchase.paid_at),
        drama.title,
        purchase.amount,
        purchase.client_name or "",
        first_name or "",
        f"@{username}" if username else "",
        purchase.tg_id,
        purchase.status,
        purchase.invoice_id,
        store.to_local(purchase.created_at),
    ]


def _append_sync(row: list) -> None:
    """gspread синхронды жұмыс істейді - бөлек ағында шақырылады."""
    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(str(credentials_file()),
                                                  scopes=SCOPES)
    worksheet = gspread.authorize(creds).open_by_key(sheet_id()).sheet1

    # Бірінші жазуда тақырып жолын қоямыз.
    if not worksheet.acell("A1").value:
        worksheet.update(values=[HEADERS], range_name="A1")

    worksheet.append_row(row, value_input_option="USER_ENTERED")


async def append_sale(purchase: Purchase, drama: Drama, username: str | None,
                      first_name: str | None) -> bool:
    """Сатылымды кестеге қосу. Сәтсіз болса False, бірақ қате лақтырмайды."""
    if not is_enabled():
        return False

    row = sale_row(purchase, drama, username, first_name)
    try:
        async with _lock:
            await asyncio.to_thread(_append_sync, row)
    except Exception:
        log.exception("Кестеге жазылмады (шот %s) - дерекқорда сақталды",
                      purchase.invoice_id)
        return False

    log.info("Кестеге жазылды: шот %s", purchase.invoice_id)
    return True
