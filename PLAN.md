# Implementation Plan: Update New Task Modal with Searchable Dropdowns

## Overview
Update the New Task Modal (`NewTaskModal.tsx`) to replace text entry fields for repository URL and branch with searchable dropdowns similar to the New Project Modal. This will provide a better user experience with:
- Searchable repository dropdown showing existing user repos
- Searchable branch dropdown (populated when a repo is selected)
- Option to create a new branch (retain existing functionality)
- Consistent UX with the New Project Modal

## Current State Analysis

### Files Involved

#### Frontend Components
1. **`agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`** (lines 1-262)
   - Current implementation uses plain text inputs for `repo_url` and `branch`
   - Has logic for `newBranch` to create branches from a source branch
   - Two modes: with pre-filled repo (from repo detail page) and without

2. **`agent/portal/frontend/src/components/projects/NewProjectModal.tsx`** (lines 1-538)
   - Target reference implementation
   - Uses `useRepos` hook for fetching repositories
   - Has searchable dropdown with filter functionality (lines 290-343)
   - Multi-step wizard approach (details → repo → options)

3. **`agent/portal/frontend/src/hooks/useRepos.ts`** (lines 1-51)
   - Provides `useRepos()` hook for fetching repos
   - Provides `createRepo()` function
   - Already implemented and working

4. **`agent/portal/frontend/src/hooks/useRepoDetail.ts`** (lines 1-64)
   - Provides `useRepoDetail()` hook that fetches branches
   - Returns branches array with `GitBranch` objects

#### Backend API Endpoints (Already Implemented)
1. **`agent/portal/routers/repos.py`**
   - `GET /api/repos` - Lists repositories (lines 80-96)
   - `GET /api/repos/{owner}/{repo}/branches` - Lists branches (lines 166-182)

2. **`agent/portal/routers/tasks.py`**
   - `POST /api/tasks` - Creates new task (lines 91-117)
   - Accepts `repo_url`, `branch`, `source_branch` fields

#### TypeScript Types
1. **`agent/portal/frontend/src/types/index.ts`**
   - `GitRepo` interface (lines 162-174) - repository metadata
   - `GitBranch` interface (lines 176-181) - branch metadata
   - All required types already defined

## Implementation Strategy

### Approach: Incremental Enhancement
- Keep the existing modal structure
- Add dropdown UI conditionally based on whether repo is pre-filled
- Preserve existing functionality (new branch creation, auto-push, etc.)
- Reuse patterns from NewProjectModal for consistency

### Key Design Decisions

1. **When to show dropdowns vs. pre-filled info**
   - If `defaultRepoUrl` is provided → show repo as read-only, show branch dropdown
   - If no `defaultRepoUrl` → show both repo dropdown and branch dropdown
   - This maintains compatibility with existing usage from RepoDetailPage

2. **Branch selection flow**
   - When repo is selected from dropdown → fetch branches for that repo
   - Show searchable branch dropdown
   - Include "Create new branch" option at top of branch list
   - When "Create new branch" is selected → show new branch name input

3. **State management**
   - Add state for selected repo object (not just URL string)
   - Add state for selected branch object
   - Add state for branch loading/error
   - Track whether user wants to create new branch vs. select existing

## Detailed Implementation Steps

### Step 1: Create Reusable Hook for Branches
**File**: `agent/portal/frontend/src/hooks/useBranches.ts` (NEW)

**Purpose**: Create a focused hook for fetching branches given owner/repo

**Implementation**:
```typescript
import { useState, useEffect, useCallback } from "react";
import { api } from "@/api/client";
import type { GitBranch } from "@/types";

export function useBranches(owner: string, repo: string, enabled: boolean = true) {
  const [branches, setBranches] = useState<GitBranch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBranches = useCallback(async () => {
    if (!owner || !repo || !enabled) {
      setBranches([]);
      return;
    }
    setLoading(true);
    try {
      const result = await api<{ count: number; branches: GitBranch[] }>(
        `/api/repos/${owner}/${repo}/branches?per_page=100`
      );
      setBranches(result.branches || []);
      setError(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to fetch branches";
      const jsonMatch = msg.match(/\d+:\s*(\{.*\})/);
      if (jsonMatch) {
        try {
          const parsed = JSON.parse(jsonMatch[1]);
          setError(parsed.error || msg);
        } catch {
          setError(msg);
        }
      } else {
        setError(msg);
      }
      setBranches([]);
    } finally {
      setLoading(false);
    }
  }, [owner, repo, enabled]);

  useEffect(() => {
    fetchBranches();
  }, [fetchBranches]);

  return { branches, loading, error, refetch: fetchBranches };
}
```

