"""bot.access — жабық арнаға жеке сілтеме."""

import time

from bot import access
from tests.conftest import telegram_error


async def test_personal_invite_is_single_use_and_expires(fake_bot):
    url = await access.personal_invite(fake_bot, -100123, 7)
    call = fake_bot.calls["create_chat_invite_link"][0]
    assert call["member_limit"] == 1
    assert call["expire_date"] > int(time.time())
    assert url == fake_bot.invite_url


async def test_personal_invite_returns_none_when_bot_lacks_rights(fake_bot):
    fake_bot.invite_fails_with = telegram_error("not enough rights")
    assert await access.personal_invite(fake_bot, -100123, 7) is None


async def test_is_member_false_when_left(fake_bot):
    fake_bot.member_status = "left"
    assert await access.is_member(fake_bot, -100123, 7) is False


async def test_is_member_true_for_member_and_owner(fake_bot):
    fake_bot.member_status = "member"
    assert await access.is_member(fake_bot, -100123, 7) is True
    fake_bot.member_status = "creator"
    assert await access.is_member(fake_bot, -100123, 7) is True


async def test_is_member_false_when_api_fails(fake_bot):
    fake_bot.member_status = "member"

    async def boom(**kwargs):
        raise telegram_error("chat not found")

    fake_bot.get_chat_member = boom
    assert await access.is_member(fake_bot, -100123, 7) is False
