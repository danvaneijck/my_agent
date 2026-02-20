# Plan: Show Tool Use Output in TaskOutputViewer

## Problem Statement

In the **Output tab** of the task detail page (`TaskOutputViewer`), Claude's tool use calls are shown with their inputs (e.g., which file was read, what command was run), but the **output/result** of each tool call is not reliably displayed.

The component already has infrastructure to display tool results, but it is not working reliably because:

1. The Claude Code CLI (running with `--output-format stream-json --verbose`) emits `tool_result` JSON events whose exact field structure has not been verified against what the UI parser expects.
2. The `toolResults` map in the component falls back to positional matching when `tool_use_id` is absent — which is fragile and can silently produce wrong associations.
3. When tool results are large, they are collapsed or truncated in ways that make them easy to miss.

---

## Architecture Context

### How logs are produced

The `_execute_task` method in `agent/modules/claude_code/tools.py` runs a Docker container with the Claude Code CLI using:

```bash
CLAUDE_ARGS="--output-format stream-json --verbose --dangerously-skip-permissions"
```

Each stdout/stderr line is written to the task's log file as:

```
[HH:MM:SS] [stdout] <raw JSON line>
[HH:MM:SS] [stderr] <raw text or JSON line>
```

### How the UI parses logs

`TaskOutputViewer` uses a regex (`LOG_LINE_RE`) to extract the JSON payloads from `[stdout]` lines. It then dispatches them by `type`:

- `system` → session start card
- `assistant` → text/tool-use blocks rendered as cards
- `tool_result` → looked up by `tool_use_id` and attached to the corresponding `tool_use` block in the prior `assistant` event
- `result` → final completion card

### Current tool result matching logic (`toolResults` memo)

```typescript
} else if (event.type === "tool_result") {
  const toolUseId = event.data.tool_use_id as string;
  if (toolUseId) {
    map.set(toolUseId, event);           // preferred: match by ID
  } else if (pendingIds.length > 0) {
    map.set(pendingIds.shift()!, event); // fallback: positional match
  }
}
```

The comment reads "Explicit tool_result events (if the CLI emits them)" — indicating uncertainty about whether the CLI actually includes this event type and in which format.

### What the CLI actually emits

When using `--output-format stream-json`, Claude Code CLI emits a `tool_result` event with this structure:

```json
{
  "type": "tool_result",
  "tool_use_id": "toolu_01AbC...",
  "content": [
    { "type": "text", "text": "file content or command output here" }
  ]
}
```

The `content` field is an **array** of content blocks (matching the Anthropic messages API format), not a plain string. The `formatToolResult` function already handles arrays, but it may fail to extract text if the array items use `"type": "text"` blocks rather than plain strings.

---

## Root Cause Analysis

### Issue 1: `tool_result` content block text extraction may fail

`formatToolResult` extracts content like this:

```typescript
content = (content as Record<string, unknown>[])
  .map((c) =>
    typeof c === "string"
      ? c
      : (c.text as string) ||
        (c.content as string) ||
        JSON.stringify(c),
  )
  .join("\n");
```

This should work for `{ "type": "text", "text": "..." }` blocks. However, if the CLI wraps tool output differently (e.g., with `is_error: true` at the top level alongside `content`), the error state may not be rendered distinctly.

### Issue 2: `tool_use_id` field presence

If the CLI does not include `tool_use_id` in the `tool_result` event (or uses a different field name), the positional fallback is used. Positional matching fails when:
- Multiple tool calls appear in a single `assistant` turn (Claude can batch tool calls)
- The tool results arrive in a different order than the tool calls

### Issue 3: `_inferred` results show as "completed" but with no content

When no real `tool_result` is found for a tool call, `flushPending` inserts a synthetic result with `content: ""`. This causes the UI to show a green checkmark (result found) but display nothing in the output collapsible — confusing because it looks like success with empty output.

### Issue 4: No debugging visibility

There is no way for a user to tell whether the tool output is missing because:
- The tool genuinely produced no output
- The result was not matched
- The result was inferred/synthetic

---

## Files to Modify

| File | Change |
|------|--------|
| `agent/portal/frontend/src/components/tasks/TaskOutputViewer.tsx` | Fix `formatToolResult`, improve `toolResults` matching, add clear "no output" indication, improve error state rendering, show tool result `is_error` distinctly |

No backend changes are required — the log file already contains the full `tool_result` JSON events with `tool_use_id`. This is a pure frontend parsing/display fix.

---

## Implementation Plan

### Step 1: Verify the actual CLI output format

Before coding, confirm the exact shape of `tool_result` events emitted by the CLI. The log file for any completed task contains lines like:

```
[14:23:01] [stdout] {"type":"tool_result","tool_use_id":"toolu_01AbC...","content":[{"type":"text","text":"..."}]}
```

Check a real log file (`/tmp/claude_tasks/<id>/task_<id>.log`) to confirm field names. **No code changes needed in this step.**

### Step 2: Fix `formatToolResult` to handle all content shapes

Update `formatToolResult` to robustly handle:

1. Plain string content (already works)
2. Array of `{ type: "text", text: "..." }` blocks (primary case from CLI)
3. Array of `{ type: "tool_result", content: [...] }` nested blocks (subagent case)
4. Array of plain strings (already works)
5. Raw objects (fall back to JSON.stringify)

Additionally, return both the extracted text AND the `is_error` boolean so the display card can use red styling for error results.

