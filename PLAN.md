# Onboarding Modal Implementation Plan

## Overview

Implement a multi-step onboarding modal that appears on each fresh sign-in when a user has not yet configured their Claude OAuth, GitHub OAuth, or LLM API keys. The modal will guide new users through setup with clear messaging that token usage is heavily capped when using shared system credentials. Model dropdowns will replace free-text input fields, with a configurable preset list.

---

## Goals

1. **Onboarding modal** — appears once per sign-in session (stored in `sessionStorage`, not `localStorage`, so it triggers again on fresh login but not on page refresh).
2. **Trigger condition** — shown if any of the following are missing: Claude OAuth credentials, GitHub OAuth credentials, or at least one LLM API key.
3. **Clear cap messaging** — prominently communicate that token usage is heavily restricted without own credentials.
4. **Model dropdowns** — replace free-text model inputs with searchable/selectable dropdowns from a configurable preset list (still allowing free-text fallback).
5. **Multi-step wizard** — one step per missing credential type, plus a welcome/intro step and a completion step.
6. **Configurable presets** — model presets stored in a single config file for easy customisation.

---

## Architecture Decisions

### Where to track "shown this session"

Use `sessionStorage` key `onboarding_shown`. This means:
- The modal shows again on a fresh browser session (new login) — desired behaviour.
- The modal does **not** show on page refresh within the same session — avoids annoyance.
- No backend state needed; the check is purely frontend.

### How to determine what's missing

A new **single** backend endpoint `GET /api/settings/onboarding-status` will return a consolidated status object covering all three credential areas. This avoids three parallel API calls on every sign-in and keeps the logic server-side.

```json
{
  "has_claude_oauth": false,
  "has_github_oauth": false,
  "has_llm_key": false,
  "has_any_key": false,
  "token_budget_monthly": 50000,
  "tokens_used_this_month": 12500
}
```

### Model preset configuration

A TypeScript config file at `portal/frontend/src/config/modelPresets.ts` exports a typed list of presets. To add/remove models, only this file changes — no component edits required.

```ts
export interface ModelPreset {
  value: string;        // e.g. "claude-sonnet-4-20250514"
  label: string;        // e.g. "Claude Sonnet 4 (Anthropic)"
  provider: "anthropic" | "openai" | "google";
  useCase?: string;     // e.g. "Best for most tasks"
}

export const DEFAULT_MODEL_PRESETS: ModelPreset[] = [ ... ];
export const SUMMARIZATION_MODEL_PRESETS: ModelPreset[] = [ ... ];
export const EMBEDDING_MODEL_PRESETS: ModelPreset[] = [ ... ];
```

---

## Files to Create

| File | Purpose |
|------|---------|
| `agent/portal/frontend/src/config/modelPresets.ts` | Model preset lists (configurable) |
| `agent/portal/frontend/src/components/onboarding/OnboardingModal.tsx` | Main modal orchestrator |
| `agent/portal/frontend/src/components/onboarding/steps/WelcomeStep.tsx` | Welcome/intro step |
| `agent/portal/frontend/src/components/onboarding/steps/ClaudeOAuthStep.tsx` | Claude OAuth setup step |
| `agent/portal/frontend/src/components/onboarding/steps/GitHubOAuthStep.tsx` | GitHub OAuth setup step |
| `agent/portal/frontend/src/components/onboarding/steps/LlmSettingsStep.tsx` | LLM API keys + model dropdowns step |
| `agent/portal/frontend/src/components/onboarding/steps/CompleteStep.tsx` | Completion/summary step |
| `agent/portal/frontend/src/components/common/ModelSelect.tsx` | Reusable model dropdown component |

---

## Files to Modify

| File | Change |
|------|--------|
| `agent/portal/routers/settings.py` | Add `GET /api/settings/onboarding-status` endpoint |
| `agent/portal/frontend/src/App.tsx` | Mount `OnboardingModal` in the authenticated layout, fetch onboarding status after auth |
| `agent/portal/frontend/src/components/settings/LlmSettingsCard.tsx` | Replace free-text model inputs with `ModelSelect` dropdowns |

---

## Step-by-Step Implementation

### Step 1 — Backend endpoint: `GET /api/settings/onboarding-status`

**File:** `agent/portal/routers/settings.py`

Add a new endpoint that combines three credential checks into one response. This reuses `CredentialStore` methods already in use elsewhere in the same file.