**Rationale**: Separating branch fetching logic makes it reusable and testable. The `enabled` parameter allows conditional fetching.

---

### Step 2: Update NewTaskModal State Management
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Changes to state variables** (around lines 23-32):

**Add**:
```typescript
// Repository selection state
const [selectedRepo, setSelectedRepo] = useState<GitRepo | null>(null);
const [repoSearch, setRepoSearch] = useState("");

// Branch selection state
const [selectedBranch, setSelectedBranch] = useState<GitBranch | null>(null);
const [branchSearch, setBranchSearch] = useState("");
const [creatingNewBranch, setCreatingNewBranch] = useState(false);
```

**Modify**: Keep existing `repoUrl`, `branch`, `newBranch` for backward compatibility with API

**Add hooks**:
```typescript
// Fetch repos (only when no defaultRepoUrl)
const { repos, loading: reposLoading } = useRepos();

// Fetch branches when repo is selected
const { branches, loading: branchesLoading } = useBranches(
  selectedRepo?.owner || "",
  selectedRepo?.repo || "",
  !!selectedRepo // only fetch when repo is selected
);
```

**Rationale**: Maintain existing state for API compatibility while adding new UI-focused state.

---

### Step 3: Update useEffect for Initialization
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Modify** the initialization effect (lines 38-49):

**Add logic** to:
1. Parse `defaultRepoUrl` to extract owner/repo and create `selectedRepo` object
2. Find matching branch in branches list if `defaultBranch` is provided
3. Reset dropdown-specific state

```typescript
useEffect(() => {
  if (open) {
    setRepoUrl(defaultRepoUrl);
    setBranch(defaultBranch);
    setNewBranch("");
    setPrompt(defaultPrompt);
    setMode("execute");
    setAutoPush(false);
    setError("");
    setRepoSearch("");
    setBranchSearch("");
    setCreatingNewBranch(false);

    // If defaultRepoUrl is provided, parse it to populate selectedRepo
    if (defaultRepoUrl) {
      // Parse git URL to extract owner/repo
      // e.g., "https://github.com/owner/repo.git" -> owner="owner", repo="repo"
      const match = defaultRepoUrl.match(/github\.com\/([^\/]+)\/([^\/\.]+)/);
      if (match) {
        setSelectedRepo({
          owner: match[1],
          repo: match[2],
          full_name: `${match[1]}/${match[2]}`,
          clone_url: defaultRepoUrl,
          // Other fields can be null/default as we only need owner/repo for branch fetching
        } as GitRepo);
      }
    } else {
      setSelectedRepo(null);
    }

    setSelectedBranch(null);
    setTimeout(() => promptRef.current?.focus(), 50);
  }
}, [open, defaultRepoUrl, defaultBranch, defaultPrompt]);
```

**Rationale**: Properly initialize dropdown state when modal opens, especially when called from repo detail page.

---

### Step 4: Create Repository Dropdown Component (Section)
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Add** after the task description textarea (around line 164), when `!defaultRepoUrl`:

