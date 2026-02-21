# Implementation Plan: Plan Review "View Full Plan" Button & PR Prompt Fix

## Overview

Two related improvements to the auto-push / plan-review workflow:

1. **"View Full Plan" button** — When a plan task reaches `awaiting_input`, the `PlanReviewPanel` shows a truncated preview. We add a button that switches to the "files" tab and auto-selects + renders `PLAN.md` as formatted markdown.
2. **PR prompt fix** — Update the task prompt (in `tools.py`) so the agent knows to exclude `PLAN.md` when creating pull requests.

---

## Files to Modify

| File | Purpose |
|------|---------|
| `agent/portal/frontend/src/components/tasks/PlanReviewPanel.tsx` | Add "View Full Plan" button with `onViewPlan` callback prop |
| `agent/portal/frontend/src/components/tasks/WorkspaceBrowser.tsx` | Add `initialFilePath` prop for auto-selection; add markdown rendering for `.md` files |
| `agent/portal/frontend/src/pages/TaskDetailPage.tsx` | Wire `onViewPlan` callback; pass `initialFilePath` and a `selectedFilePath` setter to `WorkspaceBrowser` |
| `agent/modules/claude_code/tools.py` | Extend the auto-push Git workflow prompt to instruct the agent to exclude `PLAN.md` from PRs |

---

## Step-by-Step Implementation

### Step 1 — `WorkspaceBrowser.tsx`: Add `initialFilePath` prop and markdown rendering

**Location**: `agent/portal/frontend/src/components/tasks/WorkspaceBrowser.tsx`

#### 1a. Extend the props interface

```tsx
interface WorkspaceBrowserProps {
  taskId: string;
  initialFilePath?: string;      // NEW — path relative to workspace root (e.g. "PLAN.md")
}
```

#### 1b. Auto-select file on mount / prop change

Add a `useEffect` that fires once the root-level `entries` have loaded and `initialFilePath` is set. Because `PLAN.md` lives at the workspace root (`currentPath === ""`), the logic is straightforward:

```tsx
useEffect(() => {
  if (!initialFilePath || loading || entries.length === 0 || currentPath !== "" || selectedFile) return;
  const targetName = initialFilePath.split("/").pop() ?? initialFilePath;
  const entry = entries.find((e) => e.name === targetName && e.type === "file");
  if (entry) handleEntryClick(entry);
}, [initialFilePath, loading, entries]);
```

Guard conditions:
- Skip if no `initialFilePath` specified
- Skip while still loading the directory listing
- Skip if not at the root (we only support root-level pre-selection for now; PLAN.md is always at root)
- Skip if a file is already selected (avoid re-fetching on unrelated renders)

#### 1c. Markdown rendering for `.md` files

`ReactMarkdown`, `remark-gfm`, and `rehype-highlight` are already installed (used by `PlanReviewPanel`). Add an import and a small rendering branch inside the content viewer:

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";

// Inside the content viewer, replace the single <pre> with:
const isMarkdown = /\.(md|markdown)$/i.test(selectedFile.path ?? "");

{isMarkdown ? (
  <div className="flex-1 p-4 overflow-auto prose dark:prose-invert prose-sm max-w-none">
    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
      {selectedFile.content ?? ""}
    </ReactMarkdown>
  </div>
) : (
  <pre className="flex-1 p-4 text-sm text-gray-700 dark:text-gray-300 whitespace-pre overflow-auto font-mono leading-relaxed">
    {selectedFile.content}
  </pre>
)}
```

This change benefits all `.md` files in the workspace browser, not just `PLAN.md`.

---

### Step 2 — `PlanReviewPanel.tsx`: Add "View Full Plan" button

**Location**: `agent/portal/frontend/src/components/tasks/PlanReviewPanel.tsx`

#### 2a. Add `onViewPlan` to the props interface

```tsx
interface PlanReviewPanelProps {
  task: Task;
  onContinued: (newTaskId: string) => void;
  onViewPlan?: () => void;   // NEW — called when user wants to view full PLAN.md
}
```

#### 2b. Add button to the action row

Import `FileText` from `lucide-react`. Place the button alongside the existing "Approve & Implement" and "Give Feedback" buttons:

```tsx
{onViewPlan && (
  <button
    onClick={onViewPlan}
    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600/20 text-blue-400 text-sm hover:bg-blue-600/30 transition-colors"
  >
    <FileText size={16} />
    View Full Plan
  </button>
)}
```

The button only renders when `onViewPlan` is provided, keeping the component backward-compatible.

---

### Step 3 — `TaskDetailPage.tsx`: Wire everything together

**Location**: `agent/portal/frontend/src/pages/TaskDetailPage.tsx`

#### 3a. Add `initialFilePath` state

```tsx
const [initialFilePath, setInitialFilePath] = useState<string | undefined>();
```

#### 3b. Pass `onViewPlan` to `PlanReviewPanel`

```tsx
<PlanReviewPanel
  task={task}
  onContinued={(newId) => navigate(`/tasks/${newId}`)}
  onViewPlan={() => {
    setInitialFilePath("PLAN.md");
    setViewMode("files");
  }}
