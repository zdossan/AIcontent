"""Баптаулар. Бәрі .env файлынан оқылады.

Функциялар os.getenv-ті шақырылған сәтте оқиды — модуль импортталғанда
емес. Себебі .env импорттан КЕЙІН жүктеледі (bot/__main__.py).
"""

from __future__ import annotations

import os
from pathlib import Path

TRUTHY = {"1", "true", "yes", "iya", "ia"}


class ConfigError(Exception):
    """Міндетті баптау жоқ немесе дұрыс емес."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"{name} .env файлында жоқ")
    return value


def bot_token() -> str:
    """@BotFather берген токен."""
    return _required("BOT_TOKEN")


def arzan_api_key() -> str:
    """pay.arzan.cloud кабинетіндегі API кілт."""
    return _required("ARZAN_API_KEY")


def is_sandbox() -> bool:
    """Тест режимі. Әдепкі — қосулы: кездейсоқ нақты ақша алынбасын."""
    raw = os.getenv("ARZAN_SANDBOX")
    if raw is None:
        return True
    return raw.strip().lower() in TRUTHY


def admin_ids() -> set[int]:
    """Админдердің telegram id-лері, бос орынмен бөлінеді."""
    raw = os.getenv("ADMIN_IDS", "")
    return {int(part) for part in raw.split() if part.lstrip("-").isdigit()}


def db_path() -> Path:
    """SQLite файлының жолы."""
    return Path(os.getenv("DB_PATH", "aicontent.db")).expanduser()