```python
@router.get("/onboarding-status")
async def get_onboarding_status(user: PortalUser = Depends(require_auth)) -> dict:
    """Return credential setup status for onboarding modal."""
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        llm_creds   = await store.get_all(session, user.user_id, "llm_settings")
        claude_creds = await store.get(session, user.user_id, "claude_code", "credentials_json")
        github_creds = await store.get(session, user.user_id, "github", "github_token")
        db_user_result = await session.execute(select(User).where(User.id == user.user_id))
        db_user = db_user_result.scalar_one_or_none()

    api_keys = {"anthropic_api_key", "openai_api_key", "google_api_key"}
    has_llm = bool(api_keys & set(llm_creds.keys()))

    return {
        "has_claude_oauth": claude_creds is not None,
        "has_github_oauth": github_creds is not None,
        "has_llm_key": has_llm,
        "needs_onboarding": not (has_llm and claude_creds and github_creds),
        "token_budget_monthly": db_user.token_budget_monthly if db_user else None,
        "tokens_used_this_month": db_user.tokens_used_this_month if db_user else 0,
    }
```

The endpoint reuses `_get_credential_store()` (already defined in the same file) and `CredentialStore.get_all` / `CredentialStore.get` methods. No new imports needed beyond `User` (already imported).

---

### Step 2 — Model preset configuration file

**File:** `agent/portal/frontend/src/config/modelPresets.ts`

```ts
export interface ModelPreset {
  value: string;
  label: string;
  provider: "anthropic" | "openai" | "google";
  useCase?: string;
}

export const DEFAULT_MODEL_PRESETS: ModelPreset[] = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4",        provider: "anthropic", useCase: "Best for most tasks" },
  { value: "claude-opus-4-5-20251101", label: "Claude Opus 4.5",        provider: "anthropic", useCase: "Most capable Anthropic model" },
  { value: "claude-haiku-4-5-20251001",label: "Claude Haiku 4.5",       provider: "anthropic", useCase: "Fast and affordable" },
  { value: "gpt-4o",                   label: "GPT-4o",                  provider: "openai",    useCase: "OpenAI flagship" },
  { value: "gpt-4o-mini",              label: "GPT-4o Mini",             provider: "openai",    useCase: "Fast and cheap" },
  { value: "gemini-2.0-flash",         label: "Gemini 2.0 Flash",        provider: "google",    useCase: "Google fast model" },
];

export const SUMMARIZATION_MODEL_PRESETS: ModelPreset[] = [
  { value: "gpt-4o-mini",              label: "GPT-4o Mini",             provider: "openai" },
  { value: "claude-haiku-4-5-20251001",label: "Claude Haiku 4.5",        provider: "anthropic" },
  { value: "gemini-2.0-flash",         label: "Gemini 2.0 Flash",        provider: "google" },
];

export const EMBEDDING_MODEL_PRESETS: ModelPreset[] = [
  { value: "text-embedding-3-small",   label: "text-embedding-3-small",  provider: "openai" },
  { value: "text-embedding-3-large",   label: "text-embedding-3-large",  provider: "openai" },
  { value: "gemini-embedding-001",     label: "gemini-embedding-001",     provider: "google" },
];
```

This file is the **only place** that needs updating when model names change.

---

### Step 3 — Reusable `ModelSelect` component

**File:** `agent/portal/frontend/src/components/common/ModelSelect.tsx`

A controlled select/combobox with:
- Grouped options by provider (Anthropic / OpenAI / Google sections)
- A "Custom…" option at the bottom that reveals a free-text input (for any model not in the presets)
- Displays `useCase` descriptions in option labels
- Standard TailwindCSS styling consistent with existing inputs

Props:
```ts
interface ModelSelectProps {
  presets: ModelPreset[];
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  id?: string;
}
```

Implementation note: Use a native `<select>` with `<optgroup>` for providers — avoids adding a new dependency. A custom text input appears below when "custom" is selected, matching the existing plain `<input>` style.

---

### Step 4 — Onboarding modal step components

Each step is a self-contained React component that receives `onNext: () => void` and `onSkip: () => void`.

#### `WelcomeStep.tsx`
- Title: "Welcome to Nexus"
- Explains the three things to set up (Claude OAuth, GitHub, LLM keys)
- **Prominent warning banner** (yellow/amber): "Token usage is heavily capped on shared credentials. Set up your own keys to get unrestricted access." Include the actual monthly budget figure from the onboarding status if available.
- CTA: "Get started" → `onNext()`
- Small link: "Skip for now" → closes modal (marks session as shown)

