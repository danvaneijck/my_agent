"""Telegram bot implementation."""

from __future__ import annotations

import io

import httpx
import structlog
from minio import Minio
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
from shared.database import get_session_factory
from shared.file_utils import ingest_attachment
from shared.schemas.messages import AgentResponse

logger = structlog.get_logger()


class AgentTelegramBot:
    """Telegram bot that routes messages to the orchestrator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.normalizer = TelegramNormalizer()
        self.session_factory = get_session_factory()
        self.minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        self.app = (
            Application.builder()
            .token(settings.telegram_token)
            .build()
        )
        self._setup_handlers()

    def _setup_handlers(self):
        """Register message handlers."""
        self.app.add_handler(CommandHandler("start", self._handle_start))
        # Handle text messages
        self.app.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message,
            )
        )
        # Handle document and photo attachments
        self.app.add_handler(
            MessageHandler(
                filters.Document.ALL | filters.PHOTO,
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
        """Handle incoming messages (text, documents, photos)."""
        message = update.effective_message
        if not message:
            return

        chat = update.effective_chat
        is_group = chat and chat.type in ("group", "supergroup")

        content = message.text or message.caption or ""

        # In groups, only respond when mentioned or replied to
        if is_group:
            bot_username = context.bot.username
            is_reply_to_bot = (
                message.reply_to_message
                and message.reply_to_message.from_user
                and message.reply_to_message.from_user.is_bot
            )
            is_mentioned = bot_username and f"@{bot_username}" in content

            if not is_reply_to_bot and not is_mentioned:
                return

            # Strip mention
            if is_mentioned and bot_username:
                content = content.replace(f"@{bot_username}", "").strip()

        if not content and not message.document and not message.photo:
            return

        incoming = self.normalizer.to_incoming(update)
        incoming.content = content or "(attached files)"

        # Ingest file attachments -> MinIO + FileRecord
        incoming.attachments = await self._ingest_attachments(message, context)

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

        # Send text response
        text = self.normalizer.format_response(response)
        await message.reply_text(text, parse_mode="Markdown")

        # Send response files as native Telegram documents
        response_files = await self._download_response_files(response.files)
        for fname, data in response_files:
            await message.reply_document(document=data, filename=fname)

    async def _ingest_attachments(self, message, context) -> list[dict]:
        """Download Telegram attachments and ingest into MinIO + DB."""
        ingested = []

        items = []
        if message.document:
            items.append((message.document.file_id, message.document.file_name or "document"))
        if message.photo:
            # Largest photo resolution
            items.append((message.photo[-1].file_id, "photo.jpg"))

        for file_id, filename in items:
            try:
                tg_file = await context.bot.get_file(file_id)
                buf = await tg_file.download_as_bytearray()

                info = await ingest_attachment(
                    minio_client=self.minio,
                    session_factory=self.session_factory,
                    bucket=self.settings.minio_bucket,
                    public_url_base=self.settings.minio_public_url,
                    raw_bytes=bytes(buf),
                    filename=filename,
                    user_id=None,
                )
                ingested.append(info)
            except Exception as e:
                logger.error(
                    "telegram_attachment_ingest_failed",
                    filename=filename,
                    error=str(e),
                )
        return ingested

    async def _download_response_files(self, files: list[dict]) -> list[tuple[str, io.BytesIO]]:
        """Download response files from MinIO for sending as Telegram documents."""
        result = []
        if not files:
            return result

        public_prefix = self.settings.minio_public_url.rstrip("/") + "/"
        for f in files:
            url = f.get("url", "")
            filename = f.get("filename", "file")
            try:
                if url.startswith(public_prefix):
                    key = url[len(public_prefix):]
                else:
                    continue
                resp = self.minio.get_object(self.settings.minio_bucket, key)
                data = resp.read()
                resp.close()
                resp.release_conn()
                result.append((filename, io.BytesIO(data)))
            except Exception as e:
                logger.error("telegram_file_download_failed", filename=filename, error=str(e))
        return result

    def run(self):
        """Start the bot with polling."""
        logger.info("starting_telegram_bot")
        self.app.run_polling(drop_pending_updates=True)
