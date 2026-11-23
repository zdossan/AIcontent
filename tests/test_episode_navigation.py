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


async def test_next_episode_replaces_previous_message(fake_bot, db,
                                                      drama_with_26_episodes):
    """«Алдыға» басқанда ескі бөлім чаттан өшіп, орнына жаңасы келеді."""
    d = drama_with_26_episodes
    await handlers.cb_episode(make_callback(7, f"ep:{d.id}:2"), fake_bot)
    assert fake_bot.calls["delete_message"][0]["message_id"] == 1
    assert fake_bot.calls["copy_message"][0]["message_id"] == 11


async def test_first_episode_does_not_delete_the_menu(fake_bot, db,
                                                      drama_with_26_episodes):
    """«Тегін көру» мәзір хабарламасын өшірмейді - ол бөлім емес."""
    d = drama_with_26_episodes
    await handlers.cb_free(make_callback(7, f"free:{d.id}"), fake_bot)
    assert "delete_message" not in fake_bot.calls


async def test_episode_still_protected_after_switch(fake_bot, db,
                                                    drama_with_26_episodes):
    """Ауыстырғаннан кейін де видеоны жіберуге тыйым сақталады."""
    d = drama_with_26_episodes
    await handlers.cb_episode(make_callback(7, f"ep:{d.id}:4"), fake_bot)
    assert fake_bot.calls["copy_message"][0]["protect_content"] is True


async def test_sending_episode_records_progress(fake_bot, db,
                                                drama_with_26_episodes):
    """Бөлім жіберілгенде көру прогресі жазылуы керек."""
    d = drama_with_26_episodes
    await handlers.send_episode(fake_bot, 7, d, 4)
    assert store.max_viewed(7, d.id) == 4


async def test_failed_send_does_not_record_progress(fake_bot, db, drama):
    """Бөлім жоқ болса прогресс жазылмайды."""
    await handlers.send_episode(fake_bot, 7, drama, 2)
    assert store.max_viewed(7, drama.id) == 0
