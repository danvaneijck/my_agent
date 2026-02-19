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

    has_oauth = (
        settings.slack_signing_secret
        and settings.slack_client_id
        and settings.slack_client_secret
    )

    if not has_oauth:
        logger.warning(
            "slack_config_missing",
            msg="Set SLACK_SIGNING_SECRET, SLACK_CLIENT_ID, and SLACK_CLIENT_SECRET "
                "to enable multi-workspace OAuth mode. Sleeping.",
        )
        while True:
            time.sleep(86400)

    from comms.slack_bot.bot import AgentSlackBot

    bot = AgentSlackBot(settings)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
