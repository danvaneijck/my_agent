"""OwnTracks protocol handling — parse incoming payloads and build responses."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.location_reminder import LocationReminder
from shared.models.owntracks_credential import OwnTracksCredential
from shared.models.user_location import UserLocation
from shared.schemas.notifications import Notification

logger = structlog.get_logger()


async def authenticate_owntracks(
    session: AsyncSession,
    username: str,
    password: str,
) -> str | None:
    """Verify OwnTracks credentials and return the user_id if valid.

    Uses bcrypt to check the password against the stored hash.
    """
    import bcrypt

    result = await session.execute(
        select(OwnTracksCredential).where(
            OwnTracksCredential.username == username,
            OwnTracksCredential.is_active == True,  # noqa: E712
        )
    )
    cred = result.scalar_one_or_none()
    if cred is None:
        return None

    if not bcrypt.checkpw(password.encode("utf-8"), cred.password_hash.encode("utf-8")):
        return None

    # Update last seen
    cred.last_seen_at = datetime.now(timezone.utc)
    await session.commit()

    return str(cred.user_id)


async def upsert_user_location(
    session: AsyncSession,
    user_id: str,
    payload: dict,
) -> None:
    """Insert or update the user's latest location from an OwnTracks payload."""
    uid = uuid.UUID(user_id)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(UserLocation).where(UserLocation.user_id == uid)
    )
    loc = result.scalar_one_or_none()

    if loc is None:
        loc = UserLocation(
            user_id=uid,
            latitude=payload["lat"],
            longitude=payload["lon"],
            accuracy_m=payload.get("acc"),
            speed_mps=payload.get("vel"),
            heading=payload.get("cog"),
            source="owntracks",
            updated_at=now,
            created_at=now,
        )
        session.add(loc)
    else:
        loc.latitude = payload["lat"]
        loc.longitude = payload["lon"]
        loc.accuracy_m = payload.get("acc")
        loc.speed_mps = payload.get("vel")
        loc.heading = payload.get("cog")
        loc.source = "owntracks"
        loc.updated_at = now

    await session.commit()


async def mark_waypoints_dirty(redis_client, user_id: str) -> None:
    """Flag that this user's waypoints need re-syncing on the next OwnTracks check-in.

    Instead of queuing individual waypoint dicts, we set a dirty flag.
    At sync time we query ALL active reminders from the DB and send the
    complete list via setWaypoints (which is a replace-all operation).
    """
    key = f"owntracks_waypoints_dirty:{user_id}"
    await redis_client.set(key, "1")


async def _is_waypoints_dirty(redis_client, user_id: str) -> bool:
    """Check whether this user has pending waypoint changes."""
    key = f"owntracks_waypoints_dirty:{user_id}"
    return await redis_client.exists(key)


async def _clear_waypoints_dirty(redis_client, user_id: str) -> None:
    """Clear the dirty flag after syncing."""
    key = f"owntracks_waypoints_dirty:{user_id}"
    await redis_client.delete(key)


async def _build_waypoint_list(
    session: AsyncSession,
    user_id: str,
) -> list[dict]:
    """Build the full waypoint list from all active reminders for a user."""
    uid = uuid.UUID(user_id)
    result = await session.execute(
        select(LocationReminder).where(
            LocationReminder.user_id == uid,
            LocationReminder.status == "active",
        )
    )
    reminders = result.scalars().all()

    waypoints = []
    for r in reminders:
        waypoints.append({
            "_type": "waypoint",
            "desc": r.place_name,
            "lat": r.place_lat,
            "lon": r.place_lng,
            "rad": r.radius_m,
            "tst": int(r.created_at.timestamp()),
            "rid": r.owntracks_rid,
        })
    return waypoints


async def trigger_reminder_by_rid(
    session: AsyncSession,
    redis_client,
    user_id: str,
    rid: str,
) -> Notification | None:
    """Trigger a reminder by OwnTracks region ID. Returns a Notification if triggered."""
    uid = uuid.UUID(user_id)
    now = datetime.now(timezone.utc)

    result = await session.execute(
        select(LocationReminder).where(
            LocationReminder.user_id == uid,
            LocationReminder.owntracks_rid == rid,
            LocationReminder.status == "active",
        )
    )
    reminder = result.scalar_one_or_none()
    if reminder is None:
        logger.info("reminder_not_found_for_rid", rid=rid, user_id=user_id)
        return None

    # Check cooldown
    if reminder.cooldown_until and now < reminder.cooldown_until:
        logger.info("reminder_in_cooldown", rid=rid)
        return None

    # Mark as triggered
    reminder.status = "triggered"
    reminder.triggered_at = now
    await session.commit()

    # Flag waypoints as needing sync (triggered reminder will be excluded
    # from the active list on next check-in)
    await mark_waypoints_dirty(redis_client, user_id)

    if not reminder.platform or not reminder.platform_channel_id:
        logger.warning("reminder_no_notification_target", reminder_id=str(reminder.id))
        return None

    return Notification(
        platform=reminder.platform,
        platform_channel_id=reminder.platform_channel_id,
        platform_thread_id=reminder.platform_thread_id,
        content=(
            f"You're near **{reminder.place_name}**!\n\n"
            f"Reminder: {reminder.message}"
        ),
        user_id=user_id,
    )


async def handle_owntracks_publish(
    session: AsyncSession,
    redis_client,
    user_id: str,
    payload: dict,
) -> list[dict]:
    """Process an OwnTracks POST and return response commands."""
    msg_type = payload.get("_type")
    response_cmds: list[dict] = []

    if msg_type == "location":
        await upsert_user_location(session, user_id, payload)

        # If waypoints changed since last sync, rebuild the full list from DB
        if await _is_waypoints_dirty(redis_client, user_id):
            waypoints = await _build_waypoint_list(session, user_id)
            response_cmds.append(
                {
                    "_type": "cmd",
                    "action": "setWaypoints",
                    "waypoints": {
                        "_type": "waypoints",
                        "waypoints": waypoints,
                    },
                }
            )
            await _clear_waypoints_dirty(redis_client, user_id)

            # Mark all active reminders as synced
            uid = uuid.UUID(user_id)
            await session.execute(
                update(LocationReminder)
                .where(
                    LocationReminder.user_id == uid,
                    LocationReminder.status == "active",
                )
                .values(synced_to_device=True)
            )
            await session.commit()

    elif msg_type == "transition":
        if payload.get("event") == "enter":
            rid = payload.get("rid")
            if rid:
                notification = await trigger_reminder_by_rid(
                    session, redis_client, user_id, rid
                )
                if notification:
                    # Publish to Redis pub/sub
                    channel = f"notifications:{notification.platform}"
                    await redis_client.publish(
                        channel, notification.model_dump_json()
                    )
                    logger.info(
                        "reminder_triggered",
                        rid=rid,
                        user_id=user_id,
                        platform=notification.platform,
                    )

    elif msg_type == "waypoint":
        logger.info("owntracks_waypoint_received", user_id=user_id, payload=payload)

    return response_cmds
