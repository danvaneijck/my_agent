"""Periodic health check for all module services.

Monitors ``/health`` endpoints on every configured module and publishes
Redis notifications when a service goes down or recovers.  Only alerts
on state *transitions* (healthy → unhealthy and vice-versa) to avoid
repeated notifications for the same outage.

Activated by setting ``HEALTH_CHECK_INTERVAL_SECONDS`` > 0 and both
``HEALTH_ALERT_PLATFORM`` and ``HEALTH_ALERT_CHANNEL_ID`` in the env.
"""

from __future__ import annotations

import asyncio

import httpx
import redis.asyncio as aioredis
import structlog

from shared.config import Settings
from shared.schemas.notifications import Notification

logger = structlog.get_logger()


class HealthMonitor:
    """Background loop that checks module health and sends alerts."""

    def __init__(self, settings: Settings, redis_url: str) -> None:
        self.settings = settings
        self.redis_url = redis_url
        # Tracks last-known health per module. Modules default to "healthy"
        # so the first check only alerts if a service is already down.
        self._service_state: dict[str, bool] = {}

    async def run(self) -> None:
        """Run the health check loop forever (call via ``asyncio.create_task``)."""
        interval = self.settings.health_check_interval_seconds
        platform = self.settings.health_alert_platform
        channel_id = self.settings.health_alert_channel_id

        if not interval or not platform or not channel_id:
            logger.info("health_monitor_disabled")
            return

        redis = aioredis.from_url(self.redis_url)
        logger.info(
            "health_monitor_started",
            interval=interval,
            platform=platform,
            channel_id=channel_id,
            modules=list(self.settings.module_services.keys()),
        )

        try:
            while True:
                await asyncio.sleep(interval)
                try:
                    await self._check_all(redis)
                except Exception as e:
                    logger.error("health_monitor_loop_error", error=str(e))
        except asyncio.CancelledError:
            pass
        finally:
            await redis.aclose()

    async def _check_all(self, redis: aioredis.Redis) -> None:
        """Check every module and alert on state transitions."""
        for module_name, url in self.settings.module_services.items():
            healthy = await self._check_one(module_name, url)
            was_healthy = self._service_state.get(module_name, True)

            if not healthy and was_healthy:
                await self._alert(redis, module_name, down=True)
            elif healthy and not was_healthy:
                await self._alert(redis, module_name, down=False)

            self._service_state[module_name] = healthy

    @staticmethod
    async def _check_one(module_name: str, url: str) -> bool:
        """Return True if the module's /health endpoint responds 200."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    async def _alert(self, redis: aioredis.Redis, module_name: str, *, down: bool) -> None:
        """Publish a health alert notification via Redis."""
        status = "DOWN" if down else "RECOVERED"
        msg = f"[Health Monitor] Module `{module_name}` is **{status}**"

        notification = Notification(
            platform=self.settings.health_alert_platform,
            platform_channel_id=self.settings.health_alert_channel_id,
            content=msg,
        )
        channel = f"notifications:{self.settings.health_alert_platform}"
        await redis.publish(channel, notification.model_dump_json())
        logger.info("health_alert_sent", module=module_name, status=status)
