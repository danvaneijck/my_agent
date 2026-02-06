"""Telegram bot implementation."""

from __future__ import annotations

import httpx
import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from comms.telegram_bot.normalizer import TelegramNormalizer
from shared.config import Settings
from shared.schemas.messages import AgentResponse

logger = structlog.get_logger()


class AgentTelegramBot:
    """Telegram bot that routes messages to the orchestrator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.normalizer = TelegramNormalizer()
        self.app = (
            Application.builder()
            .token(settings.telegram_token)
            .build()
        )
        self._setup_handlers()

    def _setup_handlers(self):
        """Register message handlers."""
        self.app.add_handler(CommandHandler("start", self._handle_start))
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message,
            )
        )

    async def _handle_start(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle the /start command."""
        await update.message.reply_text(
            "Hello! I'm your AI assistant. Send me a message and I'll help you out."
        )

    async def _handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Handle incoming text messages."""
        if not update.effective_message or not update.effective_message.text:
            return

        chat = update.effective_chat
        is_private = chat and chat.type == "private"
        is_group = chat and chat.type in ("group", "supergroup")

        # In groups, only respond when mentioned or replied to
        if is_group:
            bot_username = context.bot.username
            text = update.effective_message.text
            is_reply_to_bot = (
                update.effective_message.reply_to_message
                and update.effective_message.reply_to_message.from_user
                and update.effective_message.reply_to_message.from_user.is_bot
            )
            is_mentioned = bot_username and f"@{bot_username}" in text

            if not is_reply_to_bot and not is_mentioned:
                return

            # Strip mention
            if is_mentioned and bot_username:
                text = text.replace(f"@{bot_username}", "").strip()
                if not text:
                    return

        incoming = self.normalizer.to_incoming(update)

        # Clean content for group mentions
        if is_group and context.bot.username:
            incoming.content = incoming.content.replace(
                f"@{context.bot.username}", ""
            ).strip()

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
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
            logger.error("telegram_orchestrator_error", error=str(e))
            response = AgentResponse(
                content="Sorry, I'm having trouble connecting. Please try again.",
                error=str(e),
            )

        text = self.normalizer.format_response(response)
        await update.effective_message.reply_text(
            text, parse_mode="Markdown",
        )

    def run(self):
        """Start the bot with polling."""
        logger.info("starting_telegram_bot")
        self.app.run_polling(drop_pending_updates=True)
