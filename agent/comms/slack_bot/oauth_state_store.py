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
        await self.redis.setex(
            f"slack_oauth_state:{state}",
            self.expiration_seconds,
            "valid",
        )
        return state

    async def async_consume(self, state: str) -> bool:
        key = f"slack_oauth_state:{state}"
        value = await self.redis.get(key)
        if value is not None:
            await self.redis.delete(key)
            return True
        return False
