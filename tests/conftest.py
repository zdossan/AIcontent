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


@pytest.fixture
async def fake_arzan(monkeypatch):
    """Arzan Pay орнына жергілікті сервер."""
    from aiohttp import web

    class Fake:
        def __init__(self):
            self.routes: dict[str, tuple[dict, int]] = {}
            self.requests: list[tuple[str, dict]] = []

        def reply(self, path, body, status=200):
            self.routes[path] = (body, status)

    fake = Fake()

    async def handler(request):
        body = await request.json() if request.can_read_body else {}
        fake.requests.append((request.path, body))
        payload, status = fake.routes.get(request.path, ({}, 404))
        return web.json_response(payload, status=status)

    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = runner.addresses[0][1]
    monkeypatch.setenv("ARZAN_BASE_URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("ARZAN_API_KEY", "test-key")
    monkeypatch.setenv("ARZAN_SANDBOX", "true")
    yield fake
    await runner.cleanup()


@pytest.fixture
def drama(db):
    """Арнасы байланған сериал."""
    d = store.create_drama("Тең емес", "Сипаттама", 490, 26, 6)
    return store.bind_channel(d.bind_code, -1001234567890)


def make_post(chat_id: int, caption: str | None, message_id: int, *, video: bool = True):
    """Арнаға түскен нақты aiogram хабарламасын құру."""
    from datetime import datetime

    from aiogram.types import Chat, Message, Video

    return Message(
        message_id=message_id,
        date=datetime(2026, 11, 22, 12, 0, 0),
        chat=Chat(id=chat_id, type="channel", title="Тең емес"),
        caption=caption,
        video=Video(file_id="f", file_unique_id="u", width=720, height=1280,
                    duration=60) if video else None,
    )


class FakeBot:
    """Telegram орнына: шақыруларды жазып отырады.

    Нақты API-ға шығу мүмкін емес, сондықтан бот объектісі ғана жалған —
    қалған код шынайы.
    """

    invite_url = "https://t.me/+fakeinvite"

    def __init__(self):
        self.calls: dict[str, list[dict]] = {}
        self.member_status = "left"
        self.invite_fails_with: Exception | None = None
        self.send_fails_with: Exception | None = None

    def _record(self, _call: str, kwargs: dict) -> None:
        self.calls.setdefault(_call, []).append(kwargs)

    async def create_chat_invite_link(self, **kwargs):
        self._record("create_chat_invite_link", kwargs)
        if self.invite_fails_with:
            raise self.invite_fails_with
        from aiogram.types import ChatInviteLink, User
        return ChatInviteLink(
            invite_link=self.invite_url,
            creator=User(id=1, is_bot=True, first_name="bot"),
            creates_join_request=False, is_primary=False, is_revoked=False,
            member_limit=kwargs.get("member_limit"),
        )

    async def get_chat_member(self, **kwargs):
        self._record("get_chat_member", kwargs)
        from aiogram.types import (ChatMemberLeft, ChatMemberMember,
                                   ChatMemberOwner, User)
        user = User(id=kwargs.get("user_id", 0), is_bot=False, first_name="u")
        if self.member_status == "member":
            return ChatMemberMember(user=user)
        if self.member_status == "creator":
            return ChatMemberOwner(user=user, is_anonymous=False)
        return ChatMemberLeft(user=user)

    async def copy_message(self, **kwargs):
        self._record("copy_message", kwargs)

    async def send_message(self, chat_id=None, text=None, **kwargs):
        self._record("send_message", {"chat_id": chat_id, "text": text, **kwargs})
        if self.send_fails_with:
            raise self.send_fails_with

    async def send_document(self, **kwargs):
        self._record("send_document", kwargs)

    def last_text(self) -> str:
        return self.calls["send_message"][-1]["text"]

    def last_markup(self):
        return self.calls["send_message"][-1].get("reply_markup")


@pytest.fixture
def fake_bot():
    return FakeBot()


def telegram_error(message: str):
    """Нақты aiogram қатесін құру."""
    from aiogram.exceptions import TelegramBadRequest
    from aiogram.methods import CreateChatInviteLink

    return TelegramBadRequest(method=CreateChatInviteLink(chat_id=1), message=message)


def make_message(tg_id: int, text: str = "/start", chat_id: int | None = None):
    """Жеке чаттан келген нақты хабарлама."""
    from datetime import datetime

    from aiogram.types import Chat, Message, User

    return Message(
        message_id=1,
        date=datetime(2026, 11, 22, 12, 0, 0),
        chat=Chat(id=chat_id if chat_id is not None else tg_id, type="private"),
        from_user=User(id=tg_id, is_bot=False, first_name="Аян",
                       username="ayan"),
        text=text,
    )


@pytest.fixture
def drama_with_26_episodes(drama):
    """1-26 бөлім: message_id 10-дан басталады."""
    for number in range(1, 27):
        store.add_episode(drama.id, number, 9 + number)
    return drama


@pytest.fixture
def drama_with_3_episodes(drama):
    for number in range(1, 4):
        store.add_episode(drama.id, number, 9 + number)
    return drama


@pytest.fixture
def paid_user(drama):
    """Сериалды сатып алған қолданушының tg_id-і."""
    tg_id = 777
    store.create_purchase(tg_id, drama.id, "qr_paid", drama.price_kzt)
    store.mark_paid("qr_paid")
    return tg_id
