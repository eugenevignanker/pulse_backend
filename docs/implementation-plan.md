# Alpaca Trading API Compatibility Proxy

**Implementation plan — converted from `alpaca_proxy_implementation_plan.docx` on 17 August 2026.**

## Objective

Build a server that presents the REST and WebSocket behavior expected by Alpaca Trading API clients while adding first-party username/password authentication and bearer-token enforcement. The client must never receive Alpaca API credentials.

- Preserve Alpaca endpoint paths, methods, query parameters, JSON names, status codes, and material error semantics.
- Add `POST /auth/login` and authoritative `POST /auth/verify`.
- Verify every protected request before any upstream call.
- Keep per-user Alpaca credentials only on the server.
- Support authenticated `/stream` `trade_updates`.

## Chosen implementation baseline

- **Language/framework:** Python 3.11+, FastAPI, HTTPX, and WebSockets.
- **Persistence:** filesystem records initially. Token records live one-per-file beneath an ignored service-owned directory. Repository abstractions must permit a SQLite implementation without route changes.
- **Token format:** opaque `ptk_<random>.<HMAC signature>` bearer tokens. Validate a keyed digest, signature, expiry, status, and scopes. Do not persist raw tokens.
- **Credentials:** user-to-Alpaca mappings are server controlled. Password hashes use Argon2id (bcrypt only if necessary). Alpaca values are encrypted at rest or stored as secret-manager references, never plaintext in Git or client responses.
- **WebSocket:** use the precise bearer-token `auth` protocol in [websocket-protocol.md](websocket-protocol.md). It mirrors Alpaca's required command ordering while the proxy performs the upstream Alpaca credential exchange.

## Authentication requirements

### Login

`POST /auth/login` accepts `username` and `password`; it returns an access token, `Bearer` type, configurable expiration (initially 3600 seconds), and stable user identity. Invalid credentials return a generic `401`; login rate limits return `429`. Never include Alpaca IDs, password hashes, or secrets in the token or response.

### Verification

`POST /auth/verify` accepts a token and returns either an active result (`user_id`, username, expiry, scopes) or `{"active": false}`. It is authoritative for expiry, revocation, disabled users, and scopes.

Every protected HTTP request must carry one well-formed bearer token. Middleware verifies it exactly once in the normal successful path, rejects missing/invalid tokens with `401`, insufficient scopes with `403`, and fails closed with `503` if the verifier is unavailable. Login, verifier service traffic, and health checks are the only exceptions.

## User-to-Alpaca mapping

The server maps immutable `user_id` to `alpaca_environment`, encrypted `alpaca_api_key_id`, encrypted `alpaca_api_secret`, enabled state, and allowed scopes. A caller can never choose this mapping via request body, headers, query strings, or WebSocket data. Support credential rotation independently of user login.

## Version 1 API surface

P0: `GET /v2/account`, `GET/POST /v2/orders`, `GET/PATCH/DELETE /v2/orders/{order_id}`, `GET /v2/positions`, `GET /v2/positions/{symbol_or_asset_id}`, `GET /v2/assets`, `GET /v2/assets/{symbol_or_asset_id}`, `GET /v2/clock`, and WebSocket `/stream` for `trade_updates`.

P1: account configurations, cancel-all orders, close positions, calendar, and all-position close. Each route must be checked against the current official Alpaca schema and receive a contract test before implementation.

Use `https://paper-api.alpaca.markets` for paper mappings and `https://api.alpaca.markets` for live mappings. Apply explicit connection/read timeouts. Preserve safe upstream response codes/bodies and never retry non-idempotent order requests without an explicit idempotency design.

## Local error contract

```json
{"error":{"code":"AUTH_TOKEN_INVALID","message":"Authentication token is invalid or expired","request_id":"<correlation-id>"}}
```

Use `AUTH_TOKEN_MISSING` (401), `AUTH_TOKEN_INVALID` (401), `AUTH_FORBIDDEN` (403), `AUTH_SERVICE_UNAVAILABLE` (503), `TRADING_ACCOUNT_UNAVAILABLE` (403), `ALPACA_TIMEOUT` (504), and `INTERNAL_ERROR` (500). Preserve Alpaca error semantics for upstream-originated errors whenever safe.

## Implementation sequence

1. Capture current Alpaca OpenAPI/fixtures and maintain the proxy OpenAPI contract.
2. Implement user store, Argon2id password hashes, token issue/verify/revoke, and rate-limit/security tests.
3. Implement request IDs, logging, settings, filesystem-store interfaces, credential resolution, HTTP client, and mandatory verification middleware.
4. Deliver P0 read-only routes with fixtures and proxy-vs-paper contract tests.
5. Deliver order mutations with duplicate-submission safeguards, then P1 routes.
6. Deliver the WebSocket bridge and verify authentication at connect and each subscription command.
7. Harden compatibility and record deviations in `KNOWN_INCOMPATIBILITIES.md`.

## Definition of done

A user can log in; every protected request and socket control command is verified before Alpaca access; expired/revoked tokens fail; no credentials reach clients/logs; P0 paper routes and `trade_updates` work; OpenAPI, unit, integration, contract, and security tests pass.

## Official references

- [Trading API overview](https://docs.alpaca.markets/us/docs/trading-api)
- [API reference](https://docs.alpaca.markets/us/reference)
- [WebSocket streaming](https://docs.alpaca.markets/us/docs/websocket-streaming)
- [Alpaca documentation index](https://docs.alpaca.markets/us/llms.txt)

This plan is not a substitute for a production threat model, secret-management review, TLS configuration review, or penetration test before live-money trading.
