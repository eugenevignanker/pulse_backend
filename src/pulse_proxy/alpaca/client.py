"""Client for the fixed deployment-owned Alpaca Trading API credentials."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from pulse_proxy.config import Settings


@dataclass(frozen=True, slots=True)
class AlpacaResponse:
    status_code: int
    content: bytes
    content_type: str | None
    request_id: str | None


class AlpacaTradingClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def get_account(self) -> AlpacaResponse:
        key_id = self._settings.alpaca_api_key_id
        secret = self._settings.alpaca_api_secret
        if not key_id or secret is None:
            raise RuntimeError("Alpaca API credentials are not configured")
        base_url = (
            self._settings.alpaca_paper_base_url
            if self._settings.alpaca_environment == "paper"
            else self._settings.alpaca_live_base_url
        )
        timeout = httpx.Timeout(
            connect=self._settings.alpaca_connect_timeout_ms / 1000,
            read=self._settings.alpaca_read_timeout_ms / 1000,
            write=self._settings.alpaca_read_timeout_ms / 1000,
            pool=self._settings.alpaca_connect_timeout_ms / 1000,
        )
        headers = {
            "APCA-API-KEY-ID": key_id,
            "APCA-API-SECRET-KEY": secret.get_secret_value(),
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{base_url.rstrip('/')}/v2/account", headers=headers)
        return AlpacaResponse(
            status_code=response.status_code,
            content=response.content,
            content_type=response.headers.get("content-type"),
            request_id=response.headers.get("x-request-id"),
        )
