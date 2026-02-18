# Implementation Plan: OAuth Flow for Git Tokens

## Overview

This plan details the implementation of OAuth authentication flows for GitHub and Bitbucket to replace the current manual PAT (Personal Access Token) and SSH key pasting workflow in the portal. The implementation will mirror the existing Claude Code OAuth flow pattern (PKCE) already proven in the codebase.

## Current State Analysis

### Existing Authentication Methods

**GitHub (PAT + SSH)**
- Service: `github`
- Credential keys:
  - `github_token` (PAT) — pasted manually from GitHub Settings
  - `ssh_private_key` (optional) — pasted from `~/.ssh/id_ed25519`
  - `git_author_name` — git commit identity
  - `git_author_email` — git commit identity
- Usage: PAT used for GitHub REST API calls in `GitHubProvider`
- Location: `agent/modules/git_platform/providers/github.py`

**Bitbucket (via Atlassian)**
- Service: `atlassian`
- Credential keys:
  - `url` — Atlassian instance URL
  - `username` — email
  - `api_token` — Atlassian API token
- Usage: HTTP Basic Auth in `BitbucketProvider`
- Location: `agent/modules/git_platform/providers/bitbucket.py`

### Existing OAuth Infrastructure

The portal already has two OAuth systems that provide proven patterns:

**1. Portal Login OAuth** (`agent/portal/oauth_providers.py`)
- Providers: Discord, Google, Slack
- Flow: Standard authorization code flow
- Pattern:
  - `OAuthProvider` abstract base class
  - `get_auth_url(redirect_uri)` — builds authorization URL
  - `exchange_code(code, redirect_uri)` — exchanges code for tokens
  - Returns normalized `OAuthUserProfile`

**2. Claude Code OAuth** (`agent/portal/claude_oauth.py`)
- Provider: Anthropic
- Flow: PKCE (Proof Key for Code Exchange) for public client
- Pattern:
  - `generate_pkce()` — creates verifier + challenge
  - `build_authorize_url(challenge, state)` — builds auth URL
  - `exchange_code(code, verifier, state)` — exchanges with verifier
  - `refresh_access_token(refresh_token)` — token refresh
  - PKCE state stored in Redis (10-minute TTL)
  - Frontend flow:
    1. User clicks "Connect"
    2. Backend generates PKCE, returns auth URL
    3. New tab opens, user authorizes
    4. User copies code, pastes back
    5. Backend exchanges code for tokens
- Endpoints:
  - `POST /api/settings/credentials/claude_code/oauth/start`
  - `POST /api/settings/credentials/claude_code/oauth/exchange`
  - `POST /api/settings/credentials/claude_code/oauth/refresh`
  - `GET /api/settings/credentials/claude_code/status`

## Design Decisions

### OAuth Flow Selection

**GitHub**: Use standard authorization code flow with client secret (web application flow)
- GitHub supports both public (PKCE) and confidential (with secret) clients
- Since the portal backend is a confidential environment, we can use client secret
- Simpler than PKCE (no verifier/challenge management)
- Requires GitHub OAuth App registration

**Bitbucket**: Use standard authorization code flow with client secret
- Bitbucket Cloud OAuth 2.0 supports web application flow
- Requires Bitbucket OAuth Consumer registration
- Separate from Atlassian Cloud (Jira/Confluence) — different OAuth provider

### Why Not PKCE for Git Providers?

PKCE is designed for public clients (mobile apps, SPAs, CLI tools) where the client secret cannot be kept confidential. The portal is a traditional web application with a backend server, so:
- Client secret can be stored securely in environment variables
- Standard authorization code flow is simpler and well-supported
- No need to manage verifier/challenge in Redis
- Both GitHub and Bitbucket support this flow

### Architecture Approach

**Option A: Generic Git OAuth Module**
- Create `agent/portal/git_oauth.py` with abstract `GitOAuthProvider` base class
- Implement `GitHubOAuthProvider` and `BitbucketOAuthProvider`
- Pros: Clean abstraction, reusable for future providers (GitLab, etc.)
- Cons: More initial setup

