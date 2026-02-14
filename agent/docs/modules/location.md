# location

Location-based reminders using OwnTracks. Geofence events triggered by physical proximity, named places, and location tracking.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `location.create_reminder` | Create a geofence reminder (one-off or persistent) | user |
| `location.list_reminders` | List reminders, optionally filtered by status | user |
| `location.disable_reminder` | Pause an active reminder | user |
| `location.enable_reminder` | Re-enable a paused reminder | user |
| `location.delete_reminder` | Permanently delete a reminder | user |
| `location.get_location` | Get last known location with reverse-geocoded address | user |
| `location.set_named_place` | Save a named place (home, work, gym) | user |
| `location.generate_pairing_credentials` | Generate OwnTracks HTTP credentials for phone setup | user |

## Tool Details

### `location.create_reminder`
- **place** (string, required) — natural language description (e.g. "the supermarket", "home", "123 Main St")
- **message** (string, required) — what to remind about (e.g. "buy toilet paper")
- **mode** (string, optional) — `once` (default, fires once) or `persistent` (recurring with cooldown)
- **trigger_on** (string, optional) — `enter` (default), `leave`, or `both`
- **cooldown_minutes** (integer, optional) — min minutes between triggers for persistent mode (default 60)
- **radius_m** (integer, optional) — trigger radius in meters (default 30)
- **place_lat** / **place_lng** (number, optional) — explicit coordinates, skips geocoding
- If geocoding returns multiple candidates, returns them for the user to pick, then call again with explicit lat/lng

### `location.list_reminders`
- **status** (string, optional) — `active`, `paused`, `triggered`, `cancelled`, `expired`, `all` (default: active)

### `location.disable_reminder`
- **reminder_id** (string, required) — sets status to `paused`

### `location.enable_reminder`
- **reminder_id** (string, required) — resumes a paused reminder

### `location.delete_reminder`
- **reminder_id** (string, required) — permanent deletion, cannot be undone

### `location.get_location`
- No parameters
- Returns last known lat/lng, accuracy, speed, heading, and reverse-geocoded address

### `location.set_named_place`
- **name** (string, required) — e.g. "home", "work", "gym"
- **lat** / **lng** (number, optional) — uses current location if omitted

### `location.generate_pairing_credentials`
- No parameters
- Returns username, password, and OwnTracks HTTP setup instructions

## Implementation Notes

- Geocoding via `resolve_place()` with distance bias from user's current location
- Named places are checked before geocoding — if user says "home" and has a named place, it's used directly
- OwnTracks waypoints are marked dirty when reminders change, synced to device on next connection
- Haversine distance calculation for proximity checks
- Credential generation: random 16-char alphanumeric username and password

## Database

- **LocationReminder** — `id`, `user_id`, `message`, `place_name`, `place_lat/lng`, `radius_m`, `mode`, `trigger_on`, `owntracks_rid`, `status`, `cooldown_until`, `expires_at`
- **UserLocation** — `user_id` (unique), `latitude`, `longitude`, `accuracy_m`, `speed_mps`, `heading`, `source`, `updated_at`
- **UserNamedPlace** — `user_id`, `name`, `latitude`, `longitude`, `address` (unique per user+name)
- **OwnTracksCredential** — `user_id`, `username`, `password_hash`, `device_name`, `is_active`, `last_seen_at`

## Key Files

- `agent/modules/location/manifest.py`
- `agent/modules/location/tools.py`
- `agent/modules/location/main.py`
