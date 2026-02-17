# Implementation Plan: Add Bitbucket Repos Tab to Portal

## Overview
Add support for displaying Bitbucket repositories alongside GitHub repositories in the portal's repos navigation. When users have Bitbucket credentials configured, show a tabbed interface with separate "GitHub" and "Bitbucket" tabs. Each tab will display repositories from the respective platform.

## Current State Analysis

### Backend Infrastructure
- **git_platform module** (`agent/modules/git_platform/`):
  - Already has `BitbucketProvider` implementation in `providers/bitbucket.py`
  - Has `GitHubProvider` implementation in `providers/github.py`
  - Both implement the common `GitProvider` interface from `providers/base.py`
  - `main.py` currently only checks for GitHub credentials in `_get_tools_for_user()`
  - Module supports both GitHub and Bitbucket at the infrastructure level

### Credential Storage
- **Settings API** (`agent/portal/routers/settings.py`):
  - Defines `SERVICE_DEFINITIONS` for various services
  - Has `atlassian` service with keys: `url`, `username`, `api_token`
  - Bitbucket credentials are NOT currently separate - they could use Atlassian credentials
  - Uses `CredentialStore` for encrypted credential storage

### Frontend
- **ReposPage** (`agent/portal/frontend/src/pages/ReposPage.tsx`):
  - Currently shows a single list of repositories
  - Uses `useRepos` hook to fetch repos
  - No tab interface currently

- **useRepos hook** (`agent/portal/frontend/src/hooks/useRepos.ts`):
  - Calls `/api/repos` endpoint
  - Returns flat list of repos

- **Repos router** (`agent/portal/routers/repos.py`):
  - Proxies to `git_platform` module
  - All endpoints assume single provider

## Implementation Strategy

### Phase 1: Backend - Add Bitbucket Credential Support

**1.1. Update settings.py to add Bitbucket service definition**
- File: `agent/portal/routers/settings.py`
- Add `"bitbucket"` entry to `SERVICE_DEFINITIONS` dict:
  ```python
  "bitbucket": {
      "label": "Bitbucket",
      "keys": [
          {"key": "username", "label": "Bitbucket Username", "type": "text"},
          {"key": "app_password", "label": "App Password", "type": "password"},
      ],
  }
  ```
- This allows users to configure Bitbucket credentials separately from Atlassian

**1.2. Update git_platform module to support multiple providers per user**
- File: `agent/modules/git_platform/main.py`
- Modify `_get_tools_for_user()` to check for both GitHub and Bitbucket credentials:
  ```python
  async def _get_tools_for_user(user_id: str | None, provider: str = "github") -> GitPlatformTools | None:
      """Resolve a GitPlatformTools instance for the given user and provider.

      Priority:
      1. User's stored credentials for the specified provider
      2. Global GIT_PLATFORM_TOKEN env var (fallback)
      """
  ```
- Check for provider-specific credentials (github or bitbucket)
- Return appropriate provider instance or fallback

**1.3. Update execute endpoint to accept provider parameter**
- File: `agent/modules/git_platform/main.py`
- Modify `/execute` to accept optional `provider` argument in tool call arguments
- Default to "github" for backward compatibility
- Pass provider to `_get_tools_for_user()`

### Phase 2: Backend - Add Provider-Specific API Endpoints

**2.1. Add provider detection endpoint**
- File: `agent/portal/routers/repos.py`
- Add new endpoint: `GET /api/repos/providers`
- Returns: `{"providers": ["github", "bitbucket"]}`
- Implementation:
  ```python
  @router.get("/providers")
  async def list_providers(user: PortalUser = Depends(require_auth)) -> dict:
      """List configured git providers for the user."""
      store = _get_credential_store()
      factory = get_session_factory()
      async with factory() as session:
          github_token = await store.get(session, user.user_id, "github", "github_token")
          bb_username = await store.get(session, user.user_id, "bitbucket", "username")
          bb_password = await store.get(session, user.user_id, "bitbucket", "app_password")

      providers = []
      if github_token:
          providers.append("github")
      if bb_username and bb_password:
          providers.append("bitbucket")

      return {"providers": providers}
  ```

**2.2. Modify list_repos endpoint**
- File: `agent/portal/routers/repos.py`
- Add optional `provider` query parameter (default: "github")
- Pass provider to git_platform module tool call
- Update tool call arguments to include provider:
  ```python
  args: dict = {"per_page": per_page, "sort": sort, "provider": provider}
  ```

