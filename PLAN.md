# Knowledge Portal — Implementation Plan

## Overview

This plan covers two areas:

1. **Knowledge module review** — Audit user-data isolation in `agent/modules/knowledge/` and identify any gaps or improvements needed.
2. **Portal Knowledge section** — Add a new `/knowledge` page to the portal where users can view, search, add, and delete their stored memories.

---

## Part 1: Knowledge Module Review

### Current State

The `knowledge` module stores per-user semantic memories in the `memory_summaries` table. User isolation is enforced at multiple layers:

| Layer | Mechanism |
|---|---|
| Database FK | `user_id UUID NOT NULL REFERENCES users.id` |
| Query filtering | Every SELECT/DELETE has `.where(MemorySummary.user_id == uid)` |
| Double-check delete | `forget()` requires BOTH `memory_id` AND `user_id` to match |
| Orchestrator injection | Core sets `tool_call.user_id = str(user.id)` before every tool call |
| Module validation | All four tools raise `ValueError` if `user_id` is missing |

### Issues Found

#### Issue 1 — `recall()` leaks embeddings-less memories across users (low severity, edge case)
In `tools.py:82`, the embedding fallback path filters by `user_id` correctly but is worth verifying against production; no actual bug found — the fallback `recall()` at line 88–93 correctly applies `.where(MemorySummary.user_id == uid)`.

#### Issue 2 — No `updated_at` field (enhancement, not a bug)
The `MemorySummary` model has no `updated_at` timestamp. This means memories cannot be edited in the portal — only created or deleted. This is intentional (memories are immutable facts), so no change needed.

#### Issue 3 — `list_memories` has a hardcoded `limit=20` default, with no offset/pagination support
For users with many memories, the portal would only show the 20 most recent. This is a UX gap. The portal router and tool should accept `limit` and `offset` parameters.

**Fix**: Add `offset: int = 0` parameter to `knowledge.list_memories` tool and the `list_memories()` method in `tools.py`.

#### Issue 4 — No `conversation_id` exposed in list/recall output
The `memory_summaries` table has `conversation_id` (optional), but the tool output omits it. The portal could show which conversation created the memory, giving useful context.

**Fix**: Include `conversation_id` in the serialized output from `list_memories()` and `recall()`.

#### Issue 5 — No database index on `user_id` in `memory_summaries`
The model has a FK but no explicit index. For users with thousands of memories, queries will be slow without an index. The migration should add `CREATE INDEX ix_memory_summaries_user_id ON memory_summaries(user_id)`.

**Fix**: Add an Alembic migration to create the index.

#### Issue 6 — The `forget()` method checks `rowcount` after `commit()`
In `tools.py:143–147`, `session.commit()` is called before checking `result.rowcount`. This is safe with SQLAlchemy async, but the check should happen before commit to allow rollback if desired. Low severity — current behavior is functionally correct (commit succeeds, then raises ValueError).

### Summary: No Critical Security Issues
User data isolation is solid. The identified issues are enhancements and minor improvements, not security vulnerabilities.

---

## Part 2: Portal Knowledge Section

### Architecture

Follow the exact same pattern used by the `skills` section:

```
Backend:  agent/portal/routers/knowledge.py
Frontend: agent/portal/frontend/src/hooks/useKnowledge.ts
          agent/portal/frontend/src/pages/KnowledgePage.tsx
          agent/portal/frontend/src/components/knowledge/  (optional sub-components)
Router:   agent/portal/main.py  (include knowledge router)
Sidebar:  agent/portal/frontend/src/components/layout/Sidebar.tsx  (add nav item)
App.tsx:  agent/portal/frontend/src/App.tsx  (add route)
Types:    agent/portal/frontend/src/types/index.ts  (add Memory type)
```

---

## Implementation Steps

### Step 1 — Knowledge module `tools.py` improvements

**File**: `agent/modules/knowledge/tools.py`

Changes:
- Add `offset: int = 0` parameter to `list_memories()` method
- Add `.offset(offset)` to the SQLAlchemy query
- Include `conversation_id` in serialized output for `list_memories()` and `recall()`
- No other behavioral changes needed

**Before** (`list_memories` signature):
```python
async def list_memories(self, limit: int = 20, user_id: str | None = None) -> list[dict]:
```

**After**:
```python
async def list_memories(self, limit: int = 50, user_id: str | None = None, offset: int = 0) -> list[dict]:
```

And add `.offset(offset)` to the query. Increase default limit to 50 to support the portal.

