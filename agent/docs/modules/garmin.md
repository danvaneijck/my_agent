# garmin

Fetch health, fitness, and activity data from Garmin Connect.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `garmin.get_daily_summary` | Steps, calories, distance, floors, active minutes, HR zones | user |
| `garmin.get_heart_rate` | Resting HR and HR zone summaries | user |
| `garmin.get_sleep` | Sleep duration, stages (deep/light/REM), sleep score | user |
| `garmin.get_body_composition` | Weight, BMI, body fat, muscle, water, bone over date range | user |
| `garmin.get_activities` | Recent workouts with type, duration, distance, calories, avg HR | user |
| `garmin.get_stress` | Daily stress level and duration breakdowns | user |
| `garmin.get_steps` | Daily step counts over a date range | user |

## Tool Details

### `garmin.get_daily_summary`
- **date** (string, optional) — YYYY-MM-DD (default: today)

### `garmin.get_heart_rate`
- **date** (string, optional) — YYYY-MM-DD (default: today)

### `garmin.get_sleep`
- **date** (string, optional) — YYYY-MM-DD (default: today, returns previous night)

### `garmin.get_body_composition`
- **start_date** (string, optional) — YYYY-MM-DD (default: 30 days ago)
- **end_date** (string, optional) — YYYY-MM-DD (default: today)

### `garmin.get_activities`
- **limit** (integer, optional) — default 10
- **activity_type** (string, optional) — e.g. `running`, `cycling`, `walking`

### `garmin.get_stress`
- **date** (string, optional) — YYYY-MM-DD (default: today)

### `garmin.get_steps`
- **start_date** (string, optional) — YYYY-MM-DD (default: 7 days ago)
- **end_date** (string, optional) — YYYY-MM-DD (default: today)

## Implementation Notes

- Uses `garminconnect` Python library
- Token caching: saves tokens to `~/.garmin_tokens` after login to avoid re-authentication
- Auth retry: on `GarminConnectAuthenticationError`, resets the client and retries once
- Time formatting: `_seconds_to_hm()` helper converts seconds to "Xh Ym" format
- Safe nested dict access: `_safe_get(data, *keys)` prevents KeyErrors on missing data
- Unit conversions: meters to km, milliseconds to minutes
- Credentials configured via environment variables

## Key Files

- `agent/modules/garmin/manifest.py`
- `agent/modules/garmin/tools.py`
- `agent/modules/garmin/main.py`
