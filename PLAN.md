# Implementation Plan: Move Benchmarker Credentials to Portal Settings

## Overview
This plan details the migration of Benchmarker module authentication from environment variables (`BENCHMARKER_API_URL`, `BENCHMARKER_API_KEY`) to per-user credentials stored in the portal settings, following the established pattern used by Garmin, Renpho, and Atlassian modules.

## Current State Analysis

### Benchmarker Module (Current)
- **Location**: `agent/modules/benchmarker/`
- **Initialization**: `main.py` lines 32-35 - Creates a single global `BenchmarkerClient` using env vars from `settings.benchmarker_api_url` and `settings.benchmarker_api_key`
- **Credential Source**: Environment variables only (no per-user support)
- **Tools**: 9 tools including device_lookup, send_downlink, organisation_summary, etc.

### Configuration (`agent/shared/shared/config.py`)
- Lines 124-126: Defines `benchmarker_api_url` and `benchmarker_api_key` as global settings
- These are loaded from `.env` file via pydantic-settings

### Credential Infrastructure (Existing)
- **Database Table**: `user_credentials` - stores encrypted per-user service credentials
- **Model**: `agent/shared/shared/models/user_credential.py` - UserCredential ORM model
- **Store**: `agent/shared/shared/credential_store.py` - CredentialStore class with Fernet encryption
- **Portal API**: `agent/portal/routers/settings.py` - REST endpoints for credential CRUD
- **Portal Frontend**: Settings page with credential management UI

## Reference Implementation: Garmin Module

The Garmin module (`agent/modules/garmin/main.py`) provides the pattern to follow:

1. **Global Variables** (lines 45-52):
   - `_credential_store` - for encrypted credential access
   - `_session_factory` - for database sessions
   - `_fallback_tools` - tools initialized from env vars (fallback)
   - `_user_tools_cache` - per-user tools cache to preserve sessions

2. **User Credential Resolver** (`_get_tools_for_user` function, lines 55-82):
   - Accepts `user_id` parameter
   - Looks up user credentials from credential store
   - Returns cached instance if available
   - Falls back to global env vars if user creds not found
   - Handles errors gracefully with logging

3. **Startup Logic** (lines 84-107):
   - Initializes credential store if encryption key is configured
   - Sets up fallback tools from env vars
   - Logs initialization mode

4. **Execute Endpoint** (lines 115-144):
   - Extracts `user_id` from ToolCall
   - Resolves tools for user via `_get_tools_for_user`
   - Returns helpful error if no credentials configured
   - Executes tool method with resolved tools

## Implementation Steps

### 1. Update Portal Settings Definition
**File**: `agent/portal/routers/settings.py`

**Changes**:
- Add `"benchmarker"` entry to `SERVICE_DEFINITIONS` dict (after line 89)
- Define credential keys:
  - `api_url` - Instance URL (type: text)
  - `api_key` - API Key (type: password)

**Code to Add**:
```python
"benchmarker": {
    "label": "Benchmarker IoT Platform",
    "keys": [
        {"key": "api_url", "label": "API URL", "type": "text"},
        {"key": "api_key", "label": "API Key", "type": "password"},
    ],
},
```

**Location**: After the `atlassian` definition (line 89)

**Rationale**: This makes the benchmarker service discoverable in the portal UI and defines what credentials are needed.

---

### 2. Refactor Benchmarker Module - main.py
**File**: `agent/modules/benchmarker/main.py`

**Changes Required**:

#### 2.1 Add Imports (lines 3-13)
Add missing imports:
```python
import uuid
from pathlib import Path
```

Add credential store imports:
```python
from shared.credential_store import CredentialStore
from shared.database import get_session_factory
```

#### 2.2 Remove Global Client (lines 26-36)
**Remove**:
```python
settings = get_settings()
client: BenchmarkerClient | None = None

@app.on_event("startup")
async def startup():
    global client
    client = BenchmarkerClient(
        api_url=settings.benchmarker_api_url,
        api_key=settings.benchmarker_api_key,
    )
    logger.info("benchmarker_module_ready")
```

