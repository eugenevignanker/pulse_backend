"""Create a local development user for POST /auth/login."""

import argparse
from getpass import getpass
from uuid import uuid4

from pulse_proxy.auth.users import FilesystemUserStore
from pulse_proxy.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--user-id", default=str(uuid4()))
    parser.add_argument("--scope", action="append", default=["trading:read"])
    args = parser.parse_args()

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("passwords do not match")
    user = FilesystemUserStore(Settings().user_store_path).create(
        user_id=args.user_id,
        username=args.username,
        password=password,
        scopes=set(args.scope),
    )
    print(f"created user {user.username} ({user.user_id})")


if __name__ == "__main__":
    main()
