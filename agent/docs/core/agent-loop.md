# Agent Loop

> **Quick Context**: The core reasoning cycle that powers the AI agent's decision-making.
>
> **Related Files**: `agent/core/orchestrator/agent_loop.py`
>
> **Related Docs**: [Core Overview](overview.md), [Tool Registry](tool-registry.md), [Context Builder](context-builder.md)
>
> **When to Read**: Modifying agent behavior, understanding execution flow, debugging tool execution

## Purpose

The Agent Loop is the heart of the AI agent system. It implements a reason/act/observe cycle that:
- Resolves users and conversations
- Builds context with memories and history
- Calls the LLM with available tools
- Executes tool calls and loops back with results
- Manages token budgets and iteration limits

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                      Agent Loop                            │
│                                                            │
│  run(IncomingMessage) → AgentResponse                      │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 1. Resolve User                                      │ │
│  │    platform_user_id → User (auto-create if guest)   │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 2. Check Budget                                      │ │
│  │    Verify token_budget_monthly                       │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 3. Resolve Persona                                   │ │
│  │    server → platform → default                       │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 4. Resolve Conversation                              │ │
│  │    Find/create in channel/thread                     │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 5. Get Available Tools                               │ │
│  │    Filter by permission + allowed_modules            │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 6. Register File Attachments                         │ │
│  │    Create FileRecords, enrich message content        │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 7. Build Context                                     │ │
│  │    System prompt + memories + history                │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 8. LOOP (up to max_agent_iterations, default 10)    │ │
│  │                                                      │ │
│  │  ┌─────────────────────────────────────────┐        │ │
│  │  │ Call LLM → LLMResponse                  │        │ │
│  │  └──────────────┬──────────────────────────┘        │ │
│  │                 │                                    │ │
│  │                 ▼                                    │ │
│  │  ┌─────────────────────────────────────────┐        │ │
│  │  │ stop_reason == "tool_use"?              │        │ │
│  │  └──────┬──────────────────┬───────────────┘        │ │
│  │         NO                 YES                       │ │
│  │         │                   │                        │ │
│  │         ▼                   ▼                        │ │
│  │  ┌──────────┐    ┌──────────────────────┐           │ │
│  │  │ Break    │    │ Execute Each Tool    │           │ │
│  │  │ Loop     │    │ Append Results       │           │ │
│  │  └──────────┘    │ Continue Loop        │           │ │
│  │                  └──────────────────────┘           │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│  ┌──────────────────────────────────────────────────────┐ │
│  │ 9. Save Messages & Extract Files                    │ │
│  └──────────────────────────────────────────────────────┘ │
│                        ↓                                   │
│                 AgentResponse                              │
└────────────────────────────────────────────────────────────┘
```

## Step-by-Step Breakdown

### 1. Resolve User
**Code**: `agent_loop.py:69` (`_resolve_user()`)

Maps platform user ID to internal User record, auto-creating guests if needed.

```python
async def _resolve_user(self, session: AsyncSession, incoming: IncomingMessage) -> User:
    # Look up UserPlatformLink
    result = await session.execute(
        select(UserPlatformLink)
        .where(
            UserPlatformLink.platform == incoming.platform,
            UserPlatformLink.platform_user_id == incoming.platform_user_id,
        )
    )
    link = result.scalar_one_or_none()

    if link:
        # Existing user
        user = await session.get(User, link.user_id)
        return user

    # Auto-create guest user
    user = User(
        id=uuid.uuid4(),
        permission_level="guest",
        token_budget_monthly=5000,  # or from settings
        tokens_used_this_month=0,
        budget_reset_at=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc),
    )
    session.add(user)

    # Create platform link
    link = UserPlatformLink(
        id=uuid.uuid4(),
        user_id=user.id,
        platform=incoming.platform,
        platform_user_id=incoming.platform_user_id,
        platform_username=incoming.platform_user_id,  # or from incoming
    )
    session.add(link)

    return user
