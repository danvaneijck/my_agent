# Implementation Plan: GitHub Actions on Repo Detail Page and Home Dashboard

## Overview

Add a **GitHub Actions** widget to two places in the portal:

1. **Repo Detail Page** (`RepoDetailPage.tsx`) — a new "Actions" tab alongside Branches, Pull Requests, and Issues, showing the latest workflow runs for the selected repository.
2. **Home Dashboard** (`HomePage.tsx`) — a new "GitHub Actions" dashboard card showing recent/in-progress workflow runs across all repos.

---

## GitHub Actions API

The GitHub REST API endpoint for workflow runs is:

```
GET /repos/{owner}/{repo}/actions/runs
```

Parameters of interest: `status` (in_progress, queued, completed, etc.), `per_page`, `branch`.

Each run object contains: `id`, `name` (workflow name), `display_title`, `status` (`queued`, `in_progress`, `completed`), `conclusion` (`success`, `failure`, `cancelled`, `skipped`, `timed_out`, `neutral`), `head_branch`, `head_sha`, `event` (push, pull_request, etc.), `created_at`, `updated_at`, `html_url`.

---

## Files to Create / Modify

### 1. `agent/modules/git_platform/providers/base.py`
**Add** an abstract method `list_workflow_runs`.

### 2. `agent/modules/git_platform/providers/github.py`
**Add** implementation of `list_workflow_runs` using `GET /repos/{owner}/{repo}/actions/runs`.

### 3. `agent/modules/git_platform/providers/bitbucket.py`
**Add** a stub implementation of `list_workflow_runs` (Bitbucket uses Pipelines, not Actions — return empty list with a note).

### 4. `agent/modules/git_platform/tools.py`
**Add** `list_workflow_runs` method delegating to the provider.

### 5. `agent/modules/git_platform/manifest.py`
**Add** `git_platform.list_workflow_runs` tool definition.

### 6. `agent/modules/git_platform/main.py`
**Add** `"list_workflow_runs"` to `TOOL_MAP`.

### 7. `agent/portal/routers/repos.py`
**Add** `GET /api/repos/{owner}/{repo}/actions` endpoint (portal proxy to the module tool).
**Add** `GET /api/repos/actions/running` endpoint (cross-repo summary of in-progress runs for the dashboard card).

### 8. `agent/portal/frontend/src/types/index.ts`
**Add** `GitWorkflowRun` and `GitWorkflowRunSummary` TypeScript interfaces.

### 9. `agent/portal/frontend/src/hooks/useRepoDetail.ts`
**Add** workflow runs to the data fetched by `useRepoDetail`.

### 10. `agent/portal/frontend/src/hooks/useDashboard.ts`
**Add** `workflowRuns` fetch (cross-repo running/recent actions) to `useDashboard`.

### 11. `agent/portal/frontend/src/pages/RepoDetailPage.tsx`
**Add** "Actions" tab with a workflow runs list.

### 12. `agent/portal/frontend/src/pages/HomePage.tsx`
**Add** `GitHubActionsCard` component and render it in the dashboard grid.

---

## Step-by-Step Implementation

### Step 1 — Add `list_workflow_runs` to the base provider

**File:** `agent/modules/git_platform/providers/base.py`

Add an abstract method:

```python
@abstractmethod
async def list_workflow_runs(
    self, owner: str, repo: str,
    status: str | None = None,
    branch: str | None = None,
    per_page: int = 20,
) -> dict:
    """List GitHub Actions workflow runs for a repository."""
```

---

### Step 2 — Implement `list_workflow_runs` in GitHub provider

**File:** `agent/modules/git_platform/providers/github.py`

Add a new method to `GitHubProvider`:

