"""bot.config - баптаулар .env-тен дұрыс оқылуын тексеру."""

from bot import config


def test_admin_ids_parses_space_separated(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "913413251 42")
    assert config.admin_ids() == {913413251, 42}


def test_admin_ids_empty_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    assert config.admin_ids() == set()


def test_sandbox_defaults_to_true(monkeypatch):
    monkeypatch.delenv("ARZAN_SANDBOX", raising=False)
    assert config.is_sandbox() is True