```

**Key Behaviors:**
- Guest users created on first message
- Platform links support multi-platform users
- Permission level defaults to "guest"

### 2. Check Budget
**Code**: `agent_loop.py:72` (`_check_budget()`)

Verifies user hasn't exceeded monthly token budget.

```python
def _check_budget(self, user: User) -> bool:
    # Null budget = unlimited (admin/owner)
    if user.token_budget_monthly is None:
        return True

    # Check if budget period expired
    if datetime.now(timezone.utc) >= user.budget_reset_at:
        # Reset for new period
        user.tokens_used_this_month = 0
        user.budget_reset_at = datetime.now(timezone.utc) + timedelta(days=30)
        return True

    # Check if under budget
    return user.tokens_used_this_month < user.token_budget_monthly
```

**Budget Reset:**
- Automatic monthly reset based on `budget_reset_at`
- Admins/owners have `null` budget (unlimited)
- Guests default to 5,000 tokens/month

### 3. Resolve Persona
**Code**: `agent_loop.py:78` (`_resolve_persona()`)

Selects persona with cascading priority: server-specific → platform-specific → default.

```python
async def _resolve_persona(
    self, session: AsyncSession, incoming: IncomingMessage
) -> Persona | None:
    # 1. Try server-specific (Discord guilds, Slack workspaces)
    if incoming.platform_server_id:
        result = await session.execute(
            select(Persona)
            .where(
                Persona.platform == incoming.platform,
                Persona.platform_server_id == incoming.platform_server_id,
            )
        )
        if persona := result.scalar_one_or_none():
            return persona

    # 2. Try platform-specific
    result = await session.execute(
        select(Persona)
        .where(
            Persona.platform == incoming.platform,
            Persona.platform_server_id.is_(None),
        )
    )
    if persona := result.scalar_one_or_none():
        return persona

    # 3. Default persona
    result = await session.execute(
        select(Persona).where(Persona.is_default.is_(True))
    )
    return result.scalar_one_or_none()
```

**Persona Fields:**
- `system_prompt` — Custom instructions for LLM
- `allowed_modules` — JSON array of permitted modules
- `default_model` — Override default LLM
- `max_tokens_per_request` — Output token limit

### 4. Resolve Conversation
**Code**: `agent_loop.py:81` (`_resolve_conversation()`)

Finds or creates conversation for the channel/thread.

```python
async def _resolve_conversation(
    self,
    session: AsyncSession,
    user: User,
    incoming: IncomingMessage,
    persona: Persona | None,
) -> Conversation:
    # Look for existing conversation in this channel/thread
    query = (
        select(Conversation)
        .where(
            Conversation.platform == incoming.platform,
            Conversation.platform_channel_id == incoming.platform_channel_id,
        )
    )

    if incoming.platform_thread_id:
        query = query.where(
            Conversation.platform_thread_id == incoming.platform_thread_id
        )
    else:
        query = query.where(Conversation.platform_thread_id.is_(None))

    result = await session.execute(query)
    conversation = result.scalar_one_or_none()

    if conversation:
        # Update last active
        conversation.last_active_at = datetime.now(timezone.utc)
        return conversation

    # Create new conversation
    conversation = Conversation(
        id=uuid.uuid4(),
        user_id=user.id,
        persona_id=persona.id if persona else None,
        platform=incoming.platform,
        platform_channel_id=incoming.platform_channel_id,
        platform_thread_id=incoming.platform_thread_id,
        started_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
        is_summarized=False,
    )
    session.add(conversation)
    return conversation
```

**Conversation Scope:**
- Unique per (platform, channel_id, thread_id) tuple
- Threads are separate conversations
- Persists across multiple messages

### 5. Get Available Tools
**Code**: `agent_loop.py:88-90`

Filters tools by user permission and persona's allowed modules.

```python
# Parse allowed modules from persona
allowed_modules = (
    json.loads(persona.allowed_modules)
    if persona
    else parse_list(self.settings.default_guest_modules)
)

# Get filtered tools
tools = self.tool_registry.get_tools_for_user(
    user.permission_level,
    allowed_modules
)

# Convert to OpenAI format for LLM
openai_tools = self.tool_registry.tools_to_openai_format(tools) if tools else None
```

**Permission Hierarchy:**
```
guest < user < admin < owner

