"""Slack bot implementation using Socket Mode."""

from __future__ import annotations

import io
import re
from comms.slack_bot.block_builder import BlockBuilder
import httpx
import structlog
from slackify_markdown import slackify_markdown
from minio import Minio
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from comms.slack_bot.normalizer import SlackNormalizer
from shared.config import Settings
from shared.file_utils import upload_attachment
from shared.schemas.messages import AgentResponse

logger = structlog.get_logger()


class AgentSlackBot:
    """Slack bot using Socket Mode that routes messages to the orchestrator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.normalizer = SlackNormalizer()
        self.bot_user_id: str | None = None
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
            logger.info("event_mention_received", user=event.get("user"))
            await self._handle_message(event, say, client, is_mention=True)

        @self.app.event("message")
        async def handle_message(event, say, client):
            channel_type = event.get("channel_type", "")
            thread_ts = event.get("thread_ts")
            user_id = event.get("user")

            logger.info(
                "event_message_received",
                channel_type=channel_type,
                thread_ts=thread_ts,
                user=user_id,
                text=event.get("text", "")[:30],  # Log first 30 chars
            )

            # 1. Handle Direct Messages (Always reply)
            if channel_type == "im":
                logger.info("handling_im_message")
                await self._handle_message(event, say, client, is_mention=False)
                return

            # 2. Handle Threads (Check logic)
            if thread_ts:
                logger.info("checking_thread_logic", thread_ts=thread_ts)
                should_reply = await self._should_reply_to_thread(client, event)

                logger.info("thread_decision_made", should_reply=should_reply)

                if should_reply:
                    await self._handle_message(event, say, client, is_mention=False)
            else:
                logger.info("ignoring_channel_message_no_thread")

    async def _handle_message(self, event, say, client, is_mention: bool):
        if event.get("bot_id"):
            return

        if self.bot_user_id is None:
            try:
                auth = await client.auth_test()
                self.bot_user_id = auth.get("user_id")
            except Exception:
                pass

        # 1. SEND "THINKING" STATUS
        # We send a temporary message immediately so the user knows we are working.
        thread_ts = event.get("thread_ts") or event.get("ts")
        channel_id = event.get("channel")

        loading_msg = await say(
            text=":thinking_face: *Thinking...*", thread_ts=thread_ts
        )
        loading_ts = loading_msg[
            "ts"
        ]  # We need this timestamp to edit the message later

        try:
            incoming = self.normalizer.to_incoming(event, self.bot_user_id)

            # Ingest Slack file attachments
            incoming.attachments = await self._ingest_attachments(event, client)

            if not incoming.content and not incoming.attachments:
                # If nothing to process, delete the loading message
                await client.chat_delete(channel=channel_id, ts=loading_ts)
                return

            if not incoming.content:
                incoming.content = "(attached files)"

            # Call Orchestrator
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

            # Format Response (Using the markdown helper we made earlier)
            raw_text = self.normalizer.format_response(response)
            formatted_text = self._clean_markdown_for_slack(raw_text)

            response_blocks = BlockBuilder.text_to_blocks(response.content)

            # 2. UPDATE THE "THINKING" MESSAGE WITH THE REAL RESPONSE
            # Instead of say(), we use client.chat_update
            await client.chat_update(
                channel=channel_id,
                ts=loading_ts,
                text=formatted_text,
                blocks=response_blocks,
            )

            # Upload response files natively to Slack (if any)
            for f in response.files:
                await self._upload_response_file(client, channel_id, thread_ts, f)

        except Exception as e:
            logger.error("slack_processing_error", error=str(e))

            # If it fails, update the loading message to show the error
            await client.chat_update(
                channel=channel_id,
                ts=loading_ts,
                text=f":warning: I encountered an error: {str(e)}",
            )

    def _clean_markdown_for_slack(self, text: str) -> str:
        """
        Manually convert standard Markdown to Slack mrkdwn.
        """
        if not text:
            return ""

        # 1. Convert Headers (### Heading) to Bold (*Heading*)
        # Matches #, ##, ### followed by space and text
        text = re.sub(r"^#{1,6}\s+(.*?)$", r"*\1*", text, flags=re.MULTILINE)

        # 2. Convert Bold (**Bold**) to Slack Bold (*Bold*)
        text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)

        # 3. Convert Bold with extra spaces (** Bold **) to (*Bold*)
        # LLMs sometimes add spaces inside the asterisks which breaks formatting
        text = re.sub(r"\*\*\s+(.*?)\s+\*\*", r"*\1*", text)

        # 4. Convert Links [Text](URL) to <URL|Text>
        text = re.sub(r"\[(.*?)\]\((.*?)\)", r"<\2|\1>", text)

        return text

    async def _should_reply_to_thread(self, client, event) -> bool:
        """Check if the bot should reply to a generic thread message."""
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        current_ts = event.get("ts")

        # Ensure we know our own ID
        if self.bot_user_id is None:
            try:
                auth = await client.auth_test()
                self.bot_user_id = auth.get("user_id")
                logger.info("bot_user_id_fetched", bot_id=self.bot_user_id)
            except Exception as e:
                logger.error("auth_test_failed", error=str(e))
                return False

        try:
            # Fetch context (last 5 messages)
            history = await client.conversations_replies(
                channel=channel_id, ts=thread_ts, limit=5
            )
            messages = history.get("messages", [])

            # Sort by timestamp just in case
            messages.sort(key=lambda x: float(x["ts"]))

            # Filter out the message that JUST triggered this event
            previous_msgs = [m for m in messages if m["ts"] != current_ts]

            if not previous_msgs:
                logger.info("thread_empty_or_new")
                return False

            last_msg = previous_msgs[-1]
            last_user = last_msg.get("user")

            logger.info(
                "thread_history_check",
                last_user=last_user,
                my_bot_id=self.bot_user_id,
                last_text=last_msg.get("text", "")[:20],
            )

            # REPLY CONDITION: The last message was sent by ME (the bot).
            # This means the user just replied to me, so I should continue.
            if last_user == self.bot_user_id:
                return True

            return False

        except Exception as e:
            logger.error("check_thread_history_failed", error=str(e))
            return False

    async def _ingest_attachments(self, event: dict, client) -> list[dict]:
        """Download Slack file attachments and upload to MinIO."""
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
                        headers={
                            "Authorization": f"Bearer {self.settings.slack_bot_token}"
                        },
                    )
                    if resp.status_code != 200:
                        logger.warning(
                            "slack_file_download_failed", status=resp.status_code
                        )
                        continue
                    raw_bytes = resp.content

                info = upload_attachment(
                    minio_client=self.minio,
                    bucket=self.settings.minio_bucket,
                    public_url_base=self.settings.minio_public_url,
                    raw_bytes=raw_bytes,
                    filename=filename,
                )
                ingested.append(info)
            except Exception as e:
                logger.error(
                    "slack_attachment_ingest_failed",
                    filename=filename,
                    error=str(e),
                )
        return ingested

    async def _upload_response_file(
        self, client, channel: str, thread_ts: str, f: dict
    ):
        """Download a response file from MinIO and upload to Slack."""
        url = f.get("url", "")
        filename = f.get("filename", "file")
        public_prefix = self.settings.minio_public_url.rstrip("/") + "/"

        try:
            if url.startswith(public_prefix):
                key = url[len(public_prefix) :]
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
