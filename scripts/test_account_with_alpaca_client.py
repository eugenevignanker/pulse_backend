"""Invoke the proxy's GET /v2/account endpoint through alpaca-py.

Run the proxy first, then set PULSE_PROXY_TOKEN to a proxy-issued token with
the trading:read scope. No Alpaca key or secret is supplied to this client.
"""

import os

try:
    from alpaca.trading.client import TradingClient
except ModuleNotFoundError as error:
    raise SystemExit(
        "alpaca-py is not installed; activate .venv or run .venv/bin/python "
        "scripts/test_account_with_alpaca_client.py"
    ) from error


def main() -> None:
    token = os.environ.get("PULSE_PROXY_TOKEN")
    if not token:
        raise SystemExit("PULSE_PROXY_TOKEN must contain a proxy bearer token")

    proxy_url = os.environ.get("PULSE_PROXY_URL", "http://127.0.0.1:8000")
    client = TradingClient(
        oauth_token=token,
        paper=True,
        url_override=proxy_url,
    )

    account = client.get_account()
    print(account)


if __name__ == "__main__":
    main()
