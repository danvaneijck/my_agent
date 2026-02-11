# Design: Location-Based Reminders

## Overview

Enable users to create reminders triggered by physical proximity to a location.

**Example interaction:**
> "When I get to the supermarket, remind me to buy toilet paper"

The system resolves "the supermarket" to geographic coordinates, monitors the user's location via an Android companion app, and sends a proactive notification when the user arrives.

---

## High-Level Architecture

```
Android Phone                          Agent System
┌──────────────────┐                  ┌────────────────────────────────┐
│  Companion App   │   HTTPS POST     │  Location Module (FastAPI)     │
│                  │ ──────────────►  │                                │
│  - Fused Location│  /location/update│  ┌──────────────────────────┐  │
│    Provider      │                  │  │ Location Ingestion API   │  │
│  - Geofence API  │  ◄────────────── │  │ (receives GPS updates)   │  │
│  - Auth token    │  /location/fences│  └──────────┬───────────────┘  │
│                  │  (push geofences │             │                  │
│                  │   to device)     │             ▼                  │
└──────────────────┘                  │  ┌──────────────────────────┐  │
                                      │  │ Geofence Worker          │  │
                                      │  │ (background loop)        │  │
                                      │  │ checks proximity         │  │
                                      │  └──────────┬───────────────┘  │
                                      │             │                  │
                                      │             ▼                  │
                                      │  Redis pub/sub                 │
                                      │  notifications:{platform}      │
                                      └────────────┬───────────────────┘
                                                   │
                                                   ▼
                                      ┌────────────────────────────────┐
                                      │  Bots (Discord/Telegram/Slack) │
                                      │  "You're near the supermarket! │
                                      │   Don't forget: toilet paper"  │
                                      └────────────────────────────────┘
```

---

## Components

### 1. Android Companion App

A lightweight Android app that reports the user's GPS to the agent system.

**Core responsibilities:**
- Collect location via Android's Fused Location Provider
- Send periodic updates to the agent's Location Module
- Authenticate via a per-user API token
- Optionally register native Android geofences for battery efficiency

**Location strategy (battery-aware):**

| User state | Update interval | Method |
|---|---|---|
| Moving (speed > 2 m/s) | 30 seconds | Fused Location (high accuracy) |
| Stationary | 5 minutes | Fused Location (balanced) |
| Active geofences exist | Passive | Android Geofencing API |

The Android Geofencing API is ideal here because it uses hardware-level monitoring that barely impacts battery. The OS batches checks and wakes the app only on enter/exit events. Limit: ~100 geofences per app (more than enough for reminders).

**Hybrid approach:**
- The app registers Android-native geofences for each active reminder's coordinates
- On geofence enter, the app immediately POSTs an event to the server
- The app *also* sends periodic location updates as a fallback (and so the agent can answer "where am I?" queries)
- The server does its own proximity check as a redundant trigger

**Auth:**
- User links their phone via a bot command (`/link-phone`)
- Server generates a one-time pairing code displayed in chat
- User enters the code in the Android app
- Server returns a long-lived API token tied to the user's internal UUID
- Token sent as `Authorization: Bearer <token>` on all requests

**Minimal Android tech stack:**
- Kotlin, targeting API 26+ (Android 8.0+, covers ~95% of devices)
- WorkManager for periodic location reporting
- GeofencingClient for native geofence monitoring
- Retrofit for HTTP calls to the agent
- Foreground service with persistent notification ("Agent location active")

### 2. Location Module (New Module)

A new FastAPI microservice following the existing module pattern.

**File structure:**
```
agent/modules/location/
├── __init__.py
├── Dockerfile
├── requirements.txt
├── main.py              # FastAPI app with standard + location-specific endpoints
├── manifest.py          # Tool definitions for the LLM
├── tools.py             # Tool implementations
├── geocoding.py         # Place name → coordinates resolution
├── worker.py            # Background geofence proximity checker
└── auth.py              # Phone pairing & token validation
```

#### API Endpoints (non-tool, direct HTTP)