#### 2.3 Add Per-User Credential Infrastructure (after line 25)
**Add**:
```python
# Credential store for per-user lookup
_credential_store: CredentialStore | None = None
_session_factory = None

# Fallback: global client built from env vars
_fallback_client: BenchmarkerClient | None = None

# Cache per-user clients to preserve authentication state
_user_client_cache: dict[str, BenchmarkerClient] = {}


async def _get_client_for_user(user_id: str | None) -> BenchmarkerClient | None:
    """Resolve a BenchmarkerClient instance for the given user.

    Priority:
    1. User's stored Benchmarker credentials from credential store
    2. Global BENCHMARKER_API_URL/BENCHMARKER_API_KEY env vars (fallback)
    """
    if user_id and _credential_store and _session_factory:
        # Return cached instance if available
        if user_id in _user_client_cache:
            return _user_client_cache[user_id]

        try:
            uid = uuid.UUID(user_id)
            async with _session_factory() as session:
                creds = await _credential_store.get_all(session, uid, "benchmarker")
            api_url = creds.get("api_url")
            api_key = creds.get("api_key")
            if api_url and api_key:
                client = BenchmarkerClient(api_url=api_url, api_key=api_key)
                _user_client_cache[user_id] = client
                return client
        except Exception as e:
            logger.warning("user_credential_lookup_failed", user_id=user_id, error=str(e))

    return _fallback_client


@app.on_event("startup")
async def startup():
    global _fallback_client, _credential_store, _session_factory

    settings = get_settings()

    # Set up credential store for per-user lookup
    if settings.credential_encryption_key:
        try:
            _credential_store = CredentialStore(settings.credential_encryption_key)
            _session_factory = get_session_factory()
            logger.info("benchmarker_credential_store_ready")
        except Exception as e:
            logger.warning("credential_store_init_failed", error=str(e))

    # Set up fallback from env vars
    api_url = settings.benchmarker_api_url
    api_key = settings.benchmarker_api_key
    if api_url and api_key:
        _fallback_client = BenchmarkerClient(api_url=api_url, api_key=api_key)
        logger.info("benchmarker_module_ready", mode="global_fallback")
    else:
        logger.info(
            "benchmarker_no_global_creds",
            msg="No BENCHMARKER_API_URL/API_KEY — will use per-user credentials only"
        )
```

**Rationale**:
- Follows Garmin pattern exactly
- Maintains backward compatibility with env vars
- Caches clients per user to preserve authentication state
- Graceful fallback if per-user creds unavailable

#### 2.4 Update Execute Endpoint (lines 45-82)
**Replace entire `execute` function with**:
```python
@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        user_id = args.pop("user_id", None) or call.user_id

        # Resolve client for user
        client = await _get_client_for_user(user_id)
        if client is None:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error="No Benchmarker credentials configured. Add API URL and API Key in Portal Settings, or set BENCHMARKER_API_URL and BENCHMARKER_API_KEY in .env.",
            )

        # Route to appropriate tool method
        if tool_name == "device_lookup":
            result = await client.device_lookup(**args)
        elif tool_name == "send_downlink":
            result = await client.send_downlink(**args)
        elif tool_name == "organisation_summary":
            result = await client.organisation_summary(**args)
        elif tool_name == "site_overview":
            result = await client.site_overview(**args)
        elif tool_name == "silent_devices":
            result = await client.silent_devices(**args)
        elif tool_name == "low_battery_devices":
            result = await client.low_battery_devices(**args)
        elif tool_name == "device_issues":
            result = await client.device_issues(**args)
        elif tool_name == "org_issues_summary":
            result = await client.org_issues_summary(**args)
        elif tool_name == "provision_organisation":
            result = await client.provision_organisation(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error="Internal error processing request")
```

**Rationale**:
- Extracts `user_id` from ToolCall (core orchestrator injects this)
- Resolves appropriate client for the user
- Provides clear error message if no credentials configured
- Maintains existing tool routing logic
- Improved error handling with logging

---

### 3. Frontend Updates (Optional - UI Already Supports It)

**Files**: `agent/portal/frontend/src/components/settings/ConnectedAccounts.tsx`, `CredentialCard.tsx`

**No Changes Required**: The existing credential management UI is service-agnostic and will automatically display the Benchmarker service once it's added to `SERVICE_DEFINITIONS`. The UI:
- Fetches service list from `/api/settings/credentials`
- Renders credential cards for each service
- Provides forms for entering credentials based on `key_definitions`
- Handles save/delete operations

**Verification**: After backend changes, the Benchmarker service will appear in the Settings page under "Connected Accounts" with fields for API URL and API Key.

---

### 4. Documentation Updates

**File**: `agent/docs/modules/benchmarker.md` (if exists, otherwise create)

**Updates Needed**:
- Add section on credential configuration
- Document both portal-based and env-var methods
- Include setup instructions
- Note that per-user credentials override global env vars

