"""Garmin Connect module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="garmin",
    description="Fetch health, fitness, and activity data from Garmin Connect.",
    tools=[
        ToolDefinition(
            name="garmin.get_daily_summary",
            description=(
                "Get a daily activity summary from Garmin Connect including total steps, "
                "calories burned, distance walked/run, floors climbed, active minutes, "
                "and heart rate zones. Defaults to today."
            ),
            parameters=[
                ToolParameter(
                    name="date",
                    type="string",
                    description="Date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="garmin.get_heart_rate",
            description=(
                "Get heart rate data for a given day including resting heart rate "
                "and heart rate zone summaries. Defaults to today."
            ),
            parameters=[
                ToolParameter(
                    name="date",
                    type="string",
                    description="Date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="garmin.get_sleep",
            description=(
                "Get sleep data for a given night including total sleep duration, "
                "deep/light/REM sleep stages, sleep score, and sleep start/end times. "
                "Defaults to today (returns previous night's sleep)."
            ),
            parameters=[
                ToolParameter(
                    name="date",
                    type="string",
                    description="Date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="garmin.get_body_composition",
            description=(
                "Get body composition and weight data from Garmin over a date range. "
                "Returns weight, BMI, body fat %, muscle mass, bone mass, and body water. "
                "Defaults to the last 30 days."
            ),
            parameters=[
                ToolParameter(
                    name="start_date",
                    type="string",
                    description="Start date in YYYY-MM-DD format (default: 30 days ago)",
                    required=False,
                ),
                ToolParameter(
                    name="end_date",
                    type="string",
                    description="End date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="garmin.get_activities",
            description=(
                "Get recent activities/workouts from Garmin Connect. Returns activity name, "
                "type, duration, distance, calories, average heart rate, and more."
            ),
            parameters=[
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of activities to return (default 10)",
                    required=False,
                ),
                ToolParameter(
                    name="activity_type",
                    type="string",
                    description="Filter by activity type, e.g. 'running', 'cycling', 'walking'",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="garmin.get_stress",
            description=(
                "Get stress level data for a given day from Garmin. "
                "Includes overall stress level, rest/low/medium/high stress durations. "
                "Defaults to today."
            ),
            parameters=[
                ToolParameter(
                    name="date",
                    type="string",
                    description="Date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="garmin.get_steps",
            description=(
                "Get daily step counts over a date range from Garmin. "
                "Defaults to the last 7 days."
            ),
            parameters=[
                ToolParameter(
                    name="start_date",
                    type="string",
                    description="Start date in YYYY-MM-DD format (default: 7 days ago)",
                    required=False,
                ),
                ToolParameter(
                    name="end_date",
                    type="string",
                    description="End date in YYYY-MM-DD format (default: today)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
    ],
)
