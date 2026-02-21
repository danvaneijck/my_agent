# Plan: Render Todo List in TaskLogViewer the Same as Claude Code VS Code Extension

## Overview

The goal is to render the `TodoWrite` tool's todo list in `TaskOutputViewer.tsx` (the "output" tab of the task detail page) in the same visual style that the Claude Code VS Code extension uses — i.e., a structured, live-updating checklist showing each todo item's status (pending / in_progress / completed) and priority.

**Key insight:** The user asks about `TaskLogViewer.tsx`, but the correct component to enhance is `TaskOutputViewer.tsx`. `TaskLogViewer.tsx` is the raw log tab — it displays plain text lines without any structured rendering. `TaskOutputViewer.tsx` is the "output" tab that already parses and renders structured stream events (assistant messages, tool calls, results). Todo list rendering belongs there, because it parses the JSON event stream where `TodoWrite` appears.

---

## Background Research

### Claude Code JSON Stream Format

When Claude Code runs with `--output-format stream-json`, it emits newline-delimited JSON (JSONL). Each line is a timestamped log entry with format:

```
[HH:MM:SS] [stdout] <JSON>
```

The `TaskOutputViewer` already parses this with:

```typescript
const LOG_LINE_RE = /^\[(\d{2}:\d{2}:\d{2})\]\s+\[stdout\]\s+(.+)$/;
```

### How TodoWrite Appears in the Stream

When Claude uses the `TodoWrite` tool, the stream contains two events:

**1. An `assistant` event with a `tool_use` block:**

```json
{
  "type": "assistant",
  "message": {
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_01abc...",
        "name": "TodoWrite",
        "input": {
          "todos": [
            { "id": "1", "content": "Research codebase", "status": "completed", "priority": "high" },
            { "id": "2", "content": "Write implementation", "status": "in_progress", "priority": "high" },
            { "id": "3", "content": "Run tests", "status": "pending", "priority": "medium" }
          ]
        }
      }
    ]
  }
}
```

**2. A `user` event with the `tool_result`:**

```json
{
  "type": "user",
  "message": {
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toulu_01abc...",
        "content": "Todos have been modified successfully...",
        "is_error": false
      }
    ]
  }
}
```

### How the VS Code Extension Renders Todos

The VS Code extension displays `TodoWrite` calls as a special compact panel (not a generic tool call block). It shows:

- A checklist icon or task icon header
- Each todo item on its own row with:
  - A status indicator icon:
    - `completed` → filled checkmark (green)
    - `in_progress` → spinner or half-filled circle (yellow/blue)
    - `pending` → empty circle (gray)
  - The todo content text
  - Priority badge (high / medium / low) — though the interactive UI omits priority display
- Items are grouped/ordered (completed items typically shown below active ones, or in order)
- The panel updates in-place each time `TodoWrite` is called (showing the latest state)

### Current State of the Codebase

- `TaskOutputViewer.tsx` already handles `assistant` events with `tool_use` blocks (via `AssistantCard`)
- Currently, `TodoWrite` tool calls render as **generic tool call blocks** — showing the tool name, a collapsible "Input" with the raw JSON todos array, and a collapsible "Output"
- There is no special `TodoWrite` rendering — no `TodoCard` component, no dedicated todo list display
- The `toolSummary()` function in `TaskOutputViewer.tsx` has no case for `TodoWrite`
- No `TodoItem` or todo-related TypeScript types exist in `src/types/index.ts`

---

## Files to Modify

### Primary File
- `agent/portal/frontend/src/components/tasks/TaskOutputViewer.tsx`
  - Add `TodoCard` component (renders the full todo list beautifully)
  - Add a `TodoWrite` case to `toolSummary()`
  - Add `TodoWrite` special rendering inside `AssistantCard` (instead of the generic tool block)

### Secondary File
- `agent/portal/frontend/src/types/index.ts`
  - Add `TodoItem` and `TodoStatus` TypeScript interfaces

### No Backend Changes Required
The todo data is already present in the log stream — `TodoWrite` is a tool call like any other and already flows through the existing log pipeline. No changes are needed to the backend, API, WebSocket, or log streaming code.

---

## Implementation Plan

### Step 1: Add TypeScript Types

In `agent/portal/frontend/src/types/index.ts`, add:

```typescript
export type TodoStatus = "pending" | "in_progress" | "completed";
export type TodoPriority = "high" | "medium" | "low";

export interface TodoItem {
  id: string;
  content: string;
  status: TodoStatus;
  priority?: TodoPriority;
}
```

