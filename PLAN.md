# Plan: Skills Integration in New Task Modal

## Overview

This plan covers integrating the existing `skills_modules` with the Claude Code `NewTaskModal` so users can attach skills to a task at creation time. Selected skills have their content injected into the prompt context before the task is dispatched to the `claude_code` module.

**Goal:** When creating a new Claude Code task, users can select one or more of their saved skills. The skill contents are prepended to the task prompt as context, guiding Claude Code's execution (coding style, procedures, templates, etc.).

---

## Current State Analysis

### What exists

| Concern | Status |
|---|---|
| `GET /api/skills` portal endpoint | **Exists** (`portal/routers/skills.py`) |
| `useSkills` hook | **Exists** (`portal/frontend/src/hooks/useSkills.ts`) returns `SkillSummary[]` (no `content` field) |
| `NewTaskModal.tsx` | **Exists** — has prompt, repo, branch, mode, auto-push; **no skills section** |
| `NewTaskRequest` backend model | Has `prompt`, `repo_url`, `branch`, `source_branch`, `timeout`, `mode`, `auto_push`; **no `skill_ids`** |
| `create_task` backend handler | Passes args directly to `claude_code.run_task`; **no skill injection** |
| `task_skills` DB table | Exists but is tied to `project_tasks.id` (UUID FK), **not compatible** with claude_code task IDs (short hex strings) |

### Key constraint

The `task_skills` table stores `task_id UUID FK → project_tasks.id`. Claude Code task IDs are short hex strings like `"abc123def456"` and live only in the claude_code module's JSON files — they are not project planner tasks. Therefore we **cannot reuse `task_skills`** for tracking skill associations to claude_code tasks without a schema change, which is out of scope here. Skill injection into the prompt is sufficient for the current feature.

---

## Architecture Decision: Prompt Injection

Skills are fetched server-side and prepended to the prompt in a structured Markdown block before calling `claude_code.run_task`. This approach:

