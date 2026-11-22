"""Жария оферта құжаты.

PDF боттың өз ішінде жатыр - сыртқы сайтқа тәуелді болмауы үшін.
"""

from __future__ import annotations

from pathlib import Path

FILENAME = "KelesiBolim-oferta.pdf"


def path() -> Path:
    return Path(__file__).parent / "assets" / "oferta.pdf"


def document():
    """Telegram-ге жіберуге дайын файл."""
    from aiogram.types import FSInputFile

    return FSInputFile(path(), filename=FILENAME)
