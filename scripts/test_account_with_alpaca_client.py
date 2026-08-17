"""Log in to the proxy, then invoke GET /v2/account through alpaca-py."""

import os
from getpass import getpass

import httpx

try:
    from alpaca.trading.client import TradingClient
except ModuleNotFoundError as error:
    raise SystemExit(
        "alpaca-py is not installed; activate .venv or run .venv/bin/python "
        "scripts/test_account_with_alpaca_client.py"
    ) from error


def main() -> None:
    proxy_url = os.environ.get("PULSE_PROXY_URL", "http://127.0.0.1:8000")
    username = os.environ.get("PULSE_PROXY_USERNAME") or input("Username: ")
    password = os.environ.get("PULSE_PROXY_PASSWORD") or getpass("Password: ")
    try:
        login_response = httpx.post(
            f"{proxy_url.rstrip('/')}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        login_response.raise_for_status()
        token = login_response.json()["access_token"]
    except (httpx.HTTPError, KeyError, ValueError) as error:
        raise SystemExit(f"proxy login failed: {error}") from error

    client = TradingClient(
        oauth_token=token,
        paper=True,
        url_override=proxy_url,
    )

    account = client.get_account()
    print(account)


if __name__ == "__main__":
    main()
