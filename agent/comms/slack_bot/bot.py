"""Slack bot implementation using HTTP mode with multi-workspace OAuth."""

from __future__ import annotations

import asyncio
import re

import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, Request
from minio import Minio
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.oauth.async_oauth_settings import AsyncOAuthSettings
from slack_sdk.oauth.installation_store.models.installation import Installation
from slack_sdk.oauth.state_utils import OAuthStateUtils
from slack_sdk.web.async_client import AsyncWebClient
from sqlalchemy import select

from comms.slack_bot.block_builder import BlockBuilder
from comms.slack_bot.installation_store import PostgresInstallationStore
from comms.slack_bot.normalizer import SlackNormalizer
from comms.slack_bot.oauth_state_store import RedisOAuthStateStore
from shared.auth import get_service_auth_headers
from shared.config import Settings
from shared.database import get_session_factory
from shared.file_utils import upload_attachment
from shared.models.slack_installation import SlackInstallation
from shared.schemas.messages import AgentResponse
from shared.schemas.notifications import Notification

logger = structlog.get_logger()

THINKING_FRAMES = [
    ":thinking_face: *Thinking...*",
    ":hourglass_flowing_sand: *Processing...*",
    ":gear: *Working on it...*",
    ":brain: *Reasoning...*",
    ":mag: *Researching...*",
    ":pencil2: *Composing response...*",
]


class _ProxyAwareStateUtils(OAuthStateUtils):
    """Skip cookie-based browser check when behind a reverse proxy.

    The Redis state store already validates the OAuth state parameter,
    so the cookie is a redundant CSRF check that breaks behind SSL-terminating
    proxies where the bot sees HTTP internally.
    """

    def is_valid_browser(self, state: str, request_headers: dict) -> bool:
        return True


