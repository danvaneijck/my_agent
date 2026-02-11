# Design: Location-Based Reminders

## Overview

Enable users to create reminders triggered by physical proximity to a location.

**Example interaction:**
> "When I get to the supermarket, remind me to buy toilet paper"

The system resolves "the supermarket" to geographic coordinates, monitors the user's location via the [OwnTracks](https://owntracks.org/) mobile app, and sends a proactive notification when the user arrives.

---

## High-Level Architecture

```
Mobile Phone                            Agent System
┌──────────────────────┐               ┌──────────────────────────────────┐
│  OwnTracks App       │  HTTPS POST   │  Location Module (FastAPI)       │
│  (Android / iOS)     │ ────────────► │                                  │
│                      │   POST /pub   │  ┌────────────────────────────┐  │
│  - Location updates  │               │  │ OwnTracks Endpoint         │  │
│    (_type: location) │               │  │ (receives location &       │  │
│  - Geofence events   │  ◄──────────  │  │  transition events)        │  │
│    (_type: transition)│  HTTP 200    │  └─────────────┬──────────────┘  │
│  - Native geofencing │  + setWay-   │                │                  │
│    (OS-level)        │    points     │                ▼                  │
│                      │   commands    │  ┌────────────────────────────┐  │
│  HTTP Basic Auth     │               │  │ Geofence Worker            │  │
└──────────────────────┘               │  │ (background loop, fallback │  │
                                       │  │  server-side check)        │  │
                                       │  └─────────────┬──────────────┘  │
                                       │                │                  │
                                       │                ▼                  │
                                       │  Redis pub/sub                    │
                                       │  notifications:{platform}         │
                                       └───────────────┬──────────────────┘
                                                       │
                                                       ▼
                                       ┌──────────────────────────────────┐
                                       │  Bots (Discord / Telegram / Slack)│
                                       │  "You're near the supermarket!   │
                                       │   Don't forget: toilet paper"    │
                                       └──────────────────────────────────┘
```

---

## Why OwnTracks (not a custom app)

