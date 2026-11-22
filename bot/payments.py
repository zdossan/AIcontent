"""Arzan Pay (Kaspi) API клиенті.

Құжаттама: https://pay.arzan.cloud/docs
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass

import aiohttp

from bot import config

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=20)

# .env бұл модуль импортталғаннан кейін жүктеледі, сондықтан баптаулар
# модуль деңгейінде емес, шақырылған сәтте оқылады.


def _base_url() -> str:
    return os.getenv("ARZAN_BASE_URL", "https://pay.arzan.cloud/api").rstrip("/")


def is_sandbox() -> bool:
    """Тест режимі. Баптау bot.config-те оқылады."""
    return config.is_sandbox()


class ArzanError(Exception):
    """Arzan Pay қайтарған қате."""

    def __init__(self, code: str, message: str, status: int = 0) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.status = status


@dataclass(slots=True)
class Invoice:
    id: str
    status: str
    amount: str

    @property
    def is_paid(self) -> bool:
        return self.status == "paid"

    @property
    def is_final(self) -> bool:
        """Бұдан әрі күтудің мағынасы жоқ күйлер."""
        return self.status in {
            "paid",
            "cancelled",
            "expired",
            "error",
            "refunded",
            "partially_refunded",
        }


def _api_key() -> str:
    key = os.getenv("ARZAN_API_KEY")
    if not key:
        raise ArzanError("no_api_key", "ARZAN_API_KEY .env файлында жоқ")
    return key


async def _request(method: str, path: str, *, payload: dict | None = None,
                   headers: dict | None = None) -> dict:
    hdrs = {"X-API-Key": _api_key(), "Accept": "application/json"}
    if headers:
        hdrs.update(headers)

    async with aiohttp.ClientSession(timeout=TIMEOUT) as session:
        url = f"{_base_url()}{path}"
        async with session.request(method, url, json=payload, headers=hdrs) as resp:
            # Kaspi-дің жауабында кейде жолішілік \n кездеседі — ол қатаң JSON
            # үшін жарамсыз. Сондықтан strict=False арқылы оқимыз.
            raw = await resp.text()
            try:
                body = json.loads(raw, strict=False)
            except ValueError:
                body = {"error": "bad_response", "message": raw[:200]}

            if resp.status >= 400:
                code = str(body.get("error", "http_error"))
                msg = str(body.get("message", resp.reason or ""))
                log.error("Arzan %s %s -> %s %s: %s", method, path, resp.status, code, msg)
                raise ArzanError(code, msg, resp.status)
            return body


@dataclass(slots=True)
class PaymentLink:
    id: str
    url: str
    amount: str
    expires_at: str


async def create_payment_link(*, amount: int, description: str,
                              external_order_id: str) -> PaymentLink:
    """Сомасы бекітілген Kaspi төлем сілтемесін жасау.

    Телефон нөмірі керек емес — қолданушы сілтемені басып, Kaspi-де
    дайын соманы көреді. Сілтеме ~3 минуттан кейін ескіреді.
    """
    payload = {
        "amount": amount,
        "comment": description,
        "external_order_id": external_order_id,
        "is_sandbox": is_sandbox(),
    }
    headers = {"Idempotency-Key": f"{external_order_id}-{uuid.uuid4().hex[:8]}"}
    data = await _request("POST", "/v1/payment-links", payload=payload, headers=headers)
    log.info("Төлем сілтемесі жасалды: %s (sandbox=%s)", data.get("id"), is_sandbox())
    return PaymentLink(
        id=data["id"],
        url=data["payment_url"],
        amount=str(data.get("amount", amount)),
        expires_at=str(data.get("expires_at", "")),
    )


async def get_invoice(invoice_id: str) -> Invoice:
    """Шоттың ағымдағы күйін сұрау."""
    data = await _request("GET", f"/v1/invoices/{invoice_id}")
    return Invoice(id=data["id"], status=data.get("status", "pending"),
                   amount=str(data.get("amount", "")))


async def check_many(ids: list[str]) -> dict[str, str]:
    """Бірнеше шоттың күйін бір сұраумен тексеру.

    Бот қайта қосылғанда күтіп қалған төлемдерді қуып жету үшін керек.
    Жауапта ok=false болғандары нәтижеге кірмейді.
    """
    if not ids:
        return {}
    data = await _request("POST", "/v1/invoices/status/check", payload={"ids": ids})
    result: dict[str, str] = {}
    for item in data.get("data", []):
        if item.get("ok") and isinstance(item.get("payment"), dict):
            status = item["payment"].get("status")
            if status:
                result[str(item["id"])] = str(status)
    return result
