# Short drama бот — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Telegram-бот на казахском, который продаёт short drama: каталог сериалов, 6 бесплатных серий, оплата 490 ₸ через Arzan Pay и автоматическая выдача доступа в закрытый канал.

**Architecture:** aiogram 3 на long polling, без входящих портов. Состояние в SQLite. Каждый сериал — отдельный закрытый канал, где бот админ: первые серии он копирует оттуда в личный чат через `copy_message(protect_content=True)`, а после оплаты выдаёт одноразовую инвайт-ссылку. Оплата подтверждается опросом Arzan Pay, пока платёжная ссылка жива (~3 мин).

**Tech Stack:** Python 3.12, aiogram 3.15.0, aiohttp, python-dotenv, SQLite (`sqlite3` из стандартной библиотеки), pytest + pytest-asyncio.

**Spec:** `docs/superpowers/specs/2026-11-22-shortdrama-bot-design.md`

**Донор кода:** `~/jabiq-invest-bot` — рабочий бот того же владельца. Переносятся `bot/payments.py` (клиент Arzan Pay) и `bot/group.py` (инвайт-ссылки), структура проекта и `deploy/`.

## Global Constraints

- Python 3.12, aiogram 3.15.0, aiohttp, python-dotenv — версии как в `~/jabiq-invest-bot/requirements.txt`.
- Весь текст, который видит пользователь, — на казахском и только в `bot/texts.py`. В остальных модулях строк для пользователя нет.
- Цена, количество серий, число бесплатных серий и `channel_id` живут в БД, а не в `.env`.
- Любая отправка видео пользователю — с `protect_content=True`.
- Часовой пояс `Asia/Almaty` для всех отображаемых дат.
- `.env`, `*.db`, `*.log`, `*.mp4` не коммитятся (`.gitignore` уже в репозитории).
- Комментарии в коде — на казахском, как в `jabiq-invest-bot`.
- Каждая задача завершается коммитом и `git push`.

## Review Focus

1. **Двойной клик по кнопке оплаты** — создаются два счёта, человек платит дважды. Покрывается в Task 7.
2. **Подпись видео без числа или повтор номера** — каталог молча ломается. Покрывается в Task 4.
3. **Серий залито меньше, чем бесплатных** (3 из 6) — бот должен отдать что есть и не упасть. Покрывается в Task 6.
4. **Бот не админ канала или без права приглашать** — оплата прошла, инвайт не создался. Покрывается в Task 5.
5. **Человек заблокировал бота после оплаты** — доступ обязан сохраниться в базе и выдаться при возврате. Покрывается в Task 7.

---

### Task 1: Каркас проекта и настройки

