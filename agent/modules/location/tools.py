"""Location module tool implementations."""

from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.location.geocoding import haversine_m, resolve_place, reverse_geocode
from modules.location.owntracks import mark_waypoints_dirty
from shared.models.location_reminder import LocationReminder
from shared.models.named_place import UserNamedPlace
from shared.models.owntracks_credential import OwnTracksCredential
from shared.models.user_location import UserLocation

logger = structlog.get_logger()


class LocationTools:
    """Tool implementations for the location module."""

    def __init__(
        self,
        session_factory: async_sessionmaker,
        redis_client,
        owntracks_endpoint_url: str,
    ):
        self.session_factory = session_factory
        self.redis_client = redis_client
        self.owntracks_endpoint_url = owntracks_endpoint_url

    async def create_reminder(
        self,
        place: str,
        message: str,
        mode: str = "once",
        trigger_on: str = "enter",
        cooldown_minutes: int | None = None,
        radius_m: int = 30,
        place_lat: float | None = None,
        place_lng: float | None = None,
        platform: str | None = None,
        platform_channel_id: str | None = None,
        platform_thread_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Create a location-based reminder or persistent event."""
        if not user_id:
            return {"error": "user_id is required"}

        if trigger_on not in ("enter", "leave", "both"):
            return {"error": "trigger_on must be 'enter', 'leave', or 'both'"}

        if mode not in ("once", "persistent"):
            return {"error": "mode must be 'once' or 'persistent'"}

        cooldown_seconds = (cooldown_minutes * 60) if cooldown_minutes else 3600

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            # If explicit coordinates provided, skip geocoding
            if place_lat is not None and place_lng is not None:
                place_name = place
                lat, lng = place_lat, place_lng
            else:
                # Get user's last known location for bias
                loc_result = await session.execute(
                    select(UserLocation).where(UserLocation.user_id == uid)
                )
                user_loc = loc_result.scalar_one_or_none()
                near_lat = user_loc.latitude if user_loc else None
                near_lng = user_loc.longitude if user_loc else None

                candidates = await resolve_place(
                    place, user_id, session, near_lat, near_lng
                )

                if not candidates:
                    return {
                        "success": False,
                        "error": f"Could not find a location for '{place}'. Try being more specific or provide coordinates.",
                    }

                if len(candidates) == 1:
                    lat = candidates[0].lat
                    lng = candidates[0].lng
                    place_name = candidates[0].name
                else:
                    # Return candidates for the LLM to present to the user
                    return {
                        "success": False,
                        "ambiguous": True,
                        "candidates": [
                            {
                                "name": c.name,
                                "lat": c.lat,
                                "lng": c.lng,
                                "address": c.address,
                                "distance_m": (
                                    round(c.distance_m) if c.distance_m else None
                                ),
                            }
                            for c in candidates[:5]
                        ],
                        "message": "Multiple locations found. Ask the user which one they mean, then call again with place_lat and place_lng.",
                    }

            # Create the reminder
            rid = str(uuid.uuid4())[:8]
            reminder = LocationReminder(
                user_id=uid,
                message=message,
                place_name=place_name,
                place_lat=lat,
                place_lng=lng,
                radius_m=radius_m,
                trigger_on=trigger_on,
                mode=mode,
                cooldown_seconds=cooldown_seconds,
                platform=platform,
                platform_channel_id=platform_channel_id,
                platform_thread_id=platform_thread_id,
                owntracks_rid=rid,
                status="active",
            )
            session.add(reminder)
            await session.commit()
            await session.refresh(reminder)

            # Flag waypoints as needing sync on next OwnTracks check-in
            await mark_waypoints_dirty(self.redis_client, user_id)

            return {
                "success": True,
                "reminder_id": str(reminder.id),
                "place_name": place_name,
                "lat": lat,
                "lng": lng,
                "radius_m": radius_m,
                "trigger_on": trigger_on,
                "mode": mode,
                "cooldown_minutes": cooldown_seconds // 60,
                "message": message,
                "status": "active",
                "note": "The geofence will be synced to the user's phone on the next OwnTracks check-in.",
            }

    async def list_reminders(
        self,
        status: str = "active",
        user_id: str | None = None,
    ) -> dict:
        """List location reminders for the user."""
        if not user_id:
            return {"error": "user_id is required"}

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            query = select(LocationReminder).where(LocationReminder.user_id == uid)
            if status != "all":
                query = query.where(LocationReminder.status == status)
            query = query.order_by(LocationReminder.created_at.desc())

            result = await session.execute(query)
            reminders = result.scalars().all()

            return {
                "reminders": [
                    {
                        "id": str(r.id),
                        "message": r.message,
                        "place_name": r.place_name,
                        "lat": r.place_lat,
                        "lng": r.place_lng,
                        "radius_m": r.radius_m,
                        "trigger_on": r.trigger_on,
                        "mode": r.mode,
                        "cooldown_minutes": r.cooldown_seconds // 60,
                        "trigger_count": r.trigger_count,
                        "status": r.status,
                        "synced_to_device": r.synced_to_device,
                        "triggered_at": (
                            r.triggered_at.isoformat() if r.triggered_at else None
                        ),
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in reminders
                ],
                "count": len(reminders),
            }

    async def cancel_reminder(
        self,
        reminder_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Cancel/delete an active or paused reminder."""
        return await self.delete_reminder(reminder_id=reminder_id, user_id=user_id)

    async def delete_reminder(
        self,
        reminder_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Permanently delete a reminder/event."""
        if not user_id:
            return {"error": "user_id is required"}

        uid = uuid.UUID(user_id)
        rid = uuid.UUID(reminder_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(LocationReminder).where(
                    LocationReminder.id == rid,
                    LocationReminder.user_id == uid,
                )
            )
            reminder = result.scalar_one_or_none()
            if reminder is None:
                return {"success": False, "error": "Reminder not found"}

            reminder.status = "cancelled"
            await session.commit()

            # Clean up Redis state
            await self.redis_client.delete(f"geofence_inside:{reminder.id}")
            await mark_waypoints_dirty(self.redis_client, user_id)

            return {
                "success": True,
                "reminder_id": str(reminder.id),
                "message": f"Deleted: {reminder.message} (at {reminder.place_name})",
            }

    async def disable_reminder(
        self,
        reminder_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Pause an active reminder so it stops triggering."""
        if not user_id:
            return {"error": "user_id is required"}

        uid = uuid.UUID(user_id)
        rid = uuid.UUID(reminder_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(LocationReminder).where(
                    LocationReminder.id == rid,
                    LocationReminder.user_id == uid,
                )
            )
            reminder = result.scalar_one_or_none()
            if reminder is None:
                return {"success": False, "error": "Reminder not found"}

            if reminder.status != "active":
                return {
                    "success": False,
                    "error": f"Reminder is '{reminder.status}', can only disable active reminders",
                }

            reminder.status = "paused"
            await session.commit()

            # Clean up Redis state and remove waypoint from device
            await self.redis_client.delete(f"geofence_inside:{reminder.id}")
            await mark_waypoints_dirty(self.redis_client, user_id)

            return {
                "success": True,
                "reminder_id": str(reminder.id),
                "message": f"Disabled: {reminder.message} (at {reminder.place_name})",
            }

    async def enable_reminder(
        self,
        reminder_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Re-enable a paused reminder."""
        if not user_id:
            return {"error": "user_id is required"}

        uid = uuid.UUID(user_id)
        rid = uuid.UUID(reminder_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(LocationReminder).where(
                    LocationReminder.id == rid,
                    LocationReminder.user_id == uid,
                )
            )
            reminder = result.scalar_one_or_none()
            if reminder is None:
                return {"success": False, "error": "Reminder not found"}

            if reminder.status != "paused":
                return {
                    "success": False,
                    "error": f"Reminder is '{reminder.status}', can only enable paused reminders",
                }

            reminder.status = "active"
            reminder.cooldown_until = None
            await session.commit()

            # Re-sync waypoint to device
            await mark_waypoints_dirty(self.redis_client, user_id)

            return {
                "success": True,
                "reminder_id": str(reminder.id),
                "message": f"Enabled: {reminder.message} (at {reminder.place_name})",
            }

    async def get_location(
        self,
        user_id: str | None = None,
    ) -> dict:
        """Get the user's last known location."""
        if not user_id:
            return {"error": "user_id is required"}

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(UserLocation).where(UserLocation.user_id == uid)
            )
            loc = result.scalar_one_or_none()
            if loc is None:
                return {
                    "success": False,
                    "error": "No location data found. The user may need to set up OwnTracks first.",
                }

            # Reverse geocode for human-readable address
            address = await reverse_geocode(loc.latitude, loc.longitude)

            age_s = (datetime.now(timezone.utc) - loc.updated_at).total_seconds()

            return {
                "success": True,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "accuracy_m": loc.accuracy_m,
                "address": address,
                "source": loc.source,
                "updated_at": loc.updated_at.isoformat(),
                "age_seconds": round(age_s),
                "stale": age_s > 600,
            }

    async def set_named_place(
        self,
        name: str,
        lat: float | None = None,
        lng: float | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Save a named place for the user."""
        if not user_id:
            return {"error": "user_id is required"}

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            # If no coordinates, use current location
            if lat is None or lng is None:
                loc_result = await session.execute(
                    select(UserLocation).where(UserLocation.user_id == uid)
                )
                user_loc = loc_result.scalar_one_or_none()
                if user_loc is None:
                    return {
                        "success": False,
                        "error": "No current location available. Provide lat/lng or set up OwnTracks first.",
                    }
                lat = user_loc.latitude
                lng = user_loc.longitude

            # Reverse geocode for address
            address = await reverse_geocode(lat, lng)

            # Upsert named place
            result = await session.execute(
                select(UserNamedPlace).where(
                    UserNamedPlace.user_id == uid,
                    UserNamedPlace.name == name.lower().strip(),
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.latitude = lat
                existing.longitude = lng
                existing.address = address
            else:
                place = UserNamedPlace(
                    user_id=uid,
                    name=name.lower().strip(),
                    latitude=lat,
                    longitude=lng,
                    address=address,
                )
                session.add(place)

            await session.commit()

            return {
                "success": True,
                "name": name.lower().strip(),
                "lat": lat,
                "lng": lng,
                "address": address,
                "note": f'Saved "{name}" — future reminders can reference this place by name.',
            }

    async def generate_pairing_credentials(
        self,
        user_id: str | None = None,
    ) -> dict:
        """Generate OwnTracks HTTP credentials for the user."""
        import bcrypt

        if not user_id:
            return {"error": "user_id is required"}

        uid = uuid.UUID(user_id)

        # Generate username and password
        suffix = "".join(
            secrets.choice(string.ascii_lowercase + string.digits) for _ in range(4)
        )
        username = f"agent_{suffix}"
        password = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(12)
        )
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        async with self.session_factory() as session:
            # Check if user already has credentials
            result = await session.execute(
                select(OwnTracksCredential).where(
                    OwnTracksCredential.user_id == uid,
                    OwnTracksCredential.is_active == True,  # noqa: E712
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Deactivate old credentials
                existing.is_active = False
                await session.flush()

            cred = OwnTracksCredential(
                user_id=uid,
                username=username,
                password_hash=password_hash,
            )
            session.add(cred)
            await session.commit()

        endpoint = self.owntracks_endpoint_url

        return {
            "success": True,
            "username": username,
            "password": password,
            "endpoint_url": endpoint,
            "setup_instructions": (
                "Install OwnTracks from the Play Store (Android) or App Store (iOS), "
                "then configure:\n"
                "1. Open Settings → Connection\n"
                f"2. Mode: HTTP\n"
                f"3. URL: {endpoint}\n"
                f"4. Username: {username}\n"
                f"5. Password: {password}\n\n"
                "That's it! OwnTracks will start sharing your location. "
                "You can pause at any time from the OwnTracks app."
            ),
        }
