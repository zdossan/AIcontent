"""bot.admin - иесіне арналған командалар."""

import pytest

from bot import admin, store
from tests.conftest import ADMIN_ID, make_message


@pytest.fixture(autouse=True)
def admin_env(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", str(ADMIN_ID))


async def feed(fake_bot, fsm, answers: list[str]) -> None:
    """Диалогты қадам-қадам өткізу."""
    await admin.cmd_new(make_message(ADMIN_ID, "/жаңа"), fake_bot, fsm)
    for answer in answers:
        await admin.handle_new_step(make_message(ADMIN_ID, answer), fake_bot, fsm)


async def test_non_admin_gets_no_answer(fake_bot, db):
    await admin.cmd_stats(make_message(999, "/stats"), fake_bot)
    assert "send_message" not in fake_bot.calls


async def test_new_drama_dialog_creates_drama_and_returns_code(fake_bot, db, fsm):
    await feed(fake_bot, fsm, ["Тең емес", "Сипаттама", "490", "26", "6"])
    d = store.get_drama(1)
    assert (d.title, d.price_kzt, d.total_episodes, d.free_episodes) == (
        "Тең емес", 490, 26, 6)
    assert d.bind_code in fake_bot.last_text()


async def test_new_drama_rejects_non_numeric_price(fake_bot, db, fsm):
    await feed(fake_bot, fsm, ["Тең емес", "Сипаттама", "тегін"])
    assert "сан" in fake_bot.last_text().lower()
    assert store.all_dramas() == []


async def test_new_drama_rejects_free_above_total(fake_bot, db, fsm):
    await feed(fake_bot, fsm, ["Тең емес", "Сипаттама", "490", "26", "30"])
    assert store.all_dramas() == []


async def test_bolimder_reports_missing_episodes(fake_bot, db, drama):
    store.add_episode(drama.id, 1, 10)
    store.add_episode(drama.id, 3, 12)
    await admin.cmd_bolimder(make_message(ADMIN_ID, "/bolimder"), fake_bot)
    assert "2" in fake_bot.last_text()


async def test_stats_shows_sales(fake_bot, db, drama, paid_user):
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert "490" in text and "Барлық уақытта: 1" in text


async def test_export_sends_csv(fake_bot, db, drama, paid_user):
    await admin.cmd_export(make_message(ADMIN_ID, "/export"), fake_bot)
    assert fake_bot.calls["send_document"]


async def test_command_during_dialog_cancels_it(fake_bot, db, fsm):
    """Диалог ортасында /start жазса - иесі тұрып қалмауы керек."""
    await admin.cmd_new(make_message(ADMIN_ID, "/жаңа"), fake_bot, fsm)
    await admin.handle_new_step(make_message(ADMIN_ID, "/start"), fake_bot, fsm)
    assert await fsm.get_state() is None
    assert store.all_dramas() == []


async def test_stats_does_not_list_individual_buyers(fake_bot, db, drama,
                                                     paid_user):
    """/stats - қысқа есеп. Жеке адамдардың аты мен id-і онда көрінбейді,
    олар /export пен Google кестеде қалады."""
    store.upsert_user(paid_user, "aigerim", "Әйгерім")
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert "aigerim" not in text
    assert str(paid_user) not in text


async def test_stats_counts_pending_separately(fake_bot, db, drama, paid_user):
    """Аяқталмаған төлемдер сатылымға қосылмауы керек."""
    store.create_purchase(555, drama.id, "qr_pending", 490)
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert "490" in text
    assert "980" not in text


async def test_admin_commands_are_registered_in_menu(fake_bot, db, monkeypatch):
    """Иесінің Telegram мәзірінде командалар көрінуі керек."""
    monkeypatch.setenv("ADMIN_IDS", str(ADMIN_ID))
    await admin.setup_admin_commands(fake_bot)
    call = fake_bot.calls["set_my_commands"][0]
    names = [c.command for c in call["commands"]]
    assert {"stats", "export", "bolimder"} <= set(names)
    assert call["scope"].chat_id == ADMIN_ID


async def test_no_admin_commands_without_admins(fake_bot, db, monkeypatch):
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    await admin.setup_admin_commands(fake_bot)
    assert "set_my_commands" not in fake_bot.calls


async def test_stats_shows_user_count(fake_bot, db, drama, paid_user):
    """Ботты қанша адам ашқаны көрінуі керек."""
    store.upsert_user(111, "a", "A")
    store.upsert_user(222, "b", "B")
    store.upsert_user(paid_user, "c", "C")
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    assert "/start басқандар: 3" in fake_bot.last_text()


async def test_stats_shows_conversion(fake_bot, db, drama, paid_user):
    """4 адам ашса, 1-еуі төлесе - конверсия 25%."""
    for tg_id in (111, 222, 333):
        store.upsert_user(tg_id, None, None)
    store.upsert_user(paid_user, None, None)
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    assert "25" in fake_bot.last_text()


def test_users_count_is_distinct(db):
    store.upsert_user(7, "a", "A")
    store.upsert_user(7, "a2", "A2")
    assert store.users_count() == 1


async def test_stats_shows_funnel_step(fake_bot, db, drama_with_26_episodes):
    """Тегін бөлімдерді аяқтағандар саны статистикада болуы керек."""
    store.upsert_user(111, None, None)
    store.upsert_user(222, None, None)
    store.mark_viewed(111, drama_with_26_episodes.id, 6)
    store.mark_viewed(222, drama_with_26_episodes.id, 3)
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert "аяқтағандар" in text.lower()


async def test_stats_shows_payment_periods(fake_bot, db, drama, paid_user):
    """Төлемдер бүгін / осы айда / барлық уақытта болып бөлінуі керек."""
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert "Бүгін" in text
    assert "Осы айда" in text
    assert "Барлық уақытта" in text


async def test_stats_hides_per_drama_breakdown_for_single_drama(
        fake_bot, db, drama, paid_user):
    """Бір сериал болса, оны бөлек тізіп жазудың мағынасы жоқ."""
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    assert fake_bot.last_text().count("Тең емес") == 0


async def test_stats_shows_per_drama_breakdown_for_several(
        fake_bot, db, drama, paid_user):
    second = store.create_drama("Екінші", "", 990, 10, 3)
    store.bind_channel(second.bind_code, -100555)
    store.create_purchase(555, second.id, "qr_2", 990)
    store.mark_paid("qr_2")
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert "Тең емес" in text and "Екінші" in text


async def test_stats_follows_the_requested_layout(fake_bot, db, drama, paid_user):
    """Иесі сұраған құрылым: тақырып, мүшелер, төлемдер, конверсия."""
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    for block in ("📊", "Статистика", "👥 <b>Мүшелер</b>", "Белсенді:",
                  "💰 <b>Төлемдер</b>", "📈 <b>Конверсия</b>",
                  "/start басқандар:", "Төлемді бастағандар:",
                  "Төлем жасағандар:"):
        assert block in text, block


async def test_stats_order_of_blocks(fake_bot, db, drama, paid_user):
    await admin.cmd_stats(make_message(ADMIN_ID, "/stats"), fake_bot)
    text = fake_bot.last_text()
    assert text.index("Мүшелер") < text.index("Төлемдер") < text.index("Конверсия")