```tsx
{/* Repository selection dropdown */}
{!defaultRepoUrl && (
  <div className="space-y-3">
    <label className="block text-sm text-gray-400 mb-1.5">
      Repository <span className="text-gray-600">(optional)</span>
    </label>

    {/* Search input */}
    <div className="relative">
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
      <input
        value={repoSearch}
        onChange={(e) => setRepoSearch(e.target.value)}
        placeholder="Search repositories..."
        className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
      />
    </div>

    {/* Repo list dropdown */}
    {repoSearch && (
      <div className="max-h-52 overflow-y-auto border border-border rounded-lg divide-y divide-border bg-surface">
        {reposLoading ? (
          <div className="px-3 py-4 text-sm text-gray-500 text-center">Loading repos...</div>
        ) : filteredRepos.length === 0 ? (
          <div className="px-3 py-4 text-sm text-gray-500 text-center">
            No matching repos
          </div>
        ) : (
          filteredRepos.map((repo) => (
            <button
              key={repo.full_name}
              type="button"
              onClick={() => {
                setSelectedRepo(repo);
                setRepoUrl(repo.clone_url);
                setRepoSearch("");
                setSelectedBranch(null);
                setBranch(repo.default_branch);
              }}
              className="w-full text-left px-3 py-2.5 hover:bg-surface-lighter transition-colors"
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-white font-mono">{repo.full_name}</span>
                {repo.private && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
                    private
                  </span>
                )}
              </div>
              {repo.description && (
                <p className="text-xs text-gray-500 mt-0.5 truncate">{repo.description}</p>
              )}
            </button>
          ))
        )}
      </div>
    )}

    {/* Selected repo indicator */}
    {selectedRepo && (
      <div className="bg-accent/10 border border-accent/20 rounded-lg px-3 py-2 flex items-center justify-between">
        <span className="text-sm text-accent font-mono">{selectedRepo.full_name}</span>
        <button
          type="button"
          onClick={() => {
            setSelectedRepo(null);
            setRepoUrl("");
            setSelectedBranch(null);
            setBranch("");
          }}
          className="p-1 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
        >
          <X size={14} />
        </button>
      </div>
    )}
  </div>
)}
```

**Rationale**: Following the NewProjectModal pattern (lines 290-343) for consistency. Only show when repo isn't pre-filled.

---

### Step 5: Create Branch Dropdown Component (Section)
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Add** after repository selection, when repo is selected or pre-filled:

```tsx
{/* Branch selection dropdown */}
{(selectedRepo || defaultRepoUrl) && (
  <div className="space-y-3">
    <label className="block text-sm text-gray-400 mb-1.5">
      <GitBranch size={14} className="inline mr-1 -mt-0.5" />
      Branch
    </label>

    {/* "Create new branch" option */}
    <button
      type="button"
      onClick={() => {
        setCreatingNewBranch(!creatingNewBranch);
        if (!creatingNewBranch) {
          setSelectedBranch(null);
          setNewBranch("");
        }
      }}
      className={`w-full text-left px-3 py-2 rounded-lg border transition-colors ${
        creatingNewBranch
          ? "bg-accent/10 border-accent/30 text-accent"
          : "bg-surface border-border text-gray-300 hover:bg-surface-lighter"
      }`}
    >
      <Plus size={14} className="inline mr-2 -mt-0.5" />
      Create new branch
    </button>

    {/* New branch name input (shown when creating new branch) */}
    {creatingNewBranch && (
      <div>
        <input
          value={newBranch}
          onChange={(e) => setNewBranch(e.target.value)}
          placeholder="feature/my-new-feature"
          className="w-full px-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent font-mono"
        />
        {newBranch.trim() && (
          <p className="text-xs text-gray-500 mt-1">
            Will create <span className="text-accent font-mono">{newBranch.trim()}</span> from{" "}
            <span className="font-mono">{selectedBranch?.name || branch || "default branch"}</span>
          </p>
        )}
      </div>
    )}

    {/* Existing branch selection */}
    {!creatingNewBranch && (
      <>
        {/* Search input */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            value={branchSearch}
            onChange={(e) => setBranchSearch(e.target.value)}
            placeholder="Search branches..."
            className="w-full pl-9 pr-3 py-2 rounded-lg bg-surface border border-border text-white text-sm placeholder-gray-500 focus:outline-none focus:border-accent"
          />
        </div>

        {/* Branch list dropdown */}
        {branchSearch && (
          <div className="max-h-52 overflow-y-auto border border-border rounded-lg divide-y divide-border bg-surface">
            {branchesLoading ? (
              <div className="px-3 py-4 text-sm text-gray-500 text-center">Loading branches...</div>
            ) : filteredBranches.length === 0 ? (
              <div className="px-3 py-4 text-sm text-gray-500 text-center">
                No matching branches
              </div>
            ) : (
              filteredBranches.map((branch) => (
                <button
                  key={branch.name}
                  type="button"
                  onClick={() => {
                    setSelectedBranch(branch);
                    setBranch(branch.name);
                    setBranchSearch("");
                  }}
                  className="w-full text-left px-3 py-2.5 hover:bg-surface-lighter transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-white font-mono">{branch.name}</span>
                    {branch.protected && (
                      <Shield size={12} className="text-yellow-400" />
                    )}
                  </div>
                  {branch.updated_at && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      Updated {formatRelativeDate(branch.updated_at)}
                    </p>
                  )}
                </button>
              ))
            )}
          </div>
        )}

        {/* Selected branch indicator */}
        {selectedBranch && (
          <div className="bg-accent/10 border border-accent/20 rounded-lg px-3 py-2 flex items-center justify-between">
            <span className="text-sm text-accent font-mono">{selectedBranch.name}</span>
            <button
              type="button"
              onClick={() => {
                setSelectedBranch(null);
                setBranch("");
              }}
              className="p-1 rounded hover:bg-surface-lighter text-gray-400 hover:text-gray-200"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </>
    )}
  </div>
)}
```

