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