Serialized output change (add `conversation_id`):
```python
return [
    {
        "memory_id": str(m.id),
        "content": m.summary,
        "conversation_id": str(m.conversation_id) if m.conversation_id else None,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
    for m in memories
]
```

Apply same `conversation_id` field to `recall()` output.

### Step 2 — Knowledge module `manifest.py` improvements

**File**: `agent/modules/knowledge/manifest.py`

Changes:
- Add `offset` parameter to `knowledge.list_memories` tool definition
- Update `limit` default description to note the 50 default

### Step 3 — Add database index via Alembic migration

**New file**: `agent/alembic/versions/<hash>_add_index_memory_summaries_user_id.py`

Migration adds:
```sql
CREATE INDEX ix_memory_summaries_user_id ON memory_summaries (user_id);
```

This is a non-breaking additive migration that improves query performance.

### Step 4 — Backend portal router: `agent/portal/routers/knowledge.py`

Create a new FastAPI router following the same pattern as `routers/skills.py`.

**Endpoints:**

```
GET    /api/knowledge              → list_memories (with limit, offset, search_query params)
POST   /api/knowledge              → remember (create a new memory)
POST   /api/knowledge/recall       → recall (semantic search over memories)
DELETE /api/knowledge/{memory_id}  → forget (delete a memory)
```

**Request/Response models:**

```python
class CreateMemoryRequest(BaseModel):
    content: str

class RecallRequest(BaseModel):
    query: str
    max_results: int = 5

class MemoryResponse(BaseModel):
    memory_id: str
    content: str
    conversation_id: str | None
    created_at: str

class MemoryListResponse(BaseModel):
    memories: list[MemoryResponse]
    count: int
```

**Implementation pattern** (follows skills router):
```python
@router.get("")
async def list_memories(
    limit: int = 50,
    offset: int = 0,
    user: PortalUser = Depends(require_auth),
) -> dict:
    result = await call_tool(
        module="knowledge",
        tool_name="knowledge.list_memories",
        arguments={"limit": limit, "offset": offset},
        user_id=str(user.user_id),
    )
    memories = result.get("result", [])
    return {"memories": memories, "count": len(memories)}

@router.post("")
async def remember(
    request: CreateMemoryRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    result = await call_tool(
        module="knowledge",
        tool_name="knowledge.remember",
        arguments={"content": request.content},
        user_id=str(user.user_id),
    )
    return result.get("result", {})

@router.post("/recall")
async def recall(
    request: RecallRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    result = await call_tool(
        module="knowledge",
        tool_name="knowledge.recall",
        arguments={"query": request.query, "max_results": request.max_results},
        user_id=str(user.user_id),
    )
    memories = result.get("result", [])
    return {"memories": memories, "count": len(memories)}

@router.delete("/{memory_id}")
async def forget(
    memory_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    result = await call_tool(
        module="knowledge",
        tool_name="knowledge.forget",
        arguments={"memory_id": memory_id},
        user_id=str(user.user_id),
    )
    return result.get("result", {})
```

### Step 5 — Register router in `agent/portal/main.py`

Add import and `app.include_router()` call:

```python
from portal.routers import knowledge
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
```

### Step 6 — TypeScript types in `agent/portal/frontend/src/types/index.ts`

Add the `Memory` interface:

```typescript
export interface Memory {
  memory_id: string;
  content: string;
  conversation_id: string | null;
  created_at: string;
}

export interface MemoryListResponse {
  memories: Memory[];
  count: number;
}

export interface RecallResponse {
  memories: Memory[];
  count: number;
}
```

### Step 7 — Frontend hook: `agent/portal/frontend/src/hooks/useKnowledge.ts`

Custom React hook for data management, following the `useSkills.ts` pattern:

```typescript
// State hook for browsing/managing memories
export function useKnowledge(searchQuery?: string) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => { ... }, [searchQuery]);

  useEffect(() => { fetchMemories(); }, [fetchMemories]);

  return { memories, loading, error, refetch: fetchMemories };
}

// Standalone async helper functions (not hooks)
export async function rememberFact(content: string): Promise<Memory>
export async function recallMemories(query: string, maxResults?: number): Promise<RecallResponse>
export async function forgetMemory(memoryId: string): Promise<{ memory_id: string; deleted: boolean }>
```

Client-side search filtering: When `searchQuery` is provided, filter the `memories` array by `content.toLowerCase().includes(searchQuery.toLowerCase())`. This avoids an API round-trip for simple text search, since semantic recall (`/recall` endpoint) is available for semantic search.

### Step 8 — Frontend page: `agent/portal/frontend/src/pages/KnowledgePage.tsx`