**File**: `CLAUDE.md` or `README.md`

**Updates Needed**:
- Update Benchmarker module description to note per-user credential support
- Remove requirement for global env vars (now optional)

---

### 5. Configuration Cleanup (Optional)

**File**: `agent/shared/shared/config.py`

**Current** (lines 124-126):
```python
# Benchmarker
benchmarker_api_url: str = ""
benchmarker_api_key: str = ""
```

**Recommended**: Keep these as-is for backward compatibility. They serve as fallback when per-user credentials aren't configured.

**Optional Enhancement**: Add comment to clarify fallback behavior:
```python
# Benchmarker (fallback credentials - users can configure per-user credentials in portal)
benchmarker_api_url: str = ""
benchmarker_api_key: str = ""
```

---

### 6. Environment Variable Documentation

**File**: `agent/.env.example` (if exists)

**Update**:
```env
# Benchmarker IoT Platform (optional - users can configure in portal settings)
BENCHMARKER_API_URL=https://your-benchmarker-instance.com
BENCHMARKER_API_KEY=your_api_key_here
```

---

## Testing Plan

### 1. Unit Tests (if test suite exists)
**Location**: `agent/modules/benchmarker/tests/` (create if needed)

**Test Cases**:
- `test_user_credential_lookup_success` - User has credentials in DB
- `test_user_credential_lookup_missing` - User has no credentials, falls back to env
- `test_client_caching` - Same user_id returns cached client
- `test_no_credentials_error` - Neither user nor global creds exist
- `test_credential_priority` - User creds override global env vars

### 2. Integration Testing

**Scenario 1: Global Credentials Only**
1. Set `BENCHMARKER_API_URL` and `BENCHMARKER_API_KEY` in `.env`
2. Restart benchmarker module
3. Execute a tool (e.g., `benchmarker.device_lookup`) without user credentials
4. Verify it uses global credentials

**Scenario 2: Per-User Credentials**
1. Log into portal with test user
2. Navigate to Settings → Connected Accounts
3. Verify "Benchmarker IoT Platform" appears in service list
4. Enter API URL and API Key
5. Save credentials
6. Execute a benchmarker tool via chat/API
7. Verify it uses user's credentials (check logs)

**Scenario 3: Credential Priority**
1. Configure both global env vars AND per-user credentials
2. Execute tool as that user
3. Verify per-user credentials are used (check logs for `user_credential_lookup_failed` absence)

**Scenario 4: No Credentials**
1. Remove global env vars
2. Execute tool as user without credentials
3. Verify error message: "No Benchmarker credentials configured..."

**Scenario 5: Credential Update**
1. Update user credentials in portal
2. Clear cache or use different tool to trigger new request
3. Verify new credentials are used

### 3. Manual Testing Checklist

- [ ] Portal UI displays Benchmarker in Connected Accounts
- [ ] Can save Benchmarker credentials via portal
- [ ] Can view configured services (without showing secrets)
- [ ] Can delete Benchmarker credentials
- [ ] Tools work with per-user credentials
- [ ] Tools fall back to global env vars when user creds missing
- [ ] Error message is helpful when no credentials exist
- [ ] Logs show correct credential source (user vs fallback)
- [ ] Multiple users can have different Benchmarker credentials
- [ ] Client caching works (no redundant auth attempts)

---

## Migration Path for Existing Users

### Phase 1: Deploy with Backward Compatibility
1. Deploy updated code
2. Existing deployments continue using env vars (fallback mechanism)
3. No immediate action required from users

### Phase 2: User Migration (Optional)
1. Users can optionally move credentials to portal settings
2. Per-user credentials override env vars
3. Multi-user environments benefit from per-user configuration

### Phase 3: Deprecation (Future)
1. After sufficient adoption, consider deprecating global env vars
2. Log warnings if only global creds are configured
3. Eventually remove fallback mechanism (breaking change)

**Recommendation**: Keep fallback indefinitely for single-user deployments and backward compatibility.

---

## Risk Assessment

### Low Risk Items
- ✅ Pattern is well-established (Garmin, Renpho, Atlassian)
- ✅ Backward compatible (env vars still work)
- ✅ No database migrations required (uses existing `user_credentials` table)
- ✅ No changes to tool interfaces or manifests
- ✅ Frontend already supports arbitrary services

### Medium Risk Items
- ⚠️ **Client Caching**: If caching logic has bugs, credentials might not refresh when updated
  - **Mitigation**: Follow Garmin pattern exactly, which is proven in production
  - **Mitigation**: Add cache invalidation if credential update detected

