"""Small in-memory fixed-window login rate limiter."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta


class LoginRateLimiter:
    def __init__(self, attempts_per_minute: int) -> None:
        self._attempts_per_minute = attempts_per_minute
        self._attempts: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)

    def allow(self, username: str, source_address: str) -> bool:
        now = datetime.now(UTC)
        attempts = self._attempts[(username.casefold(), source_address)]
        cutoff = now - timedelta(minutes=1)
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        return len(attempts) < self._attempts_per_minute

    def record_failure(self, username: str, source_address: str) -> None:
        self._attempts[(username.casefold(), source_address)].append(datetime.now(UTC))

    def reset(self, username: str, source_address: str) -> None:
        self._attempts.pop((username.casefold(), source_address), None)