Single-page design (no separate detail page needed — memories are simple text entries).

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  Knowledge Base                      [+ Add Memory]  │
│  N memories stored                                   │
├──────────────────┬──────────────────────────────────┤
│                  │                                  │
│  [Search...]     │  [Semantic Recall Mode]           │
│                  │  [Search query...]  [Recall]      │
├──────────────────┴──────────────────────────────────┤
│                                                      │
│  Memory Card                         [Delete]        │
│  Stored fact content text here...                    │
│  conversation_id: abc123 · 2026-02-15               │
│                                                      │
│  Memory Card                         [Delete]        │
│  Another stored fact...                              │
│  No conversation · 2026-02-10                        │
│                                                      │
└─────────────────────────────────────────────────────┘
```

**Features:**
1. **List view** — Shows all memories in reverse chronological order (most recent first)
2. **Text filter** — Client-side filter on memory content (instant, no API call)
3. **Semantic recall panel** — Toggle-able section where user can enter a query and get semantically similar memories back (calls `/api/knowledge/recall`)
4. **Add memory modal** — Simple textarea to enter a new fact; calls POST `/api/knowledge`
5. **Delete with confirmation** — Uses `ConfirmDialog` component; calls DELETE `/api/knowledge/{memory_id}`
6. **Loading/error/empty states** — Uses `Spinner`, `EmptyState` from common components
7. **Memory count display** — Shows "N memories stored" in the header
8. **Conversation link** — If `conversation_id` is present, show a small link badge

**Memory card design** (inline, no separate component file needed for simplicity):
- Shows truncated content (full content on expand/hover)
- Shows relative timestamp (e.g., "3 days ago")
- Shows conversation context if available
- Delete button aligned right

**Components to reuse:**
- `EmptyState` from `components/common/EmptyState.tsx`
- `ConfirmDialog` from `components/common/ConfirmDialog.tsx`
- `Spinner` from `components/common/Spinner.tsx`
- `Modal` from `components/common/Modal.tsx` (for add memory)

**Animations:**
- Use `AnimatePresence` from `framer-motion` for memory list (same as SkillsPage)
- Use `motion.div` with `fadeInUp` variant from `utils/animations.ts`

### Step 9 — Add route in `agent/portal/frontend/src/App.tsx`

```typescript
const KnowledgePage = lazy(() => import("./pages/KnowledgePage"));

// In router:
<Route path="/knowledge" element={<KnowledgePage />} />
```

### Step 10 — Add sidebar nav item in `agent/portal/frontend/src/components/layout/Sidebar.tsx`

Import `Brain` icon from `lucide-react` and add entry to `NAV_ITEMS`:

```typescript
{ to: "/knowledge", icon: Brain, label: "Knowledge" }
```

Position it after "Skills" in the nav order (or between Files and Schedule — to be determined by visual balance during implementation).

Also check `BottomNav.tsx` — if it has a limited set of items, determine whether Knowledge should appear there too (mobile nav).

---

## Files to Create

| File | Purpose |
|---|---|
| `agent/portal/routers/knowledge.py` | Backend API router |
| `agent/portal/frontend/src/hooks/useKnowledge.ts` | React data hook |
| `agent/portal/frontend/src/pages/KnowledgePage.tsx` | Portal page |
| `agent/alembic/versions/<hash>_add_index_memory_summaries_user_id.py` | DB index migration |

## Files to Modify

| File | Change |
|---|---|
| `agent/modules/knowledge/tools.py` | Add `offset` param, add `conversation_id` to output |
| `agent/modules/knowledge/manifest.py` | Add `offset` param to `list_memories` tool |
| `agent/portal/main.py` | Register knowledge router |
| `agent/portal/frontend/src/App.tsx` | Add `/knowledge` route |
| `agent/portal/frontend/src/components/layout/Sidebar.tsx` | Add Knowledge nav item |
| `agent/portal/frontend/src/types/index.ts` | Add `Memory` type |

---

## Implementation Order

1. Module changes (`tools.py`, `manifest.py`) + Alembic migration
2. Backend router (`routers/knowledge.py`) + register in `main.py`
3. TypeScript types (`types/index.ts`)
4. Frontend hook (`useKnowledge.ts`)
5. Frontend page (`KnowledgePage.tsx`)
6. Routing + sidebar wiring (`App.tsx`, `Sidebar.tsx`)

---

## Out of Scope

- Editing/updating memories (memories are immutable; only create and delete)
- Memory categories or tags (not in the data model; would require a migration)
- Bulk delete
- Exporting memories
- Sharing memories between users (by design, memories are strictly per-user)
- Admin view of all users' memories (security boundary — not planned)
