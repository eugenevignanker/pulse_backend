"""Filesystem-backed opaque access tokens."""

from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TokenIdentity:
    user_id: str
    username: str
    scopes: frozenset[str]
    expires_at: datetime


class TokenStore:
    """Issue and validate proxy tokens using one JSON record per token."""

    def __init__(self, root: Path, signing_key: str, ttl_seconds: int) -> None:
        self._root = root
        self._signing_key = signing_key.encode("utf-8")
        self._ttl_seconds = ttl_seconds

    def issue(self, *, user_id: str, username: str, scopes: set[str]) -> str:
        token_id = f"ptk_{secrets.token_hex(16)}"
        random_value = secrets.token_urlsafe(32)
        signature = self._sign(f"{token_id}.{random_value}")
        token = f"{token_id}.{random_value}.{signature}"
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self._ttl_seconds)
        record = {
            "token_id": token_id,
            "token_digest": self._digest(token),
            "user_id": user_id,
            "username": username,
            "scopes": sorted(scopes),
            "issued_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "revoked_at": None,
            "status": "active",
        }
        self._write_record(token_id, record)
        return token

    def verify(self, token: str) -> TokenIdentity | None:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        token_id, random_value, signature = parts
        if not token_id.startswith("ptk_") or not random_value:
            return None
        if not hmac.compare_digest(signature, self._sign(f"{token_id}.{random_value}")):
            return None
        record = self._read_record(token_id)
        if record is None or not hmac.compare_digest(record.get("token_digest", ""), self._digest(token)):
            return None
        if record.get("status") != "active" or record.get("revoked_at"):
            return None
        try:
            expires_at = datetime.fromisoformat(record["expires_at"])
        except (KeyError, TypeError, ValueError):
            return None
        if expires_at.tzinfo is None or expires_at <= datetime.now(UTC):
            return None
        try:
            return TokenIdentity(
                user_id=record["user_id"],
                username=record["username"],
                scopes=frozenset(record["scopes"]),
                expires_at=expires_at,
            )
        except (KeyError, TypeError):
            return None

    def _sign(self, value: str) -> str:
        digest = hmac.new(self._signing_key, value.encode("utf-8"), sha256).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    @staticmethod
    def _digest(token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    def _read_record(self, token_id: str) -> dict[str, object] | None:
        path = self._root / f"{token_id}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return None

    def _write_record(self, token_id: str, record: dict[str, object]) -> None:
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary_path = tempfile.mkstemp(prefix=f".{token_id}-", dir=self._root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                json.dump(record, temporary_file, separators=(",", ":"))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, self._root / f"{token_id}.json")
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