/>
```

Clicking "View Full Plan":
1. Sets `initialFilePath` to `"PLAN.md"`
2. Switches `viewMode` to `"files"`, which mounts `WorkspaceBrowser`

#### 3c. Pass `initialFilePath` to `WorkspaceBrowser`

```tsx
{viewMode === "files" && (
  <WorkspaceBrowser taskId={task.id} initialFilePath={initialFilePath} />
)}
```

**Reset consideration**: `initialFilePath` is intentionally not reset after the file is selected. If the user navigates to a different file in the browser and then clicks "View Full Plan" again, the `useEffect` guard (`selectedFile` check is removed here; instead rely on the tab switch causing a fresh mount) will re-select PLAN.md. Because switching away from "files" tab unmounts `WorkspaceBrowser`, the next mount will always start fresh and the `initialFilePath` effect will fire correctly.

---

### Step 4 — `tools.py`: Extend the PR exclusion instruction

**Location**: `agent/modules/claude_code/tools.py`, lines ~1483–1489

The current auto-push prompt block:

```python
if task.auto_push and task.repo_url:
    prompt_for_cli += (
        "\n\nIMPORTANT — Git workflow:"
        "\n- Commit your changes with descriptive commit messages as you work."
        "\n- When you are done, push your branch: git push -u origin HEAD"
        "\n- Do NOT leave uncommitted changes."
    )
```

Add one additional bullet:

```python
if task.auto_push and task.repo_url:
    prompt_for_cli += (
        "\n\nIMPORTANT — Git workflow:"
        "\n- Commit your changes with descriptive commit messages as you work."
        "\n- When you are done, push your branch: git push -u origin HEAD"
        "\n- Do NOT leave uncommitted changes."
        "\n- When creating a pull request, do NOT include PLAN.md in the PR diff."
        " PLAN.md is a planning artifact only. Before opening the PR, remove it"
        " from the branch with:"
        " `git rm --cached PLAN.md && git commit -m 'chore: remove planning artifact'`"
        " (skip this if PLAN.md was never committed on this branch)."
    )
```

This is appended to every auto-push task prompt (both plan mode and execute mode use the same prompt augmentation path), so the agent will always be aware of this rule when it has push access.

---

## Data Flow Summary

```
TaskDetailPage
  │
  ├─ state: viewMode ("output" | "logs" | "files")
  ├─ state: initialFilePath (string | undefined)
  │
  ├─ PlanReviewPanel
  │     onViewPlan={() => {
  │       setInitialFilePath("PLAN.md")
  │       setViewMode("files")        ← switches tab
  │     }}
  │     [renders "View Full Plan" button]
  │
  └─ WorkspaceBrowser (only mounted when viewMode === "files")
        initialFilePath="PLAN.md"
        │
        useEffect fires after entries load
        → fetches /api/tasks/{id}/workspace/file?path=PLAN.md
        → setSelectedFile(...)
        → renders ReactMarkdown (because path ends in .md)
```

---

## Dependency Check

- `react-markdown`, `remark-gfm`, `rehype-highlight` — already installed; already imported in `PlanReviewPanel.tsx`. No new packages required.
- `FileText` from `lucide-react` — already available (lucide-react is in the project).
- No backend API changes needed — the workspace file endpoint already serves any file at any path.
- No new database migrations, no Docker changes, no shared-package changes.

---

## Out of Scope

- Supporting `initialFilePath` for subdirectories (PLAN.md is always at the repo root).
- A "raw/rendered" toggle for markdown files in the workspace browser (can be added later).
- Modifying how PLAN.md is committed during plan mode — the file stays committed on the plan branch; the PR instruction handles exclusion at PR-creation time.
