# Git OAuth Setup Guide

This guide explains how to configure OAuth authentication for GitHub and Bitbucket in the AI Agent System, enabling seamless git integration without manual token management.

## Overview

The AI agent supports OAuth 2.0 authentication for git platforms, providing:

- **Automatic token management**: No need to manually copy/paste Personal Access Tokens
- **Secure authentication**: OAuth tokens encrypted at rest
- **Auto-refresh**: Bitbucket tokens automatically refreshed before expiry
- **User-friendly**: One-click authorization flow via portal UI

## Prerequisites

- AI Agent System deployed and accessible
- Admin access to create OAuth applications on GitHub/Bitbucket
- Portal OAuth redirect URI configured (`GIT_OAUTH_REDIRECT_URI`)

## GitHub OAuth Setup

### 1. Register GitHub OAuth App

1. Navigate to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click "OAuth Apps" → "New OAuth App"
3. Fill in the application details:
   - **Application name**: `AI Agent System` (or your preferred name)
   - **Homepage URL**: Your portal URL (e.g., `https://yourdomain.com`)
   - **Authorization callback URL**: `https://yourdomain.com/api/settings/credentials/github/oauth/callback`
     - For local development: `http://localhost:8080/api/settings/credentials/github/oauth/callback`
4. Click "Register application"
5. Note the **Client ID** (shown immediately)
6. Click "Generate a new client secret"
7. **Important**: Copy the **Client Secret** immediately (it won't be shown again)

### 2. Configure Environment Variables

Add the following to your `agent/.env` file:

```bash
# GitHub OAuth App credentials
GITHUB_OAUTH_CLIENT_ID=your_github_client_id_here
GITHUB_OAUTH_CLIENT_SECRET=your_github_client_secret_here

# Git OAuth redirect base
GIT_OAUTH_REDIRECT_URI=http://localhost:8080/api/settings/credentials
```

**For production**, update to your production domain:

```bash
GIT_OAUTH_REDIRECT_URI=https://yourdomain.com/api/settings/credentials
```

### 3. Restart Portal Service

```bash
# Rebuild and restart portal
make restart-module M=portal

# Or restart all services
make down && make up
```

### 4. Authorize GitHub in Portal

1. Navigate to Portal → Settings → Credentials → GitHub
2. Click **"Connect with GitHub"**
3. You'll be redirected to GitHub's authorization page
4. Review the requested permissions:
   - **repo**: Full control of private repositories (required for git operations)
   - **user:email**: Access to your email address (required for commit authorship)
5. Click **"Authorize [Your App Name]"**
6. You'll be redirected back to the portal
7. GitHub credentials are now configured

### OAuth Scopes

GitHub OAuth requests the following scopes:

- `repo`: Full control of private repositories
  - Allows reading, writing, and pushing to repositories
  - Required for all git operations (clone, push, PR creation, etc.)
- `user:email`: Access to user email addresses
  - Used to populate git author email for commits
  - Needed to retrieve primary email if not public

### Token Lifecycle

- **Standard OAuth tokens**: Do not expire (GitHub default behavior)
- **Fine-grained tokens**: May have expiration if configured (rare)
- **Refresh tokens**: Only issued if fine-grained token has expiration enabled
- **Auto-refresh**: If refresh token available, portal automatically refreshes expired tokens

## Bitbucket OAuth Setup

### 1. Register Bitbucket OAuth Consumer

1. Navigate to your Bitbucket workspace settings:
   - URL: `https://bitbucket.org/{workspace}/workspace/settings/oauth-consumers`
   - Replace `{workspace}` with your actual workspace name
2. Click **"Add consumer"**
3. Fill in the consumer details:
   - **Name**: `AI Agent System` (or your preferred name)
   - **Description**: OAuth consumer for AI agent git operations
   - **Callback URL**: `https://yourdomain.com/api/settings/credentials/bitbucket/oauth/callback`
     - For local development: `http://localhost:8080/api/settings/credentials/bitbucket/oauth/callback`
   - **URL**: Your portal URL (e.g., `https://yourdomain.com`)
   - **Permissions**: Select the following:
     - **Account**: Read
     - **Repositories**: Read and Write
     - **Pull requests**: Read and Write
     - **Issues**: Read and Write (if using issue tracking)
4. Click **"Save"**
5. The **Key** (Client ID) and **Secret** (Client Secret) will be displayed
6. **Important**: Copy both values immediately

### 2. Configure Environment Variables

Add the following to your `agent/.env` file:

```bash
# Bitbucket OAuth Consumer credentials
BITBUCKET_OAUTH_CLIENT_ID=your_bitbucket_key_here
BITBUCKET_OAUTH_CLIENT_SECRET=your_bitbucket_secret_here

# Git OAuth redirect base (same as GitHub)
GIT_OAUTH_REDIRECT_URI=http://localhost:8080/api/settings/credentials
```

### 3. Restart Portal Service

```bash
make restart-module M=portal
```

### 4. Authorize Bitbucket in Portal

1. Navigate to Portal → Settings → Credentials → Bitbucket
2. Click **"Connect with Bitbucket"**
3. You'll be redirected to Bitbucket's authorization page
4. Review the requested permissions
5. Click **"Grant access"**
6. You'll be redirected back to the portal
7. Bitbucket credentials are now configured

### OAuth Scopes

Bitbucket OAuth scopes are configured when registering the OAuth Consumer. Recommended scopes:

- **account:read**: Read user account information
- **repository:read**: Read repositories
- **repository:write**: Modify repositories, push commits
- **pullrequest:read**: Read pull requests
- **pullrequest:write**: Create and update pull requests
- **issue:read**: Read issues (optional)
- **issue:write**: Create and update issues (optional)

### Token Lifecycle

- **Access tokens**: Expire after **2 hours**
- **Refresh tokens**: Expire after **30 days** (rolling window)
- **Auto-refresh**: Portal automatically refreshes tokens when they expire or are expiring soon (< 5 minutes remaining)
- **Background refresh**: The `git_platform` module checks expiry before every API call and refreshes if needed
- **Transparent**: Users never need to manually refresh tokens

## Multiple Redirect URIs (Dev + Prod)

GitHub and Bitbucket OAuth apps support multiple callback URLs. To support both local development and production:

### GitHub

Register **both** callback URLs in the same OAuth App:

1. Primary: `https://yourdomain.com/api/settings/credentials/github/oauth/callback`
2. Secondary: `http://localhost:8080/api/settings/credentials/github/oauth/callback`

GitHub allows multiple callback URLs in a single OAuth App.

### Bitbucket

Bitbucket OAuth Consumers only support **one callback URL**. Options:

1. **Separate Consumers**: Create separate OAuth Consumers for dev and prod
2. **Dynamic redirect** (not recommended): Use production callback, redirect to dev
3. **Recommended**: Use separate consumers with different credentials per environment

## Troubleshooting

### "GitHub OAuth not configured" error

**Cause**: `GITHUB_OAUTH_CLIENT_ID` or `GITHUB_OAUTH_CLIENT_SECRET` not set in environment.

**Solution**:
1. Verify credentials in `agent/.env`
2. Restart portal: `make restart-module M=portal`
3. Check portal logs: `make logs-module M=portal`

### "Invalid or expired OAuth state" error

**Cause**: OAuth state mismatch (CSRF protection triggered).

**Possible reasons**:
- Took too long to authorize (> 10 minutes)
- Browser session expired
- Redis unavailable or flushed

**Solution**:
- Click "Connect with GitHub/Bitbucket" again to restart flow
- Ensure Redis is running: `docker ps | grep redis`

### "Token exchange failed" error

**Cause**: OAuth code exchange failed.

**Common causes**:
- Invalid client secret
- Callback URL mismatch (must exactly match registered URL)
- Network/firewall blocking GitHub/Bitbucket API

**Solution**:
1. Verify client credentials in `.env`
2. Verify callback URL in OAuth app settings
3. Check portal logs for detailed error: `make logs-module M=portal`

### GitHub redirect loop

**Cause**: Callback URL incorrect or portal not accessible from GitHub.

**Solution**:
- Ensure callback URL in GitHub OAuth app settings exactly matches `GIT_OAUTH_REDIRECT_URI` + `/github/oauth/callback`
- For local dev, ensure portal is accessible at `http://localhost:8080`

### Bitbucket "Token expired" warning persists

**Cause**: Auto-refresh failed (refresh token invalid or expired).

**Solution**:
1. Click "Refresh" button manually in portal
2. If manual refresh fails, click "Connect with Bitbucket" to re-authorize
3. Check portal logs for refresh errors

### "No GitHub/Bitbucket credentials configured" in git operations

**Cause**: OAuth token not stored or git_platform module can't access credential store.

**Solution**:
1. Verify `CREDENTIAL_ENCRYPTION_KEY` is set in `.env`
2. Check credentials in portal: Settings → Credentials → GitHub/Bitbucket
3. If configured but still failing, re-authorize via OAuth
4. Check git_platform logs: `make logs-module M=git-platform`

## Migration from PAT to OAuth

### For Existing PAT Users

OAuth tokens and PATs can coexist. The system prioritizes OAuth tokens:

1. OAuth token (if configured)
2. PAT (fallback)
3. Global `GIT_PLATFORM_TOKEN` env var (fallback)

**Migration steps**:
1. Navigate to Portal → Settings → Credentials → GitHub
2. Click "Connect with GitHub" (PAT remains unchanged)
3. After successful OAuth authorization, OAuth token is used
4. (Optional) Delete PAT from portal if no longer needed

**Rollback**: If you want to revert to PAT, delete the OAuth credentials (click trash icon), and the PAT will be used again.

### When to Use PAT vs OAuth

**Use OAuth when**:
- You want automatic token management
- You're using github.com (not GitHub Enterprise)
- You prefer one-click authorization

**Use PAT when**:
- You're using GitHub Enterprise with non-standard OAuth endpoints
- You need specific fine-grained permissions not available via OAuth
- Organization policy requires PATs
- Troubleshooting OAuth issues

## Security Considerations

### Token Storage

- All OAuth tokens encrypted at rest using Fernet encryption
- Encryption key: `CREDENTIAL_ENCRYPTION_KEY` environment variable
- Generate key: `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`

### CSRF Protection

- OAuth state parameter validated against Redis-stored state
- State TTL: 10 minutes
- Prevents cross-site request forgery attacks

### Token Scopes

- GitHub: `repo user:email` (minimal scopes for git operations)
- Bitbucket: Configured per OAuth Consumer (follow principle of least privilege)

### Token Revocation

If a user revokes OAuth access (via GitHub/Bitbucket settings):

1. Portal receives error on next API call
2. Error surfaced to user: "GitHub credentials invalid. Please reconnect."
3. User clicks "Connect with GitHub" to re-authorize
4. Previous tokens are overwritten with new tokens

### Network Security

- OAuth callback endpoints require authenticated portal session
- Redirect URIs must be HTTPS in production (HTTP allowed for localhost dev)

## Advanced Configuration

### Custom GitHub Enterprise

To support GitHub Enterprise with custom OAuth endpoints (future enhancement):

```bash
# GitHub Enterprise OAuth (not yet implemented)
GITHUB_ENTERPRISE_URL=https://github.yourcompany.com
GITHUB_ENTERPRISE_OAUTH_CLIENT_ID=...
GITHUB_ENTERPRISE_OAUTH_CLIENT_SECRET=...
```

Current limitation: Only github.com supported. Use PAT for GitHub Enterprise.

### Custom Token Refresh Interval

Bitbucket tokens refresh automatically when expiring soon. Default threshold: 5 minutes.

To customize (modify `agent/modules/git_platform/main.py`):

```python
# Line ~117 (in _get_tools_for_user)
if expires_at < now + timedelta(minutes=5):  # Change 5 to desired minutes
```

### Background Token Refresh Job

For proactive token refresh (future enhancement), create a scheduled job that:

1. Queries all users with Bitbucket OAuth tokens
2. Checks expiry for each token
3. Refreshes tokens expiring in < 30 minutes
4. Sends notification on refresh failure

Not currently implemented. Manual refresh available via portal UI.

## API Reference

### OAuth Endpoints

**GitHub OAuth**:
- `POST /api/settings/credentials/github/oauth/start` — Start OAuth flow (returns authorize URL)
- `GET /api/settings/credentials/github/oauth/callback?code=...&state=...` — OAuth callback (browser redirect)
- `POST /api/settings/credentials/github/oauth/refresh` — Manually refresh token
- `GET /api/settings/credentials/github/status` — Get token status (username, scopes, expiry)

**Bitbucket OAuth**:
- `POST /api/settings/credentials/bitbucket/oauth/start`
- `GET /api/settings/credentials/bitbucket/oauth/callback?code=...&state=...`
- `POST /api/settings/credentials/bitbucket/oauth/refresh`
- `GET /api/settings/credentials/bitbucket/status`

### Credential Keys

**GitHub** (service: `github`):
- `github_token`: OAuth access token
- `github_refresh_token`: OAuth refresh token (optional, only for fine-grained tokens)
- `github_token_expires_at`: ISO timestamp (optional)
- `github_token_scope`: Granted scopes (e.g., `repo user:email`)
- `github_username`: GitHub username
- `ssh_private_key`: SSH private key (optional, manual entry)
- `git_author_name`: Git commit author name
- `git_author_email`: Git commit author email

**Bitbucket** (service: `bitbucket`):
- `bitbucket_token`: OAuth access token
- `bitbucket_refresh_token`: OAuth refresh token (required)
- `bitbucket_token_expires_at`: ISO timestamp
- `bitbucket_token_scope`: Granted scopes
- `bitbucket_username`: Bitbucket username

## Related Documentation

- [Portal OAuth](../portal.md) — Portal login OAuth (Discord, Google, Slack)
- [Claude OAuth](claude-oauth.md) — Claude Code CLI OAuth (PKCE flow)
- [Git Platform Module](../modules/git_platform.md) — Git platform API integration
- [Credential Store](../architecture/credential-store.md) — Encrypted credential storage

## Support

For issues or questions:

- Check portal logs: `make logs-module M=portal`
- Check git_platform logs: `make logs-module M=git-platform`
- GitHub Issues: [Report a bug](https://github.com/yourusername/your-agent-repo/issues)