**Rationale**:
- Toggle between "create new" and "select existing" branch modes
- Show branch list with search filtering
- Display branch metadata (protected status, last update)
- Consistent with repo dropdown pattern

---

### Step 6: Add Filtering Logic
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Add** computed values using `useMemo` (after state declarations, around line 46):

```typescript
// Filter repos by search
const filteredRepos = useMemo(() => {
  if (!repoSearch.trim()) return [];
  const q = repoSearch.toLowerCase();
  return repos.filter(
    (r) =>
      r.full_name.toLowerCase().includes(q) ||
      (r.description || "").toLowerCase().includes(q)
  );
}, [repos, repoSearch]);

// Filter branches by search
const filteredBranches = useMemo(() => {
  if (!branchSearch.trim()) return [];
  const q = branchSearch.toLowerCase();
  return branches.filter((b) => b.name.toLowerCase().includes(q));
}, [branches, branchSearch]);
```

**Rationale**: Efficient filtering with memoization to avoid recalculating on every render.

---

### Step 7: Add Date Formatting Helper
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Add** helper function at top of file (before component, around line 14):

```typescript
function formatRelativeDate(dateStr: string | null): string {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDays = Math.floor(diffHr / 24);
  if (diffDays < 30) return `${diffDays}d ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
```

**Rationale**: Show human-friendly relative times for branch updates. Borrowed from RepoDetailPage (lines 41-54).

---

### Step 8: Update Imports
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Modify** import statement at top (lines 1-4):

```typescript
import { useState, useEffect, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { X, GitBranch, Upload, Search, Plus, Shield } from "lucide-react";
import { api } from "@/api/client";
import { useRepos } from "@/hooks/useRepos";
import { useBranches } from "@/hooks/useBranches";
import type { GitRepo, GitBranch as GitBranchType } from "@/types";
```

**Rationale**: Add new dependencies for dropdowns and hooks.

---

### Step 9: Update Submit Handler Logic
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Modify** `handleSubmit` function (lines 63-96):

**Update** the source_branch logic:

```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  if (!prompt.trim()) return;
  setSubmitting(true);
  setError("");

  try {
    const body: Record<string, string | boolean> = { prompt: prompt.trim(), mode };

    // Determine repo_url
    if (selectedRepo) {
      body.repo_url = selectedRepo.clone_url;
    } else if (repoUrl.trim()) {
      body.repo_url = repoUrl.trim();
    }

    // Determine branch and source_branch
    if (creatingNewBranch && newBranch.trim()) {
      body.branch = newBranch.trim();
      // Source branch is either selected branch or the default/provided branch
      const sourceBranchName = selectedBranch?.name || branch.trim();
      if (sourceBranchName) {
        body.source_branch = sourceBranchName;
      }
    } else if (selectedBranch) {
      body.branch = selectedBranch.name;
    } else if (branch.trim()) {
      body.branch = branch.trim();
    }

    if (autoPush) body.auto_push = true;

    const result = await api<{ task_id: string }>("/api/tasks", {
      method: "POST",
      body: JSON.stringify(body),
    });

    onClose();
    onCreated?.();

    if (result.task_id) {
      navigate(`/tasks/${result.task_id}`);
    }
  } catch (e) {
    setError(e instanceof Error ? e.message : "Failed to create task");
  } finally {
    setSubmitting(false);
  }
};
```

**Rationale**:
- Properly handle new state variables in API call
- Maintain backward compatibility with pre-filled values
- Correctly set source_branch when creating new branch

---

### Step 10: Remove Old Text Input UI (when not pre-filled)
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Remove** or **conditionally hide** the old text input section (lines 167-188):

The existing code block:
```tsx
{!defaultRepoUrl && (
  <div className="flex flex-col sm:flex-row gap-3">
    <div className="flex-1">
      <label className="block text-sm text-gray-400 mb-1.5">Repository URL</label>
      <input ... />
    </div>
    <div className="sm:w-40">
      <label className="block text-sm text-gray-400 mb-1.5">Branch</label>
      <input ... />
    </div>
  </div>
)}
```

**Replace** with the new dropdown sections from Steps 4 and 5.

**Rationale**: Remove redundant UI; dropdowns replace text inputs.

---

### Step 11: Update Pre-filled Repo Display
**File**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`

