"""Location module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="location",
    description="Location-based reminders using OwnTracks. Create geofence reminders triggered by physical proximity, manage named places, and track user location.",
    tools=[
        ToolDefinition(
            name="location.create_reminder",
            description=(
                "Create a location event that triggers when the user enters or leaves a location. "
                "Use mode='persistent' for recurring events (e.g. always remind when arriving at work) "
                "or mode='once' for one-off reminders. "
                "Resolves place names to coordinates via geocoding. If multiple candidates "
                "are found, returns them so you can ask the user to pick one, then call "
                "again with explicit lat/lng."
            ),
            parameters=[
                ToolParameter(
                    name="place",
                    type="string",
                    description='Natural language place description, e.g. "the supermarket", "home", "123 Main St"',
                ),
                ToolParameter(
                    name="message",
                    type="string",
                    description='What to remind the user about, e.g. "buy toilet paper"',
                ),
                ToolParameter(
                    name="mode",
                    type="string",
                    description='"once" (default) fires once then completes, "persistent" fires every time and stays active',
                    required=False,
                    enum=["once", "persistent"],
                ),
                ToolParameter(
                    name="trigger_on",
                    type="string",
                    description='When to trigger: "enter" (arriving), "leave" (departing), or "both" (default "enter")',
                    required=False,
                    enum=["enter", "leave", "both"],
                ),
                ToolParameter(
                    name="cooldown_minutes",
                    type="integer",
                    description="For persistent events: minimum minutes between triggers (default 60). Ignored for one-off reminders.",
                    required=False,
                ),
                ToolParameter(
                    name="radius_m",
                    type="integer",
                    description="Trigger radius in meters (default 30)",
                    required=False,
                ),
                ToolParameter(
                    name="place_lat",
                    type="number",
                    description="Explicit latitude — skips geocoding if provided along with place_lng",
                    required=False,
                ),
                ToolParameter(
                    name="place_lng",
                    type="number",
                    description="Explicit longitude — skips geocoding if provided along with place_lat",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.list_reminders",
            description="List the user's location events/reminders, optionally filtered by status.",
            parameters=[
                ToolParameter(
                    name="status",
                    type="string",
                    description='Filter by status (default "active")',
                    required=False,
                    enum=["active", "paused", "triggered", "cancelled", "expired", "all"],
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.disable_reminder",
            description="Pause/cancel an active location event so it stops triggering. The reminder stays in the database and can be re-enabled later with enable_reminder.",
            parameters=[
                ToolParameter(
                    name="reminder_id",
                    type="string",
                    description="UUID of the reminder to disable",
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.enable_reminder",
            description="Re-enable a paused location event so it starts triggering again.",
            parameters=[
                ToolParameter(
                    name="reminder_id",
                    type="string",
                    description="UUID of the reminder to enable",
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.delete_reminder",
            description="Permanently delete a location event/reminder from the database (any status). This cannot be undone — use disable_reminder to pause instead.",
            parameters=[
                ToolParameter(
                    name="reminder_id",
                    type="string",
                    description="UUID of the reminder to delete",
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.get_location",
            description="Get the user's last known location and reverse-geocoded address.",
            parameters=[],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.set_named_place",
            description=(
                'Save a named place for the user (e.g. "home", "work", "gym") so future '
                "reminders can reference it without geocoding. If lat/lng are omitted, "
                "uses the user's current location."
            ),
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description='Name for the place, e.g. "home", "work", "gym"',
                ),
                ToolParameter(
                    name="lat",
                    type="number",
                    description="Latitude (uses current location if omitted)",
                    required=False,
                ),
                ToolParameter(
                    name="lng",
                    type="number",
                    description="Longitude (uses current location if omitted)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.generate_pairing_credentials",
            description=(
                "Generate OwnTracks HTTP credentials for the user to set up location "
                "tracking on their phone. Returns a username, password, and setup instructions."
            ),
            parameters=[],
            required_permission="user",
        ),
    ],
)
