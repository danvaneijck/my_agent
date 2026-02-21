# Fix: Error Page Filter Always Shows "All" Errors

## Problem

In `agent/portal/frontend/src/pages/ErrorsPage.tsx`, line 286, the API URL for
fetching errors is built with faulty string interpolation:

```typescript
`/api/errors${filter !== "all" ? `?status=${filter}` : ""}?limit=100`
```

When the user selects any filter other than `"all"` (e.g. `"open"`,
`"dismissed"`, `"resolved"`), this produces a URL with **two `?` characters**:

```
/api/errors?status=open?limit=100
```

HTTP clients treat the second `?` as a literal character, so the backend
receives `status` with value `open?limit=100` (or the parameter is ignored
entirely). The backend (`agent/portal/routers/errors.py`) does not recognise
this malformed value and falls back to returning all errors, so the filter
appears to be permanently stuck on "all".

When `filter === "all"` the URL is `/api/errors?limit=100`, which is correct —
but that means the "all" button works by accident, and every other button does
not work.

## Root Cause

String interpolation appends `?limit=100` unconditionally after the optional
`?status=…` fragment. When the fragment is present the separator before `limit`
must be `&`, not `?`.

## Fix

**File:** `agent/portal/frontend/src/pages/ErrorsPage.tsx`
**Line:** 286

Replace the brittle string interpolation with `URLSearchParams`, which handles
separator logic automatically:

```typescript
// Before (broken — produces double "?" when filter is active)
api<ErrorsResponse>(
  `/api/errors${filter !== "all" ? `?status=${filter}` : ""}?limit=100`
),

// After (fixed)
api<ErrorsResponse>(
  `/api/errors?${new URLSearchParams(
    filter !== "all"
      ? { status: filter, limit: "100" }
      : { limit: "100" }
  ).toString()}`
),
```

This produces:
- filter = "all"      → `/api/errors?limit=100`
- filter = "open"     → `/api/errors?status=open&limit=100`
- filter = "dismissed"→ `/api/errors?status=dismissed&limit=100`
- filter = "resolved" → `/api/errors?status=resolved&limit=100`

## Files to Modify

| File | Change |
|---|---|
| `agent/portal/frontend/src/pages/ErrorsPage.tsx` | Fix URL construction on line 286 |

No backend changes are required. `agent/portal/routers/errors.py` already
handles the `status` query parameter correctly — it was never receiving a valid
value from the frontend.

## Steps

1. Edit line 286 in `ErrorsPage.tsx` to use `URLSearchParams`.
2. Verify the four filter buttons (`all`, `open`, `dismissed`, `resolved`) now
   each send the correct query string to the backend.
3. Commit the fix.
4. Remove `PLAN.md` from the branch and push.