class AgentSlackBot:
    """Slack bot using HTTP mode with multi-workspace OAuth support."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.normalizer = SlackNormalizer()
        self.minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        self.session_factory = get_session_factory()
        self.redis = aioredis.from_url(settings.redis_url)

        # OAuth stores
        self.installation_store = PostgresInstallationStore(
            client_id=settings.slack_client_id,
            session_factory=self.session_factory,
        )
        self.state_store = RedisOAuthStateStore(
            redis_client=self.redis,
            expiration_seconds=600,
        )

        # Derive public base URL for OAuth redirect
        from urllib.parse import urlparse
        parsed = urlparse(settings.minio_public_url)
        public_base_url = f"{parsed.scheme}://{parsed.netloc}"
        redirect_uri = f"{public_base_url}/slack/oauth_redirect"

        # Build slack-bolt app with OAuth
        oauth_settings = AsyncOAuthSettings(
            client_id=settings.slack_client_id,
            client_secret=settings.slack_client_secret,
            scopes=[
                "app_mentions:read",
                "channels:history",
                "channels:read",
                "chat:write",
                "files:read",
                "files:write",
                "groups:history",
                "groups:read",
                "im:history",
                "im:read",
                "mpim:history",
                "users:read",
                "users:write",
            ],
            state_store=self.state_store,
            install_path="/slack/install",
            redirect_uri_path="/slack/oauth_redirect",
            redirect_uri=redirect_uri,
        )
        # Override state_utils after construction to skip cookie-based
        # browser check that breaks behind SSL-terminating proxies
        oauth_settings.state_utils = _ProxyAwareStateUtils()

        self.app = AsyncApp(
            signing_secret=settings.slack_signing_secret,
            installation_store=self.installation_store,
            oauth_settings=oauth_settings,
        )
        self._setup_handlers()

        # FastAPI app wrapping slack-bolt
        self.api = FastAPI(title="Slack Bot")
        self.handler = AsyncSlackRequestHandler(self.app)

        @self.api.post("/slack/events")
        async def slack_events(req: Request):
            return await self.handler.handle(req)

        @self.api.get("/slack/install")
        async def slack_install(req: Request):
            return await self.handler.handle(req)

        @self.api.get("/slack/oauth_redirect")
        async def slack_oauth_redirect(req: Request):
            return await self.handler.handle(req)

        @self.api.get("/health")
        async def health():
            return {"status": "ok"}

    def _setup_handlers(self):
        """Register event handlers."""

        @self.app.event("app_mention")
        async def handle_mention(event, say, client, context):
            logger.info("event_mention_received", user=event.get("user"))
            await self._handle_message(event, say, client, is_mention=True, context=context)

        @self.app.event("message")
        async def handle_message(event, say, client, context):
            channel_type = event.get("channel_type", "")
            thread_ts = event.get("thread_ts")
            user_id = event.get("user")

            logger.info(
                "event_message_received",
                channel_type=channel_type,
                thread_ts=thread_ts,
                user=user_id,
                text=event.get("text", "")[:30],
            )

            # 1. Handle Direct Messages (Always reply)
            if channel_type == "im":
                logger.info("handling_im_message")
                await self._handle_message(event, say, client, is_mention=False, context=context)
                return

            # 2. Handle Threads (Check logic)
            if thread_ts:
                logger.info("checking_thread_logic", thread_ts=thread_ts)
                bot_user_id = context.get("bot_user_id") if context else None
                should_reply = await self._should_reply_to_thread(client, event, bot_user_id)

                logger.info("thread_decision_made", should_reply=should_reply)

                if should_reply:
                    await self._handle_message(event, say, client, is_mention=False, context=context)
            else:
                logger.info("ignoring_channel_message_no_thread")

    async def _handle_message(self, event, say, client, is_mention: bool, context=None):
        if event.get("bot_id"):
            return

        # Get bot_user_id from context (set by installation_store authorize)
        bot_user_id = context.get("bot_user_id") if context else None
        if bot_user_id is None:
            try:
                auth = await client.auth_test()
                bot_user_id = auth.get("user_id")
            except Exception:
                pass

        # 1. SEND "THINKING" STATUS
        thread_ts = event.get("thread_ts") or event.get("ts")
        channel_id = event.get("channel")

        loading_msg = await say(
            text=THINKING_FRAMES[0], thread_ts=thread_ts
        )
        loading_ts = loading_msg["ts"]

        # Start animated thinking indicator
        stop_thinking = await self._animate_thinking(client, channel_id, loading_ts)

        try:
            incoming = self.normalizer.to_incoming(event, bot_user_id)

            # Ingest Slack file attachments
            incoming.attachments = await self._ingest_attachments(event, client)

            if not incoming.content and not incoming.attachments:
                stop_thinking.set()
                await client.chat_delete(channel=channel_id, ts=loading_ts)
                return

            if not incoming.content:
                incoming.content = "(attached files)"

            # Call Orchestrator
            async with httpx.AsyncClient(timeout=120.0, headers=get_service_auth_headers()) as http_client:
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

            # Stop the thinking animation before updating with the real response
            stop_thinking.set()

            # Format Response
            raw_text = self.normalizer.format_response(response)
            formatted_text = self._clean_markdown_for_slack(raw_text)

            response_blocks = BlockBuilder.text_to_blocks(response.content)

            # 2. UPDATE THE "THINKING" MESSAGE WITH THE REAL RESPONSE
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
            stop_thinking.set()
            logger.error("slack_processing_error", error=str(e))

            await client.chat_update(
                channel=channel_id,
                ts=loading_ts,
                text=f":warning: I encountered an error: {str(e)}",
            )

    def _clean_markdown_for_slack(self, text: str) -> str:
        """Manually convert standard Markdown to Slack mrkdwn."""
        if not text:
            return ""

        text = re.sub(r"^#{1,6}\s+(.*?)$", r"*\1*", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
        text = re.sub(r"\*\*\s+(.*?)\s+\*\*", r"*\1*", text)
        text = re.sub(r"\[(.*?)\]\((.*?)\)", r"<\2|\1>", text)

        return text

    async def _should_reply_to_thread(self, client, event, bot_user_id: str | None = None) -> bool:
        """Check if the bot should reply to a generic thread message."""
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts")
        current_ts = event.get("ts")

        if bot_user_id is None:
            try:
                auth = await client.auth_test()
                bot_user_id = auth.get("user_id")
                logger.info("bot_user_id_fetched", bot_id=bot_user_id)
            except Exception as e:
                logger.error("auth_test_failed", error=str(e))
                return False

        try:
            history = await client.conversations_replies(
                channel=channel_id, ts=thread_ts, limit=5
            )
            messages = history.get("messages", [])
            messages.sort(key=lambda x: float(x["ts"]))
            previous_msgs = [m for m in messages if m["ts"] != current_ts]

            if not previous_msgs:
                logger.info("thread_empty_or_new")
                return False

            last_msg = previous_msgs[-1]
            last_user = last_msg.get("user")

            logger.info(
                "thread_history_check",
                last_user=last_user,
                my_bot_id=bot_user_id,
                last_text=last_msg.get("text", "")[:20],
            )

            if last_user == bot_user_id:
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
                # Use the workspace-scoped client token for authorization
                token = client.token
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    resp = await http_client.get(
                        url,
                        headers={
                            "Authorization": f"Bearer {token}"
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

    async def _animate_thinking(self, client, channel: str, ts: str) -> asyncio.Event:
        """Update the thinking message every few seconds to show the bot is active."""
        stop = asyncio.Event()

        async def _loop():
            frame = 1
            while not stop.is_set():
                await asyncio.sleep(3)
                if stop.is_set():
                    break
                try:
                    text = THINKING_FRAMES[frame % len(THINKING_FRAMES)]
                    await client.chat_update(channel=channel, ts=ts, text=text)
                    frame += 1
                except Exception:
                    break

        asyncio.create_task(_loop())
        return stop

    async def _presence_heartbeat(self):
        """Periodically re-assert 'auto' presence for all installed workspaces."""
        while True:
            try:
                async with self.session_factory() as session:
                    result = await session.execute(select(SlackInstallation))
                    installations = result.scalars().all()

                for inst in installations:
                    try:
                        client = AsyncWebClient(token=inst.bot_token)
                        await client.users_setPresence(presence="auto")
                    except Exception as e:
                        logger.warning(
                            "presence_heartbeat_failed",
                            team_id=inst.team_id,
                            error=str(e),
                        )
            except Exception as e:
                logger.warning("presence_heartbeat_loop_failed", error=str(e))
            await asyncio.sleep(30)

    async def _get_client_for_team(self, team_id: str | None) -> AsyncWebClient | None:
        """Get an AsyncWebClient for a specific workspace by team_id."""
        if team_id:
            bot = await self.installation_store.async_find_bot(team_id=team_id)
            if bot and bot.bot_token:
                return AsyncWebClient(token=bot.bot_token)

        # Fallback for legacy single-workspace mode
        if self.settings.slack_bot_token:
            return AsyncWebClient(token=self.settings.slack_bot_token)
        return None

    async def _notification_listener(self):
        """Subscribe to Redis notifications and send proactive messages."""
        try:
            pubsub = self.redis.pubsub()
            await pubsub.subscribe("notifications:slack")
            logger.info("slack_notification_listener_started")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    notification = Notification.model_validate_json(message["data"])

                    web_client = await self._get_client_for_team(
                        notification.platform_server_id
                    )
                    if web_client is None:
                        logger.error(
                            "no_installation_for_notification",
                            team_id=notification.platform_server_id,
                            channel_id=notification.platform_channel_id,
                        )
                        continue

                    await web_client.chat_postMessage(
                        channel=notification.platform_channel_id,
                        text=notification.content,
                        thread_ts=notification.platform_thread_id,
                    )
                    logger.info(
                        "notification_sent",
                        channel_id=notification.platform_channel_id,
                        team_id=notification.platform_server_id,
                        job_id=notification.job_id,
                    )
                except Exception as e:
                    logger.error("notification_send_failed", error=str(e))
        except Exception as e:
            logger.error("notification_listener_failed", error=str(e))

    async def _seed_legacy_installation(self):
        """If SLACK_BOT_TOKEN is set, ensure it exists in the installation store."""
        if not self.settings.slack_bot_token:
            return
        try:
            client = AsyncWebClient(token=self.settings.slack_bot_token)
            auth = await client.auth_test()
            team_id = auth.get("team_id")
            bot_id = auth.get("bot_id")
            bot_user_id = auth.get("user_id")

            installation = Installation(
                app_id=auth.get("app_id", ""),
                team_id=team_id,
                team_name=auth.get("team", ""),
                bot_token=self.settings.slack_bot_token,
                bot_id=bot_id,
                bot_user_id=bot_user_id,
                user_id=bot_user_id,
            )
            await self.installation_store.async_save(installation)
            logger.info("legacy_installation_seeded", team_id=team_id)
        except Exception as e:
            logger.warning("legacy_seed_failed", error=str(e))

    async def run(self):
        """Start the bot as an HTTP server."""
        import uvicorn

        logger.info("starting_slack_bot_http_mode")

        # Seed existing single-workspace token into the installation store
        await self._seed_legacy_installation()

        # Start background tasks
        self._heartbeat_task = asyncio.create_task(self._presence_heartbeat())
        self._notification_task = asyncio.create_task(self._notification_listener())

        config = uvicorn.Config(
            self.api,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            proxy_headers=True,
            forwarded_allow_ips="*",
        )
        server = uvicorn.Server(config)
        await server.serve()
