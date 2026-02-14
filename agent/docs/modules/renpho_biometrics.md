# renpho_biometrics

Body composition and biometric data from Renpho smart scales.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `renpho_biometrics.get_measurements` | List recent biometric measurements | user |
| `renpho_biometrics.get_latest` | Get the single most recent measurement | user |
| `renpho_biometrics.get_trend` | Trend summary over recent measurements | user |

## Tool Details

### `renpho_biometrics.get_measurements`
- **limit** (integer, optional) — default 10
- Returns newest-first: weight, BMI, body fat %, muscle mass, water %, bone mass, BMR, visceral fat, and more

### `renpho_biometrics.get_latest`
- No parameters
- Returns all available metrics: weight, BMI, body fat, muscle, water, bone mass, BMR, visceral fat, subcutaneous fat, protein, body age, lean body mass, fat free weight, heart rate, body shape

### `renpho_biometrics.get_trend`
- **count** (integer, optional) — number of measurements to include (default 30)
- Shows current values, first-to-last changes, and averages for key metrics

## Implementation Notes

- Uses Renpho cloud API for smart scale data
- Credentials configured via environment variables
- No database required — reads directly from Renpho API

## Key Files

- `agent/modules/renpho_biometrics/manifest.py`
- `agent/modules/renpho_biometrics/tools.py`
- `agent/modules/renpho_biometrics/main.py`