**Files:**
- Create: `requirements.txt`, `.env.example`, `README.md`, `bot/__init__.py`, `bot/config.py`, `bot/texts.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `config.bot_token() -> str`, `config.arzan_api_key() -> str`, `config.is_sandbox() -> bool`, `config.admin_ids() -> set[int]`, `config.db_path() -> Path`

- [ ] **Step 1: Write the failing test**

```python
def test_admin_ids_parses_space_separated(monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", "913413251 42")
    assert config.admin_ids() == {913413251, 42}

def test_admin_ids_empty_when_unset(monkeypatch):
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    assert config.admin_ids() == set()

def test_sandbox_defaults_to_true(monkeypatch):
    monkeypatch.delenv("ARZAN_SANDBOX", raising=False)
    assert config.is_sandbox() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL, `ModuleNotFoundError: bot.config`

- [ ] **Step 3: Implement `bot/config.py`**

Все функции читают `os.getenv` в момент вызова, не на уровне модуля — `.env` грузится позже импорта. Sandbox по умолчанию `true`: безопасный дефолт, пока владелец не переключит сам.

- [ ] **Step 4: Создать `requirements.txt`, `.env.example`, `README.md`, заготовку `bot/texts.py`**

`.env.example` — ключи `BOT_TOKEN`, `ARZAN_API_KEY`, `ARZAN_SANDBOX`, `ADMIN_IDS`, `DB_PATH` с комментариями на казахском (образец: `~/jabiq-invest-bot/.env.example`). `texts.py` пока содержит только `START_GREETING` и `HELP`.

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest -v` → PASS

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add project skeleton and settings loader" && git push
```

---

### Task 2: Хранилище (SQLite)

**Files:**
- Create: `bot/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Produces:
  - `init_db(path: Path) -> None` — создаёт таблицы, идемпотентно
  - `create_drama(title, description, price_kzt, total_episodes, free_episodes) -> Drama`
  - `bind_channel(bind_code: str, channel_id: int) -> Drama | None`
  - `active_dramas() -> list[Drama]` — только с `channel_id is not null`
  - `get_drama(drama_id: int) -> Drama | None`
  - `upsert_user(tg_id: int, username: str | None, first_name: str | None) -> None`
  - `add_episode(drama_id: int, number: int, message_id: int) -> None` — upsert по `(drama_id, number)`
  - `episodes(drama_id: int) -> list[Episode]` — по возрастанию номера
  - `create_purchase(tg_id, drama_id, invoice_id, amount) -> int`
  - `mark_paid(invoice_id: str) -> Purchase | None`
  - `paid_purchase(tg_id: int, drama_id: int) -> Purchase | None`
  - `paid_drama_ids(tg_id: int) -> set[int]`
  - `pending_purchases(since_minutes: int) -> list[Purchase]`
  - `bump_invites(purchase_id: int) -> int` — возвращает новое значение `invites_sent`
  - `sales_summary() -> list[tuple[str, int, int]]` — (название, количество, сумма)
  - `export_rows() -> list[dict]`
- Датаклассы `Drama`, `Episode`, `Purchase` с полями из схемы спецификации.

- [ ] **Step 1: Write the failing test**

```python
def test_bind_channel_activates_drama(db):
    d = store.create_drama("Тең емес", "сипаттама", 490, 26, 6)
    assert store.active_dramas() == []
    bound = store.bind_channel(d.bind_code, -1001234567890)
    assert bound.id == d.id
    assert [x.id for x in store.active_dramas()] == [d.id]

def test_bind_channel_unknown_code_returns_none(db):
    assert store.bind_channel("NOPE", -100123) is None

def test_mark_paid_is_idempotent(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_1", 490)
    first = store.mark_paid("qr_1")
    second = store.mark_paid("qr_1")
    assert first.status == "paid" and first.paid_at
    assert second.paid_at == first.paid_at

def test_add_episode_upserts_by_number(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.add_episode(d.id, 1, 100)
    store.add_episode(d.id, 1, 200)
    assert [(e.number, e.message_id) for e in store.episodes(d.id)] == [(1, 200)]

def test_paid_drama_ids(db):
    d = store.create_drama("Тең емес", "", 490, 26, 6)
    store.create_purchase(7, d.id, "qr_1", 490)
    assert store.paid_drama_ids(7) == set()
    store.mark_paid("qr_1")
    assert store.paid_drama_ids(7) == {d.id}
```

Фикстура `db` создаёт временный файл и зовёт `init_db`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_store.py -v` → FAIL

- [ ] **Step 3: Implement `bot/store.py`**

Схема таблиц — из спецификации. `bind_code` — 6 символов `A-Z0-9`, уникальный. Уникальный индекс на `(drama_id, number)` в `episodes` и частичный уникальный индекс на `(tg_id, drama_id) WHERE status='paid'` в `purchases` — страховка от двойной оплаты на уровне базы. Все вызовы синхронные, оборачиваются в `asyncio.to_thread` на стороне обработчиков; запись под `threading.Lock`.

- [ ] **Step 4: Run tests** → PASS
- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Add SQLite store for dramas, episodes and purchases" && git push
```

---

### Task 3: Клиент Arzan Pay

**Files:**
- Create: `bot/payments.py` (перенос из `~/jabiq-invest-bot/bot/payments.py`)
- Test: `tests/test_payments.py`

**Interfaces:**
- Produces: `create_payment_link(*, amount: int, description: str, external_order_id: str) -> PaymentLink`, `get_invoice(invoice_id: str) -> Invoice`, `check_many(ids: list[str]) -> dict[str, str]`, `ArzanError`, датаклассы `PaymentLink(id, url, amount, expires_at)` и `Invoice(id, status, amount)` со свойствами `is_paid` и `is_final`.

- [ ] **Step 1: Скопировать `payments.py` из донора**

```bash
cp ~/jabiq-invest-bot/bot/payments.py bot/payments.py
```

Удалить неиспользуемые `create_invoice` и `normalize_phone` — оплата идёт только по ссылке, телефон не запрашивается (YAGNI).

- [ ] **Step 2: Write the failing test**

```python
async def test_check_many_maps_ids_to_statuses(fake_api):
    fake_api.post("/v1/invoices/status/check", {
        "data": [{"id": "qr_a", "ok": True, "payment": {"status": "paid"}},
                 {"id": "qr_b", "ok": False, "error": "payment_not_found"}]})
    assert await payments.check_many(["qr_a", "qr_b"]) == {"qr_a": "paid"}

async def test_http_error_raises_arzan_error(fake_api):
    fake_api.post("/v1/payment-links", {"error": "no_balance", "message": "..."}, status=402)
    with pytest.raises(payments.ArzanError) as e:
        await payments.create_payment_link(amount=490, description="x", external_order_id="y")
    assert e.value.code == "no_balance"

def test_invoice_expired_is_final_but_not_paid():
    inv = payments.Invoice(id="qr_a", status="expired", amount="490.00")
    assert inv.is_final and not inv.is_paid
```

`fake_api` — локальный aiohttp-сервер, `ARZAN_BASE_URL` указывает на него.

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_payments.py -v` → FAIL, `check_many` не определён

- [ ] **Step 4: Implement `check_many(ids: list[str]) -> dict[str, str]` в `bot/payments.py`**

`POST /v1/invoices/status/check` с телом `{"ids": [...]}`. В словарь попадают только записи с `ok: true`; значение — `payment.status`.

- [ ] **Step 5: Run tests** → PASS
- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Port Arzan Pay client with batch status check" && git push
```

---

### Task 4: Каталог серий и привязка канала

**Files:**
- Create: `bot/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `store.add_episode`, `store.bind_channel`, `store.episodes`
- Produces: `parse_episode_number(caption: str | None) -> int | None`, `router` (aiogram `Router` с хендлерами `channel_post` и команды `/bind`)

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.parametrize("caption,expected", [
    ("3", 3), ("3-бөлім", 3), ("  12 ", 12), ("Тең емес 7-бөлім", 7),
    (None, None), ("бөлім", None), ("", None),
])
def test_parse_episode_number(caption, expected):
    assert catalog.parse_episode_number(caption) == expected

async def test_channel_post_without_number_takes_next_free(db, drama):
    store.add_episode(drama.id, 1, 10)
    await catalog.handle_channel_post(make_post(drama.channel_id, caption=None, message_id=11))
    assert [(e.number, e.message_id) for e in store.episodes(drama.id)] == [(1, 10), (2, 11)]

async def test_channel_post_from_unbound_channel_is_ignored(db):
    await catalog.handle_channel_post(make_post(-100999, caption="1", message_id=5))
    assert store.episodes(1) == []

async def test_repeated_number_overwrites_message_id(db, drama):
    await catalog.handle_channel_post(make_post(drama.channel_id, "4", 40))
    await catalog.handle_channel_post(make_post(drama.channel_id, "4", 41))
    assert [(e.number, e.message_id) for e in store.episodes(drama.id)] == [(4, 41)]
```

- [ ] **Step 2: Run test to verify it fails** → FAIL
- [ ] **Step 3: Implement `bot/catalog.py`**

`parse_episode_number` берёт первое целое число в подписи регулярным выражением. Хендлер `channel_post` реагирует только на посты с `video` из канала, у которого в базе есть сериал; при отсутствии номера берёт `max(number) + 1` и пишет предупреждение в лог. Команда `/bind <код>` работает только внутри канала: привязывает `chat.id` и удаляет своё сообщение, чтобы код не висел в канале.

- [ ] **Step 4: Run tests** → PASS
- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Collect episodes from channel posts and bind channels" && git push
```

---

### Task 5: Доступ в канал

**Files:**
- Create: `bot/access.py` (основа — `~/jabiq-invest-bot/bot/group.py`)
- Test: `tests/test_access.py`

**Interfaces:**
- Produces: `personal_invite(bot, channel_id: int, tg_id: int) -> str | None`, `is_member(bot, channel_id: int, tg_id: int) -> bool`
- `personal_invite` возвращает `None`, если Telegram отказал: вызывающая сторона обязана это обработать, молчаливый фолбэк запрещён.

- [ ] **Step 1: Write the failing test**

```python
async def test_personal_invite_is_single_use_and_expires(fake_bot):
    url = await access.personal_invite(fake_bot, -100123, 7)
    call = fake_bot.calls["create_chat_invite_link"][0]
    assert call["member_limit"] == 1
    assert call["expire_date"] > int(time.time())
    assert url == fake_bot.invite_url

async def test_personal_invite_returns_none_when_bot_lacks_rights(fake_bot):
    fake_bot.fail_with = TelegramBadRequest(method=..., message="not enough rights")
    assert await access.personal_invite(fake_bot, -100123, 7) is None

async def test_is_member_false_when_left(fake_bot):
    fake_bot.member_status = "left"
    assert await access.is_member(fake_bot, -100123, 7) is False
```

- [ ] **Step 2: Run test to verify it fails** → FAIL
- [ ] **Step 3: Implement `bot/access.py`**

`create_chat_invite_link` с `member_limit=1`, `expire_date = now + 24h`, `name=f"user {tg_id}"`. `is_member` считает участником статусы `member`, `administrator`, `creator`. Все ошибки `TelegramAPIError` логируются с `channel_id` и `tg_id`.

- [ ] **Step 4: Run tests** → PASS
- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Add single-use channel invites and membership check" && git push
```

---

### Task 6: Каталог в боте и бесплатные серии

**Files:**
- Create: `bot/keyboards.py`, `bot/handlers.py`, `bot/__main__.py`
- Modify: `bot/texts.py`
- Test: `tests/test_handlers_catalog.py`

**Interfaces:**
- Consumes: `store.active_dramas`, `store.episodes`, `store.paid_drama_ids`, `store.upsert_user`
- Produces: `router`, `send_free_episodes(bot, chat_id, drama) -> int` (сколько серий отправлено), клавиатуры `catalog_kb(dramas, paid_ids)`, `drama_kb(drama, is_paid)`

- [ ] **Step 1: Write the failing test**

```python
async def test_start_lists_active_dramas(fake_bot, db, drama):
    await handlers.cmd_start(make_message(tg_id=7))
    kb = fake_bot.last_markup()
    assert kb.inline_keyboard[0][0].text.startswith("Тең емес")

async def test_start_marks_purchased_drama(fake_bot, db, drama, paid_user):
    await handlers.cmd_start(make_message(tg_id=paid_user))
    assert "✅" in fake_bot.last_markup().inline_keyboard[0][0].text

async def test_free_episodes_copied_with_protection(fake_bot, db, drama_with_26_episodes):
    sent = await handlers.send_free_episodes(fake_bot, 7, drama_with_26_episodes)
    assert sent == 6
    calls = fake_bot.calls["copy_message"]
    assert [c["message_id"] for c in calls] == [10, 11, 12, 13, 14, 15]
    assert all(c["protect_content"] is True for c in calls)

async def test_free_episodes_sends_what_exists(fake_bot, db, drama_with_3_episodes):
    assert await handlers.send_free_episodes(fake_bot, 7, drama_with_3_episodes) == 3
```

- [ ] **Step 2: Run test to verify it fails** → FAIL
- [ ] **Step 3: Implement `/start`, карточку сериала и выдачу бесплатных серий**

`/start` зовёт `upsert_user` и строит клавиатуру из `active_dramas()`; купленные помечаются `✅`. Карточка сериала — название, описание, число серий, цена, кнопки `🎬 Тегін көру` / `💳 Толық нұсқа — {price} ₸` / `⬅️ Артқа`. `send_free_episodes` копирует серии с номерами `1..free_episodes` через `copy_message(protect_content=True)`; отсутствующие пропускает. Если отправлено меньше, чем `free_episodes`, пользователь видит `texts.EPISODES_SOON`, а админу уходит уведомление. После последней серии — тизер `texts.PAYWALL` с кнопкой оплаты.

- [ ] **Step 4: Написать `bot/__main__.py`**

Образец — `~/jabiq-invest-bot/bot/__main__.py`: загрузка `.env`, `init_db`, подключение роутеров, `delete_webhook(drop_pending_updates=False)`, `start_polling`.

- [ ] **Step 5: Run tests** → PASS
- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add drama catalog and free episode delivery" && git push
```

---

### Task 7: Оплата и выдача доступа

**Files:**
- Create: `bot/billing.py`
- Modify: `bot/handlers.py`, `bot/texts.py`, `bot/__main__.py`
- Test: `tests/test_billing.py`

**Interfaces:**
- Consumes: `payments.create_payment_link`, `payments.get_invoice`, `payments.check_many`, `access.personal_invite`, `access.is_member`, `store.*`
- Produces: `start_payment(bot, chat_id, tg_id, drama) -> None`, `watch_invoice(bot, chat_id, tg_id, drama_id, invoice_id) -> None`, `grant_access(bot, chat_id, tg_id, drama) -> bool`, `recover_pending(bot) -> int`

- [ ] **Step 1: Write the failing test**

```python
async def test_second_click_reuses_live_invoice(fake_bot, db, drama, fake_arzan):
    await billing.start_payment(fake_bot, 7, 7, drama)
    await billing.start_payment(fake_bot, 7, 7, drama)
    assert len(fake_arzan.created_links) == 1

async def test_already_paid_skips_payment_and_grants_access(fake_bot, db, drama, paid_user):
    await billing.start_payment(fake_bot, 7, paid_user, drama)
    assert fake_arzan.created_links == []
    assert fake_bot.calls["create_chat_invite_link"]

async def test_paid_invoice_marks_purchase_and_sends_invite(fake_bot, db, drama, fake_arzan):
    fake_arzan.status = "paid"
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert store.paid_purchase(7, drama.id).status == "paid"
    assert fake_bot.invite_url in fake_bot.last_text()

async def test_purchase_stays_paid_when_invite_fails(fake_bot, db, drama, fake_arzan):
    fake_arzan.status = "paid"
    fake_bot.fail_with = TelegramBadRequest(method=..., message="not enough rights")
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert store.paid_purchase(7, drama.id) is not None
    assert fake_bot.admin_notified

async def test_blocked_user_keeps_access(fake_bot, db, drama, fake_arzan):
    fake_arzan.status = "paid"
    fake_bot.send_fails_with = TelegramForbiddenError(method=..., message="bot was blocked")
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert store.paid_purchase(7, drama.id) is not None

async def test_expired_invoice_offers_new_link(fake_bot, db, drama, fake_arzan):
    fake_arzan.status = "expired"
    await billing.watch_invoice(fake_bot, 7, 7, drama.id, "qr_1")
    assert "🔄" in fake_bot.last_markup().inline_keyboard[0][0].text

async def test_recover_pending_grants_access_after_restart(fake_bot, db, drama, fake_arzan):
    store.create_purchase(7, drama.id, "qr_1", 490)
    fake_arzan.batch = {"qr_1": "paid"}
    assert await billing.recover_pending(fake_bot) == 1
    assert store.paid_purchase(7, drama.id) is not None

async def test_invite_limit_reached(fake_bot, db, drama, paid_user):
    for _ in range(5):
        await billing.grant_access(fake_bot, 7, paid_user, drama)
    assert await billing.grant_access(fake_bot, 7, paid_user, drama) is False
```

- [ ] **Step 2: Run test to verify it fails** → FAIL
- [ ] **Step 3: Implement `bot/billing.py`**

`start_payment`: если `paid_purchase` есть — сразу `grant_access` без счёта; иначе берёт живую ссылку из кэша `(tg_id, drama_id) -> (url, invoice_id, deadline)` или создаёт новую с `external_order_id = f"d{drama_id}-u{tg_id}-{uuid4().hex[:8]}"`, пишет `create_purchase` и запускает `watch_invoice` фоновой задачей.

`watch_invoice`: опрос `get_invoice` раз в 3 секунды, пока не истечёт ~200 секунд. `paid` → `mark_paid` и `grant_access`; `expired`/`failed`/`canceled` → сообщение с кнопкой `🔄 Жаңа сілтеме`. Сетевая ошибка не прерывает цикл.

`grant_access`: порядок жёсткий — сначала `mark_paid`, потом инвайт. Если `is_member` уже `True` — сообщение, что доступ есть. `bump_invites` > 5 → `False` и просьба написать админу. Если `personal_invite` вернул `None` или отправка упала — покупка остаётся `paid`, в лог и админу уходит `tg_id` с названием сериала, пользователю (если достижим) — кнопка `🔄 Қайта көру`.

`recover_pending`: при старте берёт `pending_purchases(60)`, один вызов `check_many`, по оплаченным — `grant_access`. Вызывается из `__main__` после `init_db`.

- [ ] **Step 4: Добавить кнопку `👤 Менің сериалдарым` в `bot/handlers.py`**

Тест:

```python
async def test_my_dramas_lists_only_paid(fake_bot, db, drama, other_drama, paid_user):
    await handlers.cb_my_dramas(make_callback(tg_id=paid_user))
    kb = fake_bot.last_markup()
    assert [b.text for row in kb.inline_keyboard for b in row] == ["Тең емес", "⬅️ Артқа"]
```

Кнопка в главном меню: показывает купленные сериалы, по нажатию на любой — `grant_access`, то есть свежая одноразовая ссылка с тем же лимитом в 5 выдач. Если покупок нет — `texts.NO_PURCHASES`.

- [ ] **Step 5: Run tests** → PASS
- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "Add payment flow with access granting and restart recovery" && git push
```

---

### Task 8: Админка

**Files:**
- Create: `bot/admin.py`
- Modify: `bot/__main__.py`
- Test: `tests/test_admin.py`

**Interfaces:**
- Consumes: `store.create_drama`, `store.sales_summary`, `store.export_rows`, `store.episodes`, `config.admin_ids`
- Produces: `router` с `/жаңа` (FSM-диалог), `/bolimder`, `/stats`, `/export`

- [ ] **Step 1: Write the failing test**

```python
async def test_non_admin_gets_no_answer(fake_bot, db):
    await admin.cmd_stats(make_message(tg_id=999))
    assert fake_bot.calls["send_message"] == []

async def test_new_drama_dialog_creates_drama_and_returns_code(fake_bot, db, admin_fsm):
    await admin_fsm.feed(["/жаңа", "Тең емес", "Сипаттама", "490", "26", "6"])
    d = store.get_drama(1)
    assert (d.title, d.price_kzt, d.total_episodes, d.free_episodes) == ("Тең емес", 490, 26, 6)
    assert d.bind_code in fake_bot.last_text()

async def test_new_drama_rejects_non_numeric_price(fake_bot, db, admin_fsm):
    await admin_fsm.feed(["/жаңа", "Тең емес", "Сипаттама", "тегін"])
    assert "сан" in fake_bot.last_text().lower()

async def test_bolimder_reports_missing_episodes(fake_bot, db, drama):
    store.add_episode(drama.id, 1, 10)
    store.add_episode(drama.id, 3, 12)
    await admin.cmd_bolimder(make_message(tg_id=ADMIN))
    assert "2" in fake_bot.last_text()
```

- [ ] **Step 2: Run test to verify it fails** → FAIL
- [ ] **Step 3: Implement `bot/admin.py`**

Фильтр по `config.admin_ids()` на весь роутер; не-админ не получает ответа вовсе. `/жаңа` — FSM на пять шагов (название, описание, цена, всего серий, бесплатных), числовые шаги переспрашивают при нечисловом вводе, в конце бот отдаёт `bind_code` и инструкцию, что делать с каналом. `/bolimder` перечисляет сериалы с диапазоном загруженных серий и явно называет пропущенные номера. `/stats` — продажи и выручка по сериалам. `/export` — CSV через `send_document`.

- [ ] **Step 4: Run tests** → PASS
- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Add admin commands for dramas, stats and export" && git push
```

---

### Task 9: Выкатка на Hetzner

**Files:**
- Create: `deploy/aicontent-bot.service`, `deploy/setup.sh`, `deploy/deploy.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: готовый бот из задач 1–8.

- [ ] **Step 1: Адаптировать скрипты донора**

```bash
cp ~/jabiq-invest-bot/deploy/*.sh ~/jabiq-invest-bot/deploy/jabiq-bot.service deploy/
```

Переименовать юнит в `aicontent-bot.service`, путь — `/opt/aicontent-bot`, заменить упоминания jabiq. `Restart=always`, `RestartSec=5`.

- [ ] **Step 2: Прогнать весь набор тестов локально**

Run: `.venv/bin/pytest -v` → все PASS

- [ ] **Step 3: Запустить бота локально в sandbox-режиме**

`ARZAN_SANDBOX=true`, проверить вручную: `/start` показывает каталог, `/жаңа` создаёт сериал, `/bind` привязывает канал, бесплатные серии приходят, оплата в sandbox выдаёт инвайт.

- [ ] **Step 4: Дописать в README раздел о выкатке и эксплуатации**

Как залить на сервер, где лежит база, как её бэкапить, как переключить `ARZAN_SANDBOX=false`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "Add Hetzner deployment scripts and operations guide" && git push
```