```python
async def list_workflow_runs(
    self, owner: str, repo: str,
    status: str | None = None,
    branch: str | None = None,
    per_page: int = 20,
) -> dict:
    params: dict = {"per_page": min(per_page, 100)}
    if status:
        params["status"] = status
    if branch:
        params["branch"] = branch
    data = await self._get(f"/repos/{owner}/{repo}/actions/runs", **params)
    runs = [
        {
            "id": r["id"],
            "name": r["name"],          # workflow name
            "display_title": r.get("display_title", r["name"]),
            "status": r["status"],       # queued | in_progress | completed
            "conclusion": r.get("conclusion"),  # success | failure | cancelled | ...
            "event": r.get("event"),     # push | pull_request | schedule | ...
            "branch": r.get("head_branch"),
            "sha": (r.get("head_sha") or "")[:12],
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "url": r.get("html_url"),
        }
        for r in data.get("workflow_runs", [])
    ]
    return {"total_count": data.get("total_count", len(runs)), "workflow_runs": runs}
```

---

### Step 3 — Add stub to Bitbucket provider

**File:** `agent/modules/git_platform/providers/bitbucket.py`

Implement the abstract method (Bitbucket uses Pipelines, not Actions):

```python
async def list_workflow_runs(
    self, owner: str, repo: str,
    status: str | None = None,
    branch: str | None = None,
    per_page: int = 20,
) -> dict:
    # Bitbucket uses Pipelines, not GitHub Actions
    return {"total_count": 0, "workflow_runs": [], "note": "GitHub Actions not available for Bitbucket repositories."}
```

---

### Step 4 — Add delegation in tools.py

**File:** `agent/modules/git_platform/tools.py`

```python
async def list_workflow_runs(
    self, owner: str, repo: str,
    status: str | None = None,
    branch: str | None = None,
    per_page: int = 20,
) -> dict:
    return await self.provider.list_workflow_runs(
        owner, repo, status=status, branch=branch, per_page=per_page
    )
```

---

### Step 5 — Register in manifest

**File:** `agent/modules/git_platform/manifest.py`

Add to the `tools` list:

```python
ToolDefinition(
    name="git_platform.list_workflow_runs",
    description="List GitHub Actions workflow runs for a repository. Returns run status (queued/in_progress/completed), conclusion (success/failure/cancelled), branch, and workflow name.",
    parameters=[
        _OWNER,
        _REPO,
        ToolParameter(
            name="status",
            type="string",
            description="Filter by run status.",
            enum=["queued", "in_progress", "completed", "waiting", "requested", "action_required"],
            required=False,
        ),
        ToolParameter(
            name="branch",
            type="string",
            description="Filter runs by branch name.",
            required=False,
        ),
        ToolParameter(
            name="per_page",
            type="integer",
            description="Max runs to return (default 20, max 100).",
            required=False,
        ),
    ],
    required_permission="user",
),
```

---

### Step 6 — Add to TOOL_MAP in main.py

**File:** `agent/modules/git_platform/main.py`

Add `"list_workflow_runs"` to the `TOOL_MAP` set.

---

### Step 7 — Add portal API endpoints

**File:** `agent/portal/routers/repos.py`

#### 7a. Per-repo actions endpoint

```python
@router.get("/{owner}/{repo}/actions")
async def list_workflow_runs(
    owner: str,
    repo: str,
    status: str | None = Query(None),
    branch: str | None = Query(None),
    per_page: int = Query(20, ge=1, le=100),
    provider: str = Query("github"),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List GitHub Actions workflow runs for a repository."""
    args: dict = {"owner": owner, "repo": repo, "per_page": per_page, "provider": provider}
    if status:
        args["status"] = status
    if branch:
        args["branch"] = branch
    result, err = await _safe_call(
        "git_platform", "git_platform.list_workflow_runs", args, str(user.user_id), timeout=15.0,
    )
    if err:
        return err
    return result
```

#### 7b. Cross-repo running actions endpoint (for dashboard card)

