# Weather Module

Weather data retrieval module using the [Open-Meteo API](https://open-meteo.com/) (free, no API key required).

## Tools

| Tool | Description | Permission |
|---|---|---|
| `weather.weather_current` | Current weather conditions | guest |
| `weather.weather_forecast` | Daily forecast (up to 16 days) | guest |
| `weather.weather_hourly` | Hourly forecast (up to 168 hours) | guest |
| `weather.weather_alerts` | Severe weather condition analysis | guest |

## Architecture

```
weather module
├── main.py          FastAPI app (/manifest, /execute, /health)
├── manifest.py      Tool definitions
├── tools.py         Tool implementations (caching + delegation)
├── client.py        Open-Meteo API client
├── geocoding.py     Location → coordinates (Open-Meteo Geocoding API)
├── cache.py         Redis caching with graceful fallback
├── models.py        Pydantic request models
└── tests/           Unit + integration tests (50 tests, 95% coverage)
```

## Quick Start (Standalone)

```bash
cd agent/modules/weather
docker compose up --build -d
```

The service will be available at `http://localhost:8001`.

## Quick Start (Full Stack)

```bash
# From repo root
make build-module M=weather
make up
make refresh-tools
```

## Testing

### Unit Tests

```bash
cd agent
PYTHONPATH="$(pwd):$(pwd)/shared" python3 -m pytest modules/weather/tests/ -v
```

With coverage:

```bash
PYTHONPATH="$(pwd):$(pwd)/shared" python3 -m pytest modules/weather/tests/ --cov=modules.weather --cov-report=term-missing
```

### End-to-End Tests

Start the service, then run the E2E script:

```bash
cd agent/modules/weather
docker compose up --build -d
python3 test_e2e.py
docker compose down
```

Or against a custom URL:

```bash
python3 test_e2e.py http://localhost:8001
```

## Example API Calls

### Health Check

```bash
curl http://localhost:8001/health
```

```json
{"status": "ok"}
```

### Get Manifest

```bash
curl http://localhost:8001/manifest
```

### Current Weather

```bash
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "weather.weather_current",
    "arguments": {"location": "London", "units": "metric"}
  }'
```

```json
{
  "tool_name": "weather.weather_current",
  "success": true,
  "result": {
    "location": "London, England, United Kingdom",
    "latitude": 51.5074,
    "longitude": -0.1278,
    "temperature": 8.5,
    "temperature_unit": "°C",
    "feels_like": 5.3,
    "humidity": 72,
    "description": "Overcast",
    "wind_speed": 15.2,
    "wind_unit": "km/h",
    "wind_direction": 230,
    "wind_gusts": 28.0,
    "pressure_msl": 1013.2,
    "cloud_cover": 85,
    "uv_index": 1.5,
    "time": "2026-02-15T12:00"
  }
}
```

### 7-Day Forecast

```bash
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "weather.weather_forecast",
    "arguments": {"location": "Tokyo", "days": 3}
  }'
```

```json
{
  "tool_name": "weather.weather_forecast",
  "success": true,
  "result": {
    "location": "Tokyo, Tokyo, Japan",
    "days": 3,
    "forecast": [
      {
        "date": "2026-02-15",
        "description": "Partly cloudy",
        "temp_max": 12.5,
        "temp_min": 3.8,
        "temperature_unit": "°C",
        "precipitation": 0.0,
        "precipitation_probability": 5,
        "wind_speed_max": 18.0,
        "uv_index_max": 4.0,
        "sunrise": "2026-02-15T06:28",
        "sunset": "2026-02-15T17:22"
      }
    ]
  }
}
```

### Hourly Forecast

```bash
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "weather.weather_hourly",
    "arguments": {"location": "Berlin", "hours": 6}
  }'
```

### Weather Alerts

```bash
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "weather.weather_alerts",
    "arguments": {"location": "Miami"}
  }'
```

```json
{
  "tool_name": "weather.weather_alerts",
  "success": true,
  "result": {
    "location": "Miami, Florida, United States",
    "alert_count": 1,
    "alerts": [
      {
        "type": "uv",
        "severity": "advisory",
        "message": "Very high UV index on 2026-02-15: 9.5"
      }
    ]
  }
}
```

### Error Handling

```bash
curl -X POST http://localhost:8001/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "weather.weather_current",
    "arguments": {"location": "xyzzy_nonexistent_99999"}
  }'
```

```json
{
  "tool_name": "weather.weather_current",
  "success": false,
  "result": null,
  "error": "Location not found: 'xyzzy_nonexistent_99999'"
}
```

## Configuration

The module reads configuration from the shared `Settings` class (via `.env`):

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379` | Redis connection for caching |
| `WEATHER_PORT` | `8001` | External port mapping (docker-compose) |

No API keys are required — Open-Meteo is a free and open-source weather API.

## Caching

Weather data is cached in Redis with the following TTLs:

| Data Type | TTL | Cache Key Pattern |
|---|---|---|
| Current weather | 10 min | `weather:{location}:current` |
| Daily forecast | 1 hour | `weather:{location}:forecast` |
| Hourly forecast | 30 min | `weather:{location}:hourly` |
| Alerts | 10 min | `weather:{location}:alerts` |
| Geocoding | 24 hours | `weather:{location}:geocode` |

If Redis is unavailable, the module continues to work without caching.
