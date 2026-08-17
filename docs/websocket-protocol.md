# WebSocket authentication protocol

The proxy exposes `wss://<proxy-host>/stream`, matching Alpaca's trade-update stream path. In v1 it bridges to Alpaca's `wss://paper-api.alpaca.markets/stream` or `wss://api.alpaca.markets/stream` using one fixed, deployment-owned Alpaca credential pair. It does not use client-provided or user-specific Alpaca credentials.

## Client protocol

After connection, the client must send an Alpaca-shaped `auth` command within five seconds:

```json
{"action":"auth","key":"Bearer <proxy-token>","secret":""}
```

`key` must contain exactly one `Bearer ` prefix followed by a proxy access token. `secret` is required for wire-shape compatibility but must be the empty string. The proxy rejects a non-empty `secret`; it is never an Alpaca secret.

On success, the proxy responds with the Alpaca-compatible authorization event:

```json
[{"T":"success","msg":"authenticated"}]
```

On failure, it returns an Alpaca-shaped error event and closes with code `4401`:

```json
[{"T":"error","code":401,"msg":"authentication failed"}]
```

The client may then send the native listen command:

```json
{"action":"listen","data":{"streams":["trade_updates"]}}
```

Only `trade_updates` is supported in v1. The proxy verifies the token again before processing every `listen` command and responds with Alpaca's `listening` acknowledgement shape. It forwards upstream trade-update payloads unchanged.

## Server flow

1. Parse and validate the `auth` frame.
2. Look up the token record by a keyed digest, validate its signature and expiry, and confirm it is not revoked or disabled.
3. Confirm the authenticated user is permitted to access trading through the proxy.
4. Open the upstream socket and send Alpaca's required native credentials from the deployment configuration:

   ```json
   {"action":"auth","key":"<alpaca-key-id>","secret":"<alpaca-secret>"}
   ```

5. Never forward this upstream frame to the client. Bridge the upstream success event as the proxy success event.
6. Track expiry; close with `4401` at expiry or immediately after revocation is observed during a control-command recheck.

The proxy does not accept Alpaca key IDs or secrets from URL parameters, headers, or frames. A client cannot select an Alpaca account or environment. A later credential-provider abstraction may select a per-user pair, but that is explicitly out of scope for v1 and must not change this client protocol.

## Token records

Token values are opaque random signed sequences: `ptk_<random-url-safe-value>.<signature>`. The random portion is at least 256 bits. The signature is HMAC-SHA-256 over the token identifier and random portion, using a deployment-managed signing key. The server stores only a keyed digest of the full presented token, never the raw token.

Each active or revoked token has one private JSON record at `var/tokens/<token-id>.json`, permissioned for the service account. A record contains `token_id`, token digest, `user_id`, issued/expiry timestamps, scopes, revocation timestamp, and status. It must not contain a password, raw token, or Alpaca credential. Records should be written atomically and guarded with file locks. Move to SQLite when atomic multi-record updates, revocation indexes, user-token searches, or multi-process deployments are required.