**Modify** the pre-filled repository display section (lines 119-151):

**Current**: Shows repo URL and branch with a simple new branch input.

**Update**:
- Keep the repo display as read-only
- Replace the new branch text input with the branch dropdown (from Step 5)
- This shows existing branches when coming from repo detail page

```tsx
{defaultRepoUrl && (
  <div className="space-y-3">
    {/* Read-only repo display */}
    <div className="bg-surface/50 border border-border rounded-lg px-3 py-2">
      <span className="text-xs text-gray-500 block mb-0.5">Repository</span>
      <span className="text-sm text-gray-300 font-mono">{selectedRepo?.full_name || repoUrl}</span>
    </div>

    {/* Branch dropdown - reuse from Step 5 */}
    {/* (Insert branch selection UI here) */}
  </div>
)}
```

**Rationale**: Provide branch selection even when repo is pre-filled (common use case from repo detail page).

---

## Testing Strategy

### Manual Testing Checklist

1. **New task without pre-filled repo**
   - [ ] Open modal from task list page
   - [ ] Search and select a repository
   - [ ] Verify branches load for selected repo
   - [ ] Search and select a branch
   - [ ] Create task and verify correct repo_url and branch sent to API

2. **New task with pre-filled repo (from repo detail page)**
   - [ ] Open modal from repository detail page
   - [ ] Verify repo shown as read-only
   - [ ] Verify branches load automatically
   - [ ] Select an existing branch
   - [ ] Create task and verify correct parameters

3. **Create new branch flow**
   - [ ] Click "Create new branch" button
   - [ ] Enter new branch name
   - [ ] Select source branch from dropdown
   - [ ] Verify source_branch parameter sent correctly

4. **Search functionality**
   - [ ] Test repo search with various queries
   - [ ] Test branch search with partial names
   - [ ] Verify filtering is case-insensitive

5. **Edge cases**
   - [ ] No repos available
   - [ ] No branches in selected repo
   - [ ] API errors (repo/branch fetch failures)
   - [ ] Network timeouts
   - [ ] Selecting then clearing selections

### Regression Testing

1. **Existing functionality preserved**
   - [ ] Auto-push toggle still works
   - [ ] Mode selection (execute vs. plan) still works
   - [ ] Modal closes on ESC key
   - [ ] Modal closes on outside click
   - [ ] Task navigation after creation
   - [ ] Error handling and display

2. **Integration points**
   - [ ] Opening modal from TaskList page
   - [ ] Opening modal from RepoDetailPage
   - [ ] Opening modal from NewTaskForm component
   - [ ] Callback `onCreated` executes properly

## Rollback Plan

If issues are discovered:
1. The changes are isolated to the `NewTaskModal.tsx` component and new `useBranches.ts` hook
2. Revert to text inputs by:
   - Removing dropdown UI code
   - Restoring original text input sections
   - Removing `useBranches` and `useRepos` hooks from component
