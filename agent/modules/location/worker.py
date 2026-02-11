"""Background geofence proximity checker — server-side fallback."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.location.geocoding import haversine_m
from modules.location.owntracks import queue_waypoint_deletion
from shared.models.location_reminder import LocationReminder
from shared.models.user_location import UserLocation
from shared.schemas.notifications import Notification

logger = structlog.get_logger()

# How often the worker checks (seconds)
CHECK_INTERVAL = 30
# Skip locations older than this (seconds)
STALE_THRESHOLD = 600  # 10 minutes
# Cooldown after triggering (seconds)
COOLDOWN_DURATION = 3600  # 1 hour


async def geofence_loop(
    session_factory: async_sessionmaker,
    redis_client,
) -> None:
    """Run the geofence proximity check loop.

    For each user with active reminders:
    1. Get latest location from user_locations
    2. Skip if location is stale (> 10 min old)
    3. For each active reminder, compute haversine distance
    4. If distance <= radius_m and not already triggered:
       - Mark reminder as triggered
       - Publish notification via Redis pub/sub
    """
    logger.info("geofence_worker_started")

    while True:
        try:
            await _check_all_reminders(session_factory, redis_client)
        except Exception:
            logger.exception("geofence_check_error")

        await asyncio.sleep(CHECK_INTERVAL)


async def _check_all_reminders(
    session_factory: async_sessionmaker,
    redis_client,
) -> None:
    """Single pass: check all active reminders against user locations."""
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        # Get all active reminders
        result = await session.execute(
            select(LocationReminder).where(
                LocationReminder.status == "active",
            )
        )
        reminders = result.scalars().all()

        if not reminders:
            return

        # Group by user_id
        by_user: dict[str, list[LocationReminder]] = {}
        for r in reminders:
            uid = str(r.user_id)
            by_user.setdefault(uid, []).append(r)

        # Check each user
        for user_id, user_reminders in by_user.items():
            loc_result = await session.execute(
                select(UserLocation).where(UserLocation.user_id == user_id)
            )
            location = loc_result.scalar_one_or_none()
            if location is None:
                continue

            # Skip stale locations
            age_s = (now - location.updated_at).total_seconds()
            if age_s > STALE_THRESHOLD:
                continue

            for reminder in user_reminders:
                # Check cooldown
                if reminder.cooldown_until and now < reminder.cooldown_until:
                    continue

                # Check expiry
                if reminder.expires_at and now > reminder.expires_at:
                    reminder.status = "expired"
                    await session.commit()
                    await queue_waypoint_deletion(redis_client, user_id, reminder)
                    continue

                # Compute distance
                dist = haversine_m(
                    location.latitude,
                    location.longitude,
                    reminder.place_lat,
                    reminder.place_lng,
                )

                if dist <= reminder.radius_m:
                    # Trigger
                    reminder.status = "triggered"
                    reminder.triggered_at = now
                    await session.commit()

                    await queue_waypoint_deletion(redis_client, user_id, reminder)

                    if reminder.platform and reminder.platform_channel_id:
                        notification = Notification(
                            platform=reminder.platform,
                            platform_channel_id=reminder.platform_channel_id,
                            platform_thread_id=reminder.platform_thread_id,
                            content=(
                                f"You're near **{reminder.place_name}**!\n\n"
                                f"Reminder: {reminder.message}"
                            ),
                            user_id=user_id,
                        )
                        channel = f"notifications:{notification.platform}"
                        await redis_client.publish(
                            channel, notification.model_dump_json()
                        )
                        logger.info(
                            "geofence_worker_triggered",
                            reminder_id=str(reminder.id),
                            user_id=user_id,
                            distance_m=round(dist, 1),
                        )
