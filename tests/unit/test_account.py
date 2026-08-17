from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from pulse_proxy.alpaca.client import AlpacaResponse
from pulse_proxy.auth.tokens import TokenStore
from pulse_proxy.config import Settings
from pulse_proxy.dependencies import get_alpaca_client, get_token_store
from pulse_proxy.main import create_app


class FakeAlpacaClient:
    def __init__(self) -> None:
        self.calls = 0

    async def get_account(self) -> AlpacaResponse:
        self.calls += 1
        return AlpacaResponse(
            status_code=200,
            content=b'{"id":"account-id","buying_power":"100.00"}',
            content_type="application/json",
            request_id="alpaca-request-id",
        )


def make_app(tmp_path: Path, scopes: set[str]) -> tuple[FastAPI, FakeAlpacaClient, str]:
    settings = Settings(proxy_token_signing_key="test-signing-key", token_store_path=tmp_path)
    app = create_app(settings)
    token_store = TokenStore(tmp_path, "test-signing-key", ttl_seconds=3600)
    token = token_store.issue(user_id="user-1", username="user@example.com", scopes=scopes)
    upstream = FakeAlpacaClient()
    app.dependency_overrides[get_token_store] = lambda: token_store
    app.dependency_overrides[get_alpaca_client] = lambda: upstream
    return app, upstream, token


@pytest.mark.anyio
async def test_account_forwards_alpaca_response_for_authorized_token(tmp_path: Path) -> None:
    app, upstream, token = make_app(tmp_path, {"trading:read"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v2/account", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"id": "account-id", "buying_power": "100.00"}
    assert response.headers["X-Request-ID"] == "alpaca-request-id"
    assert upstream.calls == 1


@pytest.mark.anyio
async def test_account_rejects_missing_token_without_upstream_call(tmp_path: Path) -> None:
    app, upstream, _ = make_app(tmp_path, {"trading:read"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v2/account")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_MISSING"
    assert upstream.calls == 0


@pytest.mark.anyio
async def test_account_requires_read_scope(tmp_path: Path) -> None:
    app, upstream, token = make_app(tmp_path, {"trading:write"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/v2/account", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "AUTH_FORBIDDEN"
    assert upstream.calls == 0
