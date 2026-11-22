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
