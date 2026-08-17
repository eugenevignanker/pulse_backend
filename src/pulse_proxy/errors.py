"""Proxy-owned errors that are intentionally distinct from Alpaca responses."""

from dataclasses import dataclass


@dataclass(slots=True)
class ProxyError(Exception):
    status_code: int
    code: str
    message: str