- guest can use tools with required_permission = "guest"
- user can use "guest" + "user" tools
- admin can use "guest" + "user" + "admin" tools
- owner can use all tools
```

See [Tool Registry](tool-registry.md) for filtering details.

### 6. Register File Attachments
**Code**: `agent_loop.py:106-138`

Creates FileRecord entries and enriches message content with file context.

```python
if incoming.attachments:
    # Create FileRecord for each attachment
    for att in incoming.attachments:
        file_id = uuid.uuid4()
        record = FileRecord(
            id=file_id,
            user_id=user.id,
            filename=att.get("filename", "file"),
            minio_key=att.get("minio_key", ""),
            mime_type=att.get("mime_type"),
            size_bytes=att.get("size_bytes"),
            public_url=att.get("url", ""),
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        att["file_id"] = str(file_id)

    await session.commit()  # commit so code_executor can see them

    # Enrich message with file context
    file_context = "\n\n[Attached files:]\n"
    for att in incoming.attachments:
        fname = att.get("filename", "file")
        fid = att.get("file_id", "")
        fsize = att.get("size_bytes", 0)
        fmime = att.get("mime_type", "")
        file_context += f"- {fname} (file_id: {fid}, {fsize} bytes, {fmime})\n"

    file_context += (
        "Use file_manager.read_document(file_id) to read text files, "
        "or code_executor.load_file(file_id) then run_python to process them."
    )

    message_content += file_context
```

**Why Commit Early:**
Cross-container modules (code_executor) need to query FileRecord table via their own DB connection.

### 7. Build Context
**Code**: `agent_loop.py:141-149`

Delegates to [Context Builder](context-builder.md) to assemble the prompt.

```python
context = await self.context_builder.build(
    session=session,
    user=user,
    conversation=conversation,
    persona=persona,
    incoming_message=message_content,
    model=model,
    tool_count=len(tools),
)
```

Context includes:
- System prompt from persona
- Semantic memories (vector search on user's memories)
- Conversation summary (if conversation was summarized)
- Recent messages (windowed by token count)
- Incoming message

See [Context Builder](context-builder.md) for details.

### 8. Agent Loop (Iteration)
**Code**: `agent_loop.py:167-315`

The core reasoning cycle — call LLM, execute tools, repeat.

#### 8a. Call LLM
```python
llm_response: LLMResponse = await self.llm_router.chat(
    messages=context,
    tools=openai_tools,
    model=model,
    max_tokens=max_tokens,
)
```

**LLMResponse Fields:**
- `content` — Text response
- `stop_reason` — "end_turn" | "tool_use" | "max_tokens"
- `tool_calls` — List of ToolCall if stop_reason == "tool_use"
- `model` — Actual model used (after fallback)
- `input_tokens` — Token count for input
- `output_tokens` — Token count for output

#### 8b. Log Token Usage
```python
cost = estimate_cost(
    llm_response.model or model,
    llm_response.input_tokens,
    llm_response.output_tokens,
)

token_log = TokenLog(
    id=uuid.uuid4(),
    user_id=user.id,
    conversation_id=conversation.id,
    model=llm_response.model or model,
    input_tokens=llm_response.input_tokens,
    output_tokens=llm_response.output_tokens,
    cost_estimate=cost,
    created_at=datetime.now(timezone.utc),
)
session.add(token_log)

# Update user's monthly usage
user.tokens_used_this_month += (
    llm_response.input_tokens + llm_response.output_tokens
)
```

#### 8c. Handle Tool Calls
```python
for tool_call in llm_response.tool_calls:
    tool_use_id = f"tool_{uuid.uuid4().hex[:12]}"

    # Save tool call message
    tc_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="tool_call",
        content=json.dumps({
            "name": tool_call.tool_name,
            "arguments": tool_call.arguments,
            "tool_use_id": tool_use_id,
        }),
        created_at=datetime.now(timezone.utc),
    )
    session.add(tc_msg)

    # Inject user_id
    tool_call.user_id = str(user.id)

    # Inject platform context for scheduler/location
    if tool_call.tool_name.startswith(("scheduler.", "location.")):
        tool_call.arguments["platform"] = conversation.platform
        tool_call.arguments["platform_channel_id"] = conversation.platform_channel_id
        tool_call.arguments["platform_thread_id"] = conversation.platform_thread_id
        if tool_call.tool_name == "scheduler.add_job":
            tool_call.arguments["conversation_id"] = str(conversation.id)

    # Execute tool
    result = await self.tool_registry.execute_tool(tool_call)

    # Retry once if failed
    if not result.success:
        result = await self.tool_registry.execute_tool(tool_call)

    # Save tool result message
    result_content = json.dumps({
        "name": tool_call.tool_name,
        "result": result.result if result.success else None,
        "error": result.error,
        "tool_use_id": tool_use_id,
    })
    tr_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="tool_result",
        content=result_content,
        created_at=datetime.now(timezone.utc),
    )
    session.add(tr_msg)

    # Append to context (truncate large results)
    context.append({
        "role": "tool_call",
        "name": tool_call.tool_name,
        "arguments": tool_call.arguments,
        "tool_use_id": tool_use_id,
    })

    result_text = str(result.result) if result.success else f"Error: {result.error}"
    max_chars = self.settings.tool_result_max_chars  # default 8000
    if len(result_text) > max_chars:
        result_text = result_text[:max_chars] + "\n... [truncated]"

    context.append({
        "role": "tool_result",
        "tool_use_id": tool_use_id,
        "content": result_text,
    })