3. API contract remains unchanged, so no backend changes needed for rollback

## Performance Considerations

1. **API Calls**
   - Repos are fetched once on mount via `useRepos` hook (cached)
   - Branches only fetch when repo is selected (conditional via `enabled` parameter)
   - No unnecessary refetching on re-renders (handled by hooks)

2. **Filtering**
   - Client-side filtering using `useMemo` for efficiency
   - Only recomputes when repos/branches or search query changes
   - No network calls for filtering

3. **UX Optimizations**
   - Debouncing not strictly needed (filtering is instant on client side)
   - Could add if repo/branch lists become very large (100+ items)

## Accessibility Considerations

1. **Keyboard Navigation**
   - Ensure dropdowns are keyboard-navigable
   - Tab order should be logical (repo → branch → mode → auto-push → submit)
   - ESC to close modal (already implemented)
   - Enter to submit form

2. **Screen Readers**
   - Use semantic HTML (`<label>`, `<button>`)
   - Include descriptive text for search inputs
   - ARIA labels for close buttons and icon-only buttons

3. **Visual Indicators**
   - Clear focus states for interactive elements
   - Loading states with spinners
   - Error states with red text
   - Selected items with accent color

## Future Enhancements (Out of Scope)

1. Recent repos/branches at top of list
2. Favorites/pinned repositories
3. Branch creation directly in modal (via API)
4. Protected branch warnings before selection
5. PR creation from task completion
6. Integration with default branch preferences

## Dependencies

### NPM Packages (Already Installed)
- `react` - Core framework
- `lucide-react` - Icons (Search, Plus, Shield, X, GitBranch)
- `react-router-dom` - Navigation after task creation

### Internal Dependencies
- `@/api/client` - API wrapper
- `@/hooks/useRepos` - Existing hook (no changes needed)
- `@/hooks/useBranches` - New hook to create
- `@/types` - Type definitions (GitRepo, GitBranch)

### API Endpoints (Already Implemented)
- `GET /api/repos` - List repositories
- `GET /api/repos/{owner}/{repo}/branches` - List branches
- `POST /api/tasks` - Create task (no changes needed)

## Success Criteria

1. Users can search and select repos from a dropdown instead of typing URLs
2. Users can search and select branches from a dropdown
3. Users can still create new branches with a source branch
4. Modal maintains all existing functionality (mode, auto-push, etc.)
5. UI is consistent with NewProjectModal design patterns
6. No regressions in task creation flow
7. Proper error handling for API failures
8. Responsive design works on mobile and desktop

## Estimated Complexity

- **Low Risk**: Using existing, tested patterns from NewProjectModal
- **Low Complexity**: Mostly UI changes, no new API endpoints needed
- **High Value**: Improved UX, reduced user errors, consistency across modals

## Files Changed Summary

1. **NEW**: `agent/portal/frontend/src/hooks/useBranches.ts` (~65 lines)
2. **MODIFIED**: `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx` (~400 lines, was 262)
   - Add imports (hooks, types, icons)
   - Add state variables (selectedRepo, selectedBranch, etc.)
   - Add filtering logic (useMemo)
   - Add repository dropdown UI section
   - Add branch dropdown UI section
   - Update submit handler
   - Add date formatting helper
   - Remove/replace old text inputs
3. **NO CHANGES**: Backend files, API contracts, types, other components

---

## Implementation Order

1. Create `useBranches` hook (Step 1) - isolated, testable
2. Update imports in `NewTaskModal` (Step 8) - safe
3. Add state variables (Step 2) - non-breaking
4. Add filtering logic (Step 6) - non-breaking
5. Add date helper (Step 7) - non-breaking
6. Update initialization effect (Step 3) - be careful with defaults
7. Add repository dropdown UI (Step 4) - visible change
8. Add branch dropdown UI (Step 5) - visible change
9. Update pre-filled repo display (Step 11) - visible change
10. Update submit handler (Step 9) - critical, test thoroughly
11. Remove old text inputs (Step 10) - final cleanup

This order minimizes risk by building up functionality incrementally and saving breaking changes for last.