- ⚠️ **Error Handling**: Credential lookup failures must gracefully fall back
  - **Mitigation**: Wrap credential lookup in try/except with logging
  - **Mitigation**: Always return fallback client if user lookup fails

### Testing Gaps
- No existing test suite for benchmarker module
- Need to manually verify credential priority and fallback behavior
- Recommend adding automated tests post-deployment

---

## Rollback Plan

If issues arise:

1. **Immediate Rollback**: Revert `agent/modules/benchmarker/main.py` to use global client
2. **Partial Rollback**: Keep portal settings definition, disable per-user lookup by commenting out credential store initialization
3. **Data Rollback**: Not needed - user credentials are additive, no data loss

**Rollback Command**:
```bash
git revert <commit-hash>
make restart-module M=benchmarker
```

---

## Implementation Order

1. ✅ **Update Portal Settings** (`settings.py`) - 5 minutes
   - Lowest risk, enables UI immediately

2. ✅ **Refactor Benchmarker Module** (`main.py`) - 30 minutes
   - Core implementation following Garmin pattern

3. ✅ **Update Documentation** - 15 minutes
   - Helps users understand new capability

4. ✅ **Test Locally** - 30 minutes
   - Verify both credential sources work

5. ✅ **Deploy to Staging/Dev** - 5 minutes
   - Test in realistic environment

6. ✅ **Deploy to Production** - 5 minutes
   - Zero downtime, backward compatible

**Total Estimated Time**: 90 minutes

---

## Success Criteria

- [x] Portal UI shows Benchmarker service in Connected Accounts
- [x] Users can save/update/delete Benchmarker credentials via portal
- [x] Tools execute successfully with per-user credentials
- [x] Fallback to env vars works when user credentials absent
- [x] Error messages are clear and actionable
- [x] No breaking changes to existing deployments
- [x] Logs indicate which credential source is being used
- [x] Multiple users can configure different Benchmarker instances

---

## Files to Modify

### Backend
1. **`agent/portal/routers/settings.py`**
   - Add benchmarker to SERVICE_DEFINITIONS (5 lines)

2. **`agent/modules/benchmarker/main.py`**
   - Add imports (3 lines)
   - Replace global client with per-user infrastructure (~80 lines)
   - Update execute endpoint (~50 lines)
   - Net change: ~100 lines

### Documentation
3. **`agent/docs/modules/benchmarker.md`** (create if missing)
   - Document credential configuration options

4. **`CLAUDE.md`** (optional)
   - Update benchmarker module description

### Configuration
5. **`agent/.env.example`** (if exists)
   - Add comment about optional env vars

---

## Post-Implementation Tasks

1. **Monitor Logs**: Check for `user_credential_lookup_failed` errors
2. **User Communication**: Notify users of new capability (optional)
3. **Metrics**: Track adoption of per-user credentials vs env vars
4. **Future Enhancement**: Add credential validation endpoint (test API connectivity)
5. **Future Enhancement**: Add UI indicator for credential health (valid/expired/invalid)

---

## Notes

- This change is **additive** - no existing functionality is removed
- Users with single-user deployments can continue using env vars indefinitely
- Multi-tenant or multi-user environments gain per-user credential isolation
- Pattern is consistent with other modules (Garmin, Renpho, Atlassian)
- No database migrations required
- No frontend changes required
- Zero downtime deployment possible

---

## Appendix: Credential Flow Diagram

```
User Message with Benchmarker Tool Call
    ↓
Core Orchestrator (/execute)
    ↓
ToolCall with user_id injected
    ↓
Benchmarker Module (/execute)
    ↓
_get_client_for_user(user_id)
    ↓
    ├─→ User credentials in DB?
    │   ├─→ YES: Return cached or new BenchmarkerClient(user_api_url, user_api_key)
    │   └─→ NO: Continue to fallback
    │
    └─→ Env vars configured?
        ├─→ YES: Return _fallback_client
        └─→ NO: Return None (error: "No credentials configured")
    ↓
Execute tool method with resolved client
    ↓
Return ToolResult
```

---

## Conclusion

This implementation plan provides a detailed, step-by-step approach to migrating Benchmarker credentials from environment variables to per-user portal settings. The approach:

- Follows established patterns from other modules
- Maintains backward compatibility
- Requires minimal code changes
- Poses low risk
- Provides immediate value for multi-user deployments
- Can be implemented and deployed in under 2 hours

The plan is ready for execution.
