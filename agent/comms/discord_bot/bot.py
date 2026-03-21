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
from shared.auth import get_service_auth_headers
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
        """Subscribe to Redis notifications and send proactive messages.

        Retries with exponential backoff if the Redis connection fails.
        """
        backoff = 5
        while True:
            try:
                r = aioredis.from_url(self.settings.redis_url)
                pubsub = r.pubsub()
                await pubsub.subscribe("notifications:discord")
                logger.info("discord_notification_listener_started")
                backoff = 5  # reset on successful connection

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
                logger.error("notification_listener_failed", error=str(e), retry_in=backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

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

        # Send an initial placeholder that we'll edit with progress
        status_msg = await message.reply("🔄 Thinking...", mention_author=False)

        from shared.schemas.messages import AgentResponse

        response: AgentResponse | None = None
        status_lines: list[str] = []
        last_edit_text = ""

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout=300, connect=10),
                headers=get_service_auth_headers(),
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self.settings.orchestrator_url}/message/stream",
                    json=incoming.model_dump(),
                ) as stream:
                    buffer = ""
                    async for chunk in stream.aiter_text():
                        buffer += chunk
                        # Parse SSE events from the buffer
                        while "\n\n" in buffer:
                            raw_event, buffer = buffer.split("\n\n", 1)
                            event_type, event_data = self._parse_sse(raw_event)
                            if not event_type:
                                continue

                            if event_type == "thinking":
                                iteration = event_data.get("iteration", 1)
                                if iteration == 1:
                                    status_lines = ["🔄 Thinking..."]
                                else:
                                    status_lines.append("🔄 Thinking...")
                            elif event_type == "content":
                                text = event_data.get("text", "")
                                if text:
                                    status_lines.append(text)
                            elif event_type == "tool_call":
                                tool = event_data.get("tool", "")
                                args = event_data.get("arguments", {})
                                args_str = self._format_tool_args(args)
                                display = f"🔧 `{tool}`{args_str}"
                                status_lines.append(display)
                            elif event_type == "tool_result":
                                tool = event_data.get("tool", "")
                                success = event_data.get("success", False)
                                icon = "✅" if success else "❌"
                                # Replace the last tool_call line with result
                                for i in range(len(status_lines) - 1, -1, -1):
                                    if f"🔧 `{tool}`" in status_lines[i]:
                                        # Keep args, just swap the icon
                                        status_lines[i] = status_lines[i].replace("🔧", icon)
                                        break
                            elif event_type == "done":
                                response = AgentResponse(**event_data)
                            elif event_type == "error":
                                response = AgentResponse(
                                    content="I encountered an internal error. Please try again.",
                                    error=event_data.get("error"),
                                )

                            # Edit the status message (throttle to avoid rate limits)
                            if event_type in ("thinking", "content", "tool_call", "tool_result"):
                                new_text = "\n".join(status_lines[-15:])  # Keep last 15 lines
                                if new_text and new_text != last_edit_text:
                                    try:
                                        await status_msg.edit(content=new_text[:2000])
                                        last_edit_text = new_text
                                    except discord.HTTPException:
                                        pass  # Rate limited, skip this edit
        except Exception as e:
            logger.error("discord_orchestrator_error", error=str(e))
            response = AgentResponse(
                content="Sorry, I'm having trouble connecting to my brain. Please try again.",
                error=str(e),
            )

        if response is None:
            response = AgentResponse(
                content="Sorry, I didn't receive a complete response. Please try again.",
                error="Stream ended without done event",
            )

        # Download response file attachments from MinIO
        discord_files = await self._download_files(response.files)

        # Delete the status message and send the final response
        try:
            await status_msg.delete()
        except discord.HTTPException:
            pass

        # Send response chunks
        chunks = self.normalizer.format_response(response)
        for i, chunk in enumerate(chunks):
            is_last = i == len(chunks) - 1
            if is_last and discord_files:
                await message.reply(chunk, files=discord_files, mention_author=False)
            else:
                await message.reply(chunk, mention_author=False)

    @staticmethod
    def _format_tool_args(args: dict, max_len: int = 120) -> str:
        """Format tool arguments compactly for status display."""
        if not args:
            return ""
        parts = []
        for k, v in args.items():
            if isinstance(v, str) and len(v) > 50:
                v = v[:47] + "..."
            elif isinstance(v, dict):
                v = "{...}"
            elif isinstance(v, list):
                v = f"[{len(v)} items]"
            parts.append(f"{k}={v}")
        result = "(" + ", ".join(parts) + ")"
        if len(result) > max_len:
            result = result[:max_len - 3] + "...)"
        return " " + result

    @staticmethod
    def _parse_sse(raw: str) -> tuple[str, dict]:
        """Parse a single SSE event block into (event_type, data_dict)."""
        import json as _json

        event_type = ""
        data_str = ""
        for line in raw.strip().splitlines():
            if line.startswith("event: "):
                event_type = line[7:].strip()
            elif line.startswith("data: "):
                data_str = line[6:]
        if not event_type or not data_str:
            return "", {}
        try:
            return event_type, _json.loads(data_str)
        except (ValueError, TypeError):
            return event_type, {"raw": data_str}

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
