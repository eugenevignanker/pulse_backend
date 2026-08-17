# Pulse Alpaca Compatibility Proxy

An in-progress Python service that exposes an Alpaca Trading API-compatible REST and WebSocket surface while authenticating clients with first-party bearer tokens. Alpaca API credentials remain server-side.

## Current status

This repository contains the project baseline and API/security design. REST forwarding, login, token persistence, credential resolution, and the WebSocket bridge have not yet been implemented.

## Design decisions

- **Runtime:** Python 3.11+ with FastAPI, HTTPX, and WebSockets support.
- **Initial persistence:** filesystem-backed JSON records, stored outside version control under `var/`. Each token has its own record in `var/tokens/`.
- **Migration path:** repository interfaces isolate persistence so SQLite can replace filesystem stores when indexed queries, concurrent writers, transactions, or operational scale require it.
- **Secrets:** never store plaintext passwords or Alpaca credentials in the repository. Store only encrypted credential material or secret-manager references in local records.
- **WebSocket:** clients use a bearer token in Alpaca-shaped `auth` frames; the proxy verifies it, then authenticates upstream using server-side Alpaca credentials. Details are in [docs/websocket-protocol.md](docs/websocket-protocol.md).

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

## Layout

```text
src/pulse_proxy/       Application package
docs/                  Implementation plan and protocol decisions
openapi/               Hand-maintained proxy API contract
tests/                 Unit, contract, integration, and security tests
var/                   Ignored local runtime state
```

The detailed implementation sequence is in [docs/implementation-plan.md](docs/implementation-plan.md).
