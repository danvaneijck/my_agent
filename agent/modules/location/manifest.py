"""Location module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="location",
    description="Location-based reminders using OwnTracks. Create geofence reminders triggered by physical proximity, manage named places, and track user location.",
    tools=[
        ToolDefinition(
            name="location.create_reminder",
            description=(
                "Create a reminder that triggers when the user arrives at a location. "
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
            description="List the user's location-based reminders, optionally filtered by status.",
            parameters=[
                ToolParameter(
                    name="status",
                    type="string",
                    description='Filter by status (default "active")',
                    required=False,
                    enum=["active", "triggered", "cancelled", "expired", "all"],
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="location.cancel_reminder",
            description="Cancel an active location reminder by its ID.",
            parameters=[
                ToolParameter(
                    name="reminder_id",
                    type="string",
                    description="UUID of the reminder to cancel",
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
