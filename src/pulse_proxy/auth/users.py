"""Filesystem-backed user records with Argon2id password hashes."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


@dataclass(frozen=True, slots=True)
class User:
    user_id: str
    username: str
    password_hash: str
    scopes: frozenset[str]
    enabled: bool


class FilesystemUserStore:
    """Store one private user record per normalized username digest."""

    def __init__(self, root: Path, password_hasher: PasswordHasher | None = None) -> None:
        self._root = root
        self._password_hasher = password_hasher or PasswordHasher()

    def create(self, *, user_id: str, username: str, password: str, scopes: set[str]) -> User:
        normalized = self._normalize_username(username)
        if not password:
            raise ValueError("password must not be empty")
        if self.find_by_username(normalized) is not None:
            raise ValueError("username already exists")
        user = User(
            user_id=user_id,
            username=normalized,
            password_hash=self._password_hasher.hash(password),
            scopes=frozenset(scopes),
            enabled=True,
        )
        self._write(self._path_for(normalized), {
            "user_id": user.user_id,
            "username": user.username,
            "password_hash": user.password_hash,
            "scopes": sorted(user.scopes),
            "enabled": user.enabled,
        })
        return user

    def find_by_username(self, username: str) -> User | None:
        normalized = self._normalize_username(username)
        try:
            record = json.loads(self._path_for(normalized).read_text(encoding="utf-8"))
            return User(
                user_id=record["user_id"],
                username=record["username"],
                password_hash=record["password_hash"],
                scopes=frozenset(record["scopes"]),
                enabled=record["enabled"],
            )
        except (FileNotFoundError, OSError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def verify_password(self, user: User, password: str) -> bool:
        try:
            return self._password_hasher.verify(user.password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    @staticmethod
    def _normalize_username(username: str) -> str:
        return username.strip().casefold()

    def _path_for(self, username: str) -> Path:
        return self._root / f"{sha256(username.encode('utf-8')).hexdigest()}.json"

    def _write(self, path: Path, record: dict[str, object]) -> None:
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary_path = tempfile.mkstemp(prefix=".user-", dir=self._root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                json.dump(record, temporary_file, separators=(",", ":"))
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