**2.3. Update all repo endpoints to support provider parameter**
- File: `agent/portal/routers/repos.py`
- Endpoints to update:
  - `GET /repos` - add `provider` query param
  - `POST /repos` - add `provider` to request body
  - `GET /repos/{owner}/{repo}` - add `provider` query param
  - All branch, issue, and PR endpoints - add `provider` query param
- Each endpoint should pass provider to `_safe_call()` arguments

### Phase 3: Frontend - Add Tab Interface

**3.1. Create useProviders hook**
- File: `agent/portal/frontend/src/hooks/useProviders.ts` (new file)
- Implementation:
  ```tsx
  import { useState, useEffect } from "react";
  import { api } from "@/api/client";

  export function useProviders() {
    const [providers, setProviders] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
      async function fetchProviders() {
        try {
          const data = await api<{ providers: string[] }>("/api/repos/providers");
          setProviders(data.providers || []);
          setError(null);
        } catch (e) {
          setError(e instanceof Error ? e.message : "Failed to fetch providers");
          setProviders([]);
        } finally {
          setLoading(false);
        }
      }
      fetchProviders();
    }, []);

    return { providers, loading, error };
  }
  ```

**3.2. Update ReposPage to show tabs when multiple providers exist**
- File: `agent/portal/frontend/src/pages/ReposPage.tsx`
- Add state for active provider:
  ```tsx
  const { providers } = useProviders();
  const [activeProvider, setActiveProvider] = useState<string>("github");
  ```
