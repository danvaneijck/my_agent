"""Discord bot entry point."""

from __future__ import annotations

import sys
import os
import time
import asyncio

import structlog

# Import specific discord errors to handle fatal vs non-fatal crashes
from discord.errors import LoginFailure, PrivilegedIntentsRequired

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

    logger.info("starting_discord_bot_loop")

    while True:
        try:

            bot = AgentDiscordBot(settings)

            logger.info("connecting_to_discord")
            bot.run(settings.discord_token)

        except LoginFailure:
            logger.error("invalid_discord_token_terminating")
            sys.exit(1)

        except PrivilegedIntentsRequired:
            logger.error("privileged_intents_missing_terminating")
            sys.exit(1)

        except Exception as e:
            logger.error("bot_crashed_restarting", error=str(e))

            time.sleep(5)

        except KeyboardInterrupt:
            logger.info("bot_stopped_by_user")
            break


if __name__ == "__main__":
    main()
