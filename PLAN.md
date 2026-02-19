# Plan: User-Configurable LLM API Keys & Model Settings

## Overview

Allow portal users to enter their own Anthropic/OpenAI/Google API keys and choose
preferred models in a new "LLM Settings" tab on the Settings page.

**Behaviour rules:**
- If a user has stored their own API keys, those keys are used for their requests
  and **token budget enforcement is bypassed** (they pay directly to the provider).
- Usage (token counts) is still recorded for analytics — only the budget *gate* is
  skipped.
- If no personal keys are stored, the system falls back to the env-var keys as
  today, and the normal budget limit applies.

---

## Architecture

The personal API keys and model preferences are stored using the **existing
`UserCredential` / `CredentialStore` infrastructure** — the same encrypted-at-rest
store already used for GitHub, Garmin, Atlassian, etc.  No new database table is
needed.

A new credential service key `"llm_settings"` will hold:

| `credential_key`        | Example value                         |
|-------------------------|---------------------------------------|
| `anthropic_api_key`     | `sk-ant-...`                          |
| `openai_api_key`        | `sk-...`                              |
| `google_api_key`        | `AIza...`                             |
| `default_model`         | `claude-sonnet-4-20250514`            |
| `summarization_model`   | `gpt-4o-mini`                         |
| `embedding_model`       | `text-embedding-3-small`              |

The core orchestrator's `AgentLoop` will look up the user's personal credentials
before calling `LLMRouter`, and if found, instantiate a **per-request
`LLMRouter`** that uses the user's keys instead of the global one.

---

## Files to Create / Modify

### 1. `agent/portal/routers/settings.py` — add `llm_settings` service definition

Add a new entry to `SERVICE_DEFINITIONS`:

```python
"llm_settings": {
    "label": "LLM API Keys & Models",
    "keys": [
        {"key": "anthropic_api_key",   "label": "Anthropic API Key",   "type": "password"},
        {"key": "openai_api_key",       "label": "OpenAI API Key",      "type": "password"},
        {"key": "google_api_key",       "label": "Google API Key",      "type": "password"},
        {"key": "default_model",        "label": "Default Chat Model",  "type": "text"},
        {"key": "summarization_model",  "label": "Summarisation Model", "type": "text"},
        {"key": "embedding_model",      "label": "Embedding Model",     "type": "text"},
    ],
},
```

The generic `PUT /api/settings/credentials/llm_settings` endpoint already handles
save/delete for any service listed in `SERVICE_DEFINITIONS`, so no new route code
is needed.

Add a new convenience endpoint:

```
GET /api/settings/llm-settings/status
```

Returns whether personal keys are configured and which providers are active, so
the frontend can show a status badge. No secret values are returned.

### 2. `agent/shared/shared/llm_settings_resolver.py` *(new file)*

A small helper module used by the core orchestrator that retrieves a user's
personal LLM credentials and, if present, builds an override `Settings`-like
object that the `LLMRouter` can be constructed from.

```python
async def get_user_llm_overrides(
    session: AsyncSession,
    user_id: uuid.UUID,
    credential_store: CredentialStore,
) -> dict | None:
    """
    Returns a dict of overrides or None if no personal keys are configured.
    Keys: anthropic_api_key, openai_api_key, google_api_key,
          default_model, summarization_model, embedding_model
    Only populated keys are included — absent keys fall back to global settings.
    """
```

This module lives in `shared/` so both core and portal can import it without
circular dependencies.

### 3. `agent/core/orchestrator/agent_loop.py` — per-user LLM router

Modify `AgentLoop.__init__` to accept and store the `CredentialStore` (instantiated
in core `startup()`).

Modify `_run_inner` (after `_resolve_user`, before building context):

```python
# Attempt to load user's personal LLM settings
from shared.llm_settings_resolver import get_user_llm_overrides
from core.llm_router.router import LLMRouter as _LLMRouter

user_overrides = await get_user_llm_overrides(session, user.id, self.credential_store)
if user_overrides:
    # Build a one-off Settings object with the user's keys merged over globals
    user_settings = self.settings.model_copy(update=user_overrides)
    active_router = _LLMRouter(user_settings)
    user_has_own_keys = True
else:
    active_router = self.llm_router
    user_has_own_keys = False
```