```python
@router.get("/actions/running")
async def list_running_workflow_runs(
    provider: str = Query("github"),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List in-progress and recently completed workflow runs across all repos."""
    repos_result, err = await _safe_call(
        "git_platform",
        "git_platform.list_repos",
        {"per_page": 20, "sort": "updated", "provider": provider},
        str(user.user_id),
    )
    if err:
        return err

    repos = repos_result.get("repos", [])
    if not repos:
        return {"total_count": 0, "workflow_runs": []}

    async def _fetch_runs(repo: dict) -> list[dict]:
        owner_name = repo.get("owner", "")
        repo_name = repo.get("repo", "")
        try:
            result = await call_tool(
                module="git_platform",
                tool_name="git_platform.list_workflow_runs",
                arguments={
                    "owner": owner_name,
                    "repo": repo_name,
                    "per_page": 5,
                    "provider": provider,
                },
                user_id=str(user.user_id),
                timeout=10.0,
            )
            runs = result.get("result", {}).get("workflow_runs", [])
            for run in runs:
                run["owner"] = owner_name
                run["repo"] = repo_name
            return runs
        except Exception:
            return []

    all_runs_nested = await asyncio.gather(*[_fetch_runs(r) for r in repos[:10]])
    all_runs = [run for batch in all_runs_nested for run in batch]

    # Sort: in_progress first, then by updated_at descending
    def _sort_key(r):
        status_order = {"in_progress": 0, "queued": 1, "completed": 2}
        return (status_order.get(r.get("status", ""), 3), -(0 if not r.get("updated_at") else 1))

    all_runs.sort(key=lambda r: (
        {"in_progress": 0, "queued": 1, "completed": 2}.get(r.get("status", ""), 3),
        r.get("updated_at", "") or ""
    ))
    # Reverse completed entries within each group by updated_at
    in_progress = [r for r in all_runs if r.get("status") != "completed"]
    completed = sorted(
        [r for r in all_runs if r.get("status") == "completed"],
        key=lambda r: r.get("updated_at", "") or "",
        reverse=True,
    )
    all_runs = in_progress + completed[:10]

    return {"total_count": len(all_runs), "workflow_runs": all_runs[:20]}
```

**Note:** The `/actions/running` route must be registered **before** the `/{owner}/{repo}` catch-all routes to avoid path-parameter conflicts. Since it doesn't contain `{owner}/{repo}` placeholders it will be fine at any position as long as it appears before `/{owner}/{repo}/...` routes — FastAPI resolves specific paths before parameterized ones. To be safe, place it immediately after the `/pulls/all` route.

---

### Step 8 — Add TypeScript types

**File:** `agent/portal/frontend/src/types/index.ts`

Append:

```typescript
export interface GitWorkflowRun {
  id: number;
  name: string;
  display_title: string;
  status: "queued" | "in_progress" | "completed";
  conclusion: "success" | "failure" | "cancelled" | "skipped" | "timed_out" | "neutral" | null;
  event: string;
  branch: string | null;
  sha: string;
  created_at: string;
  updated_at: string;
  url: string;
  // Cross-repo fields (added by dashboard endpoint)
  owner?: string;
  repo?: string;
}
```

---

### Step 9 — Update `useRepoDetail` hook

**File:** `agent/portal/frontend/src/hooks/useRepoDetail.ts`

- Import `GitWorkflowRun` type.
- Add `workflowRuns: GitWorkflowRun[]` to `RepoDetailData`.
- Fetch from `/api/repos/${owner}/${repo}/actions?per_page=20&provider=${provider}` in `Promise.all`, with `.catch(() => ({ total_count: 0, workflow_runs: [] }))`.
- Include `workflowRuns` in the returned state.

---

### Step 10 — Update `useDashboard` hook

**File:** `agent/portal/frontend/src/hooks/useDashboard.ts`

- Import `GitWorkflowRun`.
- Add `workflowRuns: GitWorkflowRun[]` to `DashboardData`.
- Add `fetchWorkflowRuns` function that calls `/api/repos/actions/running?provider=github`.
- Initialize state: `const [workflowRuns, setWorkflowRuns] = useState<GitWorkflowRun[]>([])`.
- Add to `fetchAll` (`Promise.allSettled` call).
- Add `workflowRuns` key to `refetchSection` map.
- Return `workflowRuns` from the hook.