```

**Context Injection:**
- `user_id` — Always injected so modules can associate resources
- `platform`, `platform_channel_id`, `platform_thread_id` — For modules that send notifications (scheduler, location)
- `conversation_id` — For scheduler to resume conversation

**Retry Logic:**
One automatic retry if tool execution fails.

#### 8d. Loop Control
```python
if llm_response.stop_reason != "tool_use" or not llm_response.tool_calls:
    # Final response — save and break
    final_content = llm_response.content or ""
    assistant_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role="assistant",
        content=final_content,
        token_count=llm_response.output_tokens,
        model_used=llm_response.model or model,
        created_at=datetime.now(timezone.utc),
    )
    session.add(assistant_msg)
    break

# Continue loop with tool results appended to context
```

**Loop Termination:**
- LLM returns final text (stop_reason != "tool_use")
- Max iterations reached (default 10)

### 9. Extract Files from Tool Results
**Code**: `agent_loop.py:317-339`

Scans tool results for file URLs to include in response.

```python
# Extract files from tool results
for msg in context:
    if msg.get("role") == "tool_result":
        result_data = json.loads(msg.get("content", "{}"))
        if "result" in result_data and result_data["result"]:
            # Check for top-level "url" key
            if isinstance(result_data["result"], dict):
                if "url" in result_data["result"]:
                    files.append({
                        "filename": result_data["result"].get("filename", "file"),
                        "url": result_data["result"]["url"],
                        "minio_key": result_data["result"].get("minio_key", ""),
                    })

                # Check for "files" array
                if "files" in result_data["result"]:
                    for f in result_data["result"]["files"]:
                        if isinstance(f, dict) and "url" in f:
                            files.append(f)
```

## Iteration Limits

**Default**: `max_agent_iterations = 10`

**Why Limit?**
- Prevent infinite loops
- Control costs
- Ensure timely responses

**What Happens at Limit?**
Loop exits with whatever content LLM has generated. If LLM is still calling tools, response may be incomplete.

**Adjusting Limit:**
Set in `shared/config.py`:
```python
max_agent_iterations: int = 15  # increase if needed
```

## Token Budget Management

### Budget Tracking
```python
user.tokens_used_this_month += (input_tokens + output_tokens)
```

### Budget Reset
Automatic monthly reset:
```python
if datetime.now(timezone.utc) >= user.budget_reset_at:
    user.tokens_used_this_month = 0
    user.budget_reset_at = datetime.now(timezone.utc) + timedelta(days=30)