All `await active_router.chat(...)` and `await active_router.embed(...)` calls in
the loop use `active_router` instead of `self.llm_router`.

Modify `_check_budget` call site:

```python
# Skip budget gate when user brings their own keys
if not user_has_own_keys and not self._check_budget(user):
    return AgentResponse(
        content="You've exceeded your monthly token budget. ..."
    )
```

Token logging is unchanged — usage is always recorded regardless of key source.

### 4. `agent/core/main.py` — pass CredentialStore to AgentLoop

In `startup()`:

```python
from shared.credential_store import CredentialStore

cred_store = None
if settings.credential_encryption_key:
    cred_store = CredentialStore(settings.credential_encryption_key)

agent_loop = AgentLoop(
    settings=settings,
    llm_router=llm_router,
    tool_registry=tool_registry,
    context_builder=context_builder,
    session_factory=session_factory,
    credential_store=cred_store,   # NEW
)
```

If `credential_encryption_key` is not set, `cred_store` is `None`; the agent loop
treats that as "no personal keys available" and uses the global router.

### 5. `agent/portal/frontend/src/pages/SettingsPage.tsx` — new "LLM Settings" tab

Add a fifth tab `"llm"` alongside Appearance / Credentials / Accounts / Profile.

The tab content shows:
- A card with three password fields: Anthropic API Key, OpenAI API Key, Google API Key.
- A card with three text fields: Default Model, Summarisation Model, Embedding Model.
- A "Save" button that calls `PUT /api/settings/credentials/llm_settings` with the
  non-empty values.
- A "Clear" button per-section (calls `DELETE /api/settings/credentials/llm_settings`).
- A status banner: "Using your own API keys — token budget not enforced" (green) or
  "Using shared keys — budget limits apply" (yellow).

The tab fetches `GET /api/settings/llm-settings/status` on mount to populate the
banner and pre-fill model fields from stored values (API key fields remain empty
for security — only show placeholder `••••••` if configured).

Model name inputs include a small hint text listing example valid model strings for
each provider.

### 6. `agent/portal/frontend/src/components/settings/LlmSettingsCard.tsx` *(new)*

Extracted React component for the LLM settings form to keep `SettingsPage.tsx`
manageable. Accepts props: `onUpdate: () => void`.

---

## Detailed Step-by-Step Implementation

### Step 1 — Backend: add `llm_settings` to credential service definitions
**File:** `agent/portal/routers/settings.py`

- Insert `"llm_settings"` into `SERVICE_DEFINITIONS` dict (see schema above).
- Add `GET /api/settings/llm-settings/status` endpoint that:
  1. Calls `store.get_all(session, user.user_id, "llm_settings")`.
  2. Returns `{ configured_keys: [...], has_anthropic, has_openai, has_google,
     default_model, summarization_model, embedding_model }`.
  - Does not return raw key values.

### Step 2 — Shared helper: `llm_settings_resolver.py`
**File:** `agent/shared/shared/llm_settings_resolver.py` *(new)*

```python
from __future__ import annotations
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from shared.credential_store import CredentialStore

async def get_user_llm_overrides(
    session: AsyncSession,
    user_id: uuid.UUID,
    credential_store: CredentialStore | None,
) -> dict | None:
    if credential_store is None:
        return None
    creds = await credential_store.get_all(session, user_id, "llm_settings")
    if not creds:
        return None

    # Only include keys that are actually present
    KEY_MAP = {
        "anthropic_api_key": "anthropic_api_key",
        "openai_api_key": "openai_api_key",
        "google_api_key": "google_api_key",
        "default_model": "default_model",
        "summarization_model": "summarization_model",
        "embedding_model": "embedding_model",
    }
    overrides = {dst: creds[src] for src, dst in KEY_MAP.items() if src in creds}
    # Only meaningful if at least one API key is present
    has_key = any(k in overrides for k in ("anthropic_api_key", "openai_api_key", "google_api_key"))
    return overrides if has_key else None
```

### Step 3 — Core: wire CredentialStore into AgentLoop
**Files:** `agent/core/main.py`, `agent/core/orchestrator/agent_loop.py`

- `AgentLoop.__init__` gets a new optional parameter: `credential_store: CredentialStore | None = None`.
- `startup()` in `main.py` instantiates `CredentialStore` if `credential_encryption_key`
  is set, and passes it to `AgentLoop`.

