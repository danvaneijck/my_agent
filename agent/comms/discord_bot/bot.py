"""Discord bot implementation."""

from __future__ import annotations

import httpx
import structlog
import discord
from discord import Intents

from comms.discord_bot.normalizer import DiscordNormalizer
from shared.config import Settings

logger = structlog.get_logger()


class AgentDiscordBot(discord.Client):
    """Discord bot that routes messages to the orchestrator."""

    def __init__(self, settings: Settings):
        intents = Intents.default()
        intents.message_content = True
        intents.messages = True
        super().__init__(intents=intents)

        self.settings = settings
        self.normalizer = DiscordNormalizer()

    async def on_ready(self):
        logger.info("discord_bot_ready", user=str(self.user))

    async def on_message(self, message: discord.Message):
        # Ignore own messages
        if message.author == self.user:
            return

        # Respond in DMs or when mentioned
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.user and self.user.mentioned_in(message)

        if not is_dm and not is_mentioned:
            return

        # Strip the mention from the message content
        content = message.content
        if self.user and is_mentioned:
            content = content.replace(f"<@{self.user.id}>", "").strip()
            content = content.replace(f"<@!{self.user.id}>", "").strip()

        if not content:
            return

        # Override content with cleaned version
        incoming = self.normalizer.to_incoming(message)
        incoming.content = content

        # Show typing indicator while processing
        async with message.channel.typing():
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.settings.orchestrator_url}/message",
                        json=incoming.model_dump(),
                    )
                    if resp.status_code == 200:
                        from shared.schemas.messages import AgentResponse
                        response = AgentResponse(**resp.json())
                    else:
                        from shared.schemas.messages import AgentResponse
                        response = AgentResponse(
                            content="Sorry, I encountered an error processing your request.",
                            error=f"HTTP {resp.status_code}",
                        )
            except Exception as e:
                logger.error("discord_orchestrator_error", error=str(e))
                from shared.schemas.messages import AgentResponse
                response = AgentResponse(
                    content="Sorry, I'm having trouble connecting to my brain. Please try again.",
                    error=str(e),
                )

        # Send response
        chunks = self.normalizer.format_response(response)
        for chunk in chunks:
            await message.reply(chunk, mention_author=False)
