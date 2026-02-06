"""Discord message normalizer."""

from __future__ import annotations

import discord

from shared.schemas.messages import AgentResponse, IncomingMessage


class DiscordNormalizer:
    """Normalize Discord messages to/from the common format."""

    def to_incoming(self, message: discord.Message) -> IncomingMessage:
        """Convert a Discord message to the normalized format."""
        thread_id = None
        if isinstance(message.channel, discord.Thread):
            thread_id = str(message.channel.id)

        server_id = None
        if message.guild:
            server_id = str(message.guild.id)

        # Attachments are ingested by the bot (not the normalizer)
        return IncomingMessage(
            platform="discord",
            platform_user_id=str(message.author.id),
            platform_username=str(message.author),
            platform_channel_id=str(message.channel.id),
            platform_thread_id=thread_id,
            platform_server_id=server_id,
            content=message.content,
        )

    def format_response(self, response: AgentResponse) -> list[str]:
        """Format an AgentResponse for Discord, splitting at 2000 chars.

        File links are NOT added here — the bot attaches them
        as native discord.File objects so images display inline.
        """
        content = response.content
        if response.error:
            content += f"\n\n⚠️ Error: {response.error}"

        # Split at Discord's 2000 char limit
        chunks = []
        while len(content) > 2000:
            # Find a good split point
            split_at = content.rfind("\n", 0, 2000)
            if split_at == -1:
                split_at = content.rfind(" ", 0, 2000)
            if split_at == -1:
                split_at = 2000

            chunks.append(content[:split_at])
            content = content[split_at:].lstrip()

        if content:
            chunks.append(content)

        return chunks if chunks else ["I processed your request but have no response to show."]
