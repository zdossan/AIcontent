"""Тегін бөлімдерді бір-бірлеп көрсету: «алдыға» / «артқа» түймелері."""

from bot import handlers, store
from tests.conftest import make_callback


def labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row]


async def test_free_view_sends_only_first_episode(fake_bot, db, drama_with_26_episodes):
    d = drama_with_26_episodes
    await handlers.cb_free(make_callback(7, f"free:{d.id}"), fake_bot)
    assert len(fake_bot.calls["copy_message"]) == 1
    assert fake_bot.calls["copy_message"][0]["message_id"] == 10


async def test_first_episode_has_only_forward_button(fake_bot, db, drama_with_26_episodes):
    d = drama_with_26_episodes
    await handlers.cb_free(make_callback(7, f"free:{d.id}"), fake_bot)
    assert labels(fake_bot.calls["copy_message"][0]["reply_markup"]) == [
        "Алдыға ➡️", "⬅️ Мәзірге"]


async def test_middle_episode_has_both_buttons(fake_bot, db, drama_with_26_episodes):
    d = drama_with_26_episodes
    await handlers.cb_episode(make_callback(7, f"ep:{d.id}:3"), fake_bot)
    call = fake_bot.calls["copy_message"][0]
    assert call["message_id"] == 12
    assert labels(call["reply_markup"])[:2] == ["⬅️ Артқа", "Алдыға ➡️"]


async def test_last_free_episode_offers_payment(fake_bot, db, drama_with_26_episodes):
    """6-бөлім - соңғы тегін. Одан әрі тек төлем арқылы."""
    d = drama_with_26_episodes
    await handlers.cb_episode(make_callback(7, f"ep:{d.id}:6"), fake_bot)
    assert "💳" in " ".join(labels(fake_bot.calls["copy_message"][0]["reply_markup"]))


async def test_paid_episode_is_not_sent_for_free(fake_bot, db, drama_with_26_episodes):
    """7-бөлімді тікелей сұраса да бот тегін бермейді."""
    d = drama_with_26_episodes
    await handlers.cb_episode(make_callback(7, f"ep:{d.id}:7"), fake_bot)
    assert "copy_message" not in fake_bot.calls
    assert "💳" in " ".join(labels(fake_bot.last_markup()))


async def test_episode_caption_shows_position(fake_bot, db, drama_with_26_episodes):
    d = drama_with_26_episodes
    await handlers.cb_episode(make_callback(7, f"ep:{d.id}:3"), fake_bot)
    assert fake_bot.calls["copy_message"][0]["caption"] == "«Тең емес» - 3 / 26 бөлім"


async def test_missing_episode_is_reported(fake_bot, db, drama_with_3_episodes):
    """Жүктелмеген бөлімді сұраса - түсінікті жауап."""
    d = drama_with_3_episodes
    await handlers.cb_episode(make_callback(7, f"ep:{d.id}:5"), fake_bot)
    assert "copy_message" not in fake_bot.calls
    assert fake_bot.last_text()
