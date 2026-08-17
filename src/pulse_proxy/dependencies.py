"""FastAPI dependencies shared by protected proxy routes."""

from typing import Annotated

from fastapi import Depends, Header, Request

from pulse_proxy.alpaca.client import AlpacaTradingClient
from pulse_proxy.auth.tokens import TokenIdentity, TokenStore
from pulse_proxy.config import Settings
from pulse_proxy.errors import ProxyError


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_token_store(request: Request) -> TokenStore:
    settings = get_settings(request)
    signing_key = settings.proxy_token_signing_key
    if signing_key is None:
        raise ProxyError(503, "AUTH_CONFIGURATION_INVALID", "Token verification is not configured")
    return TokenStore(
        root=settings.token_store_path,
        signing_key=signing_key.get_secret_value(),
        ttl_seconds=settings.token_ttl_seconds,
    )


def get_alpaca_client(request: Request) -> AlpacaTradingClient:
    return AlpacaTradingClient(get_settings(request))


def require_trading_read(
    authorization: Annotated[str | None, Header()] = None,
    token_store: TokenStore = Depends(get_token_store),
) -> TokenIdentity:
    """Require one valid proxy bearer token with read access."""
    if not authorization or not authorization.startswith("Bearer "):
        raise ProxyError(401, "AUTH_TOKEN_MISSING", "A bearer token is required")
    token = authorization.removeprefix("Bearer ")
    if not token or " " in token:
        raise ProxyError(401, "AUTH_TOKEN_MISSING", "A bearer token is required")
    identity = token_store.verify(token)
    if identity is None:
        raise ProxyError(401, "AUTH_TOKEN_INVALID", "Authentication token is invalid or expired")
    if "trading:read" not in identity.scopes:
        raise ProxyError(403, "AUTH_FORBIDDEN", "Token lacks the required scope")
    return identity