### Step 4 — Core: per-request router + budget bypass
**File:** `agent/core/orchestrator/agent_loop.py`

In `_run_inner`, after resolving the user and before the budget check:

```python
user_overrides = await get_user_llm_overrides(
    session, user.id, self.credential_store
)
if user_overrides:
    user_settings = self.settings.model_copy(update=user_overrides)
    active_router = LLMRouter(user_settings)
    user_has_own_keys = True
else:
    active_router = self.llm_router
    user_has_own_keys = False

# Budget check — skip if user brings own keys
if not user_has_own_keys and not self._check_budget(user):
    return AgentResponse(
        content="You've exceeded your monthly token budget. ..."
    )
```

Replace `self.llm_router.chat(...)` with `active_router.chat(...)` in the loop.

> **Note:** `ContextBuilder` also calls `llm_router.embed()` internally for semantic
> memory retrieval. Pass `active_router` into `ContextBuilder.build()` so embeddings
> also use the user's keys when available. The `ContextBuilder.build()` signature
> needs a new optional `llm_router` parameter that overrides `self.llm_router` when
> provided.

### Step 5 — Frontend: new LLM Settings tab
**Files:** `agent/portal/frontend/src/pages/SettingsPage.tsx`,
`agent/portal/frontend/src/components/settings/LlmSettingsCard.tsx` *(new)*

- Add tab definition and conditional render block in `SettingsPage.tsx`.
- `LlmSettingsCard` manages its own local form state with three sections:
  1. **API Keys** — three password inputs. Populated with empty string on load
     (never show stored values), but show "Configured" badge if key exists.
  2. **Model Preferences** — three text inputs. Pre-filled from status endpoint.
  3. Saves via `PUT /api/settings/credentials/llm_settings`.
  4. Fetches status from `GET /api/settings/llm-settings/status` on mount/update.

---

## Data Flow Diagram

```
User submits API keys in portal
    │
    ▼
PUT /api/settings/credentials/llm_settings
    │  (portal routers/settings.py)
    │  Fernet-encrypt → user_credentials table
    │  service="llm_settings", key="anthropic_api_key", ...
    ▼
User sends a chat message
    │
    ▼
AgentLoop._run_inner()
    ├── _resolve_user()
    ├── get_user_llm_overrides()  ← reads user_credentials, decrypts
    │       has keys?
    │       ├── YES → build one-off LLMRouter(user_keys)
    │       │         user_has_own_keys = True
    │       └── NO  → use global LLMRouter
    │                 user_has_own_keys = False
    ├── budget check  ← skipped if user_has_own_keys
    ├── ... context build, tool loop ...
    ├── active_router.chat(...)  ← uses user's keys OR global keys
    └── token_log saved always (analytics)
```

---

## No New Migration Required

The `user_credentials` table already supports arbitrary `(service, credential_key)`
pairs. Storing `service="llm_settings"` rows requires no schema change.

---

## ContextBuilder Note

`agent/core/orchestrator/context_builder.py` holds a reference to `llm_router`
for embed calls (semantic memory search). The cleanest change is to add an optional
`llm_router` override parameter to `ContextBuilder.build()`:

```python
async def build(
    self,
    ...,
    llm_router: LLMRouter | None = None,   # NEW — overrides self.llm_router
) -> list[dict]:
    router = llm_router or self.llm_router
    ...
```

The call site in `agent_loop.py` passes `active_router` here.

---

## Summary of Files Changed / Created

| File | Change |
|---|---|
| `agent/portal/routers/settings.py` | Add `llm_settings` to `SERVICE_DEFINITIONS`; add status endpoint |
| `agent/shared/shared/llm_settings_resolver.py` | **New** — helper to fetch/decode user LLM overrides |
| `agent/core/orchestrator/agent_loop.py` | Accept `credential_store`; per-request router; budget bypass |
| `agent/core/orchestrator/context_builder.py` | Accept optional `llm_router` override in `build()` |
| `agent/core/main.py` | Instantiate `CredentialStore`; pass to `AgentLoop` |
| `agent/portal/frontend/src/pages/SettingsPage.tsx` | Add "LLM Settings" tab |
| `agent/portal/frontend/src/components/settings/LlmSettingsCard.tsx` | **New** — React form component |

No Alembic migration, no new Docker service, no new environment variables required.
