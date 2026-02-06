"""Discord bot entry point."""

from __future__ import annotations

import sys
import os

import structlog

# Ensure shared package is importable
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
    from comms.discord_bot.bot import AgentDiscordBot

    settings = get_settings()

    if not settings.discord_token:
        logger.error("discord_token_not_set")
        sys.exit(1)

    bot = AgentDiscordBot(settings)
    logger.info("starting_discord_bot")
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
