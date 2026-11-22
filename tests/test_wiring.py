"""Барлық роутерлер бір-біріне кедергі жасамай жиналады ма."""

import pytest

from bot import admin, catalog, config, handlers


def test_dispatcher_accepts_all_routers():
    from aiogram import Dispatcher

    dp = Dispatcher()
    dp.include_router(admin.router)
    dp.include_router(handlers.router)
    dp.include_router(catalog.router)
    assert len(dp.sub_routers) == 3


def test_missing_token_fails_loudly(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    with pytest.raises(config.ConfigError) as err:
        config.bot_token()
    assert "BOT_TOKEN" in str(err.value)


def test_every_user_facing_string_lives_in_texts():
    """Хендлерлерде қатаң жазылған қазақша мәтін болмауы керек."""
    import re
    from pathlib import Path

    cyrillic_literal = re.compile(r'"[^"]*[әіңғүұқөһА-Яа-я][^"]*"')
    for name in ("handlers.py", "billing.py", "access.py", "catalog.py"):
        source = Path("bot", name).read_text()
        # Логтар мен docstring-терді алып тастаймыз: олар ботта көрінбейді.
        code = re.sub(r'""".*?"""', "", source, flags=re.S)
        code = "\n".join(line for line in code.split("\n")
                         if "log." not in line and not line.strip().startswith("#"))
        assert not cyrillic_literal.findall(code), f"{name}: мәтін texts.py-ға көшірілсін"