#### `ClaudeOAuthStep.tsx`
- Title: "Connect your Claude account"
- Reuses the existing `ClaudeOAuthFlow` component from `CredentialCard.tsx` (extract it or import it)
- Explains: "Claude OAuth lets the agent run Claude Code tasks using your own Claude subscription"
- Token cap messaging: "Without this, Claude Code tasks use shared quota and may be throttled"
- Progress indicator showing step N of total
- "Already done / Skip this step" link

#### `GitHubOAuthStep.tsx`
- Title: "Connect GitHub"
- Reuses `GitOAuthFlow` component (service="github")
- Explains: "Required for code tasks, PRs, and repository management"
- "Skip this step" link

#### `LlmSettingsStep.tsx`
- Title: "Set up LLM API keys"
- Minimal version of `LlmSettingsCard` focused on just:
  1. API key inputs (Anthropic, OpenAI, Google) — password fields, same as existing
  2. Default model selector using `ModelSelect` (with `DEFAULT_MODEL_PRESETS`)
- **Does not** show summarization/embedding model pickers here (too much for onboarding)
- Prominent cap warning: "Without your own key, you share a monthly budget of X tokens across all users"
- On save: calls existing `PUT /api/settings/credentials/llm_settings`
- "Skip for now" link

#### `CompleteStep.tsx`
- Title: "You're all set!"
- Summary of what was configured (green checkmarks) vs what was skipped (grey dashes)
- "Go to dashboard" button → closes modal

---

### Step 5 — Main `OnboardingModal.tsx` orchestrator

**File:** `agent/portal/frontend/src/components/onboarding/OnboardingModal.tsx`

```ts
interface OnboardingStatus {
  has_claude_oauth: boolean;
  has_github_oauth: boolean;
  has_llm_key: boolean;
  needs_onboarding: boolean;
  token_budget_monthly: number | null;
  tokens_used_this_month: number;
}

interface OnboardingModalProps {
  status: OnboardingStatus;
  onClose: () => void;
}
```

Logic:
1. Determine which steps to show based on `status` (only include steps for missing credentials)
2. Always include Welcome (first) and Complete (last)
3. Maintain `currentStep: number` state
4. Track which steps were completed vs skipped with `completedSteps: Set<string>`
5. Show step progress indicator (e.g. "Step 2 of 4") in the modal header
6. Modal size: `lg` (uses existing `Modal` component)
7. The modal cannot be dismissed by clicking the backdrop — must use "Skip" or complete
8. On final close: sets `sessionStorage.setItem("onboarding_shown", "1")`

Step routing logic:
```ts
const steps: StepDef[] = [
  { id: "welcome",    component: WelcomeStep,     skip: false },
  { id: "claude",     component: ClaudeOAuthStep, skip: status.has_claude_oauth },
  { id: "github",     component: GitHubOAuthStep, skip: status.has_github_oauth },
  { id: "llm",        component: LlmSettingsStep, skip: status.has_llm_key },
  { id: "complete",   component: CompleteStep,    skip: false },
].filter(s => !s.skip);
```

---

### Step 6 — Wire up in `App.tsx`

**File:** `agent/portal/frontend/src/App.tsx`

Modify the authenticated `App` component to:

1. After verifying the JWT (the existing `api("/api/auth/me")` call), also fetch `GET /api/settings/onboarding-status`.
2. Check `sessionStorage.getItem("onboarding_shown")` — if already set this session, skip the modal.
3. If `status.needs_onboarding` is true and session flag is not set, store the status in state and render `<OnboardingModal>` over the app.
4. Pass `onClose` that sets the session flag and clears modal state.

The `OnboardingModal` is rendered **outside** the `<Layout>` / `<Routes>` tree, positioned via `fixed inset-0 z-[100]` so it appears over everything.

```tsx
// In App component state:
const [onboardingStatus, setOnboardingStatus] = useState<OnboardingStatus | null>(null);
const [showOnboarding, setShowOnboarding] = useState(false);

// After auth verification:
if (!sessionStorage.getItem("onboarding_shown")) {
  const obStatus = await api<OnboardingStatus>("/api/settings/onboarding-status");
  if (obStatus.needs_onboarding) {
    setOnboardingStatus(obStatus);
    setShowOnboarding(true);
  } else {
    sessionStorage.setItem("onboarding_shown", "1");
  }
}

// In JSX (alongside existing routes):
{showOnboarding && onboardingStatus && (
  <OnboardingModal
    status={onboardingStatus}
    onClose={() => {
      sessionStorage.setItem("onboarding_shown", "1");
      setShowOnboarding(false);
    }}
  />
)}
```

