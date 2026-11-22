"""bot.catalog — арнадағы посттардан бөлімдер жинау."""

import pytest

from bot import catalog, store
from tests.conftest import make_post


@pytest.mark.parametrize("caption,expected", [
    ("3", 3), ("3-бөлім", 3), ("  12 ", 12), ("Тең емес 7-бөлім", 7),
    (None, None), ("бөлім", None), ("", None),
])
def test_parse_episode_number(caption, expected):
    assert catalog.parse_episode_number(caption) == expected


async def test_channel_post_without_number_takes_next_free(db, drama):
    store.add_episode(drama.id, 1, 10)
    await catalog.handle_channel_post(make_post(drama.channel_id, None, 11))
    assert [(e.number, e.message_id) for e in store.episodes(drama.id)] == [(1, 10), (2, 11)]


async def test_channel_post_from_unbound_channel_is_ignored(db):
    await catalog.handle_channel_post(make_post(-100999, "1", 5))
    assert store.episodes(1) == []


async def test_repeated_number_overwrites_message_id(db, drama):
    await catalog.handle_channel_post(make_post(drama.channel_id, "4", 40))
    await catalog.handle_channel_post(make_post(drama.channel_id, "4", 41))
    assert [(e.number, e.message_id) for e in store.episodes(drama.id)] == [(4, 41)]


async def test_post_without_video_is_ignored(db, drama):
    await catalog.handle_channel_post(make_post(drama.channel_id, "5", 50, video=False))
    assert store.episodes(drama.id) == []


async def test_unknown_channel_post_is_logged(db, caplog):
    """Байланбаған арнадан келген кез келген пост логқа түсуі керек —
    әйтпесе «бот ештеңе алмай жатыр» дегенді тексеру мүмкін емес."""
    import logging

    with caplog.at_level(logging.INFO, logger="bot.catalog"):
        await catalog.log_channel_post(make_post(-100777, "сәлем", 1, video=False))
    assert "-100777" in caplog.text