- Requires **no changes** to the `claude_code` module
- Requires **no new DB tables** or migrations
- Works for all skill categories (code, procedure, template, reference, config)
- Is simple to implement and easy to audit (the enriched prompt is stored in the task's workspace)

**Injected format:**

```
## Skills Context

The following skills are included as context for this task:

---
### [Skill Name]
*Category: code | Language: python*
> [Description if present]

```python
[skill content]
```

---
### [Another Skill Name]
...

---

## Task

[original user prompt]
```

---

## Files to Modify

### Backend

1. **`agent/portal/routers/tasks.py`**
   - Add `skill_ids: list[str] | None = None` to `NewTaskRequest`
   - Add `_format_skill_block(skill: dict) -> str` helper function
   - In `create_task`: if `skill_ids` is set, fetch each skill via `call_tool(skills_modules.get_skill)`, build the skills context block, and prepend to prompt

### Frontend

2. **`agent/portal/frontend/src/components/tasks/NewTaskModal.tsx`**
   - Import `useSkills` and `SkillSummary` from `@/hooks/useSkills`
   - Import `BookOpen`, `ChevronDown`, `Check` from `lucide-react`
   - Add `selectedSkillIds: string[]` state (default `[]`)
   - Add `skillsExpanded: boolean` state and `skillSearch: string` state
   - Add `filteredSkills` memo and `toggleSkill` helper
   - Add skills selector UI section between mode toggle and auto-push toggle
   - Reset `selectedSkillIds`, `skillsExpanded`, `skillSearch` on modal open
   - Include `skill_ids` in the POST body when skills are selected

---

## Step-by-Step Implementation

### Step 1 — Backend: Add helper function

In `agent/portal/routers/tasks.py`, add this helper above the route definitions:

```python
def _format_skill_block(skill: dict) -> str:
    """Format a skill dict into a readable Markdown block for prompt injection."""
    name = skill.get("name", "Unnamed Skill")
    category = skill.get("category") or ""
    language = skill.get("language") or ""
    description = skill.get("description") or ""
    content = skill.get("content", "")

    meta_parts = []
    if category:
        meta_parts.append(f"Category: {category}")
    if language:
        meta_parts.append(f"Language: {language}")

    lines = [f"### {name}"]
    if meta_parts:
        lines.append(f"*{' | '.join(meta_parts)}*")
    if description:
        lines.append(f"> {description}")
    lines.append("")

    fence = f"```{language}" if language else "```"
    lines.append(f"{fence}\n{content}\n```")
    lines.append("")
    return "\n".join(lines)
```

### Step 2 — Backend: Extend `NewTaskRequest` and `create_task`

Update the model:

```python
class NewTaskRequest(BaseModel):
    prompt: str
    repo_url: str | None = None
    branch: str | None = None
    source_branch: str | None = None
    timeout: int | None = None
    mode: str = "execute"
    auto_push: bool = False
    skill_ids: list[str] | None = None  # NEW
```

Update `create_task` to inject skills before building `args`:

```python
@router.post("")
async def create_task(
    body: NewTaskRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Start a new Claude Code task."""
    prompt = body.prompt

    # Fetch and inject selected skills into the prompt
    if body.skill_ids:
        skill_blocks: list[str] = []
        for skill_id in body.skill_ids:
            try:
                result = await call_tool(
                    module="skills_modules",
                    tool_name="skills_modules.get_skill",
                    arguments={"skill_id": skill_id},
                    user_id=str(user.user_id),
                    timeout=10.0,
                )
                skill = result.get("result", {})
                if skill:
                    skill_blocks.append(_format_skill_block(skill))
            except Exception as e:
                logger.warning("skill_fetch_failed_for_task", skill_id=skill_id, error=str(e))

        if skill_blocks:
            header = "## Skills Context\n\nThe following skills are included as context for this task:\n\n---\n"
            skills_section = header + "\n---\n".join(skill_blocks)
            prompt = f"{skills_section}\n---\n\n## Task\n\n{body.prompt}"

    args: dict = {"prompt": prompt}
    if body.repo_url:
        args["repo_url"] = body.repo_url
    # ... rest of existing logic unchanged
```

### Step 3 — Frontend: Update `NewTaskModal.tsx`

**Add imports:**

```typescript
import { X, GitBranch, Upload, Search, Plus, Shield, BookOpen, ChevronDown, Check } from "lucide-react";
import { useSkills } from "@/hooks/useSkills";
```

**Add state (alongside existing state declarations):**

```typescript
const [selectedSkillIds, setSelectedSkillIds] = useState<string[]>([]);
const [skillsExpanded, setSkillsExpanded] = useState(false);
const [skillSearch, setSkillSearch] = useState("");
```

**Add hook (alongside existing hooks):**

```typescript
const { skills, loading: skillsLoading } = useSkills();
```

**Add filtered skills memo (alongside existing useMemo declarations):**

```typescript
const filteredSkills = useMemo(() => {
  if (!skillSearch.trim()) return skills;
  const q = skillSearch.toLowerCase();
  return skills.filter(
    (s) =>
      s.name.toLowerCase().includes(q) ||
      (s.description || "").toLowerCase().includes(q) ||
      (s.category || "").toLowerCase().includes(q)
  );
}, [skills, skillSearch]);
```

**Add toggle helper (before `handleSubmit`):**

```typescript
const toggleSkill = (skillId: string) => {
  setSelectedSkillIds((prev) =>
    prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId]
  );
};
```

**Reset on open** — inside the existing `useEffect` for `open`, add:

```typescript
setSelectedSkillIds([]);
setSkillsExpanded(false);
setSkillSearch("");
```

**Submit body** — inside `handleSubmit`, after `if (autoPush)`:

```typescript
if (selectedSkillIds.length > 0) {
  (body as Record<string, unknown>).skill_ids = selectedSkillIds;
}
```

**Skills UI section** — insert between the mode toggle block and the auto-push block:

```tsx
{/* Skills selector */}
<div>
  <button
    type="button"
    onClick={() => setSkillsExpanded(!skillsExpanded)}
    className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 transition-colors"
  >
    <BookOpen size={14} />
    <span>Include Skills</span>
    {selectedSkillIds.length > 0 && (
      <span className="px-1.5 py-0.5 rounded-full bg-accent/20 text-accent text-xs font-medium">
        {selectedSkillIds.length}
      </span>
    )}
    <ChevronDown
      size={14}
      className={`ml-auto transition-transform ${skillsExpanded ? "rotate-180" : ""}`}
    />
  </button>

  {skillsExpanded && (
    <div className="mt-2 space-y-2">
      <div className="relative">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
        <input
          value={skillSearch}
          onChange={(e) => setSkillSearch(e.target.value)}
          placeholder="Search skills..."
          className="w-full pl-9 pr-3 py-2 rounded-lg bg-white dark:bg-surface border border-light-border dark:border-border text-gray-900 dark:text-white text-sm placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:border-accent"
        />
      </div>

      <div className="max-h-48 overflow-y-auto border border-light-border dark:border-border rounded-lg divide-y divide-light-border dark:divide-border bg-white dark:bg-surface">
        {skillsLoading ? (
          <div className="px-3 py-4 text-sm text-center text-gray-500">Loading skills...</div>
        ) : filteredSkills.length === 0 ? (
          <div className="px-3 py-4 text-sm text-center text-gray-500">
            {skills.length === 0 ? "No skills saved yet." : "No matching skills."}
          </div>
        ) : (
          filteredSkills.map((skill) => {
            const selected = selectedSkillIds.includes(skill.skill_id);
            return (
              <button
                key={skill.skill_id}
                type="button"
                onClick={() => toggleSkill(skill.skill_id)}
                className={`w-full text-left px-3 py-2.5 transition-colors ${
                  selected
                    ? "bg-accent/10"
                    : "hover:bg-gray-100 dark:hover:bg-surface-lighter"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {skill.name}
                  </span>
                  <div className="flex items-center gap-2 shrink-0">
                    {skill.category && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-surface-lighter text-gray-500 dark:text-gray-400">
                        {skill.category}
                      </span>
                    )}
                    {selected && <Check size={14} className="text-accent" />}
                  </div>
                </div>
                {skill.description && (
                  <p className="text-xs text-gray-500 mt-0.5 truncate">{skill.description}</p>
                )}
              </button>
            );
          })
        )}
      </div>
    </div>
  )}
</div>
```

---

## Edge Cases & Considerations

| Scenario | Handling |
|---|---|
| No skills saved | Skills section shows "No skills saved yet." — still renders, not intrusive |
| Skill fetch fails at task creation | `logger.warning` logged, skill silently skipped; task proceeds without it |
| Template skill selected | Raw content included (with `{{variable}}` placeholders visible); future work could add a variable substitution step |
| Large skill content | Full content injected; very large skills increase token usage — user's responsibility to manage |
| Empty `skill_ids` list | Backend skips injection entirely (treated same as `None`) |
| Skill doesn't belong to user | `get_skill` in skills_modules returns error; caught, logged, skipped |
| Skills section collapsed by default | Keeps modal clean; badge on the trigger shows count of selected skills |

---

## What Is NOT In Scope

- **New DB table for claude_task_skills tracking** — deferred; would require an Alembic migration and new endpoints. The `task_skills` table is tied to project_planner task UUIDs and is incompatible with claude_code task IDs.
- **Template variable substitution UI** — template skills are injected with raw content; Jinja2 variable prompting in the modal is future work.
- **Skill content preview on hover** — `useSkills` returns `SkillSummary` (no `content`); per-skill content fetching would need additional API calls.
- **Auto-suggesting skills by repo/language** — future enhancement.
- **Changes to `claude_code` module** — not needed; injection happens at the portal router layer.

---

## Summary of Changes

| File | Change type | Description |
|---|---|---|
| `agent/portal/routers/tasks.py` | Modify | Add `skill_ids` to `NewTaskRequest`; add `_format_skill_block()` helper; update `create_task` to fetch skills and inject into prompt |
| `agent/portal/frontend/src/components/tasks/NewTaskModal.tsx` | Modify | Add `useSkills` import, skill-related state, `filteredSkills` memo, `toggleSkill` helper, skills selector UI, reset on open, `skill_ids` in submit body |

No new files, no new DB migrations, no changes to `claude_code` or `skills_modules` modules.