### Step 2: Add `TodoCard` Component in `TaskOutputViewer.tsx`

Create a new `TodoCard` component that takes the `TodoWrite` tool's input and renders a VS Code-style todo list. Insert it before the existing `AssistantCard` component.

**Visual design (matching VS Code extension style):**

```
┌─────────────────────────────────────────┐
│ ☑  Todo List  (3 items)                 │
│                                         │
│  ✓  Research codebase           [high]  │
│  ◉  Write implementation        [high]  │
│  ○  Run tests                  [med]    │
└─────────────────────────────────────────┘
```

**Implementation details:**
- Header row: `ListTodo` icon (from lucide-react) + "Todo List" label + item count badge
- One row per todo item:
  - Status icon:
    - `completed` → `CheckCircle2` icon, green (`text-green-400`)
    - `in_progress` → `Circle` icon with half-fill or `Loader2` spinner, yellow (`text-yellow-400`)
    - `pending` → `Circle` icon, gray (`text-gray-400`)
  - Content text:
    - `completed` → strikethrough + muted color (`line-through text-gray-400 dark:text-gray-600`)
    - `in_progress` → normal weight, accent color or white
    - `pending` → normal weight, normal color
  - Priority badge (small pill on right): only if priority is present
    - `high` → red/orange pill
    - `medium` → yellow pill
    - `low` → gray pill
- Container: rounded border with subtle background, similar to tool cards
- Border/bg color reflects overall state (any in_progress → yellow tint, all completed → green tint, mixed → neutral)
- Compact, no collapsible wrappers — always fully visible (unlike tool input/output blocks)

**Example JSX structure:**