These are called by the Android app directly, not by the LLM:

```
POST /location/update
  Body: { "lat": 40.7128, "lng": -74.0060, "accuracy_m": 10.5, "speed_mps": 1.2, "timestamp": "..." }
  Auth: Bearer token
  → Updates user_locations table
  → Returns 200 OK

GET /location/fences
  Auth: Bearer token
  → Returns list of active geofences for this user
  → Android app registers these with its native GeofencingClient
  Response: { "fences": [{ "id": "uuid", "lat": 40.71, "lng": -74.00, "radius_m": 150 }, ...] }

POST /location/fence-event
  Body: { "fence_id": "uuid", "event": "enter" | "exit", "lat": 40.71, "lng": -74.00 }
  Auth: Bearer token
  → Immediate geofence trigger (client-side detection)
  → Publishes notification via Redis

POST /location/pair
  Body: { "pairing_code": "ABC123" }
  → Validates code, returns API token
  Response: { "token": "...", "user_id": "..." }
```

#### LLM Tools

These are available to the agent when a user makes a natural language request:

**`location.create_reminder`**
```
Parameters:
  - place: string (required) — natural language place description ("the supermarket", "home", "123 Main St")
  - message: string (required) — what to remind about ("buy toilet paper")
  - radius_m: integer (optional, default 150) — trigger radius in meters
  - place_lat: number (optional) — explicit latitude (skip geocoding)
  - place_lng: number (optional) — explicit longitude (skip geocoding)

Flow:
  1. If lat/lng not provided, geocode the place name (see Geocoding below)
  2. If geocoding returns multiple results, return them for the LLM to ask the user to pick
  3. Create location_reminders record
  4. Return reminder details + confirmation
```

**`location.list_reminders`**
```
Parameters:
  - status: string (optional, default "active") — filter by status
Returns: list of active reminders with place names, messages, and coordinates
```

**`location.cancel_reminder`**
```
Parameters:
  - reminder_id: string (required)
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
  - lat: number (required)
  - lng: number (required)
Flow: saves a named place for the user so future reminders can reference it without geocoding
```

**`location.generate_pairing_code`**
```
Parameters: (none, user_id injected)
Returns: a 6-character alphanumeric code (valid for 10 minutes)
Stores code in Redis with TTL
```

#### Geocoding (`geocoding.py`)

Resolves natural language place descriptions to coordinates.

**Strategy (cascading):**

1. **Named places first** — check user's saved places ("home", "work", "the gym")
2. **Geocode near user** — use the user's last known location as a bias point
3. **External geocoding API** — call OpenStreetMap Nominatim (free, no API key) or Google Places API (better results, costs money)

```python
async def resolve_place(place: str, user_id: str, near_lat: float, near_lng: float) -> list[PlaceResult]:
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

This returns nearby supermarkets ranked by distance from the user's current location.

#### Background Geofence Worker (`worker.py`)

A background loop (similar to the scheduler worker pattern) that acts as a server-side redundancy check.

```python
async def geofence_loop(session_factory, redis):
    """
    Runs every 15 seconds.
    For each user with active reminders:
      1. Get latest location from user_locations
      2. For each active reminder, compute haversine distance
      3. If distance <= radius_m and wasn't previously triggered:
         - Mark reminder as triggered
         - Publish notification via Redis pub/sub
         - Set cooldown (don't re-trigger for 1 hour if user lingers)
    """
