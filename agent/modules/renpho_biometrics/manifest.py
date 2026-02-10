"""Renpho biometrics module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="renpho_biometrics",
    description="Fetch body composition and biometric data from Renpho smart scales.",
    tools=[
        ToolDefinition(
            name="renpho_biometrics.get_measurements",
            description=(
                "Fetch biometric measurements from Renpho smart scales. "
                "Returns body composition data including weight, BMI, body fat %, "
                "muscle mass, water %, bone mass, BMR, visceral fat, and more. "
                "Results are sorted newest-first."
            ),
            parameters=[
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of measurements to return (default 10)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="renpho_biometrics.get_latest",
            description=(
                "Get the single most recent biometric measurement from the Renpho scale. "
                "Returns all available metrics: weight, BMI, body fat, muscle, water, "
                "bone mass, BMR, visceral fat, subcutaneous fat, protein, body age, "
                "lean body mass, fat free weight, heart rate, and body shape."
            ),
            parameters=[],
            required_permission="user",
        ),
        ToolDefinition(
            name="renpho_biometrics.get_trend",
            description=(
                "Get a trend summary of biometric data over a specified number of "
                "recent measurements. Shows current values, changes from first to last, "
                "and averages for key metrics."
            ),
            parameters=[
                ToolParameter(
                    name="count",
                    type="integer",
                    description="Number of recent measurements to include in trend analysis (default 30)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
    ],
)