```typescript
// New signature
function parseToolResult(resultEvent: StreamEvent): { content: string; isError: boolean } {
  const isError = resultEvent.data.is_error === true;
  let content = resultEvent.data.content;

  if (Array.isArray(content)) {
    content = (content as Record<string, unknown>[])
      .map((c) => {
        if (typeof c === "string") return c;
        if (c.type === "text" && c.text) return c.text as string;
        if (c.type === "tool_result") {
          // nested content blocks (subagent tool use)
          const inner = Array.isArray(c.content)
            ? (c.content as Record<string, unknown>[]).map(i => (i.text as string) || JSON.stringify(i)).join("\n")
            : String(c.content ?? "");
          return inner;
        }
        return JSON.stringify(c);
      })
      .join("\n");
  }

  if (typeof content !== "string") {
    content = JSON.stringify(content, null, 2);
  }

  return { content: content as string, isError };
}
```

### Step 3: Improve `toolResults` matching in the memo

The current fallback (positional) is error-prone. Improve the matching:

1. **Primary**: match by `tool_use_id` (keep as-is)
2. **Fallback**: positional — keep as-is but only use it if exactly one tool was pending (to avoid wrong associations for batched calls)
3. **Sentinel**: distinguish between "inferred complete" (synthetic) and "real result with empty content" by using `null` vs `""` as the content value

```typescript
} else if (pendingIds.length === 1) {
  // Only use positional fallback when there is exactly one pending tool
  // (batched tool calls can't be matched positionally)
  map.set(pendingIds.shift()!, event);
} else if (pendingIds.length > 1) {
  // Cannot determine which pending tool this result belongs to — skip
  // so the UI shows "running" state rather than wrong association
}
```

### Step 4: Update `AssistantCard` to use the new `parseToolResult`

Replace the existing result rendering in `AssistantCard`:

**Current:**
```typescript
const resultContent = resultEvent
  ? formatToolResult(resultEvent)
  : undefined;
```

**New:**
```typescript
const parsed = resultEvent && !resultEvent.data._inferred
  ? parseToolResult(resultEvent)
  : null;
const resultContent = parsed?.content;
const resultIsError = parsed?.isError ?? false;
```

Then update the status icon logic to use `resultIsError` for error styling even when a result was found:

```typescript
let borderClass = "border-light-border dark:border-border";
let bgClass = "bg-gray-50 dark:bg-surface/50";
let iconColor = "text-blue-400";

if (isRunning) {
  borderClass = "border-yellow-500/40";
  bgClass = "bg-yellow-500/5";
  iconColor = "text-yellow-400";
} else if (isError || resultIsError) {   // <-- also check resultIsError
  borderClass = "border-red-500/40";
  bgClass = "bg-red-500/5";
  iconColor = "text-red-400";
} else if (hasResult) {
  borderClass = "border-green-500/40";
  bgClass = "bg-green-500/5";
  iconColor = "text-green-400";
}
```

And update the output collapsible to show "Error output" vs "Output" label:

```typescript
{resultContent && (
  <Collapsible
    label={`${resultIsError ? "Error output" : "Output"} (${resultLines.length} lines)`}
    defaultOpen={!isLongResult || resultIsError}  // auto-open errors
  >
    <pre className={`text-xs ... ${resultIsError ? "text-red-400" : "text-gray-600 dark:text-gray-400"}`}>
      {display}
    </pre>
  </Collapsible>
)}
```

### Step 5: Handle empty and inferred results distinctly

When `resultEvent.data._inferred === true`, the tool was "flushed" with synthetic empty content. In this case, show a subtle "no output captured" note rather than silently showing nothing:

```typescript
{!resultContent && hasResult && !resultEvent?.data._inferred && (
  <p className="text-xs text-gray-400 italic pl-1">no output</p>
)}
{!resultContent && hasResult && resultEvent?.data._inferred && (
  <p className="text-xs text-gray-400 italic pl-1">output not captured</p>
)}
```

### Step 6: Add `tool_use_id` to the `StreamEvent` data display (optional debug info)

When the collapsible "Input" section is shown, also show the `tool_use_id` at the bottom of the card in a very subtle way to help with debugging:

```typescript
{toolUseId && (
  <p className="text-[10px] text-gray-400 dark:text-gray-600 font-mono mt-1 select-all">
    {toolUseId}
  </p>
)}
```

---

## Summary of Changes

### `TaskOutputViewer.tsx`

1. **Rename `formatToolResult` → `parseToolResult`** and update it to return `{ content: string; isError: boolean }` instead of a plain string.
2. **Update the `toolResults` memo**: tighten the positional fallback to only apply when `pendingIds.length === 1` (avoid wrong associations for batched tool calls).
3. **Update `AssistantCard`**: use `parseToolResult` result, pass `isError` to styling/label logic, auto-open error outputs.
4. **Distinguish synthetic vs real results**: show "output not captured" note for `_inferred` results vs "no output" for real empty results.
5. **Show `tool_use_id`** in a small monospace label at the bottom of each tool card (helps debug matching issues).

---

## What This Does NOT Change

- No backend changes — the log file format is fine.
- No changes to the raw "Logs" tab (`TaskLogViewer`) — that tab is intentionally a raw log viewer.
- No changes to API endpoints or WebSocket streaming.
- No changes to the `ToolCallsDisplay` used in the chat interface (different context).

---

## Testing Approach

After implementing:

1. Run any Claude Code task that uses file reading (`Read` tool) or shell commands (`Bash` tool).
2. Open the task detail page → Output tab.
3. Verify that completed tool calls show a collapsible "Output (N lines)" section with the actual content.
4. Run a task that triggers a tool error (e.g., read a non-existent file).
5. Verify that the error tool result shows red styling and "Error output" label.
6. Confirm that batch tool calls (when Claude issues multiple tool calls in one turn) are not incorrectly cross-associated.
