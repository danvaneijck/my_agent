"""Slack message normalizer."""

from __future__ import annotations

from shared.schemas.messages import AgentResponse, IncomingMessage


class SlackNormalizer:
    """Normalize Slack messages to/from the common format."""

    def to_incoming(self, event: dict, bot_user_id: str | None = None) -> IncomingMessage:
        """Convert a Slack event to the normalized format."""
        text = event.get("text", "")

        # Strip bot mention
        if bot_user_id:
            text = text.replace(f"<@{bot_user_id}>", "").strip()

        thread_id = event.get("thread_ts")
        channel_id = event.get("channel", "")

        # Slack doesn't have a direct "server" concept, but team_id is similar
        server_id = event.get("team")

        # Attachments are ingested by the bot (not the normalizer)
        return IncomingMessage(
            platform="slack",
            platform_user_id=event.get("user", "unknown"),
            platform_username=None,  # Would need to fetch from Slack API
            platform_channel_id=channel_id,
            platform_thread_id=thread_id,
            platform_server_id=server_id,
            content=text,
        )

    def format_response(self, response: AgentResponse) -> str:
        """Format an AgentResponse for Slack.

        File attachments are uploaded natively to Slack by the bot.
        """
        content = response.content
        if response.error:
            content += f"\n\n:warning: Error: {response.error}"

        return content