**Error handling:** When GitHub isn't configured (no provider error), silently return empty array (no error shown on the card). Use `.catch()` pattern like `fetchPullRequests`.

---

### Step 11 — Add "Actions" tab to RepoDetailPage

**File:** `agent/portal/frontend/src/pages/RepoDetailPage.tsx`

#### Changes

1. **Import** new icons: `Workflow` from lucide-react (or `GitBranch` + a suitable icon — use `Play` or `Zap` since `Workflow` may not exist in the installed version; check available icons — use `ActivitySquare` or fall back to `Zap`).

2. **Extend `Tab` type:**
   ```typescript
   type Tab = "branches" | "pulls" | "issues" | "actions";
   ```

3. **Import `GitWorkflowRun`** type.

4. **Update `useRepoDetail`** destructuring to include `workflowRuns`.

5. **Add tab entry:**
   ```typescript
   { key: "actions", label: "Actions", icon: Zap, count: workflowRuns.length }
   ```

6. **Add Actions tab content** (new JSX block after `{tab === "issues" && ...}`):

```tsx
{tab === "actions" && (
  <div className="divide-y divide-light-border dark:divide-border/50">
    {workflowRuns.length === 0 ? (
      <div className="text-center py-12 text-gray-500 text-sm">
        No workflow runs found
      </div>
    ) : (
      workflowRuns.map((run) => (
        <div
          key={run.id}
          className="flex items-center justify-between px-4 py-3 hover:bg-surface-lighter/50 transition-colors"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <WorkflowStatusIcon status={run.status} conclusion={run.conclusion} />
              <span className="text-sm text-gray-200 truncate">
                {run.display_title || run.name}
              </span>
              <WorkflowStatusBadge status={run.status} conclusion={run.conclusion} />
            </div>
            <div className="flex items-center gap-2 text-xs text-gray-500 ml-6">
              <span>{run.name}</span>
              {run.branch && <span className="font-mono">{run.branch}</span>}
              <span>{run.event}</span>
              {run.updated_at && <span>{formatRelativeDate(run.updated_at)}</span>}
            </div>
          </div>
          {run.url && (
            <a
              href={run.url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 text-gray-500 hover:text-accent transition-colors shrink-0 ml-3"
              title="View on GitHub"
            >
              <ExternalLink size={14} />
            </a>
          )}
        </div>
      ))
    )}
  </div>
)}
```

7. **Add helper components** (above the main component):

```tsx
function WorkflowStatusIcon({
  status,
  conclusion,
}: {
  status: string;
  conclusion: string | null;
}) {
  if (status === "in_progress") {
    return <span className="w-3 h-3 rounded-full bg-yellow-400 animate-pulse shrink-0" />;
  }
  if (status === "queued") {
    return <span className="w-3 h-3 rounded-full bg-blue-400 shrink-0" />;
  }
  // completed
  if (conclusion === "success") return <span className="w-3 h-3 rounded-full bg-green-400 shrink-0" />;
  if (conclusion === "failure") return <span className="w-3 h-3 rounded-full bg-red-400 shrink-0" />;
  if (conclusion === "cancelled") return <span className="w-3 h-3 rounded-full bg-gray-400 shrink-0" />;
  return <span className="w-3 h-3 rounded-full bg-gray-500 shrink-0" />;
}

function WorkflowStatusBadge({
  status,
  conclusion,
}: {
  status: string;
  conclusion: string | null;
}) {
  if (status === "in_progress") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] bg-yellow-500/20 text-yellow-400">
        in progress
      </span>
    );
  }
  if (status === "queued") {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] bg-blue-500/20 text-blue-400">
        queued
      </span>
    );
  }
  const label = conclusion || "completed";
  const style =
    conclusion === "success"
      ? "bg-green-500/20 text-green-400"
      : conclusion === "failure"
      ? "bg-red-500/20 text-red-400"
      : conclusion === "cancelled"
      ? "bg-gray-500/20 text-gray-400"
      : "bg-gray-500/20 text-gray-400";
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] ${style}`}>
      {label}
    </span>
  );
}
```

---

### Step 12 — Add GitHub Actions card to Home Dashboard

**File:** `agent/portal/frontend/src/pages/HomePage.tsx`

#### Changes

1. **Import** `GitWorkflowRun` type and icon (`Zap` from lucide-react or similar).

2. **Add `GitHubActionsCard` component** (following the existing card pattern):

```tsx
const WORKFLOW_STATUS_COLORS: Record<string, string> = {
  in_progress: "bg-yellow-500/20 text-yellow-400",
  queued: "bg-blue-500/20 text-blue-400",
  success: "bg-green-500/20 text-green-400",
  failure: "bg-red-500/20 text-red-400",
  cancelled: "bg-gray-500/20 text-gray-400",
  skipped: "bg-gray-600/20 text-gray-500",
  timed_out: "bg-orange-500/20 text-orange-400",
  neutral: "bg-gray-500/20 text-gray-400",
};