Note: The onboarding status fetch is wrapped in a try/catch — if the credential store is not configured (503), no modal is shown.

---

### Step 7 — Update `LlmSettingsCard.tsx` to use `ModelSelect`

**File:** `agent/portal/frontend/src/components/settings/LlmSettingsCard.tsx`

Replace the three plain `<input type="text">` fields for `default_model`, `summarization_model`, and `embedding_model` with `<ModelSelect>` using the appropriate preset lists. The component already fetches and pre-fills these values, so the change is a straightforward swap of the input element.

The `ModelSelect` "custom" option falls back to a text input so existing saved values not in the preset list continue to work.

---

## UI Design Notes

### Token cap messaging (used across multiple steps)

Use a consistent amber/yellow callout block for the cap warning:

```
⚠ Token access is heavily capped without your own credentials
  Shared accounts have a monthly budget of ~X tokens across all users.
  Add your own API keys or OAuth connections to get unrestricted access.
```

This block appears on:
- The Welcome step (overview)
- The LlmSettingsStep (adjacent to the API key inputs)
- Potentially the ClaudeOAuthStep sidebar note

### Progress indicator

Inside the modal header (next to the title), show: `Step N of M` in muted text. Steps that were already configured are skipped entirely from the count.

### Modal close behaviour

- **Backdrop click** — disabled for onboarding modal (unlike the generic `Modal` component). Achieved by not passing `onClose` to the backdrop overlay, or wrapping the existing `Modal` with `onClose={() => {}}` for the backdrop and providing explicit buttons inside.
- **Explicit skip/close** buttons on each step and in the modal header ("×" button) are available and all trigger the same `onClose` handler.

---

## Testing Plan

1. **Happy path** — fresh sign-in with no credentials set: modal appears with all three credential steps visible.
2. **Partial setup** — user has LLM key but no Claude/GitHub: only those two steps appear.
3. **Fully configured** — no modal shown; `needs_onboarding: false` from API.
4. **Page refresh** — modal does not re-appear within the same browser session.
5. **New login** (clear sessionStorage) — modal re-appears if credentials still missing.
6. **Skip all** — user can dismiss via "Skip for now" at any step; modal does not return this session.
7. **Model dropdown** — preset options grouped by provider; custom value falls back to text input; existing saved non-preset model names still display correctly.
8. **Cap warning** — budget figure shows correctly when `token_budget_monthly` is not null; shows generic message when null.
9. **Credential store not configured** — 503 from onboarding-status is caught silently, no modal shown.
10. **OAuth flows inside modal** — Claude and GitHub OAuth flows complete successfully within the modal steps.

---

## Implementation Order

1. `agent/portal/routers/settings.py` — add `/onboarding-status` endpoint
2. `agent/portal/frontend/src/config/modelPresets.ts` — create preset config
3. `agent/portal/frontend/src/components/common/ModelSelect.tsx` — create reusable component
4. `agent/portal/frontend/src/components/onboarding/steps/WelcomeStep.tsx`
5. `agent/portal/frontend/src/components/onboarding/steps/ClaudeOAuthStep.tsx`
6. `agent/portal/frontend/src/components/onboarding/steps/GitHubOAuthStep.tsx`
7. `agent/portal/frontend/src/components/onboarding/steps/LlmSettingsStep.tsx`
8. `agent/portal/frontend/src/components/onboarding/steps/CompleteStep.tsx`
9. `agent/portal/frontend/src/components/onboarding/OnboardingModal.tsx`
10. `agent/portal/frontend/src/App.tsx` — wire up modal after auth
11. `agent/portal/frontend/src/components/settings/LlmSettingsCard.tsx` — swap in `ModelSelect`

---

## Out of Scope

- Backend persistence of "onboarding completed" state (sessionStorage is sufficient for the requirement of showing once per sign-in)
- Admin configuration of the model preset list via the UI (file-based config is sufficient)
- Bitbucket OAuth onboarding step (GitHub is the primary target; Bitbucket can be set up later in Settings)
- Telegram / Slack account linking in onboarding (out of scope for initial version)
