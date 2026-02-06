"""Slack bot entry point."""

from __future__ import annotations

import asyncio
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
    from comms.slack_bot.bot import AgentSlackBot

    settings = get_settings()

    if not settings.slack_bot_token or not settings.slack_app_token:
        logger.error("slack_tokens_not_set")
        sys.exit(1)

    bot = AgentSlackBot(settings)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
