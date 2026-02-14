# myfitnesspal

Nutrition, meal diary, and body measurement data from MyFitnessPal.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `myfitnesspal.get_day` | Food diary for a specific date | user |
| `myfitnesspal.get_measurements` | Body measurements over a date range | user |
| `myfitnesspal.get_report` | Nutrition/fitness report over a date range | user |
| `myfitnesspal.search_food` | Search the food database | user |

## Tool Details

### `myfitnesspal.get_day`
- **date** (string, optional) — YYYY-MM-DD (default: today)
- Returns meals (breakfast, lunch, dinner, snacks) with individual food entries
- Includes nutritional totals: calories, carbs, fat, protein, sodium, sugar
- Includes daily goals and completion status

### `myfitnesspal.get_measurements`
- **measurement** (string, optional) — type to retrieve: `Weight`, `Body Fat`, `Waist`, `Neck`, `Hips` (default: Weight)
- **start_date** (string, optional) — YYYY-MM-DD (default: 30 days ago)
- **end_date** (string, optional) — YYYY-MM-DD (default: today)

### `myfitnesspal.get_report`
- **report_name** (string, optional) — `Net Calories`, `Total Calories`, `Carbs`, `Fat`, `Protein`, `Fiber`, `Sugar` (default: Net Calories)
- **report_category** (string, optional) — `Nutrition` or `Fitness` (default: Nutrition)
- **start_date** (string, optional) — YYYY-MM-DD (default: 7 days ago)
- **end_date** (string, optional) — YYYY-MM-DD (default: today)
- Returns daily values for the requested metric

### `myfitnesspal.search_food`
- **query** (string, required) — e.g. "chicken breast", "banana"
- Returns matching foods with nutritional info and serving sizes

## Implementation Notes

- Uses MyFitnessPal API via `httpx`
- Credentials configured via environment variables
- No database required — reads directly from MFP API
- Listed as a slow module (120s timeout)

## Key Files

- `agent/modules/myfitnesspal/manifest.py`
- `agent/modules/myfitnesspal/tools.py`
- `agent/modules/myfitnesspal/main.py`