[OwnTracks](https://owntracks.org/) is a free, open-source, well-maintained location tracking app for Android and iOS. It already does everything we need:

| Need | OwnTracks support |
|---|---|
| Periodic GPS reporting | Yes — POSTs `_type: location` JSON to any HTTP endpoint |
| Battery-efficient geofencing | Yes — uses native OS geofencing APIs under the hood |
| Geofence enter/exit events | Yes — sends `_type: transition` with `event: enter/leave` |
| Server-pushed geofences | Yes — server returns `setWaypoints` commands in HTTP response |
| Authentication | Yes — HTTP Basic auth |
| Offline queueing | Yes — queues payloads when endpoint is unreachable |
| iOS support | Yes — same protocol, same features |

Building a custom app would duplicate all of this with months of development and ongoing maintenance.

**Alternative for power users:** [Tasker](https://tasker.joaoapps.com/) (Android) or [Shortcuts](https://support.apple.com/guide/shortcuts/intro-to-shortcuts-apdf22b0444c/ios) (iOS) can also POST location to an HTTP endpoint on a schedule. These work as a basic fallback but don't support server-pushed geofences or transition events.

---

## Components

### 1. OwnTracks App (existing, no code to write)

Users install OwnTracks from the Play Store / App Store and configure it to point at the agent's location module.

**OwnTracks sends to our server:**

| Message type | When | Key fields |
|---|---|---|
| `_type: location` | Periodically / on significant move | `lat`, `lon`, `acc`, `vel`, `tst`, `inregions[]` |
| `_type: transition` | Entering or leaving a waypoint | `event` (enter/leave), `lat`, `lon`, `desc`, `rid`, `tst`, `wtst` |
| `_type: waypoint` | When user manually creates a waypoint | `desc`, `lat`, `lon`, `rad`, `rid`, `tst` |

**Our server can push back to OwnTracks (in HTTP response):**

The OwnTracks HTTP protocol allows the server to return an array of commands in the 200 response body. This is how we push new geofences to the device without any custom app logic:

```json
[
  {
    "_type": "cmd",
    "action": "setWaypoints",
    "waypoints": {
      "_type": "waypoints",
      "waypoints": [
        {
          "_type": "waypoint",
          "desc": "Whole Foods on 3rd Ave",
          "lat": 40.7128,
          "lon": -74.0060,
          "rad": 150,
          "tst": 1707600000,
          "rid": "reminder-uuid-here"
        }
      ]
    }
  }
]
```

When OwnTracks receives this response, it registers the waypoints as native OS geofences. When the user enters the radius, OwnTracks automatically sends a `_type: transition` event back to our server — no custom code on the phone.

### 2. Location Module (New Module)

A new FastAPI microservice following the existing module pattern.

**File structure:**
```
agent/modules/location/
├── __init__.py
├── Dockerfile
├── requirements.txt
├── main.py              # FastAPI app: /pub, /manifest, /execute, /health
├── manifest.py          # Tool definitions for the LLM
├── tools.py             # Tool implementations
├── geocoding.py         # Place name → coordinates resolution
├── worker.py            # Background geofence proximity checker (fallback)
└── owntracks.py         # OwnTracks protocol handling (parse/respond)
```

#### OwnTracks HTTP Endpoint

A single endpoint that speaks the OwnTracks protocol. This is called by the OwnTracks app, not by the LLM.

```
POST /pub
  Headers:
    Content-Type: application/json
    Authorization: Basic base64(username:password)
    X-Limit-U: <username>      (alternative to Basic auth)
    X-Limit-D: <device-name>
  Body: OwnTracks JSON payload (location, transition, waypoint, etc.)
  Response: 200 OK with JSON array (empty [] or commands to push)
```

**Handling by `_type`:**

| `_type` | Action |
|---|---|
| `location` | Upsert `user_locations` row. Check `inregions[]` for any active reminders. Return pending `setWaypoints` commands if new reminders were created since last sync. |
| `transition` | If `event == "enter"`, look up reminder by `rid`. If active, trigger it: mark as triggered, publish notification via Redis. |
| `waypoint` | Log it. No action needed (user-created waypoints in OwnTracks UI). |

**How geofences get pushed to the device:**

When the agent creates a new location reminder, the module stores a `pending_waypoints` flag for that user in Redis. On the next `_type: location` POST from OwnTracks (which happens regularly), the server includes the `setWaypoints` command in the response body. This is the OwnTracks-native way to push geofences — no polling endpoint needed.

```python
async def handle_owntracks_publish(payload: dict, user_id: str) -> list[dict]:
    """Process an OwnTracks POST and return response commands."""
    msg_type = payload.get("_type")
    response_cmds = []

    if msg_type == "location":
        await upsert_user_location(user_id, payload)
        # Check if we have new waypoints to push
        pending = await get_pending_waypoints(user_id)
        if pending:
            response_cmds.append({
                "_type": "cmd",
                "action": "setWaypoints",
                "waypoints": {
                    "_type": "waypoints",
                    "waypoints": pending,
                }
            })
            await clear_pending_waypoints(user_id)

    elif msg_type == "transition":
        if payload.get("event") == "enter":
            await trigger_reminder_by_rid(user_id, payload["rid"])

    return response_cmds  # Returned as HTTP 200 JSON body
```

#### User Authentication

OwnTracks uses HTTP Basic auth (`username:password`). We map this to internal users:

**Pairing flow:**
1. User asks the agent: "link my phone" or "set up location tracking"
2. LLM calls `location.generate_pairing_credentials`
3. Module creates a random username + password, stores the mapping `(username, password) → user_id` in the DB
4. Agent replies with setup instructions:
   ```
   Install OwnTracks and configure:
   - Mode: HTTP
   - URL: https://your-agent.com/pub
   - Username: agent_dan_7k2m
   - Password: xK9mP2vL8nQ4
   ```
5. OwnTracks sends these credentials with every POST

**Storage:** `owntracks_credentials` table (see Database Tables below).

#### LLM Tools

These are available to the agent when a user makes a natural language request:

**`location.create_reminder`**
```
Parameters:
  - place: string (required) — natural language place description
    ("the supermarket", "home", "123 Main St")
  - message: string (required) — what to remind about ("buy toilet paper")
  - radius_m: integer (optional, default 150) — trigger radius in meters
  - place_lat: number (optional) — explicit latitude (skip geocoding)
  - place_lng: number (optional) — explicit longitude (skip geocoding)

Flow:
  1. If lat/lng not provided, geocode the place name (see Geocoding)
  2. If geocoding returns multiple candidates, return them for the LLM
     to ask the user to pick
  3. Create location_reminders record in DB
  4. Queue a setWaypoints command for the user's next OwnTracks check-in
     (store in Redis as pending waypoint)
  5. Return reminder details + confirmation
```

**`location.list_reminders`**
```
Parameters:
  - status: string (optional, default "active") — filter by status
Returns: list of reminders with place names, messages, coordinates, and status
```

**`location.cancel_reminder`**
```
Parameters:
  - reminder_id: string (required)
Flow:
  1. Mark reminder as "cancelled" in DB
  2. Queue a setWaypoints command with invalid lat/lon (-1000000) to
     delete the waypoint from the OwnTracks device on next check-in
```

**`location.get_location`**
```
Parameters: (none, user_id injected)
Returns: last known location, timestamp, and reverse-geocoded address
```

**`location.set_named_place`**
```
Parameters:
  - name: string (required) — e.g. "home", "work", "gym"
  - lat: number (optional) — if omitted, uses current location
  - lng: number (optional) — if omitted, uses current location
Flow: saves a named place for the user so future reminders can
      reference it without geocoding ("remind me when I get home")
```

**`location.generate_pairing_credentials`**
```
Parameters: (none, user_id injected)
Returns: { username, password, endpoint_url, setup_instructions }
Generates OwnTracks HTTP Basic credentials tied to this user
```

#### Geocoding (`geocoding.py`)

Resolves natural language place descriptions to coordinates.

**Strategy (cascading):**

1. **Named places first** — check user's saved places ("home", "work", "the gym")
2. **Geocode near user** — use the user's last known location as a bias point
3. **External geocoding API** — OpenStreetMap Nominatim (free, no API key required)

```python
async def resolve_place(
    place: str,
    user_id: str,
    near_lat: float | None,
    near_lng: float | None,
) -> list[PlaceResult]:
    """
    Returns a list of candidate locations, ranked by relevance.
    If exactly one strong match, return it directly.
    If ambiguous, return top 3-5 for the LLM to present to the user.
    """
```

**Nominatim example query:**
```
GET https://nominatim.openstreetmap.org/search
  ?q=supermarket
  &format=json
  &limit=5
  &viewbox={lng-0.05},{lat+0.05},{lng+0.05},{lat-0.05}  (bias near user)
  &bounded=0
```

Returns nearby supermarkets ranked by distance from the user's current location. Nominatim is free and requires no API key, but has a rate limit of 1 request/second. For higher volume, Google Places API can be swapped in via the `geocoding_provider` config.

#### Background Geofence Worker (`worker.py`)

A background loop that acts as a server-side fallback. The primary trigger mechanism is OwnTracks `transition` events (client-side, instant). This worker catches edge cases where OwnTracks misses a transition.

```python
async def geofence_loop(session_factory, redis):
    """
    Runs every 30 seconds.
    For each user with active reminders:
      1. Get latest location from user_locations
      2. Skip if location is stale (> 10 min old)
      3. For each active reminder, compute haversine distance
      4. If distance <= radius_m and not already triggered:
         - Mark reminder as triggered
         - Publish notification via Redis pub/sub
         - Set cooldown (don't re-trigger for 1 hour)
    """
```

**Why both client-side and server-side?**
- OwnTracks `transition` events are the primary trigger (instant, battery-efficient)
- Server-side loop handles cases where the OwnTracks event was missed (app killed by OS, network blip, etc.)
- Deduplication via the reminder's `triggered_at` field prevents double-notifications

### 3. Database Tables

**`user_locations`** — latest known position per user

```
user_locations
  id                UUID PK
  user_id           UUID FK → users.id (UNIQUE — one row per user)
  latitude          Float (NOT NULL)
  longitude         Float (NOT NULL)
  accuracy_m        Float | null
  speed_mps         Float | null     — meters per second
  heading           Float | null     — degrees from north
  source            String           — "owntracks" | "manual"
  updated_at        DateTime(tz)     — last update time
  created_at        DateTime(tz)
```

**`location_reminders`** — geofence-based reminders

```
location_reminders
  id                UUID PK
  user_id           UUID FK → users.id
  conversation_id   UUID FK → conversations.id | null

  -- What to remind
  message           String (NOT NULL)     — "buy toilet paper"

  -- Where to trigger
  place_name        String (NOT NULL)     — "Whole Foods on 3rd Ave"
  place_lat         Float (NOT NULL)
  place_lng         Float (NOT NULL)
  radius_m          Integer (default 150) — trigger radius

  -- Where to notify
  platform          String                — "discord" | "telegram" | "slack"
  platform_channel_id String              — channel where reminder was created
  platform_thread_id  String | null

  -- OwnTracks sync
  owntracks_rid     String (NOT NULL)     — region ID sent to OwnTracks device
  synced_to_device  Boolean (default false) — whether setWaypoints was delivered

  -- Lifecycle
  status            String                — "active" | "triggered" | "cancelled" | "expired"
  triggered_at      DateTime(tz) | null   — when user entered geofence
  expires_at        DateTime(tz) | null   — optional auto-expiry
  cooldown_until    DateTime(tz) | null   — prevent re-trigger while lingering
  created_at        DateTime(tz)
```

**`user_named_places`** — saved locations per user

```
user_named_places
  id                UUID PK
  user_id           UUID FK → users.id
  name              String (NOT NULL)     — "home", "work", "gym"
  latitude          Float (NOT NULL)
  longitude         Float (NOT NULL)
  address           String | null         — human-readable address
  created_at        DateTime(tz)
  UNIQUE(user_id, name)
```

**`owntracks_credentials`** — maps OwnTracks auth to internal users

```
owntracks_credentials
  id                UUID PK
  user_id           UUID FK → users.id
  username          String (NOT NULL, UNIQUE)
  password_hash     String (NOT NULL)     — bcrypt hash
  device_name       String | null
  is_active         Boolean (default true)
  last_seen_at      DateTime(tz) | null
  created_at        DateTime(tz)
```

**Redis keys:**
```
owntracks_pending_waypoints:{user_id}  → JSON list of waypoint objects to push
user_location:{user_id}                → {lat, lng, updated_at} (TTL: 10 min, fast cache)
```

### 4. Notification Format

When triggered, the notification sent through the existing Redis pub/sub:

```python
Notification(
    platform="discord",
    platform_channel_id="123456",
    content="You're near **Whole Foods on 3rd Ave**!\n\nReminder: buy toilet paper",
    user_id="<uuid>",
)
```

---

## End-to-End Flows

### Setup (one-time)

```
User (Discord):  Hey, I want to set up location reminders

Agent LLM:       [calls location.generate_pairing_credentials()]

Module:          [creates owntracks_credentials record]
                 [returns credentials + instructions]

Agent:           Here's how to set up location tracking:

                 1. Install OwnTracks from the Play Store (or App Store)
                 2. Open Settings → Connection
                    - Mode: HTTP
                    - URL: https://your-agent.com/pub
                    - Username: agent_dan_7k2m
                    - Password: xK9mP2vL8nQ4
                 3. That's it! OwnTracks will start sharing your location.

                 You can pause at any time from the OwnTracks app.
```

### Creating a Reminder

```
User (Discord):  When I get to the supermarket, remind me to buy toilet paper

Agent LLM:       [understands intent, calls location.create_reminder(
                   place="the supermarket",
                   message="buy toilet paper"
                 )]

Module:          [geocodes "the supermarket" near user's last known location]
                 [finds 2 candidates within 3km]
                 [returns candidates to LLM]

Agent LLM:       I found two supermarkets near you:
                 1. Whole Foods — 0.4 mi away on 3rd Ave
                 2. Trader Joe's — 1.2 mi away on Broadway
                 Which one?

User:            Whole Foods

Agent LLM:       [calls location.create_reminder(
                   place="Whole Foods on 3rd Ave",
                   message="buy toilet paper",
                   place_lat=40.7128, place_lng=-74.0060
                 )]

Module:          [creates location_reminders record with owntracks_rid]
                 [queues setWaypoints command in Redis for next OwnTracks check-in]
                 [returns confirmation]

Agent:           Done! I'll remind you to buy toilet paper when you arrive
                 at Whole Foods on 3rd Ave. (150m trigger radius)
```

### Geofence Sync (automatic, invisible to user)

```
OwnTracks App:   [periodic location POST to /pub]
                 { "_type": "location", "lat": 40.75, "lon": -73.99, ... }

Module:          [upserts user_locations]
                 [sees pending waypoints in Redis for this user]
                 [returns HTTP 200 with setWaypoints command]:
                 [
                   {
                     "_type": "cmd",
                     "action": "setWaypoints",
                     "waypoints": {
                       "_type": "waypoints",
                       "waypoints": [{
                         "_type": "waypoint",
                         "desc": "Whole Foods on 3rd Ave",
                         "lat": 40.7128, "lon": -74.0060,
                         "rad": 150, "rid": "reminder-uuid",
                         "tst": 1707600000
                       }]
                     }
                   }
                 ]

OwnTracks App:   [receives waypoint, registers native OS geofence]
                 [marks synced_to_device = true on next location POST]
```

### Trigger

```
[Later that day...]

OwnTracks App:   [OS detects user entered 150m radius of Whole Foods]
                 [sends transition event to /pub]:
                 {
                   "_type": "transition",
                   "event": "enter",
                   "rid": "reminder-uuid",
                   "desc": "Whole Foods on 3rd Ave",
                   "lat": 40.7130, "lon": -74.0058,
                   "tst": 1707645000
                 }

Module:          [looks up reminder by rid → found, status = active]
                 [marks reminder as triggered, sets triggered_at]
                 [publishes Notification to Redis]
                 [queues setWaypoints with invalid coords to remove
                  the geofence from the device]

Discord Bot:     [receives notification from Redis pub/sub]
                 [sends message to user's channel]

User (Discord):  You're near Whole Foods on 3rd Ave!
                 Reminder: buy toilet paper
```

---

## Design Decisions & Trade-offs

### Why OwnTracks over alternatives?

| Approach | Pros | Cons |
|---|---|---|
| **OwnTracks** | Existing app, native geofencing, server-push via protocol, Android + iOS, battery efficient, free, open source | Can't customize the app UX, users must install a separate app |
| **Custom Android app** | Full UX control | Months to build, ongoing maintenance, Android-only, duplicates OwnTracks |
| **Tasker / Shortcuts** | No app install for power users who have it | Fragile, no server-push geofences, no transition events, complex setup |
| **Google Maps sharing** | No app install | No API for geofence triggers, polling-only, no programmatic access |

### Why Nominatim for geocoding?

- Free, no API key, no billing setup
- Good enough for common places (supermarkets, gyms, restaurants)
- Rate limit (1 req/sec) is fine for our use case
- Can swap to Google Places API via config if quality is insufficient

### Why 150m default radius?

GPS accuracy on Android/iOS is typically 5-15m outdoors, 15-50m indoors. A 150m radius provides reliable triggering without false positives from being on an adjacent block. Users can override per reminder.

### Why a server-side geofence worker as fallback?

OwnTracks transition events are reliable but not guaranteed — the OS can kill the app, or network issues can delay delivery. The server-side worker (checking every 30s against the `inregions` array in location payloads or computing haversine distance) catches these edge cases. Deduplication via `triggered_at` prevents double notifications.

### Expiry & cleanup

- Reminders default to no expiry, but the user (or LLM) can set `expires_at`
- A nightly cleanup job marks expired reminders as `"expired"` and queues waypoint deletions
- The LLM can suggest expiry: "Should this reminder expire after a certain time?"

### Privacy

- Location data stays within the user's self-hosted infrastructure
- `user_locations` only stores the latest position (not a history/track)
- Users can pause location sharing from OwnTracks at any time
- OwnTracks credentials are per-user, password is bcrypt-hashed in DB
- OwnTracks is open source — users can audit what data it sends

---

## Integration Points with Existing System

| Existing component | Integration |
|---|---|
| `shared/config.py` | Add `geocoding_provider`, `geocoding_api_key` (optional), `owntracks_endpoint_url`, module URL |
| `docker-compose.yml` | Add `location` service |
| `shared/models/` | Add `user_location.py`, `location_reminder.py`, `named_place.py`, `owntracks_credential.py` |
| `shared/schemas/notifications.py` | Already supports what we need (no changes) |
| Redis pub/sub | Use existing `notifications:{platform}` channels |
| Scheduler module | Not needed — location module has its own geofence worker |
| Knowledge module | Could auto-remember triggered reminders as memories |
| Core `/embed` | Not needed (no semantic search over reminders) |

---

## Module Registration

**`shared/config.py`:**
```python
module_services = {
    ...
    "location": "http://location:8000",
}
```

**`docker-compose.yml`:**
```yaml
location:
  build:
    context: .
    dockerfile: modules/location/Dockerfile
  env_file: .env
  depends_on:
    - postgres
    - redis
  networks:
    - agent-net
  restart: unless-stopped
```

---

## Exposing /pub to the Internet

The OwnTracks app on the user's phone needs to reach the `/pub` endpoint over the internet. The internal Docker network won't work here. Options:

1. **Reverse proxy (recommended)** — nginx/Caddy in front of the location module, with TLS termination. Only expose `/pub` externally; all other module endpoints stay internal.
2. **Cloudflare Tunnel** — zero-config option if you're already using Cloudflare. Maps a public hostname to the internal service.
3. **Tailscale/WireGuard** — if the phone is on the same tailnet/VPN as the server, no public exposure needed.

OwnTracks strongly recommends HTTPS since it uses HTTP Basic auth.

---

## Future Extensions (not in v1)

- **Location history** — opt-in track storage for "where was I last Tuesday?"
- **Shared places** — server-wide named places ("the office")
- **Recurring geofence reminders** — "every time I get to the gym, remind me to stretch"
- **Exit-based reminders** — "when I leave work, remind me to pick up groceries" (OwnTracks already sends `event: leave` transitions)
- **Time + location combos** — "tomorrow when I get to work, remind me to email Bob"
- **Proximity to other users** — "when Dan is nearby, remind me to give him the book" (requires consent)
- **`inregions` enrichment** — use the `inregions` array in location payloads to proactively tell the agent where the user is, enabling context-aware responses
