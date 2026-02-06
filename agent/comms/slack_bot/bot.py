"""Slack bot implementation using Socket Mode."""

from __future__ import annotations

import io

import httpx
import structlog
from minio import Minio
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from comms.slack_bot.normalizer import SlackNormalizer
from shared.config import Settings
from shared.database import get_session_factory
from shared.file_utils import ingest_attachment
from shared.schemas.messages import AgentResponse

logger = structlog.get_logger()


class AgentSlackBot:
    """Slack bot using Socket Mode that routes messages to the orchestrator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.normalizer = SlackNormalizer()
        self.bot_user_id: str | None = None
        self.session_factory = get_session_factory()
        self.minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )

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

        # Ingest Slack file attachments -> MinIO + FileRecord
        incoming.attachments = await self._ingest_attachments(event, client)

        if not incoming.content and not incoming.attachments:
            return

        if not incoming.content:
            incoming.content = "(attached files)"

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

        # Upload response files natively to Slack
        for f in response.files:
            await self._upload_response_file(client, event.get("channel", ""), thread_ts, f)

    async def _ingest_attachments(self, event: dict, client) -> list[dict]:
        """Download Slack file attachments and ingest into MinIO + DB."""
        ingested = []
        if "files" not in event:
            return ingested

        for f in event["files"]:
            url = f.get("url_private", "")
            filename = f.get("name", "file")
            if not url:
                continue

            try:
                # Slack private URLs require bot token authorization
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    resp = await http_client.get(
                        url,
                        headers={"Authorization": f"Bearer {self.settings.slack_bot_token}"},
                    )
                    if resp.status_code != 200:
                        logger.warning("slack_file_download_failed", status=resp.status_code)
                        continue
                    raw_bytes = resp.content

                info = await ingest_attachment(
                    minio_client=self.minio,
                    session_factory=self.session_factory,
                    bucket=self.settings.minio_bucket,
                    public_url_base=self.settings.minio_public_url,
                    raw_bytes=raw_bytes,
                    filename=filename,
                    user_id=None,
                )
                ingested.append(info)
            except Exception as e:
                logger.error(
                    "slack_attachment_ingest_failed",
                    filename=filename,
                    error=str(e),
                )
        return ingested

    async def _upload_response_file(self, client, channel: str, thread_ts: str, f: dict):
        """Download a response file from MinIO and upload to Slack."""
        url = f.get("url", "")
        filename = f.get("filename", "file")
        public_prefix = self.settings.minio_public_url.rstrip("/") + "/"

        try:
            if url.startswith(public_prefix):
                key = url[len(public_prefix):]
            else:
                return

            resp = self.minio.get_object(self.settings.minio_bucket, key)
            data = resp.read()
            resp.close()
            resp.release_conn()

            await client.files_upload_v2(
                channel=channel,
                thread_ts=thread_ts,
                file=data,
                filename=filename,
                title=filename,
            )
        except Exception as e:
            logger.error("slack_file_upload_failed", filename=filename, error=str(e))

    async def run(self):
        """Start the bot with Socket Mode."""
        logger.info("starting_slack_bot")
        handler = AsyncSocketModeHandler(self.app, self.settings.slack_app_token)
        await handler.start_async()
