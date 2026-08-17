"""ASGI entry point for the proxy."""

from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from pulse_proxy.alpaca.client import AlpacaResponse, AlpacaTradingClient
from pulse_proxy.auth.rate_limit import LoginRateLimiter
from pulse_proxy.auth.tokens import TokenIdentity, TokenStore
from pulse_proxy.auth.users import FilesystemUserStore
from pulse_proxy.config import Settings
from pulse_proxy.dependencies import (
    get_alpaca_client,
    get_login_rate_limiter,
    get_token_store,
    get_user_store,
    require_trading_read,
)
from pulse_proxy.errors import ProxyError


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginUser(BaseModel):
    id: str
    username: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    user: LoginUser


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Pulse Alpaca Compatibility Proxy", version="0.1.0")
    app.state.settings = settings or Settings()
    app.state.login_rate_limiter = LoginRateLimiter(app.state.settings.login_rate_limit_per_minute)

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))
        response = await call_next(request)
        if "X-Request-ID" not in response.headers:
            response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ProxyError)
    async def proxy_error_handler(request: Request, error: ProxyError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": error.code,
                    "message": error.message,
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
        )

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        """Return process liveness without consulting dependencies."""
        return {"status": "ok"}

    @app.post("/auth/login", tags=["auth"], response_model=LoginResponse)
    async def login(
        payload: LoginRequest,
        request: Request,
        user_store: FilesystemUserStore = Depends(get_user_store),
        token_store: TokenStore = Depends(get_token_store),
        rate_limiter: LoginRateLimiter = Depends(get_login_rate_limiter),
    ) -> LoginResponse:
        """Validate local credentials and issue a proxy bearer token."""
        source_address = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(payload.username, source_address):
            raise ProxyError(429, "AUTH_RATE_LIMITED", "Too many login attempts")
        user = user_store.find_by_username(payload.username)
        if user is None or not user.enabled or not user_store.verify_password(user, payload.password):
            rate_limiter.record_failure(payload.username, source_address)
            raise ProxyError(401, "AUTH_CREDENTIALS_INVALID", "Invalid username or password")
        rate_limiter.reset(payload.username, source_address)
        token = token_store.issue(user_id=user.user_id, username=user.username, scopes=set(user.scopes))
        return LoginResponse(
            access_token=token,
            expires_in=app.state.settings.token_ttl_seconds,
            user=LoginUser(id=user.user_id, username=user.username),
        )

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        """Temporary readiness endpoint; dependency checks will be added with stores."""
        return {"status": "ok"}

    @app.get("/v2/account", tags=["alpaca"])
    async def get_account(
        _: TokenIdentity = Depends(require_trading_read),
        client: AlpacaTradingClient = Depends(get_alpaca_client),
    ) -> Response:
        """Return Alpaca's account response without exposing upstream credentials."""
        try:
            upstream: AlpacaResponse = await client.get_account()
        except RuntimeError as error:
            raise ProxyError(503, "ALPACA_CREDENTIALS_UNAVAILABLE", "Trading is unavailable") from error
        except httpx.TimeoutException as error:
            raise ProxyError(504, "ALPACA_TIMEOUT", "Alpaca request timed out") from error
        except httpx.HTTPError as error:
            raise ProxyError(502, "ALPACA_UNAVAILABLE", "Alpaca request failed") from error
        headers = {"X-Request-ID": upstream.request_id} if upstream.request_id else None
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            media_type=upstream.content_type,
            headers=headers,
        )

    return app


app = create_app()
