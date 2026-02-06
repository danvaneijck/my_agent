"""Slack bot entry point."""

from __future__ import annotations

import asyncio
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

    if not settings.slack_bot_token or not settings.slack_app_token:
        logger.warning("slack_tokens_not_set", msg="Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN to enable. Sleeping.")
        # Sleep indefinitely so Docker doesn't restart-loop and spam logs
        while True:
            time.sleep(86400)

    from comms.slack_bot.bot import AgentSlackBot

    bot = AgentSlackBot(settings)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