**Option B: Provider-Specific Implementations**
- Add GitHub OAuth directly to `oauth_providers.py`
- Add Bitbucket OAuth separately
- Pros: Faster to implement, follows existing pattern
- Cons: Less reusable

**Decision**: Use Option A for better long-term maintainability and consistency with existing OAuth provider abstraction.

### Token Storage Strategy

**What to Store**:
- GitHub:
  - `github_token` — OAuth access token (replaces PAT)
  - `github_refresh_token` — for token renewal (optional, GitHub doesn't expire tokens by default unless configured)
  - Keep existing: `ssh_private_key`, `git_author_name`, `git_author_email`
- Bitbucket:
  - `bitbucket_token` — OAuth access token
  - `bitbucket_refresh_token` — Bitbucket tokens expire in 2 hours, refresh tokens in 30 days
  - Keep existing Atlassian credentials for Jira/Confluence access

**Why Separate Storage**:
- Bitbucket OAuth only grants repository access
- Atlassian credentials still needed for Jira/Confluence APIs
- Two distinct authentication mechanisms

### User Experience Flow

**Current (PAT)**:
1. User navigates to Settings → Credentials → GitHub
2. User reads setup guide
3. User opens GitHub in new tab, creates PAT
4. User copies PAT, pastes into portal
5. User optionally pastes SSH key
6. User saves

**New (OAuth)**:
1. User navigates to Settings → Credentials → GitHub
2. User clicks "Connect with GitHub" button
3. New tab opens to GitHub authorization page
4. User authorizes (already logged into GitHub)
5. GitHub redirects to portal callback
6. Portal exchanges code, saves token
7. Portal shows success, closes tab automatically (or redirect to success page)
8. User optionally adds SSH key still (if needed)
9. Portal shows token status (no expiry for GitHub, refresh countdown for Bitbucket)

**Hybrid Approach**: Keep manual PAT entry as fallback option
- OAuth flow is primary, recommended method
- Manual PAT paste available under "or paste token manually"
- Similar to Claude Code OAuth UI pattern
- Accommodates users who prefer PATs or use GitHub Enterprise with different OAuth setup

## Implementation Steps

### Phase 1: Backend OAuth Infrastructure

#### 1.1 Create Git OAuth Module

**File**: `agent/portal/git_oauth.py`

```python
"""OAuth providers for git platforms (GitHub, Bitbucket, GitLab, etc.)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlencode
import httpx
import structlog

@dataclass
class GitOAuthTokens:
    """Normalized OAuth tokens from git provider."""
    provider: str
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None  # seconds
    scope: str | None = None
    token_type: str = "Bearer"

class GitOAuthProvider(ABC):
    """Abstract OAuth provider for git platforms."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (github, bitbucket, gitlab)."""
        ...

    @abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Build authorization URL."""
        ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> GitOAuthTokens:
        """Exchange authorization code for tokens."""
        ...

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> GitOAuthTokens | None:
        """Refresh expired access token."""
        ...

    @abstractmethod
    async def get_user_info(self, access_token: str) -> dict:
        """Get authenticated user info (username, email, etc.)."""
        ...

class GitHubOAuthProvider(GitOAuthProvider):
    """GitHub OAuth 2.0 provider."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = "https://github.com/login/oauth/authorize"
        self.token_url = "https://github.com/login/oauth/access_token"
        self.api_base = "https://api.github.com"

    @property
    def name(self) -> str:
        return "github"

    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        params = urlencode({
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": "repo user:email",  # Full repo access + email
            "state": state,
        })
        return f"{self.auth_url}?{params}"

    async def exchange_code(self, code: str, redirect_uri: str) -> GitOAuthTokens:
        # Exchange code for access token
        # GitHub doesn't issue refresh tokens by default
        ...

    async def refresh_access_token(self, refresh_token: str) -> GitOAuthTokens | None:
        # GitHub tokens don't expire by default (unless fine-grained with expiration)
        # Return None to indicate no refresh needed
        return None

    async def get_user_info(self, access_token: str) -> dict:
        # GET /user to get username, email
        ...

class BitbucketOAuthProvider(GitOAuthProvider):
    """Bitbucket Cloud OAuth 2.0 provider."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.auth_url = "https://bitbucket.org/site/oauth2/authorize"
        self.token_url = "https://bitbucket.org/site/oauth2/access_token"
        self.api_base = "https://api.bitbucket.org/2.0"

    @property
    def name(self) -> str:
        return "bitbucket"

    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        params = urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "state": state,
            # Scopes: repository (read/write), account (user info)
            # No redirect_uri param for Bitbucket (configured in OAuth consumer)
        })
        return f"{self.auth_url}?{params}"

    async def exchange_code(self, code: str, redirect_uri: str) -> GitOAuthTokens:
        # POST to token_url with Basic Auth (client_id:client_secret)
        # Bitbucket returns access_token + refresh_token
        # Tokens expire: access=2h, refresh=30d
        ...

    async def refresh_access_token(self, refresh_token: str) -> GitOAuthTokens | None:
        # POST to token_url with grant_type=refresh_token
        ...

    async def get_user_info(self, access_token: str) -> dict:
        # GET /user to get username, email
        ...
```

**Dependencies**: None (uses `httpx`, `structlog` already in portal)

**Key Design Points**:
- Abstract base class mirrors `OAuthProvider` pattern
- Returns `GitOAuthTokens` dataclass (not profile) since we're obtaining service tokens, not authenticating users
- Each provider encapsulates OAuth URLs, scopes, token exchange logic
- Refresh token support varies by provider (GitHub optional, Bitbucket required)

#### 1.2 Add OAuth Endpoints to Settings Router

**File**: `agent/portal/routers/settings.py`

**New Endpoints**:
```python
# GitHub OAuth endpoints
POST /api/settings/credentials/github/oauth/start
  → Returns: {"authorize_url": str, "state": str}
  → Stores state in Redis (10-min TTL)

GET /api/settings/credentials/github/oauth/callback?code=...&state=...
  → Browser redirect endpoint (after GitHub authorization)
  → Exchanges code for token
  → Stores token in credential store
  → Redirects to frontend success page

POST /api/settings/credentials/github/oauth/refresh
  → Manually refresh token (if GitHub ever adds refresh tokens)
  → Currently no-op for GitHub

GET /api/settings/credentials/github/status
  → Returns: {configured: bool, username: str, scopes: list, ...}

# Bitbucket OAuth endpoints (identical pattern)
POST /api/settings/credentials/bitbucket/oauth/start
GET /api/settings/credentials/bitbucket/oauth/callback
POST /api/settings/credentials/bitbucket/oauth/refresh
GET /api/settings/credentials/bitbucket/status
```

**State Management**:
- Store OAuth state in Redis: `git_oauth:{provider}:{user_id}` → `{state, timestamp}`
- 10-minute TTL (same as Claude PKCE)
- Prevents CSRF attacks

**Token Storage**:
- GitHub:
  - `github_token` (access token, replaces PAT)
  - `github_token_scope` (granted scopes, for display)
  - `github_username` (for display)
- Bitbucket:
  - `bitbucket_token` (access token)
  - `bitbucket_refresh_token` (refresh token)
  - `bitbucket_token_expires_at` (ISO timestamp)
  - `bitbucket_username` (for display)

**Error Handling**:
- Invalid/expired state → 400 error with user-friendly message
- Token exchange failure → 502 error, suggest retry
- Network errors → Log and return 503

#### 1.3 Update Service Definitions

**File**: `agent/portal/routers/settings.py`

Update `SERVICE_DEFINITIONS`:

```python
"github": {
    "label": "GitHub",
    "keys": [
        {"key": "github_token", "label": "GitHub Token (PAT or OAuth)", "type": "password"},
        {"key": "github_token_scope", "label": "Token Scopes (auto-populated)", "type": "text"},
        {"key": "github_username", "label": "GitHub Username (auto-populated)", "type": "text"},
        {"key": "ssh_private_key", "label": "SSH Private Key (optional)", "type": "textarea"},
        {"key": "git_author_name", "label": "Git Author Name", "type": "text"},
        {"key": "git_author_email", "label": "Git Author Email", "type": "text"},
    ],
},
"bitbucket": {
    "label": "Bitbucket",
    "keys": [
        {"key": "bitbucket_token", "label": "Bitbucket OAuth Token", "type": "password"},
        {"key": "bitbucket_refresh_token", "label": "Refresh Token (auto-managed)", "type": "password"},
        {"key": "bitbucket_token_expires_at", "label": "Token Expiry (auto-populated)", "type": "text"},
        {"key": "bitbucket_username", "label": "Bitbucket Username (auto-populated)", "type": "text"},
    ],
},
```

**Note**: Keep existing `atlassian` service for Jira/Confluence (unchanged).

#### 1.4 Update Git Platform Module to Use OAuth Tokens

**File**: `agent/modules/git_platform/main.py`

Update `_get_tools_for_user()`:

```python
async def _get_tools_for_user(user_id: str, provider: str) -> GitPlatformTools:
    """Get provider-specific tools for a user."""

    if provider == "github":
        # Try OAuth token first, fall back to PAT
        token = await user_credentials.get(session, user_id, "github", "github_token")
        if not token and settings.git_platform_token and settings.git_platform_provider == "github":
            token = settings.git_platform_token
        if not token:
            raise ValueError("No GitHub credentials configured")

        github_provider = GitHubProvider(token)
        return GitPlatformTools(github_provider)

    elif provider == "bitbucket":
        # Try OAuth token first
        token = await user_credentials.get(session, user_id, "bitbucket", "bitbucket_token")

        # Check if token is expired, auto-refresh if needed
        expires_at_str = await user_credentials.get(session, user_id, "bitbucket", "bitbucket_token_expires_at")
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at < datetime.now(timezone.utc) + timedelta(minutes=5):
                # Token expired or expiring soon, refresh
                refresh_token = await user_credentials.get(session, user_id, "bitbucket", "bitbucket_refresh_token")
                if refresh_token:
                    # Call portal API to refresh (or implement refresh logic here)
                    # For now, just log and continue with expired token (will fail gracefully)
                    logger.warning("bitbucket_token_expired", user_id=user_id)

        # Fall back to Atlassian credentials
        if not token:
            username = await user_credentials.get(session, user_id, "atlassian", "username")
            api_token = await user_credentials.get(session, user_id, "atlassian", "api_token")
            if username and api_token:
                bitbucket_provider = BitbucketProvider(username, api_token)
                return GitPlatformTools(bitbucket_provider)

        if not token:
            raise ValueError("No Bitbucket credentials configured")

        bitbucket_provider = BitbucketProvider(token=token)  # Need to add OAuth constructor
        return GitPlatformTools(bitbucket_provider)
```

**File**: `agent/modules/git_platform/providers/github.py`

No changes needed — already uses Bearer token.

**File**: `agent/modules/git_platform/providers/bitbucket.py`

Add OAuth token support (currently only supports Basic Auth):

```python
class BitbucketProvider(GitProvider):
    def __init__(self, username: str | None = None, api_token: str | None = None, token: str | None = None):
        """Initialize with either Basic Auth (username+api_token) or OAuth (token)."""
        if token:
            # OAuth flow
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=30.0,
            )
        elif username and api_token:
            # Basic Auth flow (existing)
            auth = (username, api_token)
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=auth,
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
        else:
            raise ValueError("Must provide either token or username+api_token")
```

### Phase 2: Frontend OAuth UI

#### 2.1 Update CredentialCard Component

**File**: `agent/portal/frontend/src/components/settings/CredentialCard.tsx`

**Changes**:
1. Add `GitHubOAuthFlow` component (similar to `ClaudeOAuthFlow` but with redirect-based flow)
2. Add `BitbucketOAuthFlow` component
3. Add `GitTokenStatusBar` component (shows username, scopes, expiry for Bitbucket)
4. Update setup guides

**GitHub OAuth Flow Component**:
```typescript
function GitHubOAuthFlow({ onSuccess, onCancel }: { onSuccess: () => void; onCancel: () => void }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const startOAuth = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await api<{ authorize_url: string; state: string }>(
        "/api/settings/credentials/github/oauth/start",
        { method: "POST" }
      );
      // Redirect current window to GitHub (will redirect back to callback)
      window.location.href = data.authorize_url;
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <button
        onClick={startOAuth}
        disabled={loading}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors w-full justify-center disabled:opacity-50"
      >
        <Github size={16} />
        {loading ? "Redirecting to GitHub..." : "Connect with GitHub"}
      </button>
      {error && <p className="text-sm text-red-400">{error}</p>}
    </div>
  );
}
```

**Callback Success Page**:
Create new route: `/settings/oauth/success?provider=github`
- Shows success message
- Auto-refreshes parent page to reflect new credentials
- Option to close tab

**BitbucketOAuthFlow**: Identical pattern, different endpoint.

**Git Token Status Bar**:
```typescript
function GitTokenStatusBar({
  service,
  onRefreshDone,
}: {
  service: "github" | "bitbucket";
  onRefreshDone: () => void;
}) {
  const [status, setStatus] = useState<GitTokenStatus | null>(null);

  useEffect(() => {
    fetchStatus();
  }, []);

  const fetchStatus = async () => {
    const data = await api<GitTokenStatus>(`/api/settings/credentials/${service}/status`);
    setStatus(data);
  };

  const handleRefresh = async () => {
    await api(`/api/settings/credentials/${service}/oauth/refresh`, { method: "POST" });
    fetchStatus();
    onRefreshDone();
  };

  // Show username, scopes, expiry (for Bitbucket), refresh button
  ...
}
```

#### 2.2 Update Setup Guides

**File**: `agent/portal/frontend/src/components/settings/CredentialCard.tsx`

Update `SETUP_GUIDES`:

```typescript
github: {
  title: "Setting up GitHub credentials",
  steps: [
    {
      instruction: "Option 1: Connect with OAuth (recommended) — Click 'Connect with GitHub' above for seamless authorization.",
    },
    {
      instruction: "Option 2: Manual PAT — Create a personal access token at GitHub Settings > Developer settings > Personal access tokens. Grant 'repo' and 'user:email' scopes.",
    },
    {
      instruction: "SSH Private Key (optional): Only needed for git clone/push over SSH. Paste your private key:",
      code: "cat ~/.ssh/id_ed25519",
    },
  ],
  note: "OAuth tokens are refreshed automatically. PATs must be regenerated manually when expired.",
},
bitbucket: {
  title: "Setting up Bitbucket credentials",
  steps: [
    {
      instruction: "Click 'Connect with Bitbucket' above to authorize via OAuth.",
    },
    {
      instruction: "Bitbucket tokens expire every 2 hours but are automatically refreshed.",
    },
  ],
  note: "For Jira and Confluence access, configure Atlassian credentials separately.",
},
```

### Phase 3: Environment Configuration

#### 3.1 Add OAuth Client Credentials

**File**: `agent/.env.example`

Add new environment variables:

```bash
# GitHub OAuth (register at https://github.com/settings/developers)
GITHUB_OAUTH_CLIENT_ID=
GITHUB_OAUTH_CLIENT_SECRET=

# Bitbucket OAuth (register at https://bitbucket.org/account/settings/app-passwords/)
BITBUCKET_OAUTH_CLIENT_ID=
BITBUCKET_OAUTH_CLIENT_SECRET=

# OAuth redirect URIs (append /github or /bitbucket)
GIT_OAUTH_REDIRECT_URI=http://localhost:8080/api/settings/credentials
```

#### 3.2 Update Settings

**File**: `agent/shared/shared/config.py`

Add new settings:

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # GitHub OAuth
    github_oauth_client_id: str = ""
    github_oauth_client_secret: str = ""

    # Bitbucket OAuth
    bitbucket_oauth_client_id: str = ""
    bitbucket_oauth_client_secret: str = ""

    # Git OAuth redirect base (provider-specific path appended)
    git_oauth_redirect_uri: str = "http://localhost:8080/api/settings/credentials"
```

### Phase 4: Documentation Updates

#### 4.1 Update Developer Guide

**File**: `agent/docs/features/git-oauth-setup.md` (new file)

Document:
- How to register GitHub OAuth App
- How to register Bitbucket OAuth Consumer
- Required scopes for each provider
- Local development setup (localhost callback URLs)
- Production deployment (setting redirect URIs)

#### 4.2 Update User Guide

**File**: `CLAUDE.md`

Update git credentials section to mention OAuth as primary method.

### Phase 5: Testing & Validation

#### 5.1 Backend Tests

Create `agent/portal/tests/test_git_oauth.py`:
- Test PKCE generation (if we decide to use it)
- Test state validation
- Test token exchange (mocked)
- Test refresh flow (mocked)
- Test error handling (expired state, invalid code, etc.)

#### 5.2 Integration Tests

Test end-to-end flows:
1. Start OAuth flow → verify state saved in Redis
2. Callback with valid code → verify token saved in DB
3. Callback with invalid state → verify error
4. Refresh token → verify updated in DB
5. Git platform module uses OAuth token → verify API calls succeed

#### 5.3 Manual Testing Checklist

- [ ] GitHub OAuth flow (happy path)
- [ ] GitHub OAuth flow (user denies)
- [ ] GitHub OAuth flow (invalid state)
- [ ] GitHub token used for git operations
- [ ] GitHub manual PAT still works
- [ ] Bitbucket OAuth flow (happy path)
- [ ] Bitbucket token auto-refresh
- [ ] Bitbucket token status display
- [ ] Atlassian credentials still work for Jira/Confluence
- [ ] SSH key entry still works
- [ ] Multiple users with different providers
- [ ] Token revocation handling

## Files to Modify

### New Files
1. `agent/portal/git_oauth.py` — Git OAuth provider implementations
2. `agent/portal/frontend/src/components/settings/GitOAuthFlow.tsx` — OAuth flow UI components (or integrate into CredentialCard)
3. `agent/portal/frontend/src/pages/settings/OAuthSuccess.tsx` — OAuth callback success page
4. `agent/portal/tests/test_git_oauth.py` — Backend tests
5. `agent/docs/features/git-oauth-setup.md` — Setup documentation

### Modified Files
1. `agent/portal/routers/settings.py` — Add OAuth endpoints
2. `agent/portal/frontend/src/components/settings/CredentialCard.tsx` — Add OAuth UI
3. `agent/modules/git_platform/main.py` — Use OAuth tokens
4. `agent/modules/git_platform/providers/bitbucket.py` — Support OAuth Bearer tokens
5. `agent/shared/shared/config.py` — Add OAuth settings
6. `agent/.env.example` — Document OAuth env vars
7. `CLAUDE.md` — Update documentation

### Unchanged Files
- `agent/modules/git_platform/providers/github.py` — Already supports Bearer tokens
- `agent/portal/oauth_providers.py` — Separate concern (portal login, not git)
- `agent/portal/claude_oauth.py` — Reference implementation, not modified
- `agent/shared/shared/models/user_credential.py` — Schema supports arbitrary keys

## Migration Path

### For Existing Users with PATs

**Behavior**:
- Existing PATs continue to work (no breaking changes)
- UI shows "Migrate to OAuth" suggestion if PAT detected
- Users can migrate at their convenience
- Manual PAT entry remains available as fallback

**Migration Flow**:
1. User sees "You're using a Personal Access Token. Upgrade to OAuth for automatic token management."
2. User clicks "Upgrade to OAuth"
3. OAuth flow completes
4. Old PAT is kept (not deleted) as backup
5. New OAuth token takes precedence

### For New Users

**Behavior**:
- OAuth shown as primary option (big button)
- Manual PAT entry shown as "Advanced" or "Alternative" option
- Clear guidance on when to use each method

## Security Considerations

### Token Storage
- All tokens encrypted at rest (via `CredentialStore` with Fernet)
- Tokens never logged or exposed in responses
- OAuth state includes CSRF protection (state parameter)

### Scopes
- GitHub: Request minimal scopes (`repo`, `user:email`)
- Bitbucket: Request minimal scopes (`repository`, `account`)
- Clearly document why each scope is needed

### Token Lifecycle
- GitHub tokens: No expiration by default (unless user configures fine-grained token with expiration)
- Bitbucket tokens: 2-hour expiration, auto-refresh using refresh token
- Refresh tokens: Encrypted, used automatically, never exposed to frontend

### Redirect URI Validation
- GitHub/Bitbucket validate redirect URI against registered OAuth app
- Portal validates state parameter to prevent CSRF
- Consider adding nonce for additional security

### Token Revocation
- If token becomes invalid (user revokes, org policy changes), gracefully fail
- Surface error to user with actionable message ("Reconnect GitHub")
- Provide re-authorization flow without deleting other credentials

## Potential Challenges & Mitigations

### Challenge 1: Multiple Redirect URIs (Dev vs. Prod)
**Problem**: GitHub OAuth apps require explicit redirect URI registration. Need different URIs for `localhost:8080` (dev) and `yourdomain.com` (prod).

**Mitigation**:
- Register both URIs in single GitHub OAuth App
- OR: Create separate OAuth Apps for dev/prod
- Document in setup guide

### Challenge 2: Bitbucket Token Refresh in git_platform Module
**Problem**: Bitbucket tokens expire in 2 hours. The `git_platform` module runs as a separate service and may not have direct access to portal's OAuth refresh logic.

**Mitigation**:
- Option A: Implement refresh logic in `git_platform` module (duplicate code)
- Option B: Have `git_platform` call portal API to refresh tokens
- Option C: Rely on portal background job to proactively refresh tokens before expiry
- **Recommended**: Option A for simplicity and autonomy

### Challenge 3: Callback Page User Experience
**Problem**: After GitHub authorization, user is redirected to callback URL. Need to close tab/window and show success.

**Mitigation**:
- Callback endpoint redirects to `/settings/oauth/success?provider=github`
- Success page shows "Authorization successful! You may close this tab."
- JavaScript on success page posts message to opener window (if opened via `window.open`)
- Opener window refreshes credential list
- Auto-close tab after 3 seconds

### Challenge 4: Atlassian vs. Bitbucket Confusion
**Problem**: Users may confuse Atlassian (Jira/Confluence) credentials with Bitbucket OAuth.

**Mitigation**:
- Clear labeling: "Bitbucket (Code Repositories)" vs. "Atlassian (Jira & Confluence)"
- Add note in Bitbucket setup: "This is for Bitbucket repositories only. For Jira/Confluence, configure Atlassian credentials."
- Consider renaming service from `atlassian` to `atlassian_cloud` for clarity

### Challenge 5: GitHub Enterprise Support
**Problem**: GitHub Enterprise has different OAuth endpoints. Current implementation assumes github.com.

**Mitigation**:
- Phase 1: Support only github.com
- Phase 2: Add `GITHUB_ENTERPRISE_URL` setting
- Document limitation in setup guide
- Keep manual PAT as fallback for Enterprise users

## Alternative Approaches Considered

### Alternative 1: PKCE for All Providers
**Description**: Use PKCE flow (like Claude OAuth) for GitHub and Bitbucket instead of client secret.

**Pros**:
- Consistent with Claude OAuth pattern
- Slightly more secure (no client secret in env vars)

**Cons**:
- More complex (verifier/challenge management)
- Requires Redis storage for PKCE state
- Not necessary for confidential web application
- GitHub and Bitbucket support standard flow well

**Decision**: Use standard authorization code flow for simplicity.

### Alternative 2: GitHub App Instead of OAuth App
**Description**: Use GitHub App installation flow instead of OAuth.

**Pros**:
- More granular permissions
- Org-level installations
- Webhooks for events

**Cons**:
- More complex setup (installation flow, app manifest)
- Overkill for basic git operations
- Would require different token exchange flow

**Decision**: Use OAuth App for simplicity. GitHub App can be added later if needed.

### Alternative 3: Unified "Git Credentials" Service
**Description**: Merge GitHub, Bitbucket, GitLab into single `git` service with provider selection.

**Pros**:
- Simpler UI (single credential card)
- Unified token management

**Cons**:
- Loses per-provider granularity
- Hard to support provider-specific features
- DB schema would need provider field

**Decision**: Keep providers separate for clarity and flexibility.

## Success Criteria

### Functional Requirements
- ✅ Users can connect GitHub via OAuth
- ✅ Users can connect Bitbucket via OAuth
- ✅ OAuth tokens stored securely (encrypted)
- ✅ Tokens used by git_platform module for API calls
- ✅ Bitbucket tokens auto-refresh before expiry
- ✅ Token status visible in portal
- ✅ Manual PAT entry still available
- ✅ Existing PATs continue to work

### Non-Functional Requirements
- ✅ OAuth flow completes in < 10 seconds (typical case)
- ✅ Clear error messages for failures
- ✅ No secrets in logs or responses
- ✅ Works in both dev (localhost) and prod environments
- ✅ Documentation complete and clear

### User Experience
- ✅ OAuth flow is intuitive (minimal clicks)
- ✅ Success/failure states clearly communicated
- ✅ Token expiry warnings (for Bitbucket)
- ✅ Seamless integration with existing credential management

## Future Enhancements (Out of Scope)

1. **GitLab OAuth Support**
   - Add `GitLabOAuthProvider`
   - Similar pattern to GitHub/Bitbucket

2. **GitHub Enterprise Support**
   - Configurable OAuth endpoints
   - Enterprise-specific scopes

3. **Token Auto-Refresh Background Job**
   - Proactive refresh before expiry
   - User notification on refresh failure

4. **Multi-Account Support**
   - Multiple GitHub accounts per user
   - Account selector in UI

5. **OAuth Scope Customization**
   - Let users choose scopes during authorization
   - Store granted scopes, request re-auth if more needed

6. **Webhook Integration**
   - Listen for token revocation events
   - Notify user to re-authorize

7. **SSO Integration**
   - GitHub SSO for portal login (in addition to Discord/Google/Slack)
   - Automatic git credential provisioning on portal login

## Rollout Plan

### Phase 1: Development (Week 1)
- Implement backend OAuth infrastructure
- Create GitHub OAuth provider
- Add OAuth endpoints to settings router
- Manual testing with GitHub OAuth app in dev

### Phase 2: Frontend (Week 1)
- Update CredentialCard component
- Add OAuth flow UI
- Create callback success page
- Manual testing of full flow

### Phase 3: Bitbucket (Week 2)
- Implement Bitbucket OAuth provider
- Add Bitbucket endpoints
- Update frontend for Bitbucket
- Test token refresh flow

### Phase 4: Integration (Week 2)
- Update git_platform module to use OAuth tokens
- Test API calls with OAuth tokens
- Test fallback to PAT
- Test Bitbucket token refresh in module

### Phase 5: Documentation & Testing (Week 3)
- Write setup documentation
- Create backend tests
- Integration testing
- User acceptance testing

### Phase 6: Deployment (Week 3)
- Register production OAuth apps
- Update production env vars
- Deploy to production
- Monitor for issues

### Phase 7: User Migration (Week 4+)
- Announce OAuth availability
- Encourage PAT users to migrate
- Support users during migration
- Collect feedback

## Open Questions

1. **Should we deprecate manual PAT entry eventually?**
   - Recommendation: No, keep as advanced option for flexibility

2. **Should Bitbucket OAuth replace Atlassian credentials for Bitbucket API calls?**
   - Recommendation: Yes, prefer OAuth token, fall back to Atlassian credentials

3. **Should we support GitHub fine-grained tokens with expiration?**
   - Recommendation: Yes, detect expiration and offer refresh if refresh token available (future enhancement)

4. **Should we implement automatic token refresh for Bitbucket or rely on on-demand refresh?**
   - Recommendation: On-demand refresh in git_platform module (simpler, more reliable)

5. **Should we notify users when Bitbucket token refresh fails?**
   - Recommendation: Yes, via platform message (Discord/Telegram/Slack) or email if configured

## Conclusion

This implementation follows proven patterns from the existing Claude OAuth flow and portal login OAuth, adapted for git platform authorization. The architecture is extensible (supports future providers like GitLab), secure (encrypted storage, CSRF protection), and user-friendly (OAuth preferred, PAT fallback). The phased rollout minimizes risk and allows for iterative improvement based on user feedback.

**Total estimated effort**: 2-3 weeks for one developer
**Priority**: Medium-High (improves security and UX, but existing PAT flow works)
**Dependencies**: GitHub/Bitbucket OAuth app registration (external)
