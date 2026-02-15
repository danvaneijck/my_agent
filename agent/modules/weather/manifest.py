"""Weather module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="weather",
    description="Get current weather, forecasts, hourly data, and severe weather alerts for any location worldwide using Open-Meteo.",
    tools=[
        ToolDefinition(
            name="weather.weather_current",
            description=(
                "Get current weather conditions for a location. "
                "Returns temperature, humidity, wind, pressure, cloud cover, and UV index. "
                "Example: 'What's the weather in Tokyo?'"
            ),
            parameters=[
                ToolParameter(
                    name="location",
                    type="string",
                    description="City name or place (e.g. 'London', 'New York', 'Tokyo')",
                ),
                ToolParameter(
                    name="units",
                    type="string",
                    description="Unit system: 'metric' (Celsius, km/h) or 'imperial' (Fahrenheit, mph). Default: metric",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="weather.weather_forecast",
            description=(
                "Get a daily weather forecast for a location (up to 16 days). "
                "Returns high/low temperatures, precipitation probability, wind, and UV index per day. "
                "Example: 'What's the forecast for Paris this week?'"
            ),
            parameters=[
                ToolParameter(
                    name="location",
                    type="string",
                    description="City name or place (e.g. 'London', 'New York', 'Tokyo')",
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="Number of forecast days (1-16). Default: 7",
                    required=False,
                ),
                ToolParameter(
                    name="units",
                    type="string",
                    description="Unit system: 'metric' or 'imperial'. Default: metric",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="weather.weather_hourly",
            description=(
                "Get hourly weather forecast for a location (up to 168 hours / 7 days). "
                "Returns temperature, humidity, wind, precipitation, visibility, and UV per hour. "
                "Example: 'Give me the hourly forecast for Berlin for the next 12 hours.'"
            ),
            parameters=[
                ToolParameter(
                    name="location",
                    type="string",
                    description="City name or place (e.g. 'London', 'New York', 'Tokyo')",
                ),
                ToolParameter(
                    name="hours",
                    type="integer",
                    description="Number of hours to forecast (1-168). Default: 24",
                    required=False,
                ),
                ToolParameter(
                    name="units",
                    type="string",
                    description="Unit system: 'metric' or 'imperial'. Default: metric",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="weather.weather_alerts",
            description=(
                "Check for severe weather conditions and alerts at a location. "
                "Analyzes current and forecast data for thunderstorms, high winds, "
                "extreme temperatures, heavy precipitation, low visibility, and high UV. "
                "Example: 'Are there any weather alerts for Miami?'"
            ),
            parameters=[
                ToolParameter(
                    name="location",
                    type="string",
                    description="City name or place (e.g. 'London', 'New York', 'Tokyo')",
                ),
            ],
            required_permission="guest",
        ),
    ],
)
