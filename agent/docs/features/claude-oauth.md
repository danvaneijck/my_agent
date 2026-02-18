# Claude Code OAuth (PKCE Flow)

How the portal authenticates users with Anthropic to obtain Claude Code CLI credentials via OAuth 2.0 PKCE.

## Overview

The portal implements a manual OAuth PKCE flow that mirrors what the Claude Code CLI does internally. Users authorize via Anthropic's consent page, copy the resulting authorization code, and paste it into the portal. The portal exchanges the code for access/refresh tokens and stores them encrypted for use by the `claude_code` module.

## Endpoints & Constants

All OAuth constants live in `portal/claude_oauth.py`:

| Constant | Value |
|---|---|
| Client ID | `9d1c250a-e61b-44d9-88ed-5944d1962f5e` (Claude Code CLI's public ID) |
| Authorize URL | `https://claude.ai/oauth/authorize` |
| Token URL | `https://platform.claude.com/v1/oauth/token` |
| Redirect URI | `https://platform.claude.com/oauth/code/callback` |
| Scopes | `user:inference user:profile user:sessions:claude_code` |

**Important:** These values were verified against the Claude Code CLI npm package (v2.1.45). The domain is `platform.claude.com`, not the old `console.anthropic.com`.

## Flow

```
 User clicks "Connect Claude Account" in portal
         │
         ▼
 POST /api/settings/credentials/claude_code/oauth/start
 ├── Generate PKCE verifier + S256 challenge
 ├── Generate random state
 ├── Store {verifier, state} in Redis (10 min TTL)
 └── Return authorize_url to frontend
         │
         ▼
 Frontend opens authorize_url in new tab
 → https://claude.ai/oauth/authorize?code=true&client_id=...&redirect_uri=...
         │
         ▼
 User logs in & authorizes on Anthropic's site
 → Redirected to platform.claude.com/oauth/code/callback
 → Page displays authorization code in format: CODE#STATE
         │
         ▼
 User copies code and pastes into portal input field
         │
         ▼
 POST /api/settings/credentials/claude_code/oauth/exchange
 ├── Retrieve {verifier, state} from Redis
 ├── Split code on "#" → auth_code + returned_state
 ├── POST to platform.claude.com/v1/oauth/token (JSON):
 │     {grant_type, code, client_id, redirect_uri, code_verifier, state}
 ├── Receive {access_token, refresh_token, expires_in, scope, ...}
 ├── Build credentials JSON in Claude CLI format
 └── Encrypt and store via CredentialStore
```

## Token Exchange Request Format

The token endpoint requires **JSON** with explicit `Content-Type: application/json`:

```python
payload = {
    "grant_type": "authorization_code",
    "code": "<authorization_code>",
    "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
    "redirect_uri": "https://platform.claude.com/oauth/code/callback",
    "code_verifier": "<pkce_verifier>",
    "state": "<state_from_callback>",
}
resp = await client.post(
    "https://platform.claude.com/v1/oauth/token",
    json=payload,
    headers={"Content-Type": "application/json"},
)
```

The `state` field must be included — the CLI sends it and the endpoint expects it.

## Token Refresh

Access tokens expire after ~8 hours. Refresh uses the same token endpoint:

```python
payload = {
    "grant_type": "refresh_token",
    "refresh_token": "<refresh_token>",
    "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
}
```

The refresh token is **single-use** — each refresh returns a new refresh token that must be saved.

## Stored Credentials Format

Credentials are stored in the Claude CLI JSON format expected by the `claude_code` module:

```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "refreshToken": "sk-ant-ort01-...",
    "expiresAt": 1700000000000,
    "scopes": ["user:inference", "user:profile", "user:sessions:claude_code"],
    "subscriptionType": "pro",
    "rateLimitTier": "tier1"
  }
}
```

Token prefixes: access tokens start with `sk-ant-oat01-`, refresh tokens with `sk-ant-ort01-`.

## Portal API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/settings/credentials/claude_code/oauth/start` | Start OAuth flow, returns authorize URL |
| POST | `/api/settings/credentials/claude_code/oauth/exchange` | Exchange auth code for tokens |
| POST | `/api/settings/credentials/claude_code/oauth/refresh` | Manually refresh access token |
| GET | `/api/settings/credentials/claude_code/status` | Check token validity, expiry, scopes |

## Key Files

| File | Purpose |
|---|---|
| `portal/claude_oauth.py` | PKCE generation, URL building, token exchange/refresh, credential formatting |
| `portal/routers/settings.py` | API endpoints, Redis PKCE state, credential storage |
| `portal/frontend/src/components/settings/CredentialCard.tsx` | OAuth UI flow (`ClaudeOAuthFlow` component) |

## Gotchas

- **Domain is `platform.claude.com`** — The old `console.anthropic.com` returns "Invalid request format". Verified from CLI source.
- **JSON, not form-urlencoded** — The token endpoint accepts `application/json`, not `application/x-www-form-urlencoded`.
- **State must be sent in exchange** — The `state` parameter from the `code#state` callback must be included in the token exchange body.
- **code#state format** — Anthropic's callback page shows the code as `CODE#STATE`. The `#` separator must be split and both parts used (code for exchange, state for the state field).
- **PKCE state has 10 min TTL** — If the user takes longer than 10 minutes to authorize and paste the code, the Redis key expires. They must restart the flow.
- **Refresh tokens are single-use** — Always save the new refresh token returned by a refresh call.
- **Token expiry is ~8 hours** — The `claude_code` module should check expiry before launching tasks and auto-refresh if needed.
