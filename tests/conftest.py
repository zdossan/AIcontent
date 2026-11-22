"""Тесттерге ортақ фикстуралар."""

import pytest

from bot import store


@pytest.fixture
def db(tmp_path):
    """Әр тестке жаңа, бос дерекқор."""
    path = tmp_path / "test.db"
    store.init_db(path)
    yield path
    store.close()
