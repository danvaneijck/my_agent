# Health Page — Implementation Plan

## Overview

Add a `/health-status` page to the web portal that shows live health of every
module service. The page polls a new `GET /api/health` backend endpoint which
concurrently calls each module's `/health` endpoint and returns an aggregated
dict with per-module status, latency, and errors.

---

## Repository Analysis

### Existing code to be aware of

| File | Relevance |
|------|-----------|
| `agent/portal/routers/system.py` | Has a **conflicting** `GET /api/health` endpoint (simple portal auth check). Must be removed before registering the new health router. |
| `agent/portal/services/module_client.py` | `check_module_health(module)` already calls `/health` per module, but lacks `latency_ms`. Needs extension. |
| `agent/portal/main.py` | Registers all routers. New `health` router must be added here. |
| `agent/portal/frontend/src/types/index.ts` | `ModuleHealth` interface exists at line 386 but is missing `latency_ms`. |
| `agent/portal/frontend/src/App.tsx` | All 24 routes defined with `lazy()` imports. New `/health-status` route goes here. |
| `agent/portal/frontend/src/components/layout/Sidebar.tsx` | `NAV_ITEMS` array at line 23. New entry goes before `Settings`. |
| `agent/portal/frontend/src/components/layout/BottomNav.tsx` | Mobile bottom nav — health not added here (less-common admin page; accessible via sidebar "More" button). |

### Route conflict

`system.py` registers `router = APIRouter(prefix="/api")` and defines
`GET /api/health`. The new `health.py` router will also define `GET /api/health`.
FastAPI will use whichever is registered first, causing silent routing bugs.

**Resolution**: Remove the `GET /api/health` handler from `system.py`. The
endpoint was a simple portal-auth validation (returns `{status, user}`) — this
role is fully covered by `GET /api/auth/me` which `App.tsx` already uses for
authentication checks. Nothing in the frontend calls `/api/health` today.

---

## Phase 1 — Backend health aggregator endpoint

### Task 1.1 — Extend `check_module_health` to return `latency_ms`

**File**: `agent/portal/services/module_client.py`

Change `check_module_health` to measure wall-clock time around the HTTP call
and include `latency_ms` in the return dict. Reduce timeout from 5 s to 3 s
to match the design requirement.

```python
import time

async def check_module_health(module: str) -> dict:
    settings = get_settings()
    base_url = settings.module_services.get(module)
    if not base_url:
        return {"module": module, "status": "unknown", "error": "not configured", "latency_ms": None}
    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{base_url}/health")
            resp.raise_for_status()
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"module": module, "status": "ok", "latency_ms": latency_ms}
    except Exception as e:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return {"module": module, "status": "error", "error": str(e), "latency_ms": latency_ms}
```

**Acceptance**: `check_module_health` returns a dict that always contains
`latency_ms` (an integer millisecond value, or `None` when not configured).

---

### Task 1.2 — Remove conflicting `GET /api/health` from `system.py`

**File**: `agent/portal/routers/system.py`

Delete the `health()` function and its `@router.get("/health")` decorator
(lines 19–30). The `module_status` and `deploy_status` handlers are unaffected.

**Acceptance**: `system.py` no longer defines a `/health` route. The
`/api/system/modules` and `/api/system/deploy-status` endpoints continue to work.

---

### Task 1.3 — Create `agent/portal/routers/health.py`

New file. Defines `GET /api/health` that:

- Reads `settings.module_services` to get the full list of modules.
- Concurrently calls `check_module_health(module)` for every module using
  `asyncio.gather`.
- Returns a dict keyed by module name:

```json
{
  "research":      { "status": "ok",    "latency_ms": 12,   "error": null },
  "file_manager":  { "status": "error", "latency_ms": 3001, "error": "Connection refused" },
  "code_executor": { "status": "ok",    "latency_ms": 8,    "error": null }
}
```

Requires auth (`Depends(require_auth)`) — same pattern as the rest of the portal.

```python
"""Aggregated module health endpoint."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends

from portal.auth import PortalUser, require_auth
from portal.services.module_client import check_module_health
from shared.config import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def aggregated_health(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Concurrently check /health on every module service.

    Returns {module_name: {status, latency_ms, error}}.
    """
    settings = get_settings()
    module_names = list(settings.module_services.keys())
    results = await asyncio.gather(
        *[check_module_health(m) for m in module_names]
    )
    return {
        r["module"]: {
            "status": r["status"],
            "latency_ms": r.get("latency_ms"),
            "error": r.get("error"),
        }
        for r in results
    }
```

**Acceptance**: `curl -H "Authorization: Bearer <token>" /api/health` returns
a JSON object with one key per module in `settings.module_services`.

---

### Task 1.4 — Register the new router in `main.py`

**File**: `agent/portal/main.py`

1. Add `health` to the router import line:
   ```python
   from portal.routers import auth, chat, deployments, errors, files, health, \
       knowledge, projects, repos, schedule, settings, skills, system, tasks, usage
   ```
2. Register it (place before `system.router` to make precedence explicit):
   ```python
   app.include_router(health.router)
   ```

**Acceptance**: Portal starts without errors; `/api/health` returns module data.

---

## Phase 2 — Frontend HealthStatusPage

### Task 2.1 — Update `ModuleHealth` type

**File**: `agent/portal/frontend/src/types/index.ts`

Add `latency_ms` to the existing `ModuleHealth` interface and add a map type
for the aggregated response:

```typescript
export interface ModuleHealth {
  module: string;
  status: "ok" | "error" | "unknown";
  latency_ms: number | null;
  error?: string;
}

// Top-level shape returned by GET /api/health
export type ModuleHealthMap = Record<string, Omit<ModuleHealth, "module">>;
```

**Acceptance**: TypeScript compiles without errors when `ModuleHealthMap` is
used in the new page.

---

### Task 2.2 — Create `HealthStatusPage.tsx`

**File**: `agent/portal/frontend/src/pages/HealthStatusPage.tsx`

Behaviour:

- On mount, fetches `GET /api/health` via the existing `apiClient` wrapper.
- Repeats the fetch every 10 seconds via `setInterval` inside `useEffect`;
  clears the interval on unmount.
- While the first fetch is in flight, shows a row-by-row skeleton (use the
  existing `Skeleton` component from `components/common/Skeleton.tsx`).
- If the fetch fails (network error or non-2xx), shows an error banner above
  the table.
- Renders a table with columns: **Module**, **Status**, **Latency**.
  - Status badge: green pill "ok" / red pill "error" / grey pill "unknown".
    Reuse the `StatusBadge` component from `components/common/StatusBadge.tsx`
    if it maps cleanly, otherwise inline badge spans consistent with the rest of
    the codebase.
  - Latency column: show integer ms, or "—" when null.
- Shows a small "Last updated: HH:MM:SS" timestamp that updates on each
  successful fetch.
- Shows a summary line: "X / Y modules healthy".

Design patterns to follow:
- `motion.div` wrapper with `fadeInUp` animation variant from `utils/animations.ts`.
- `Card` component from `components/common/Card.tsx` wrapping the table.
- Tailwind dark/light theme classes matching the existing pages.
- Auth token is passed automatically by `apiClient` (`api/client.ts`).

**Acceptance**: Page renders a live table; status badges and latency values
update every 10 seconds without a page reload. Loading skeleton shown on
initial load. Error banner shown when the fetch fails.

---

### Task 2.3 — Add `/health-status` route in `App.tsx`

**File**: `agent/portal/frontend/src/App.tsx`

1. Add a lazy import with the other page imports:
   ```typescript
   const HealthStatusPage = lazy(() => import("./pages/HealthStatusPage"));
   ```
2. Add the route inside the existing `<Routes>` block:
   ```typescript
   <Route path="/health-status" element={<HealthStatusPage />} />
   ```

**Acceptance**: Navigating to `/health-status` renders `HealthStatusPage`; the
catch-all `NotFoundPage` is no longer triggered for that path.

---

## Phase 3 — Sidebar navigation link

### Task 3.1 — Add "Health" entry to `Sidebar.tsx`

**File**: `agent/portal/frontend/src/components/layout/Sidebar.tsx`

1. Import the `Activity` icon from lucide-react (already a project dependency):
   ```typescript
   import {
     ...,
     Activity,
   } from "lucide-react";
   ```
2. Add an entry to `NAV_ITEMS` just before the `Settings` entry:
   ```typescript
   { to: "/health-status", icon: Activity, label: "Health" },
   ```

No badge is needed (this is a read-only monitoring page).

**Acceptance**: Sidebar shows a "Health" link with the `Activity` icon;
clicking it navigates to `/health-status` and the link highlights as active.

---

## Summary of all files changed

| File | Change type | Notes |
|------|-------------|-------|
| `agent/portal/services/module_client.py` | Modify | Add `latency_ms`, reduce timeout to 3 s |
| `agent/portal/routers/system.py` | Modify | Remove conflicting `GET /api/health` handler |
| `agent/portal/routers/health.py` | **New** | Aggregated module health endpoint |
| `agent/portal/main.py` | Modify | Import and register `health` router |
| `agent/portal/frontend/src/types/index.ts` | Modify | Add `latency_ms` and `ModuleHealthMap` |
| `agent/portal/frontend/src/pages/HealthStatusPage.tsx` | **New** | Health status page component |
| `agent/portal/frontend/src/App.tsx` | Modify | Lazy import + `/health-status` route |
| `agent/portal/frontend/src/components/layout/Sidebar.tsx` | Modify | Add `Activity` import + nav entry |

---

## Key design decisions

1. **Route conflict resolution**: Remove `GET /api/health` from `system.py`
   entirely rather than renaming it, because the auth-validation role it served
   is already covered by `/api/auth/me`.

2. **Aggregated response format**: Return a dict keyed by module name (not a
   list) — easier for the frontend to look up by name and matches the design doc
   spec `{module_name: {status, latency_ms, error?}}`.

3. **Concurrency**: `asyncio.gather` with a 3 s timeout per module means the
   endpoint completes in ≤ 3 s regardless of the number of modules — no
   sequential bottleneck.

4. **Polling interval**: 10 s interval via `setInterval` in `useEffect` with
   cleanup on unmount — no external library needed.

5. **Loading skeleton vs spinner**: Show a skeleton on initial load (matches
   existing page patterns), then silently refresh in the background; avoid
   flashing a spinner on every 10 s poll.

6. **Bottom nav not modified**: `BottomNav.tsx` is intentionally left unchanged.
   It shows the 4 most-used tabs (Home, Tasks, Chat, Settings). Health
   monitoring is an admin/power-user concern; it is reachable via the sidebar
   "More" button on mobile.