- Show tab bar only if multiple providers are configured:
  ```tsx
  {providers.length > 1 && (
    <div className="flex gap-1 bg-surface-light rounded-lg p-1 border border-border mb-4">
      {providers.map((provider) => (
        <button
          key={provider}
          onClick={() => setActiveProvider(provider)}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            activeProvider === provider
              ? "bg-accent/15 text-accent-hover"
              : "text-gray-400 hover:text-gray-200"
          }`}
        >
          {provider === 'github' ? 'GitHub' : 'Bitbucket'}
        </button>
      ))}
    </div>
  )}
  ```
- Pass activeProvider to useRepos hook

**3.3. Update useRepos hook to accept provider parameter**
- File: `agent/portal/frontend/src/hooks/useRepos.ts`
- Add `provider` parameter to `useRepos(search, provider)`:
  ```tsx
  export function useRepos(search: string = "", provider: string = "github") {
    // ...
    const fetchRepos = useCallback(async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams({
          per_page: "100",
          sort: "updated",
          provider: provider
        });
        if (search.trim()) params.set("search", search.trim());
        const data = await api<{ count: number; repos: GitRepo[] }>(
          `/api/repos?${params}`
        );
        setRepos(data.repos || []);
        setError(null);
      } catch (e) {
        // ... error handling
      } finally {
        setLoading(false);
      }
    }, [search, provider]);
    // ...
  }
  ```

**3.4. Update RepoDetailPage to handle provider context**
- File: `agent/portal/frontend/src/pages/RepoDetailPage.tsx`
- Add provider query parameter to all API calls:
  ```tsx
  const provider = new URLSearchParams(window.location.search).get("provider") || "github";

  // Pass provider to all api calls
  const data = await api(`/api/repos/${owner}/${repo}?provider=${provider}`);
  ```
- Update navigation to include provider:
  ```tsx
  navigate(`/repos/${repo.owner}/${repo.repo}?provider=${activeProvider}`)
  ```

### Phase 4: Frontend - Credential Setup UI

**4.1. Add Bitbucket credential card**
- File: `agent/portal/frontend/src/components/settings/CredentialCard.tsx`
- Add setup guide for Bitbucket in `SETUP_GUIDES`:
  ```tsx
  bitbucket: {
    title: "Setting up Bitbucket credentials",
    steps: [
      {
        instruction: "Go to Bitbucket Settings > Personal Settings > App passwords",
      },
      {
        instruction: "Create a new app password with 'Repositories: Read' and 'Repositories: Write' permissions",
      },
      {
        instruction: "Enter your Bitbucket username and the generated app password below",
      },
    ],
  }
  ```

**4.2. Update SettingsPage to show Bitbucket credentials**
- File: `agent/portal/frontend/src/pages/SettingsPage.tsx`
- No changes needed - credentials are dynamically loaded from backend
- Verify that Bitbucket service definition appears in credentials tab

### Phase 5: Testing & Polish

**5.1. Test credential flow**
- Add Bitbucket credentials in settings
- Verify credentials are encrypted and stored correctly
- Test credential retrieval and decryption

**5.2. Test repo listing**
- With only GitHub credentials: verify single list (no tabs)
- With only Bitbucket credentials: verify single list or error handling
- With both credentials: verify tab interface appears
- Test search functionality within each provider tab
- Verify repo metadata displays correctly for both providers

**5.3. Test repo detail pages**
- Verify branches, PRs, and issues load correctly for both providers
- Test creating PRs on both platforms
- Test branch deletion on both platforms
- Verify CI status checks work for both providers

**5.4. Error handling**
- Handle case where user has Atlassian creds but no Bitbucket access
- Handle API errors from Bitbucket gracefully
- Show helpful error messages for missing credentials
- Handle provider-specific API differences (e.g., different PR states)

**5.5. UI/UX polish**
- Add provider labels/icons to distinguish GitHub vs Bitbucket repos
- Consider showing provider badge in repo cards
- Update empty states to mention both providers
- Ensure consistent styling across tabs
- Add loading states for tab switches

## Files to Modify

### Backend (Python)
1. `agent/portal/routers/settings.py` - Add Bitbucket service definition
2. `agent/modules/git_platform/main.py` - Support provider parameter in credential lookup
3. `agent/portal/routers/repos.py` - Add provider parameter to all endpoints, add providers endpoint

### Frontend (TypeScript/React)
1. `agent/portal/frontend/src/hooks/useProviders.ts` - New hook for provider detection
2. `agent/portal/frontend/src/hooks/useRepos.ts` - Add provider parameter
3. `agent/portal/frontend/src/pages/ReposPage.tsx` - Add tab interface
4. `agent/portal/frontend/src/pages/RepoDetailPage.tsx` - Handle provider context
5. `agent/portal/frontend/src/components/settings/CredentialCard.tsx` - Add Bitbucket guide

### Optional/Future Enhancements
1. `agent/portal/frontend/src/types/index.ts` - Add provider type definitions
2. `agent/portal/frontend/src/hooks/useRepoDetail.ts` - Add provider parameter
3. `agent/portal/frontend/src/components/common/RepoLabel.tsx` - Add provider badge

## Alternative Approaches Considered

### Approach A: Unified Credential Lookup
- Use Atlassian credentials for Bitbucket access (since user mentioned they have Atlassian setup)
- Pros: Reuses existing credentials, no new credential service needed
- Cons: Assumes Atlassian credentials always include Bitbucket access, less flexible

### Approach B: Separate Bitbucket Service (Chosen)
- Create dedicated Bitbucket credential service
- Pros: Clear separation, flexible for users with different accounts
- Cons: Slight duplication if user uses same credentials

### Approach C: Provider Selection Per Repo
- Let users specify provider when navigating to repo
- Pros: More flexible, could support same repo name on different platforms
- Cons: More complex UX, potential confusion

## Implementation Order Rationale

1. **Backend first**: Establish credential storage and provider support before frontend changes
2. **Endpoint updates**: Ensure API can handle provider parameter before UI depends on it
3. **Frontend tabs**: Add UI after backend is ready to serve provider-specific data
4. **Polish last**: Get core functionality working before perfecting UX

## Risk Mitigation

1. **Backward compatibility**: Default provider to "github" to avoid breaking existing functionality
2. **Graceful degradation**: If only one provider configured, show single list (no tabs)
3. **Error boundaries**: Wrap provider-specific components in error boundaries
4. **Credential validation**: Validate credentials before attempting to fetch repos
5. **Provider fallback**: If provider-specific call fails, show helpful error message

## Success Criteria

- [ ] Users can configure Bitbucket credentials in settings
- [ ] Repos page shows tabs when both GitHub and Bitbucket are configured
- [ ] Each tab displays repos from the respective provider
- [ ] All repo operations (view, branches, PRs, issues) work for both providers
- [ ] UI clearly indicates which provider each repo belongs to
- [ ] Error handling provides clear guidance when credentials are missing or invalid
- [ ] Existing GitHub-only functionality remains unchanged when Bitbucket is not configured

## Estimated Complexity

- Backend changes: **Medium** (3-4 hours)
  - Credential service: Simple addition
  - Provider routing: Moderate refactor of existing code

- Frontend changes: **Medium** (4-5 hours)
  - Tab interface: Similar to existing patterns
  - Hook updates: Straightforward parameter additions
  - Provider detection: New logic but simple

- Testing & Polish: **Low-Medium** (2-3 hours)
  - Credential flow: Standard testing
  - Multi-provider scenarios: Need to test combinations

**Total Estimate**: 9-12 hours

## Notes

- BitbucketProvider already exists and is fully implemented
- Main work is credential management and UI plumbing
- Consider adding provider icons (GitHub/Bitbucket logos) for better visual distinction
- May want to cache provider list in frontend to avoid repeated API calls
- Consider adding "Configure Credentials" button in empty state when no providers are set up
