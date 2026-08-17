# Pulse Alpaca Compatibility Proxy

An in-progress Python service that exposes an Alpaca Trading API-compatible REST and WebSocket surface while authenticating clients with first-party bearer tokens. Alpaca API credentials remain server-side.

## Current status

This repository contains the project baseline and API/security design. `GET /v2/account` is implemented as the first protected REST route; login, production user provisioning, and the WebSocket bridge remain to be implemented.

## Design decisions

- **Runtime:** Python 3.11+ with FastAPI, HTTPX, and WebSockets support.
- **Initial persistence:** filesystem-backed JSON records, stored outside version control under `var/`. Each token has its own record in `var/tokens/`.
- **Migration path:** repository interfaces isolate persistence so SQLite can replace filesystem stores when indexed queries, concurrent writers, transactions, or operational scale require it.
- **Secrets:** never store plaintext passwords or Alpaca credentials in the repository. V1 uses one deployment-owned Alpaca key/secret from environment variables or a secret manager; it is never sent to clients.
- **WebSocket:** clients use a bearer token in Alpaca-shaped `auth` frames; the proxy verifies it, then authenticates upstream with the fixed server-side Alpaca credentials. Details are in [docs/websocket-protocol.md](docs/websocket-protocol.md).
- **Future multi-account support:** a user-to-Alpaca-credential mapping can be added behind a credential-provider interface after v1, without changing the client token protocol.

## Local setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn pulse_proxy.main:app --reload
pytest
```

The starter application exposes `GET /health/live` and `GET /health/ready`. Do not put real credentials in `.env` or commit runtime files.

`GET /v2/account` requires `Authorization: Bearer <proxy-token>` with the `trading:read` scope, `PROXY_TOKEN_SIGNING_KEY`, `ALPACA_API_KEY_ID`, and `ALPACA_API_SECRET`. It forwards to the selected Alpaca environment and returns Alpaca's response unchanged, apart from never exposing upstream credentials.

## SDK smoke test

After installing the `dev` dependencies and starting the proxy, run the Alpaca SDK smoke test with a proxy-issued token:

```bash
PULSE_PROXY_TOKEN='<proxy-token>' python scripts/test_account_with_alpaca_client.py
```

The script uses `TradingClient(oauth_token=..., url_override=...)`. Do not use fake Alpaca key/secret values for this request: the proxy intentionally accepts only its own bearer token and supplies the fixed Alpaca credentials upstream.

## Layout

```text
src/pulse_proxy/       Application package
docs/                  Implementation plan and protocol decisions
openapi/               Hand-maintained proxy API contract
tests/                 Unit, contract, integration, and security tests
var/                   Ignored local runtime state
```

The detailed implementation sequence is in [docs/implementation-plan.md](docs/implementation-plan.md).
