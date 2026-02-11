"""Tests for the location module — reminders, triggers, and notifications.

The core invariant tested here: when a location reminder is created via a
conversation, the platform/channel context MUST be stored on the reminder
so that the trigger path can deliver a notification back to the user.

Regression context: a bug where ``create_reminder`` did not persist
``platform``/``platform_channel_id`` caused triggered reminders to silently
skip notification delivery.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.models.location_reminder import LocationReminder
from shared.models.user_location import UserLocation
from shared.schemas.notifications import Notification
from shared.schemas.tools import ToolCall
from tests.conftest import make_execute_side_effect


# ===================================================================
# create_reminder
# ===================================================================


class TestCreateReminder:
    """Tests for LocationTools.create_reminder."""

    @pytest.fixture
    def tools(self, mock_session_factory, mock_redis, mock_db_session):
        from modules.location.tools import LocationTools

        # Mock refresh to populate server-side defaults (created_at)
        # that would normally be set by the DB on commit.
        async def _fake_refresh(obj):
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime.now(timezone.utc)

        mock_db_session.refresh = AsyncMock(side_effect=_fake_refresh)

        return LocationTools(mock_session_factory, mock_redis, "https://example.com/pub")

    @pytest.mark.asyncio
    async def test_stores_platform_context(self, tools, mock_db_session):
        """REGRESSION: create_reminder must persist platform/channel for notification delivery."""
        user_id = str(uuid.uuid4())

        result = await tools.create_reminder(
            place="home",
            message="Goodbye!",
            place_lat=-41.28,
            place_lng=174.77,
            radius_m=50,
            platform="discord",
            platform_channel_id="123456789",
            platform_thread_id="thread_001",
            user_id=user_id,
        )

        assert result["success"] is True

        # The LocationReminder passed to session.add must have platform fields
        added_obj = mock_db_session.add.call_args[0][0]
        assert isinstance(added_obj, LocationReminder)
        assert added_obj.platform == "discord"
        assert added_obj.platform_channel_id == "123456789"
        assert added_obj.platform_thread_id == "thread_001"

    @pytest.mark.asyncio
    async def test_stores_telegram_platform(self, tools, mock_db_session):
        """Platform context works for telegram too."""
        user_id = str(uuid.uuid4())

        result = await tools.create_reminder(
            place="work",
            message="Check in",
            place_lat=-41.29,
            place_lng=174.78,
            platform="telegram",
            platform_channel_id="tg_chat_999",
            user_id=user_id,
        )

        assert result["success"] is True
        added_obj = mock_db_session.add.call_args[0][0]
        assert added_obj.platform == "telegram"
        assert added_obj.platform_channel_id == "tg_chat_999"

    @pytest.mark.asyncio
    async def test_without_platform_creates_reminder(self, tools, mock_db_session):
        """Reminder creation succeeds without platform (just won't be able to notify)."""
        user_id = str(uuid.uuid4())

        result = await tools.create_reminder(
            place="park",
            message="Go for a walk",
            place_lat=-41.30,
            place_lng=174.79,
            user_id=user_id,
        )

        assert result["success"] is True
        added_obj = mock_db_session.add.call_args[0][0]
        assert added_obj.platform is None
        assert added_obj.platform_channel_id is None

    @pytest.mark.asyncio
    async def test_returns_reminder_metadata(self, tools, mock_db_session):
        """create_reminder returns useful metadata in the response."""
        user_id = str(uuid.uuid4())

        result = await tools.create_reminder(
            place="gym",
            message="Leg day",
            place_lat=-41.31,
            place_lng=174.80,
            radius_m=200,
            platform="discord",
            platform_channel_id="ch1",
            user_id=user_id,
        )

        assert result["success"] is True
        assert result["message"] == "Leg day"
        assert result["place_name"] == "gym"
        assert result["radius_m"] == 200
        assert result["lat"] == -41.31
        assert result["lng"] == 174.80

    @pytest.mark.asyncio
    async def test_requires_user_id(self, tools, mock_db_session):
        """create_reminder fails gracefully without user_id."""
        result = await tools.create_reminder(
            place="home",
            message="test",
            place_lat=-41.28,
            place_lng=174.77,
        )

        assert "error" in result


# ===================================================================
# trigger_reminder_by_rid
# ===================================================================


class TestTriggerReminderByRid:
    """Tests for the OwnTracks reminder trigger function."""

    @pytest.mark.asyncio
    async def test_returns_notification_with_platform(
        self, mock_db_session, mock_redis, make_location_reminder
    ):
        """When reminder has platform fields, triggering returns a Notification."""
        from modules.location.owntracks import trigger_reminder_by_rid

        user_id = str(uuid.uuid4())
        reminder = make_location_reminder(
            user_id=uuid.UUID(user_id),
            message="Goodbye!",
            place_name="Home",
            platform="discord",
            platform_channel_id="123456",
            owntracks_rid="abc123",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        notification = await trigger_reminder_by_rid(
            mock_db_session, mock_redis, user_id, "abc123"
        )

        assert notification is not None
        assert isinstance(notification, Notification)
        assert notification.platform == "discord"
        assert notification.platform_channel_id == "123456"
        assert "Goodbye!" in notification.content
        assert "Home" in notification.content
        assert reminder.status == "triggered"
        assert reminder.triggered_at is not None

    @pytest.mark.asyncio
    async def test_returns_none_without_platform(
        self, mock_db_session, mock_redis, make_location_reminder
    ):
        """When reminder has NO platform, triggering returns None — the original bug."""
        from modules.location.owntracks import trigger_reminder_by_rid

        user_id = str(uuid.uuid4())
        reminder = make_location_reminder(
            user_id=uuid.UUID(user_id),
            platform=None,
            platform_channel_id=None,
            owntracks_rid="abc123",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        notification = await trigger_reminder_by_rid(
            mock_db_session, mock_redis, user_id, "abc123"
        )

        # No notification, but reminder is still marked triggered
        assert notification is None
        assert reminder.status == "triggered"

    @pytest.mark.asyncio
    async def test_not_found_returns_none(self, mock_db_session, mock_redis):
        """Unknown rid returns None without error."""
        from modules.location.owntracks import trigger_reminder_by_rid

        notification = await trigger_reminder_by_rid(
            mock_db_session, mock_redis, str(uuid.uuid4()), "nonexistent"
        )

        assert notification is None

    @pytest.mark.asyncio
    async def test_cooldown_prevents_trigger(
        self, mock_db_session, mock_redis, make_location_reminder
    ):
        """Reminder in cooldown period should not trigger."""
        from modules.location.owntracks import trigger_reminder_by_rid

        user_id = str(uuid.uuid4())
        reminder = make_location_reminder(
            user_id=uuid.UUID(user_id),
            owntracks_rid="abc123",
        )
        reminder.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        notification = await trigger_reminder_by_rid(
            mock_db_session, mock_redis, user_id, "abc123"
        )

        assert notification is None
        assert reminder.status == "active"  # unchanged


# ===================================================================
# handle_owntracks_publish (transition events)
# ===================================================================


class TestHandleOwnTracksPublish:
    """Tests for the OwnTracks payload handler."""

    @pytest.mark.asyncio
    async def test_enter_transition_triggers_and_publishes(
        self, mock_db_session, mock_redis, make_location_reminder
    ):
        """An 'enter' transition should trigger the reminder and publish notification."""
        from modules.location.owntracks import handle_owntracks_publish

        user_id = str(uuid.uuid4())
        reminder = make_location_reminder(
            user_id=uuid.UUID(user_id),
            message="You arrived!",
            platform="discord",
            platform_channel_id="ch_123",
            owntracks_rid="rid_1",
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = reminder
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        payload = {
            "_type": "transition",
            "event": "enter",
            "rid": "rid_1",
            "lat": -41.28,
            "lon": 174.77,
            "tst": 1700000000,
        }

        await handle_owntracks_publish(mock_db_session, mock_redis, user_id, payload)

        # Notification should be published to Redis
        mock_redis.publish.assert_called_once()
        channel, data = mock_redis.publish.call_args[0]
        assert channel == "notifications:discord"

        notification = Notification.model_validate_json(data)
        assert notification.platform_channel_id == "ch_123"
        assert "You arrived!" in notification.content

    @pytest.mark.asyncio
    async def test_leave_transition_does_not_trigger(
        self, mock_db_session, mock_redis
    ):
        """A 'leave' transition should not trigger any reminder."""
        from modules.location.owntracks import handle_owntracks_publish

        payload = {
            "_type": "transition",
            "event": "leave",
            "rid": "rid_1",
            "lat": -41.28,
            "lon": 174.77,
            "tst": 1700000000,
        }

        await handle_owntracks_publish(
            mock_db_session, mock_redis, str(uuid.uuid4()), payload
        )

        mock_redis.publish.assert_not_called()


# ===================================================================
# Geofence worker (_check_all_reminders)
# ===================================================================


class TestGeofenceWorker:
    """Tests for the background geofence proximity checker."""

    @pytest.mark.asyncio
    async def test_triggers_when_within_radius(
        self, mock_session_factory, mock_db_session, mock_redis,
        make_location_reminder, make_user_location,
    ):
        """Worker should trigger and publish notification when user is within radius."""
        from modules.location.worker import _check_all_reminders

        user_id = uuid.uuid4()
        reminder = make_location_reminder(
            user_id=user_id,
            message="Buy milk",
            place_name="Supermarket",
            place_lat=-41.2800,
            place_lng=174.7700,
            radius_m=150,
            platform="telegram",
            platform_channel_id="tg_999",
        )
        location = make_user_location(
            user_id=user_id,
            latitude=-41.2801,   # ~11m away
            longitude=174.7701,
        )

        # First execute: select active reminders
        reminders_result = MagicMock()
        reminders_result.scalars.return_value.all.return_value = [reminder]
        # Second execute: select user location
        location_result = MagicMock()
        location_result.scalar_one_or_none.return_value = location

        mock_db_session.execute = AsyncMock(
            side_effect=make_execute_side_effect(reminders_result, location_result)
        )

        await _check_all_reminders(mock_session_factory, mock_redis)

        # Notification published
        mock_redis.publish.assert_called_once()
        channel, data = mock_redis.publish.call_args[0]
        assert channel == "notifications:telegram"

        notification = Notification.model_validate_json(data)
        assert notification.platform_channel_id == "tg_999"
        assert "Buy milk" in notification.content
        assert reminder.status == "triggered"

    @pytest.mark.asyncio
    async def test_no_notification_without_platform(
        self, mock_session_factory, mock_db_session, mock_redis,
        make_location_reminder, make_user_location,
    ):
        """Worker should NOT publish if reminder has no platform context."""
        from modules.location.worker import _check_all_reminders

        user_id = uuid.uuid4()
        reminder = make_location_reminder(
            user_id=user_id,
            place_lat=-41.2800,
            place_lng=174.7700,
            radius_m=150,
            platform=None,
            platform_channel_id=None,
        )
        location = make_user_location(
            user_id=user_id,
            latitude=-41.2801,
            longitude=174.7701,
        )

        reminders_result = MagicMock()
        reminders_result.scalars.return_value.all.return_value = [reminder]
        location_result = MagicMock()
        location_result.scalar_one_or_none.return_value = location

        mock_db_session.execute = AsyncMock(
            side_effect=make_execute_side_effect(reminders_result, location_result)
        )

        await _check_all_reminders(mock_session_factory, mock_redis)

        # Reminder triggered but no notification
        assert reminder.status == "triggered"
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_does_not_trigger_outside_radius(
        self, mock_session_factory, mock_db_session, mock_redis,
        make_location_reminder, make_user_location,
    ):
        """Worker should not trigger when user is outside the geofence radius."""
        from modules.location.worker import _check_all_reminders

        user_id = uuid.uuid4()
        reminder = make_location_reminder(
            user_id=user_id,
            place_lat=-41.2800,
            place_lng=174.7700,
            radius_m=50,
            platform="discord",
            platform_channel_id="ch1",
        )
        location = make_user_location(
            user_id=user_id,
            latitude=-41.2850,   # ~550m away
            longitude=174.7750,
        )

        reminders_result = MagicMock()
        reminders_result.scalars.return_value.all.return_value = [reminder]
        location_result = MagicMock()
        location_result.scalar_one_or_none.return_value = location

        mock_db_session.execute = AsyncMock(
            side_effect=make_execute_side_effect(reminders_result, location_result)
        )

        await _check_all_reminders(mock_session_factory, mock_redis)

        assert reminder.status == "active"
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_stale_location(
        self, mock_session_factory, mock_db_session, mock_redis,
        make_location_reminder, make_user_location,
    ):
        """Worker should skip users whose location is older than STALE_THRESHOLD."""
        from modules.location.worker import _check_all_reminders

        user_id = uuid.uuid4()
        reminder = make_location_reminder(
            user_id=user_id,
            place_lat=-41.2800,
            place_lng=174.7700,
            radius_m=500,
            platform="discord",
            platform_channel_id="ch1",
        )
        location = make_user_location(
            user_id=user_id,
            latitude=-41.2801,
            longitude=174.7701,
            updated_at=datetime.now(timezone.utc) - timedelta(minutes=15),  # stale
        )

        reminders_result = MagicMock()
        reminders_result.scalars.return_value.all.return_value = [reminder]
        location_result = MagicMock()
        location_result.scalar_one_or_none.return_value = location

        mock_db_session.execute = AsyncMock(
            side_effect=make_execute_side_effect(reminders_result, location_result)
        )

        await _check_all_reminders(mock_session_factory, mock_redis)

        assert reminder.status == "active"
        mock_redis.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_cooldown(
        self, mock_session_factory, mock_db_session, mock_redis,
        make_location_reminder, make_user_location,
    ):
        """Worker should skip reminders in cooldown period."""
        from modules.location.worker import _check_all_reminders

        user_id = uuid.uuid4()
        reminder = make_location_reminder(
            user_id=user_id,
            place_lat=-41.2800,
            place_lng=174.7700,
            radius_m=500,
            platform="discord",
            platform_channel_id="ch1",
        )
        reminder.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=1)

        location = make_user_location(
            user_id=user_id,
            latitude=-41.2801,
            longitude=174.7701,
        )

        reminders_result = MagicMock()
        reminders_result.scalars.return_value.all.return_value = [reminder]
        location_result = MagicMock()
        location_result.scalar_one_or_none.return_value = location

        mock_db_session.execute = AsyncMock(
            side_effect=make_execute_side_effect(reminders_result, location_result)
        )

        await _check_all_reminders(mock_session_factory, mock_redis)

        assert reminder.status == "active"
        mock_redis.publish.assert_not_called()


# ===================================================================
# Execute endpoint — platform context arg stripping
# ===================================================================


class TestExecuteEndpointArgStripping:
    """Tests that the execute endpoint strips injected platform context
    from tools that don't accept it.

    REGRESSION: the orchestrator injects platform/channel/thread into ALL
    location.* tool calls, but only create_reminder accepts them.
    Other tools (list_reminders, cancel_reminder, etc.) crashed with
    'unexpected keyword argument'.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,required_args", [
        ("location.list_reminders", {}),
        ("location.cancel_reminder", {"reminder_id": str(uuid.uuid4())}),
        ("location.get_location", {}),
        ("location.set_named_place", {"name": "home"}),
    ])
    async def test_tools_survive_injected_platform_args(
        self, tool_name, required_args
    ):
        """Non-create_reminder tools must not crash when platform context is injected."""
        from modules.location.main import execute

        call = ToolCall(
            tool_name=tool_name,
            arguments={
                **required_args,
                "platform": "discord",
                "platform_channel_id": "123456",
                "platform_thread_id": None,
            },
            user_id=str(uuid.uuid4()),
        )

        result = await execute(call)

        # The tool may fail for other reasons (no DB, etc.) but it should
        # NOT fail with "unexpected keyword argument"
        assert "unexpected keyword argument" not in (result.error or "")
