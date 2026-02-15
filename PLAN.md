# Implementation Plan: Tool Call Tracking in Chat Messages

## Overview
Add tool call metadata to chat messages in the portal, showing a list/count of tools called and their sequence during each assistant response. This will provide better transparency into the agent's reasoning process.

## Current Architecture Analysis

### Backend Flow
1. **Core Orchestrator** (`agent/core/orchestrator/agent_loop.py`):
   - Agent loop executes up to `max_agent_iterations` (default 10)
   - Each iteration can involve multiple tool calls
   - Tool calls are saved as `Message` records with `role="tool_call"`
   - Tool results are saved as `Message` records with `role="tool_result"`
   - Final assistant response saved as `Message` with `role="assistant"`

2. **Database Schema** (`agent/shared/shared/models/conversation.py`):
   - `messages` table stores all message types (user, assistant, tool_call, tool_result)
   - `tool_call` messages store: `{"name": tool_name, "arguments": {...}, "tool_use_id": ...}`
   - `tool_result` messages store: `{"name": tool_name, "result": ..., "error": ..., "tool_use_id": ...}`
   - Assistant messages currently only store final `content` and `model_used`

3. **API Endpoints** (`agent/portal/routers/chat.py`):
   - `GET /api/chat/conversations/{conversation_id}/messages`: Returns messages filtered to only `user` and `assistant` roles (line 229)
   - Currently excludes `tool_call` and `tool_result` messages from portal view

4. **Frontend** (`agent/portal/frontend/src/`):
   - `ChatMessage` type (`types/index.ts`): Basic structure with role, content, files
   - `MessageBubble.tsx`: Renders user/assistant/workflow messages
   - No current display of tool call information

## Implementation Strategy

### Phase 1: Backend Changes

#### 1.1 Extend Message Model (if needed)
**File**: `agent/shared/shared/models/conversation.py`
- Current schema is sufficient - tool calls are already tracked in separate message records
- No database migration needed - we'll aggregate existing data

#### 1.2 Modify Chat API Endpoint
**File**: `agent/portal/routers/chat.py`

**Changes to `get_conversation_messages` endpoint** (line 204-231):
1. Query all messages (not just user/assistant)
2. Group tool_call and tool_result messages with their associated assistant response
3. Build tool metadata for each assistant message:
   - Extract tool calls that preceded the assistant response
   - Create ordered list of tool names
   - Count total tools and unique tools
   - Track success/failure status from tool_result messages

**New response structure**:
```python
{
    "id": str,
    "role": "assistant",
    "content": str,
    "model_used": str | None,
    "created_at": str,
    "tool_calls_metadata": {
        "total_count": int,
        "unique_tools": int,
        "tools_sequence": [
            {
                "name": str,
                "success": bool,
                "tool_use_id": str
            }
        ]
    } | None
}
```

**Algorithm**:
1. Fetch ALL messages for conversation (including tool_call/tool_result)
2. Iterate chronologically
3. Track pending tool calls in a buffer
4. When assistant message encountered:
   - Attach accumulated tool calls to it
   - Clear buffer
5. Filter to only user/assistant messages for response (now with metadata)

#### 1.3 Update WebSocket Response
**File**: `agent/portal/routers/chat.py`

**Changes to `ws_chat` endpoint** (line 373-454):
- WebSocket currently sends responses directly from `send_message()`
- The core `/message` endpoint returns `AgentResponse` which doesn't include tool metadata
- Two options:
  - **Option A**: After receiving response, query messages to get tool metadata (adds DB query)
  - **Option B**: Extend `AgentResponse` schema to include tool metadata from agent_loop

**Recommended: Option B** - cleaner, more efficient

**File**: `agent/shared/shared/schemas/messages.py`
```python
class ToolCallSummary(BaseModel):
    name: str
    success: bool
    tool_use_id: str

class ToolCallsMetadata(BaseModel):
    total_count: int
    unique_tools: int
    tools_sequence: list[ToolCallSummary]

class AgentResponse(BaseModel):
    content: str
    files: list[dict] = []
    error: str | None = None
    tool_calls_metadata: ToolCallsMetadata | None = None  # NEW
```

**File**: `agent/core/orchestrator/agent_loop.py`
- Track tool calls during agent loop execution
- Build metadata structure
- Include in `AgentResponse` return (line 323)

**Changes needed**:
1. Add list to track tool call summaries during loop
2. After each tool execution, append to tracking list (around line 246-272)
3. Build `ToolCallsMetadata` object from tracking list
4. Return in `AgentResponse`

### Phase 2: Frontend Changes

#### 2.1 Update TypeScript Types
**File**: `agent/portal/frontend/src/types/index.ts`

Add new interfaces:
```typescript
export interface ToolCallSummary {
  name: string;
  success: boolean;
  tool_use_id: string;
}

export interface ToolCallsMetadata {
  total_count: number;
  unique_tools: number;
  tools_sequence: ToolCallSummary[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  model_used?: string | null;
  created_at: string | null;
  files?: FileRef[];
  tool_calls_metadata?: ToolCallsMetadata | null;  // NEW
}
```

Update `WsChatResponse`:
```typescript
export interface WsChatResponse {
  type: "response";
  conversation_id: string;
  content: string;
  files: FileRef[];
  error: string | null;
  tool_calls_metadata?: ToolCallsMetadata | null;  // NEW
}
```

#### 2.2 Update ChatView Component
**File**: `agent/portal/frontend/src/components/chat/ChatView.tsx`

