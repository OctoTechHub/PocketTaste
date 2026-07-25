"""Create the launch accounts.

    python -m scripts.onboard_users                      # random strong passwords, printed once
    python -m scripts.onboard_users --password Demo1234! # one shared password (demos only)
    python -m scripts.onboard_users --password X --set-password   # also reset existing accounts
    python -m scripts.onboard_users --list               # show existing accounts

Passwords are printed exactly once, at creation. They are stored only as scrypt
hashes, so a lost password can be reset but never recovered.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.container import build_container  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.errors import ConflictError  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.core.security import generate_password  # noqa: E402
from app.data.mongo import MongoGateway  # noqa: E402

logger = get_logger("onboard")

LAUNCH_USERS: list[tuple[str, str, list[str]]] = [
    ("krish@gmail.com", "Krish", ["listener", "creator"]),
    ("amogh@gmail.com", "Amogh", ["listener", "creator"]),
    ("nandan@gmail.com", "Nandan", ["listener", "creator"]),
    ("rahul@gmail.com", "Rahul", ["listener", "creator"]),
]


async def main(args: argparse.Namespace) -> int:
    configure_logging()
    settings = get_settings()
    gateway = MongoGateway(settings)

    if not await gateway.connect():
        logger.error("Cannot connect to MongoDB. Set DB_URL in server/.env.")
        return 1

    container = build_container(settings, gateway)
    try:
        if args.list:
            accounts = await container.accounts_repo.list_accounts()
            logger.info("%d account(s):", len(accounts))
            for account in accounts:
                logger.info(
                    "  %-24s %-22s roles=%-22s logins=%d",
                    account.email,
                    account.user_id,
                    ",".join(account.roles),
                    account.login_count,
                )
            return 0

        if not settings.jwt_secret_configured:
            logger.warning(
                "JWT_SECRET is not set. Tokens will be signed with a per-process random key "
                "and will stop working when the server restarts. Set it in server/.env."
            )

        created: list[tuple[str, str]] = []
        for email, display_name, roles in LAUNCH_USERS:
            password = args.password or generate_password()
            try:
                account = await container.auth.register(
                    email=email, password=password, display_name=display_name, roles=roles
                )
                created.append((email, password))
                logger.info("created %-22s -> %s", email, account.user_id)
            except ConflictError:
                if args.set_password:
                    account = await container.auth.set_password(email=email, password=password)
                    created.append((email, password))
                    logger.info("reset   %-22s -> %s", email, account.user_id)
                else:
                    logger.info("exists  %-22s (skipped; --set-password to reset)", email)

        if created:
            print()
            print("=" * 68)
            print("  CREDENTIALS — shown once, stored only as scrypt hashes")
            print("=" * 68)
            for email, password in created:
                print(f"  {email:26} {password}")
            print("=" * 68)
            print("  Sign in:  POST /auth/login  {\"email\": ..., \"password\": ...}")
            print("  Then send 'Authorization: Bearer <access_token>'")
            print()
        return 0
    finally:
        await gateway.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the launch accounts.")
    parser.add_argument("--password", help="Use one shared password instead of random ones.")
    parser.add_argument(
        "--set-password",
        action="store_true",
        help="Also reset the password of accounts that already exist.",
    )
    parser.add_argument("--list", action="store_true", help="List existing accounts and exit.")
    raise SystemExit(asyncio.run(main(parser.parse_args())))
