"""Slack bot implementation using Socket Mode."""

from __future__ import annotations

import httpx
import structlog
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from comms.slack_bot.normalizer import SlackNormalizer
from shared.config import Settings
from shared.schemas.messages import AgentResponse

logger = structlog.get_logger()


class AgentSlackBot:
    """Slack bot using Socket Mode that routes messages to the orchestrator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.normalizer = SlackNormalizer()
        self.bot_user_id: str | None = None

        self.app = AsyncApp(token=settings.slack_bot_token)
        self._setup_handlers()

    def _setup_handlers(self):
        """Register event handlers."""

        @self.app.event("app_mention")
        async def handle_mention(event, say, client):
            await self._handle_message(event, say, client, is_mention=True)

        @self.app.event("message")
        async def handle_message(event, say, client):
            # Only handle DMs (im) here — mentions handled above
            channel_type = event.get("channel_type", "")
            if channel_type == "im":
                await self._handle_message(event, say, client, is_mention=False)

    async def _handle_message(self, event, say, client, is_mention: bool):
        """Process a message and send to orchestrator."""
        # Ignore bot messages
        if event.get("bot_id"):
            return

        # Get bot user ID for mention stripping
        if self.bot_user_id is None:
            try:
                auth = await client.auth_test()
                self.bot_user_id = auth.get("user_id")
            except Exception:
                pass

        incoming = self.normalizer.to_incoming(event, self.bot_user_id)

        if not incoming.content:
            return

        try:
            async with httpx.AsyncClient(timeout=60.0) as http_client:
                resp = await http_client.post(
                    f"{self.settings.orchestrator_url}/message",
                    json=incoming.model_dump(),
                )
                if resp.status_code == 200:
                    response = AgentResponse(**resp.json())
                else:
                    response = AgentResponse(
                        content="Sorry, I encountered an error processing your request.",
                        error=f"HTTP {resp.status_code}",
                    )
        except Exception as e:
            logger.error("slack_orchestrator_error", error=str(e))
            response = AgentResponse(
                content="Sorry, I'm having trouble connecting. Please try again.",
                error=str(e),
            )

        text = self.normalizer.format_response(response)

        # Reply in thread if the message was in a thread
        thread_ts = event.get("thread_ts") or event.get("ts")
        await say(text=text, thread_ts=thread_ts)

    async def run(self):
        """Start the bot with Socket Mode."""
        logger.info("starting_slack_bot")
        handler = AsyncSocketModeHandler(self.app, self.settings.slack_app_token)
        await handler.start_async()