```

### Unlimited Budget
Set `token_budget_monthly = None` for admins/owners:
```sql
UPDATE users SET token_budget_monthly = NULL WHERE id = 'uuid';
```

## Message Persistence

All messages saved to `messages` table:

**Roles:**
- `user` — User's input message
- `assistant` — LLM's final text response
- `tool_call` — LLM requested tool execution
- `tool_result` — Tool execution result

**Why Persist Tool Calls?**
- Conversation history for future context
- Debugging tool execution
- Token usage tracking
- Audit trail

## Example Execution Flow

### Simple Query (No Tools)

```
User: "Hello, how are you?"
  ↓
1. Resolve User → guest_123
2. Check Budget → 100/5000 tokens used ✓
3. Resolve Persona → default
4. Resolve Conversation → conv_789
5. Get Tools → [research, file_manager, ...]
6. Build Context → [system_prompt, "Hello, how are you?"]
7. Loop iteration 1:
   - LLM: "I'm doing well, thank you! How can I help you today?"
   - stop_reason: "end_turn"
   - Break loop
8. Save assistant message
9. Return: "I'm doing well, thank you! How can I help you today?"
```

**Iterations**: 1
**Tools Used**: 0

### Complex Query (Multiple Tools)

```
User: "Search for Python tutorials and save the top 3 links to a file"
  ↓
1-6. (same setup as above)
7. Loop iteration 1:
   - LLM: tool_use → research.web_search(query="Python tutorials", max_results=3)
   - Execute: research.web_search
   - Result: [{title: "...", url: "..."}, ...]
   - Append to context
   - Continue loop

8. Loop iteration 2:
   - LLM: tool_use → file_manager.create_document(
       title="python_tutorials.md",
       content="# Python Tutorials\n1. ...",
       format="md"
     )
   - Execute: file_manager.create_document
   - Result: {url: "https://...", file_id: "..."}
   - Append to context
   - Continue loop

9. Loop iteration 3:
   - LLM: "I've searched for Python tutorials and saved the top 3 links to python_tutorials.md"
   - stop_reason: "end_turn"
   - Break loop

10. Extract files: [python_tutorials.md]
11. Return: {content: "...", files: [{filename: "python_tutorials.md", url: "..."}]}
```

**Iterations**: 3
**Tools Used**: 2 (research.web_search, file_manager.create_document)

## Error Handling

### User Resolution Fails
Auto-create guest user — never fails.

### Budget Exceeded
Return early with budget error message.

### Persona Not Found
Use `None` — context builder uses default system prompt.

### Tool Execution Fails
- Retry once automatically
- If still fails, return error to LLM
- LLM can retry with different arguments or acknowledge failure

### LLM Call Fails
Handled by [LLM Router](llm-router.md) fallback chain.

### Database Errors
Caught by top-level try/except:
```python
except Exception as e:
    logger.error("agent_loop_error", error=str(e), exc_info=True)
    return AgentResponse(
        content="I encountered an internal error. Please try again.",
        error=str(e),
    )
```

## Performance Considerations

### Database Commits
- Early commit after conversation resolution (line 85)
- Early commit after file registration (line 123)
- **Why**: Cross-container modules query DB via separate connections

### Tool Result Truncation
Large results truncated to `tool_result_max_chars` (default 8000):
```python
if len(result_text) > max_chars:
    result_text = result_text[:max_chars] + "\n... [truncated]"
```

**Why**: Prevent context overflow, reduce token costs.

### Memory Queries
Semantic recall limited to top 5 most relevant memories.

See [Context Builder](context-builder.md) for details.

## Testing

See [Testing Guide](../development/testing.md) for:
- Unit testing agent loop steps
- Mocking LLM responses
- Mocking tool execution
- Integration testing full flow

## Related Documentation

- [Core Overview](overview.md) — Component architecture
- [Tool Registry](tool-registry.md) — Module discovery and routing
- [Context Builder](context-builder.md) — Context assembly
- [LLM Router](llm-router.md) — Provider abstraction
- [Memory System](memory-system.md) — Summarization and recall
- [Troubleshooting](../troubleshooting/common-issues.md) — Common problems

---

[Back to Core Documentation](README.md) | [Documentation Index](../INDEX.md)
