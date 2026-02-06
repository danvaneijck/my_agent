"""Telegram bot entry point."""

from __future__ import annotations

import sys
import os
import time

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

    settings = get_settings()

    if not settings.telegram_token:
        logger.warning("telegram_token_not_set", msg="Set TELEGRAM_TOKEN to enable. Sleeping.")
        # Sleep indefinitely so Docker doesn't restart-loop and spam logs
        while True:
            time.sleep(86400)

    from comms.telegram_bot.bot import AgentTelegramBot

    bot = AgentTelegramBot(settings)
    bot.run()


if __name__ == "__main__":
    main()
