"""ASGI entry point for the proxy.

Only health endpoints exist at the baseline stage. Protected Alpaca-compatible
routes will be registered after authentication middleware is implemented.
"""

from fastapi import FastAPI

app = FastAPI(title="Pulse Alpaca Compatibility Proxy", version="0.1.0")


@app.get("/health/live", tags=["health"])
async def liveness() -> dict[str, str]:
    """Return process liveness without consulting dependencies."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    """Temporary readiness endpoint; dependency checks will be added with stores."""
    return {"status": "ok"}
