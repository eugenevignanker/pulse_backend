"""ASGI entry point for the proxy."""

from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, Response

from pulse_proxy.alpaca.client import AlpacaResponse, AlpacaTradingClient
from pulse_proxy.auth.tokens import TokenIdentity
from pulse_proxy.config import Settings
from pulse_proxy.dependencies import get_alpaca_client, require_trading_read
from pulse_proxy.errors import ProxyError


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Pulse Alpaca Compatibility Proxy", version="0.1.0")
    app.state.settings = settings or Settings()

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