```tsx
function TodoCard({ todos }: { todos: TodoItem[] }) {
  const completedCount = todos.filter(t => t.status === "completed").length;
  const hasInProgress = todos.some(t => t.status === "in_progress");

  let borderClass = "border-light-border dark:border-border";
  let bgClass = "bg-gray-50 dark:bg-surface/50";

  if (hasInProgress) {
    borderClass = "border-yellow-500/30";
    bgClass = "bg-yellow-500/5";
  } else if (completedCount === todos.length && todos.length > 0) {
    borderClass = "border-green-500/30";
    bgClass = "bg-green-500/5";
  }

  return (
    <div className={`border rounded-lg p-3 ${borderClass} ${bgClass}`}>
      <div className="flex items-center gap-2 mb-2">
        <ListTodo size={13} className="text-gray-400" />
        <span className="text-xs font-medium text-gray-500">Todo List</span>
        <span className="text-xs text-gray-400">
          {completedCount}/{todos.length}
        </span>
      </div>
      <div className="space-y-1">
        {todos.map((todo) => (
          <TodoRow key={todo.id} todo={todo} />
        ))}
      </div>
    </div>
  );
}

function TodoRow({ todo }: { todo: TodoItem }) {
  const isCompleted = todo.status === "completed";
  const isInProgress = todo.status === "in_progress";

  return (
    <div className="flex items-center gap-2 text-sm">
      {/* Status icon */}
      {isCompleted ? (
        <CheckCircle2 size={13} className="text-green-400 shrink-0" />
      ) : isInProgress ? (
        <Loader2 size={13} className="text-yellow-400 animate-spin shrink-0" />
      ) : (
        <Circle size={13} className="text-gray-400 shrink-0" />
      )}

      {/* Content */}
      <span className={`flex-1 text-xs ${
        isCompleted
          ? "line-through text-gray-400 dark:text-gray-600"
          : isInProgress
          ? "text-gray-800 dark:text-gray-200"
          : "text-gray-600 dark:text-gray-400"
      }`}>
        {todo.content}
      </span>

      {/* Priority badge */}
      {todo.priority && (
        <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
          todo.priority === "high"
            ? "bg-red-500/20 text-red-400"
            : todo.priority === "medium"
            ? "bg-yellow-500/20 text-yellow-500"
            : "bg-gray-500/20 text-gray-500"
        }`}>
          {todo.priority}
        </span>
      )}
    </div>
  );
}
```

### Step 3: Update `toolSummary()` for TodoWrite

In the existing `toolSummary()` function, add:

```typescript
case "TodoWrite": {
  const todos = input.todos as Array<{ status: string }> | undefined;
  if (!todos) return "";
  const done = todos.filter(t => t.status === "completed").length;
  return `${done}/${todos.length} completed`;
}
```

### Step 4: Update `AssistantCard` to Use `TodoCard` for TodoWrite

In the `AssistantCard` component, inside the `block.type === "tool_use"` branch, add a special case **before** the generic tool card rendering:

```typescript
if (block.type === "tool_use") {
  const toolName = block.name as string;

  // Special rendering for TodoWrite
  if (toolName === "TodoWrite") {
    const todos = (block.input as { todos?: TodoItem[] }).todos ?? [];
    return (
      <div key={i} className="flex gap-2 py-1">
        <div className="mt-0.5 w-[14px] shrink-0" /> {/* spacer matching Bot icon width */}
        <div className="flex-1">
          <TodoCard todos={todos} />
        </div>
      </div>
    );
  }

  // ... existing generic tool_use rendering continues below ...
}
```

This means `TodoWrite` will render as a clean todo checklist instead of the generic "Input/Output" collapsible block.

### Step 5: Add Required Lucide Icons

Ensure the following icons are imported at the top of `TaskOutputViewer.tsx`:
- `Circle` (for pending status) — new import needed
- `ListTodo` (for the TodoCard header) — new import needed
- `CheckCircle2` and `Loader2` are already imported

### Step 6: Handle Live Updates (Latest State Wins)

Since `TodoWrite` can be called multiple times during a task (each call replaces the previous todo list), the stream will contain multiple `TodoWrite` tool_use blocks. Each one should render independently, showing the snapshot of todos at that point in time. This is the same behavior as the VS Code extension — each `TodoWrite` call renders its own card in sequence, so the user can see how the list evolved.

No additional state management is needed; the existing event-driven rendering already handles this correctly.

---

## Detailed Step-by-Step Implementation Order

1. **Add types** to `src/types/index.ts`:
   - `TodoStatus` type union
   - `TodoPriority` type union
   - `TodoItem` interface

2. **Add `TodoRow` component** to `TaskOutputViewer.tsx`:
   - Renders a single todo item with status icon, content, and priority badge

3. **Add `TodoCard` component** to `TaskOutputViewer.tsx`:
   - Header with count
   - List of `TodoRow`s
   - Dynamic border/bg based on overall progress

4. **Update `toolSummary()`** in `TaskOutputViewer.tsx`:
   - Add `TodoWrite` case returning completed/total count

5. **Update `AssistantCard`** in `TaskOutputViewer.tsx`:
   - Before generic tool_use rendering, check if `block.name === "TodoWrite"`
   - If yes, render `TodoCard` instead of generic tool block

6. **Update imports** at top of `TaskOutputViewer.tsx`:
   - Add `Circle` and `ListTodo` from `lucide-react`
   - Add `TodoItem` import from `@/types`

---

## What Does NOT Need to Change

- **`TaskLogViewer.tsx`**: The raw logs tab shows plain text — this is intentional. Todo events will appear there as raw JSON lines, which is fine for the logs tab. The user's question is best answered by improving the "output" tab (`TaskOutputViewer`), not the raw log tab.
- **Backend / API**: No changes needed. TodoWrite data is already captured in the log stream.
- **WebSocket / streaming**: No changes needed.
- **Log format / parsing regex**: No changes needed.
- **`toolResults` map logic**: No changes needed — `TodoWrite` results are already tracked as generic tool results; we just suppress showing the output block since the input (the todos list) is what matters visually.

---

## Expected Result

After this implementation:

1. When viewing a task that used `TodoWrite`, the **Output tab** will show a structured, VS Code-style todo checklist for each `TodoWrite` call instead of a raw JSON tool block.
2. The checklist shows each todo item with:
   - An appropriate status icon (spinner for in_progress, checkmark for completed, circle for pending)
   - Strikethrough styling for completed items
   - A priority badge (high/medium/low) if priorities are set
3. The checklist header shows completed/total count (e.g., "2/4")
4. The border color reflects overall progress (yellow when in-progress, green when all done)
5. Multiple `TodoWrite` calls in the same task each render their own snapshot card, showing list evolution
6. The **Logs tab** (`TaskLogViewer.tsx`) is unchanged — it still shows raw lines

---

## No-Go / Out of Scope

- Adding a persistent sidebar or floating overlay that tracks the *current* todo state across multiple `TodoWrite` calls in real-time (this would be a separate, more complex feature)
- Modifying the raw logs tab (`TaskLogViewer.tsx`) — it's intended to be raw
- Any backend changes
- Rendering todos in the task list page or task card summaries

---

## Dependency Check

All required packages are already installed:
- `lucide-react` ✓ (already used, just needs `Circle` and `ListTodo` added to imports)
- `react-markdown` ✓ (already used)
- No new npm packages required

The implementation is purely frontend TypeScript/React and touches only two files.
