"""OwnTracks protocol handling — parse incoming payloads and build responses."""

from __future__ import annotations

import json
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


async def get_pending_waypoints(redis_client, user_id: str) -> list[dict]:
    """Retrieve pending waypoint commands from Redis for a user."""
    key = f"owntracks_pending_waypoints:{user_id}"
    raw = await redis_client.get(key)
    if raw:
        return json.loads(raw)
    return []


async def clear_pending_waypoints(redis_client, user_id: str) -> None:
    """Clear pending waypoints after they've been delivered."""
    key = f"owntracks_pending_waypoints:{user_id}"
    await redis_client.delete(key)


async def queue_waypoint(
    redis_client,
    user_id: str,
    reminder: LocationReminder,
) -> None:
    """Queue a setWaypoints command for the next OwnTracks check-in."""
    key = f"owntracks_pending_waypoints:{user_id}"
    waypoint = {
        "_type": "waypoint",
        "desc": reminder.place_name,
        "lat": reminder.place_lat,
        "lon": reminder.place_lng,
        "rad": reminder.radius_m,
        "tst": int(reminder.created_at.timestamp()),
        "rid": reminder.owntracks_rid,
    }

    existing = await get_pending_waypoints(redis_client, user_id)
    existing.append(waypoint)
    await redis_client.set(key, json.dumps(existing))


async def queue_waypoint_deletion(
    redis_client,
    user_id: str,
    reminder: LocationReminder,
) -> None:
    """Queue a waypoint deletion by setting invalid coordinates."""
    key = f"owntracks_pending_waypoints:{user_id}"
    waypoint = {
        "_type": "waypoint",
        "desc": reminder.place_name,
        "lat": -1000000,
        "lon": -1000000,
        "rad": 0,
        "tst": int(reminder.created_at.timestamp()),
        "rid": reminder.owntracks_rid,
    }

    existing = await get_pending_waypoints(redis_client, user_id)
    existing.append(waypoint)
    await redis_client.set(key, json.dumps(existing))


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

    # Queue waypoint deletion from device
    await queue_waypoint_deletion(redis_client, user_id, reminder)

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

        # Check if we have new waypoints to push
        pending = await get_pending_waypoints(redis_client, user_id)
        if pending:
            response_cmds.append(
                {
                    "_type": "cmd",
                    "action": "setWaypoints",
                    "waypoints": {
                        "_type": "waypoints",
                        "waypoints": pending,
                    },
                }
            )
            await clear_pending_waypoints(redis_client, user_id)

            # Mark reminders as synced
            for wp in pending:
                rid = wp.get("rid")
                if rid and wp.get("lat", 0) > -999999:
                    await session.execute(
                        update(LocationReminder)
                        .where(LocationReminder.owntracks_rid == rid)
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
