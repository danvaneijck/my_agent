"""Redis-backed OAuth state store for CSRF protection during Slack OAuth flow."""

from __future__ import annotations

import sys
import uuid
from logging import Logger, getLogger

import redis.asyncio as aioredis
from slack_sdk.oauth.state_store.async_state_store import AsyncOAuthStateStore

logger = getLogger(__name__)


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
        # Verify it was stored
        check = await self.redis.get(key)
        print(f"[STATE-STORE] ISSUE state={state} stored={check is not None}", flush=True, file=sys.stderr)
        return state

    async def async_consume(self, state: str) -> bool:
        key = f"slack_oauth_state:{state}"
        # List all oauth state keys for debugging
        all_keys = [k async for k in self.redis.scan_iter(match="slack_oauth_state:*")]
        print(f"[STATE-STORE] CONSUME state={state} key={key}", flush=True, file=sys.stderr)
        print(f"[STATE-STORE] All state keys in Redis: {all_keys}", flush=True, file=sys.stderr)
        value = await self.redis.get(key)
        print(f"[STATE-STORE] GET result: {value}", flush=True, file=sys.stderr)
        if value is not None:
            await self.redis.delete(key)
            return True
        return False