**Changes** (line 77-84):
- When constructing `assistantMsg` from WebSocket response, include `tool_calls_metadata`
```typescript
const assistantMsg: ChatMessage = {
  id: crypto.randomUUID(),
  role: "assistant",
  content: msg.content,
  created_at: new Date().toISOString(),
  files: msg.files,
  tool_calls_metadata: msg.tool_calls_metadata,  // NEW
};
```

#### 2.3 Update MessageBubble Component
**File**: `agent/portal/frontend/src/components/chat/MessageBubble.tsx`

**New UI Section** (add after content, before file attachments):

```typescript
{/* Tool calls metadata */}
{!isUser && message.tool_calls_metadata && (
  <div className="mt-3 pt-3 border-t border-border/50">
    <ToolCallsDisplay metadata={message.tool_calls_metadata} />
  </div>
)}
```

**Create new component**: `ToolCallsDisplay`
- Expandable/collapsible section
- Show summary: "Used X tools (Y unique)"
- Expandable details showing sequence with success/failure indicators
- Use icons from lucide-react (Wrench, CheckCircle2, XCircle)

Design:
```
[Collapsed]
🔧 Used 5 tools (3 unique)  [▼]

[Expanded]
🔧 Used 5 tools (3 unique)  [▲]
  1. research.web_search ✓
  2. file_manager.create_document ✓
  3. research.fetch_webpage ✓
  4. code_executor.run_python ✗
  5. code_executor.run_python ✓
```

#### 2.4 Create ToolCallsDisplay Component
**File**: `agent/portal/frontend/src/components/chat/ToolCallsDisplay.tsx` (NEW)

Features:
- Collapsed by default (just show count)
- Click to expand and see full sequence
- Color coding: green for success, red for failure
- Tool name with module.tool format
- Numbered list showing execution order
- Maybe add tooltip showing tool_use_id on hover

Styling considerations:
- Keep compact when collapsed
- Use existing theme colors (accent, surface, border)
- Match existing MessageBubble styling
- Subtle, not overwhelming the message content

### Phase 3: Testing & Polish

#### 3.1 Backend Testing
1. Test conversation with no tool calls (metadata should be null)
2. Test conversation with single tool call
3. Test conversation with multiple tool calls (same tool)
4. Test conversation with multiple different tools
5. Test conversation with failed tool calls
6. Test WebSocket flow with tool metadata
7. Verify existing messages endpoint still works

#### 3.2 Frontend Testing
1. Test display with no tool calls (shouldn't show section)
2. Test collapsed/expanded state
3. Test display with many tools (scrolling?)
4. Test responsive layout
5. Test with workflow messages (shouldn't show tools section)
6. Test WebSocket real-time updates

#### 3.3 Edge Cases
1. Max iterations reached (many tool calls)
2. Tool call without result (shouldn't happen but handle gracefully)
3. Mixed success/failure in same response
4. Very long tool names (truncation?)

## File Modification Summary

### Backend Files to Modify
1. `agent/shared/shared/schemas/messages.py` - Add ToolCallsMetadata to AgentResponse
2. `agent/core/orchestrator/agent_loop.py` - Track and return tool metadata
3. `agent/portal/routers/chat.py` - Include metadata in REST endpoint and WebSocket

### Frontend Files to Modify
1. `agent/portal/frontend/src/types/index.ts` - Add TypeScript interfaces
2. `agent/portal/frontend/src/components/chat/ChatView.tsx` - Pass metadata to messages
3. `agent/portal/frontend/src/components/chat/MessageBubble.tsx` - Render metadata section
4. `agent/portal/frontend/src/components/chat/ToolCallsDisplay.tsx` - NEW component

### No Database Changes Required
- All necessary data already stored in messages table
- Using existing tool_call and tool_result messages
- No migration needed

## Implementation Order

1. **Backend Schema** - Add ToolCallsMetadata classes to shared schemas
2. **Agent Loop** - Track tool calls and build metadata
3. **REST API** - Aggregate tool calls for historical messages
4. **WebSocket** - Pass through metadata from agent loop
5. **Frontend Types** - Add TypeScript interfaces
6. **Frontend Component** - Create ToolCallsDisplay component
7. **Frontend Integration** - Wire up ChatView and MessageBubble
8. **Testing** - Comprehensive testing of all flows
9. **Polish** - UI refinements, animations, loading states

## Success Criteria

- [ ] Assistant messages in portal show tool call count
- [ ] Tool call sequence is displayed in correct order
- [ ] Success/failure status is clearly indicated
- [ ] Both REST and WebSocket flows work correctly
- [ ] Historical conversations show tool metadata
- [ ] New conversations receive metadata in real-time
- [ ] UI is clean and doesn't overwhelm the message content
- [ ] No breaking changes to existing API contracts
- [ ] All existing tests still pass

## Risk Assessment

**Low Risk**:
- Additive changes only (new optional fields)
- No database migration required
- Existing API consumers unaffected (new fields are optional)
- Can be feature-flagged if needed

**Potential Issues**:
- Performance: Aggregating tool calls for historical messages (mitigated by limiting message query to 200)
- WebSocket timing: Tool metadata must be ready before response sent (should be fine, it's built during loop)
- UI clutter: Too much information could overwhelm users (mitigated by collapsed-by-default design)

## Future Enhancements (Out of Scope)

- Tool execution timing/duration
- Tool argument display (could be large)
- Tool result preview
- Filter messages by tools used
- Statistics dashboard for tool usage
- Export tool call data
- Retry failed tool calls from UI