```

**Why both client-side and server-side geofencing?**
- Android geofence events are the primary trigger (instant, battery-efficient)
- Server-side loop is the fallback for cases where the Android event is delayed or missed
- Deduplication via the reminder's `triggered_at` field prevents double-notifications

### 3. Database Tables

Two new tables, plus a pairing-codes mechanism in Redis.

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
  source            String           — "android_gps" | "manual"
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

**Redis keys:**
```
phone_pairing:{code}  → user_id   (TTL: 10 minutes)
phone_token:{token}   → user_id   (persistent, or long TTL)
user_location:{user_id} → {lat, lng, updated_at}  (TTL: 10 min, fast cache for worker)
```

### 4. Notification Format

When triggered, the notification sent through the existing Redis pub/sub:

```python
Notification(
    platform="discord",
    platform_channel_id="123456",
    content="📍 You're near **Whole Foods on 3rd Ave**!\n\nReminder: buy toilet paper",
    user_id="<uuid>",
)
```

---

## End-to-End Flow

### Setup (one-time)

```
User (Discord):  /link-phone
Agent:           Sure! Open the companion app and enter this code: X7K2M9
                 It expires in 10 minutes.

User (Android):  [enters X7K2M9 in app]
App:             [POST /location/pair → receives API token]
App:             [starts location service, begins sending updates]
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

Module:          [creates reminder in DB]
                 [returns confirmation]

Agent:           Done! I'll remind you to buy toilet paper when you arrive
                 at Whole Foods on 3rd Ave. (150m trigger radius)
```

### Trigger

```
[Later that day...]

Android App:     [detects user entered geofence via Android Geofencing API]
                 [POST /location/fence-event { fence_id, event: "enter" }]

Module:          [validates fence_id maps to active reminder]
                 [marks reminder as triggered]
                 [publishes Notification to Redis]

Discord Bot:     [receives notification from Redis pub/sub]
                 [sends message to user's channel]

User (Discord):  📍 You're near Whole Foods on 3rd Ave!
                 Reminder: buy toilet paper
```

---

## Design Decisions & Trade-offs

### Why a dedicated Android app vs. Tasker/IFTTT?

| Approach | Pros | Cons |
|---|---|---|
| **Custom app** | Full control, native geofencing, clean UX, push geofences from server | Requires building & maintaining an Android app |
| **Tasker + HTTP** | No app to build, user configures automations | Fragile, complex setup for users, no server-push of geofences, hard to manage multiple reminders |
| **Google Maps sharing** | No app needed | No API for geofence triggers, only shows current location, polling-only |

**Recommendation:** Custom app. It's a small app (single Activity + foreground Service), and Android's Geofencing API is the only way to get battery-efficient, reliable proximity triggers.

### Why Nominatim over Google Places?

Start with Nominatim (free, no API key, good enough for common places). Add Google Places as an optional upgrade if geocoding quality becomes an issue. The `geocoding.py` abstraction supports swapping providers.

### Why 150m default radius?

GPS accuracy on Android is typically 5-15m outdoors, 15-50m indoors. A 150m radius provides reliable triggering without false positives from being on the same block. Users can override this per reminder.

### Expiry & cleanup

- Reminders default to no expiry, but the user (or LLM) can set `expires_at`
- A nightly cleanup job marks expired reminders as `"expired"`
- The LLM can suggest expiry: "Should this reminder expire after a certain time?"

### Privacy considerations

- Location data stays within the user's self-hosted agent infrastructure
- `user_locations` only stores the latest position (not a history/track)
- Users can pause location sharing from the Android app at any time
- The `/location/update` endpoint only accepts updates for the authenticated user

---

## Integration Points with Existing System

| Existing component | Integration |
|---|---|
| `shared/config.py` | Add `geocoding_provider`, `geocoding_api_key` (optional), module URL |
| `docker-compose.yml` | Add `location` service |
| `shared/models/` | Add `user_location.py`, `location_reminder.py`, `named_place.py` |
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

## Future Extensions (not in v1)

- **iOS companion app** — same architecture, use CLLocationManager + CLCircularRegion
- **Location history** — opt-in track storage for "where was I last Tuesday?"
- **Shared places** — server-wide named places ("the office")
- **Recurring geofence reminders** — "every time I get to the gym, remind me to stretch"
- **Exit-based reminders** — "when I leave work, remind me to pick up groceries"
- **Time + location combos** — "tomorrow when I get to work, remind me to email Bob"
- **Proximity to other users** — "when Dan is nearby, remind me to give him the book" (requires consent)
