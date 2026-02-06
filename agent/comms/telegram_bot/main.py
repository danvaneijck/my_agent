"""Telegram bot entry point."""

from __future__ import annotations

import sys
import os

import structlog

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()


def main():
    from shared.config import get_settings
    from comms.telegram_bot.bot import AgentTelegramBot

    settings = get_settings()

    if not settings.telegram_token:
        logger.error("telegram_token_not_set")
        sys.exit(1)

    bot = AgentTelegramBot(settings)
    bot.run()


if __name__ == "__main__":
    main()
