# Plan: Fix Benchmarker Credentials Stale Cache Bug

## Problem Statement

When a user updates their Benchmarker API endpoint (or token) via the portal settings, subsequent tool calls continue using the **old** endpoint. The user's new credentials are saved correctly to the database, but the `benchmarker` module never picks them up because it caches the client in process memory.

## Root Cause

`agent/modules/benchmarker/main.py` maintains an in-process per-user client cache:

```python
# Cache per-user clients to preserve authentication state
_user_client_cache: dict[str, BenchmarkerClient] = {}

async def _get_client_for_user(user_id: str | None) -> BenchmarkerClient | None:
    if user_id and _credential_store and _session_factory:
        # Return cached instance if available  ← NEVER invalidated
        if user_id in _user_client_cache:
            return _user_client_cache[user_id]
        ...
        _user_client_cache[user_id] = client  # cached forever in process
        return client
    return _fallback_client
```

This cache:
- Has **no TTL** — entries live for the lifetime of the container process.
- Has **no invalidation mechanism** — nothing clears it when the portal's `PUT /api/settings/credentials/benchmarker` endpoint updates the DB.
- Means any `api_url` or `api_key` change in the portal is silently ignored until the `benchmarker` container is manually restarted.

The credential store, DB write path (portal `PUT` endpoint), and `BenchmarkerClient._request` are all correct — the bug is exclusively in this in-process cache.

## File to Modify

| File | Change |
|---|---|
| `agent/modules/benchmarker/main.py` | Remove the in-process cache; always fetch credentials from DB per call |

No other files need to change.

## Detailed Implementation Steps

### Step 1 — Delete `_user_client_cache`

Remove the module-level dict declaration at line 41:

```python
# DELETE this line:
_user_client_cache: dict[str, BenchmarkerClient] = {}
```

### Step 2 — Rewrite `_get_client_for_user` to always query the DB

Replace the current implementation of `_get_client_for_user` (lines 44–69) with a version that removes both cache-read and cache-write, always fetching fresh credentials:

```python
async def _get_client_for_user(user_id: str | None) -> BenchmarkerClient | None:
    """Resolve a BenchmarkerClient instance for the given user.

    Always fetches credentials from the DB so that updates made via the portal
    are picked up immediately without restarting the module.

    Priority:
    1. User's stored Benchmarker credentials from credential store
    2. Global BENCHMARKER_API_URL/BENCHMARKER_API_KEY env vars (fallback)
    """
    if user_id and _credential_store and _session_factory:
        try:
            uid = uuid.UUID(user_id)
            async with _session_factory() as session:
                creds = await _credential_store.get_all(session, uid, "benchmarker")
            api_url = creds.get("api_url")
            api_key = creds.get("api_key")
            if api_url and api_key:
                return BenchmarkerClient(api_url=api_url, api_key=api_key)
        except Exception as e:
            logger.warning("user_credential_lookup_failed", user_id=user_id, error=str(e))

    return _fallback_client
```

Key differences from the original:
- The `if user_id in _user_client_cache: return _user_client_cache[user_id]` early-return is removed.
- The `_user_client_cache[user_id] = client` write is removed.
- A fresh `BenchmarkerClient` is constructed on every tool call using the latest DB values.

### Step 3 — Rebuild and restart the benchmarker container

After the code change, the running container still holds the old in-memory cache in its process. Restart it to clear it:

```bash
make restart-module M=benchmarker
```

### Step 4 — Verify the fix manually

1. In the portal Settings → Benchmarker, set credentials to Endpoint A / Key A.
2. Trigger a Benchmarker tool call (e.g., `organisation_summary`) — confirm it queries Endpoint A.
3. Update portal credentials to Endpoint B / Key B.
4. Trigger another tool call **without restarting the module**.
5. Confirm the call goes to Endpoint B — this would have failed before the fix.

## Performance Impact

The DB lookup on every tool call is a single indexed SELECT on `(user_id, service)` against `user_credentials`. SQLAlchemy's async session factory already pools connections, so this is a fast, low-overhead operation. No meaningful latency increase is expected.

If profiling later shows this to be a bottleneck, a short TTL cache (e.g., 60 seconds using `time.monotonic()`) can be added. It is not needed now.

## What Was NOT Broken

- **Portal `PUT /api/settings/credentials/benchmarker`** — correctly encrypts and upserts new values.
- **`CredentialStore.get_all`** — correctly decrypts and returns latest DB values.
- **`BenchmarkerClient._request`** — correctly uses `self.api_url` and `self.api_key` per HTTP call.
- **DB model / migration** — `user_credentials` table and `UserCredential` ORM model are correct.

## Summary

The fix is a one-file, ~5 line change: remove the `_user_client_cache` dict and its two usages in `_get_client_for_user`. After `make restart-module M=benchmarker`, portal credential updates will take effect on the next tool call with no container restart needed.
