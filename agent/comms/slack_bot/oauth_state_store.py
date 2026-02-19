"""Redis-backed OAuth state store for CSRF protection during Slack OAuth flow."""

from __future__ import annotations

import logging
import uuid
from logging import Logger

import redis.asyncio as aioredis
from slack_sdk.oauth.state_store.async_state_store import AsyncOAuthStateStore

logger = logging.getLogger(__name__)


class RedisOAuthStateStore(AsyncOAuthStateStore):
    def __init__(
        self,
        redis_client: aioredis.Redis,
        expiration_seconds: int = 600,
    ):
        self.redis = redis_client
        self.expiration_seconds = expiration_seconds
        self._logger = logger

    @property
    def logger(self) -> Logger:
        return self._logger

    async def async_issue(self, *args, **kwargs) -> str:
        state = str(uuid.uuid4())
        key = f"slack_oauth_state:{state}"
        await self.redis.setex(key, self.expiration_seconds, "valid")
        logger.info("oauth_state_issued: %s (ttl=%d)", state, self.expiration_seconds)
        # Verify it was stored
        check = await self.redis.get(key)
        logger.info("oauth_state_verify_after_issue: key=%s exists=%s", key, check is not None)
        return state

    async def async_consume(self, state: str) -> bool:
        key = f"slack_oauth_state:{state}"
        value = await self.redis.get(key)
        logger.info("oauth_state_consume: key=%s found=%s", key, value is not None)
        if value is not None:
            await self.redis.delete(key)
            return True
        return False
