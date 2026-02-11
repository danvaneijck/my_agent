"""Discord bot implementation."""

from __future__ import annotations

import asyncio
import io

import httpx
import redis.asyncio as aioredis
import structlog
import discord
from discord import Intents
from minio import Minio

from comms.discord_bot.normalizer import DiscordNormalizer
from shared.config import Settings
from shared.file_utils import upload_attachment
from shared.schemas.notifications import Notification

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
        self.minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        self._notification_task: asyncio.Task | None = None

    async def on_ready(self):
        logger.info("discord_bot_ready", user=str(self.user))
        # on_ready fires again on reconnect — avoid duplicate listeners
        if self._notification_task is None or self._notification_task.done():
            self._notification_task = asyncio.create_task(
                self._notification_listener()
            )

    async def _notification_listener(self):
        """Subscribe to Redis notifications and send proactive messages."""
        try:
            r = aioredis.from_url(self.settings.redis_url)
            pubsub = r.pubsub()
            await pubsub.subscribe("notifications:discord")
            logger.info("discord_notification_listener_started")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    notification = Notification.model_validate_json(message["data"])
                    channel = self.get_channel(int(notification.platform_channel_id))
                    if channel is None:
                        channel = await self.fetch_channel(int(notification.platform_channel_id))
                    if channel:
                        await channel.send(notification.content)
                        logger.info(
                            "notification_sent",
                            channel_id=notification.platform_channel_id,
                            job_id=notification.job_id,
                        )
                except Exception as e:
                    logger.error("notification_send_failed", error=str(e))
        except Exception as e:
            logger.error("notification_listener_failed", error=str(e))

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

        if not content and not message.attachments:
            return

        # Override content with cleaned version
        incoming = self.normalizer.to_incoming(message)
        incoming.content = content or "(attached files)"

        # Ingest file attachments → MinIO + FileRecord
        incoming.attachments = await self._ingest_attachments(
            message, incoming.platform_user_id
        )

        # Show typing indicator while processing
        async with message.channel.typing():
            try:
                async with httpx.AsyncClient(timeout=120) as client:
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

        # Download response file attachments from MinIO
        discord_files = await self._download_files(response.files)

        # Send response chunks
        chunks = self.normalizer.format_response(response)
        for i, chunk in enumerate(chunks):
            is_last = i == len(chunks) - 1
            if is_last and discord_files:
                await message.reply(chunk, files=discord_files, mention_author=False)
            else:
                await message.reply(chunk, mention_author=False)

    async def _ingest_attachments(
        self, message: discord.Message, platform_user_id: str
    ) -> list[dict]:
        """Download Discord attachments and upload to MinIO."""
        ingested = []
        for attachment in message.attachments:
            try:
                data = await attachment.read()
                info = upload_attachment(
                    minio_client=self.minio,
                    bucket=self.settings.minio_bucket,
                    public_url_base=self.settings.minio_public_url,
                    raw_bytes=data,
                    filename=attachment.filename,
                )
                ingested.append(info)
            except Exception as e:
                logger.error(
                    "discord_attachment_ingest_failed",
                    filename=attachment.filename,
                    error=str(e),
                )
        return ingested

    async def _download_files(self, files: list[dict]) -> list[discord.File]:
        """Download files from MinIO and return as discord.File objects."""
        attachments: list[discord.File] = []
        if not files:
            return attachments

        public_prefix = self.settings.minio_public_url.rstrip("/") + "/"

        for f in files:
            url = f.get("url", "")
            filename = f.get("filename", "file")
            try:
                # Extract the MinIO object key from the public URL
                if url.startswith(public_prefix):
                    key = url[len(public_prefix) :]
                else:
                    logger.warning("unknown_file_url_format", url=url)
                    continue

                # Download from MinIO using internal Docker network
                resp = self.minio.get_object(self.settings.minio_bucket, key)
                data = resp.read()
                resp.close()
                resp.release_conn()

                attachments.append(discord.File(io.BytesIO(data), filename=filename))
                logger.info("file_attached", filename=filename, size=len(data))
            except Exception as e:
                logger.error("file_download_failed", filename=filename, error=str(e))

        return attachments