function workflowDisplayStatus(run: GitWorkflowRun): string {
  if (run.status === "in_progress") return "in_progress";
  if (run.status === "queued") return "queued";
  return run.conclusion || "completed";
}

function GitHubActionsCard({
  workflowRuns,
  loading,
  error,
}: {
  workflowRuns: GitWorkflowRun[];
  loading: boolean;
  error?: string;
}) {
  const navigate = useNavigate();

  // If not configured (no GitHub token), skip rendering the card
  const isNotConfigured = error
    ? /not configured|no provider configured|no github/i.test(error)
    : false;
  if (isNotConfigured) return null;

  const stats = useMemo(() => {
    const running = workflowRuns.filter((r) => r.status === "in_progress").length;
    const queued = workflowRuns.filter((r) => r.status === "queued").length;
    const success = workflowRuns.filter((r) => r.status === "completed" && r.conclusion === "success").length;
    const failed = workflowRuns.filter((r) => r.status === "completed" && r.conclusion === "failure").length;
    return { running, queued, success, failed };
  }, [workflowRuns]);

  const recent = useMemo(() => workflowRuns.slice(0, 5), [workflowRuns]);

  return (
    <DashboardCard
      title="GitHub Actions"
      icon={Zap}
      loading={loading && workflowRuns.length === 0}
      error={isNotConfigured ? undefined : error}
      headerAction={
        <button
          onClick={() => navigate("/repos")}
          className="text-xs text-accent hover:text-accent-hover flex items-center gap-1"
          aria-label="View repositories"
        >
          View repos <ArrowRight size={12} />
        </button>
      }
    >
      <StatRow
        items={[
          { label: "Running", value: stats.running, color: "text-yellow-400" },
          { label: "Queued", value: stats.queued, color: "text-blue-400" },
          { label: "Success", value: stats.success, color: "text-green-400" },
          { label: "Failed", value: stats.failed, color: "text-red-400" },
        ]}
      />
      {recent.length === 0 ? (
        <div className="px-4 pb-4 text-sm text-gray-500 text-center">
          No recent workflow runs
        </div>
      ) : (
        <div className="divide-y divide-light-border dark:divide-border/50">
          {recent.map((run) => {
            const displayStatus = workflowDisplayStatus(run);
            return (
              <div
                key={`${run.owner}-${run.repo}-${run.id}`}
                className="flex items-center gap-3 px-4 py-3"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-800 dark:text-gray-200 truncate">
                      {run.display_title || run.name}
                    </span>
                    <Badge status={displayStatus} colorMap={WORKFLOW_STATUS_COLORS} />
                  </div>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-gray-500">
                    {run.owner && run.repo && (
                      <button
                        onClick={() => navigate(`/repos/${run.owner}/${run.repo}?provider=github`)}
                        className="hover:text-accent transition-colors"
                      >
                        {run.owner}/{run.repo}
                      </button>
                    )}
                    {run.branch && <span className="font-mono">{run.branch}</span>}
                    <span>{formatRelative(run.updated_at)}</span>
                  </div>
                </div>
                {run.url && (
                  <a
                    href={run.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-gray-500 hover:text-accent p-1 transition-colors shrink-0"
                    title="View on GitHub"
                  >
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </DashboardCard>
  );
}
```

3. **Import `Zap`** from `lucide-react` at the top of the file.

4. **Add to dashboard grid** (inside the `motion.div` grid, after the `ClaudeCodeUsageCard`):

```tsx
<motion.div variants={staggerItemVariants}>
  <GitHubActionsCard
    workflowRuns={dashboard.workflowRuns}
    loading={dashboard.loading}
    error={dashboard.errors.workflowRuns}
  />
</motion.div>
```

5. **Update `DashboardSkeleton`** count from `7` to `8` (or keep at 7 and rely on the card's own skeleton).

---

## Architecture Decisions

### Why a new portal endpoint rather than reusing `get_ci_status`?

`get_ci_status` returns the status for a **single ref** (branch/commit SHA). For the dashboard we need workflow runs across multiple repos. The new `list_workflow_runs` tool returns structured run history with direct links, status, and conclusions — more actionable than the check-runs JSON from `get_ci_status`.

### Why `list_workflow_runs` is GitHub-only

Bitbucket Pipelines uses a different API and data model. The stub returns an empty list with a note, keeping the interface consistent without breaking Bitbucket users.

### Dashboard endpoint strategy

Rather than exposing a generic endpoint per repo (which would require the frontend to orchestrate N requests), the portal backend `/api/repos/actions/running` fans out to all repos and returns a merged, sorted result. This follows the same pattern as `/api/repos/pulls/all`.

### Route ordering

The `/api/repos/actions/running` route uses a non-parameterized segment after the prefix. FastAPI resolves fixed paths before path-parameter patterns, so placing it before `/{owner}/{repo}` routes is safe — but as a best practice, register it near the other collection-level routes (`/pulls/all`).

### Error handling / graceful degradation

- If GitHub isn't configured, the dashboard card is hidden entirely (returns `null`) — same pattern as the PR card's `isNotConfigured` handling.
- Per-repo Actions tab shows "No workflow runs found" when the response is empty.
- Network/module errors are caught and show an error message inside the card.

---

## Summary of Changed/Created Files

| File | Change |
|------|--------|
| `agent/modules/git_platform/providers/base.py` | Add abstract `list_workflow_runs` |
| `agent/modules/git_platform/providers/github.py` | Implement `list_workflow_runs` |
| `agent/modules/git_platform/providers/bitbucket.py` | Add stub `list_workflow_runs` |
| `agent/modules/git_platform/tools.py` | Delegate `list_workflow_runs` to provider |
| `agent/modules/git_platform/manifest.py` | Add `git_platform.list_workflow_runs` tool definition |
| `agent/modules/git_platform/main.py` | Add `"list_workflow_runs"` to `TOOL_MAP` |
| `agent/portal/routers/repos.py` | Add `GET /api/repos/{owner}/{repo}/actions` and `GET /api/repos/actions/running` |
| `agent/portal/frontend/src/types/index.ts` | Add `GitWorkflowRun` interface |
| `agent/portal/frontend/src/hooks/useRepoDetail.ts` | Fetch and expose `workflowRuns` |
| `agent/portal/frontend/src/hooks/useDashboard.ts` | Fetch and expose `workflowRuns` |
| `agent/portal/frontend/src/pages/RepoDetailPage.tsx` | Add "Actions" tab |
| `agent/portal/frontend/src/pages/HomePage.tsx` | Add `GitHubActionsCard` component and render it |
