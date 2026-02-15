"""Context builder - assembles LLM context for each request."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.conversation import Conversation, Message
from shared.models.memory import MemorySummary
from shared.models.persona import Persona
from shared.models.user import User

try:
    from shared.models.project import Project
    from shared.models.project_phase import ProjectPhase
    from shared.models.project_task import ProjectTask
    _HAS_PROJECTS = True
except ImportError:
    _HAS_PROJECTS = False
from shared.utils.tokens import count_messages_tokens

logger = structlog.get_logger()

# Approximate context window sizes for models
MODEL_CONTEXT_WINDOWS = {
    "claude": 200000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gemini": 1000000,
}

DEFAULT_CONTEXT_WINDOW = 128000

# ---------------------------------------------------------------------------
# Heuristic: does the incoming message need full conversation history?
# ---------------------------------------------------------------------------
# Patterns that suggest the message refers to prior conversation context.
_CONTEXTUAL_PATTERNS = re.compile(
    r"""(?x)              # verbose mode
    \b(?:
        # pronouns / anaphora referencing a prior entity
        it | that | this | those | them | its | their | these
        # continuation / additive words
        | also | again | another | too | more | instead | otherwise | as\s+well
        # back-references
        | same | previous | last\s+one | above | mentioned | earlier
        # short affirmations / negations (responding to agent)
        | yes | no | ok | okay | sure | nah | yep | nope | correct
        # explicit conversation references
        | you\s+said | you\s+mentioned | as\s+before | like\s+before
        # cancel / modify previous action
        | cancel | undo | revert | change\s+it | update\s+it
        # approval / continuation of a pending action
        | approve | go\s+ahead | proceed | looks\s+good | lgtm | ship\s+it | do\s+it
    )\b
    """,
    re.IGNORECASE,
)

# Minimum word count below which a message is almost certainly a follow-up
_SHORT_MESSAGE_THRESHOLD = 4


class ContextBuilder:
    """Assembles the LLM context for each request."""

    def __init__(self, settings, llm_router=None):
        self.settings = settings
        self.llm_router = llm_router

    def _get_context_budget(self, model: str) -> int:
        """Get 80% of the model's context window."""
        for prefix, window in MODEL_CONTEXT_WINDOWS.items():
            if model.startswith(prefix):
                return int(window * 0.8)
        return int(DEFAULT_CONTEXT_WINDOW * 0.8)

    async def build(
        self,
        session: AsyncSession,
        user: User,
        conversation: Conversation,
        persona: Persona | None,
        incoming_message: str,
        model: str | None = None,
        tool_count: int = 0,
    ) -> list[dict]:
        """Build the context messages list for an LLM call.

        Structure:
        1. System prompt (persona + tools + datetime)
        2. Relevant semantic memories (max 3)
        3. Conversation summary (if partially summarized)
        4. Recent working memory (last N messages)
        5. New user message
        """
        target_model = model or self.settings.default_model
        # Reserve budget for tool definitions which are sent alongside messages
        tool_overhead = getattr(self.settings, "tool_schema_token_budget", 4000) if tool_count > 0 else 0
        budget = self._get_context_budget(target_model) - tool_overhead
        messages: list[dict] = []

        # 1. System prompt
        system_prompt = self._build_system_prompt(persona)
        messages.append({"role": "system", "content": system_prompt})

        # 2. Active project summaries
        project_context = await self._get_active_projects(session, user)
        if project_context:
            messages.append({"role": "system", "content": project_context})

        # 3. Semantic memories (if embedding/llm_router is available)
        memories = await self._get_semantic_memories(session, user, incoming_message)
        if memories:
            memory_text = "Relevant context from past conversations:\n"
            for mem in memories:
                memory_text += f"- {mem.summary}\n"
            messages.append({"role": "system", "content": memory_text})

        # 4. Conversation summary
        if conversation.is_summarized:
            summary = await self._get_conversation_summary(session, conversation)
            if summary:
                messages.append({
                    "role": "system",
                    "content": f"Summary of earlier conversation:\n{summary}",
                })

        # 5. Working memory — load adaptively based on message content
        needs_full = self._needs_full_context(incoming_message)
        recent_messages = await self._get_recent_messages(
            session, conversation, full=needs_full,
        )
        logger.info(
            "context_depth",
            full_context=needs_full,
            messages_loaded=len(recent_messages),
        )
        history_max = getattr(self.settings, "history_tool_result_max_chars", 1500)
        for msg in recent_messages:
            if msg.role == "tool_call":
                try:
                    data = json.loads(msg.content)
                    messages.append({
                        "role": "tool_call",
                        "name": data.get("name", ""),
                        "arguments": data.get("arguments", {}),
                        "tool_use_id": data.get("tool_use_id", ""),
                    })
                except json.JSONDecodeError:
                    messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == "tool_result":
                try:
                    data = json.loads(msg.content)
                    result_content = data.get("result", "")
                    # Truncate large historical tool results to save tokens
                    if isinstance(result_content, str) and len(result_content) > history_max:
                        result_content = result_content[:history_max] + "\n... [truncated]"
                    elif isinstance(result_content, (dict, list)):
                        result_str = json.dumps(result_content)
                        if len(result_str) > history_max:
                            result_content = result_str[:history_max] + "\n... [truncated]"
                    messages.append({
                        "role": "tool_result",
                        "name": data.get("name", ""),
                        "content": result_content,
                        "tool_use_id": data.get("tool_use_id", ""),
                    })
                except json.JSONDecodeError:
                    messages.append({"role": "user", "content": msg.content})
            else:
                messages.append({"role": msg.role, "content": msg.content})

        # 6. New user message
        messages.append({"role": "user", "content": incoming_message})

        # Trim to fit within budget
        messages = self._trim_to_budget(messages, budget, target_model)

        # Sanitize: remove orphaned tool_call/tool_result messages.
        # This handles working-memory window cuts and any pre-existing
        # broken history in the DB.
        messages = self._sanitize_tool_pairs(messages)

        return messages

    def _build_system_prompt(self, persona: Persona | None) -> str:
        """Build the system prompt from persona configuration."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        scheduler_guidance = (
            "\n\nWhen you submit a long-running task (like claude_code.run_task), "
            "use scheduler.add_job to monitor it. For multi-step workflows "
            "(e.g. build then deploy), use on_complete='resume_conversation' "
            "so the conversation resumes automatically when the task completes "
            "and you can call the next tool (like deployer.deploy). For simple "
            "monitoring where just a notification is needed, use on_complete='notify' "
            "(default). Do not ask the user to check back manually."
        )

        claude_code_guidance = (
            "\n\nClaude Code rules:"
            "\n- ALWAYS pass repo_url, branch (from phase_branch), source_branch, "
            "and auto_push=true when running project tasks with run_task."
            "\n- When a task finishes with 'awaiting_input' (plan mode), and the "
            "user approves, use continue_task with the ORIGINAL task_id, "
            "mode='execute', and auto_push=true. Never create a new run_task."
            "\n- Prefer continue_task over run_task for follow-up work in the "
            "same project — it preserves the workspace files and conversation "
            "context. Only start a fresh run_task when previous work has been "
            "pushed and a clean workspace is needed."
        )

        if persona:
            return (
                f"{persona.system_prompt}\n\n"
                f"Current date and time: {now}\n"
                f"You have access to tools. Use them when needed to accomplish tasks."
                f"{scheduler_guidance}"
                f"{claude_code_guidance}"
            )
        return (
            "You are a helpful AI assistant with access to various tools. "
            "Be concise, accurate, and helpful. If you're unsure about something, say so.\n\n"
            f"Current date and time: {now}\n"
            "You have access to tools. Use them when needed to accomplish tasks."
            f"{scheduler_guidance}"
            f"{claude_code_guidance}"
        )

    async def _get_active_projects(
        self,
        session: AsyncSession,
        user: User,
    ) -> str | None:
        """Build a brief summary of the user's active projects for system context."""
        if not _HAS_PROJECTS:
            return None

        try:
            from sqlalchemy import func

            result = await session.execute(
                select(Project)
                .where(Project.user_id == user.id)
                .where(Project.status.in_(["active", "planning"]))
                .order_by(Project.updated_at.desc())
                .limit(5)
            )
            projects = list(result.scalars().all())

            if not projects:
                return None

            lines = ["Active projects:"]
            for p in projects:
                # Get task counts
                counts_result = await session.execute(
                    select(ProjectTask.status, func.count(ProjectTask.id))
                    .where(ProjectTask.project_id == p.id)
                    .group_by(ProjectTask.status)
                )
                counts = {row[0]: row[1] for row in counts_result.all()}
                total = sum(counts.values())
                done = counts.get("done", 0)
                doing = counts.get("doing", 0)
                review = counts.get("in_review", 0)

                parts = [f'"{p.name}" ({p.status})']
                if total > 0:
                    parts.append(f"{done}/{total} tasks done")
                    if doing > 0:
                        parts.append(f"{doing} in progress")
                    if review > 0:
                        parts.append(f"{review} in review")
                if p.repo_owner and p.repo_name:
                    parts.append(f"repo: {p.repo_owner}/{p.repo_name}")
                if p.project_branch:
                    parts.append(f"project_branch: {p.project_branch}")

                lines.append(f"- {', '.join(parts)}")

                # Show in-progress tasks with claude_task_ids so LLM can
                # use continue_task instead of creating new workspaces
                if doing > 0:
                    doing_result = await session.execute(
                        select(ProjectTask)
                        .where(
                            ProjectTask.project_id == p.id,
                            ProjectTask.status == "doing",
                        )
                        .order_by(ProjectTask.order_index)
                        .limit(5)
                    )
                    doing_tasks = list(doing_result.scalars().all())
                    for t in doing_tasks:
                        task_info = f'  - Task "{t.title}"'
                        if t.claude_task_id:
                            task_info += f" [claude_task_id: {t.claude_task_id}]"
                        lines.append(task_info)

            lines.append(
                "\nProject execution workflow:"
                "\n1. get_next_task(phase_id) — returns the next todo task with "
                "phase_branch, source_branch, and project_branch."
                "\n2. update_task(status='doing') BEFORE starting any claude_code work."
                "\n3. claude_code.run_task with repo_url, branch=phase_branch, "
                "source_branch=source_branch, and auto_push=true. In the prompt, "
                "reference relevant docs from the repo (e.g. CLAUDE.md, docs/) so "
                "the task agent follows project conventions. Then scheduler.add_job "
                "with on_complete='resume_conversation' to monitor it. Include "
                "the project task_id in the on_success_message for tracking."
                "\n4. On task completion: update_task(status='in_review'). Create a PR "
                "from phase_branch into project_branch using git_platform.create_pull_request. "
                "Store the pr_number on the task with update_task(pr_number=...)."
                "\n5. If auto_merge is enabled, merge the PR with git_platform.merge_pull_request "
                "and update_task(status='done'). Otherwise notify the user the PR is ready."
                "\n6. For subsequent tasks in the same phase, prefer continue_task on the "
                "previous workspace (keeps file context). Only start a fresh run_task when "
                "previous work is pushed and a clean workspace is needed."
            )
            lines.append(
                "\nBatch execution (for simpler projects or when the user "
                "requests implementing multiple phases at once):"
                "\n1. get_execution_plan(project_id) — returns all todo tasks, "
                "design doc, and a pre-built prompt."
                "\n2. bulk_update_tasks(task_ids=todo_task_ids, status='doing') — "
                "marks all tasks as in-progress."
                "\n3. claude_code.run_task with the plan's prompt, repo_url, "
                "branch=plan.branch, source_branch=plan.source_branch, "
                "auto_push=true."
                "\n4. scheduler.add_job to monitor, with on_complete='resume_conversation'."
                "\n5. On completion: bulk_update_tasks(task_ids, status='done', "
                "claude_task_id=task_id). Optionally create a single PR from "
                "the project branch into the default branch."
                "\nUse batch execution when the user says things like "
                "'implement everything', 'do all phases', or 'implement the "
                "whole project'. Use sequential execution for complex projects "
                "where each task needs individual review."
            )

            return "\n".join(lines)
        except Exception as e:
            logger.warning("active_projects_context_failed", error=str(e))
            return None

    async def _get_semantic_memories(
        self,
        session: AsyncSession,
        user: User,
        query: str,
        max_results: int = 3,
    ) -> list[MemorySummary]:
        """Retrieve semantically relevant memories via vector search.

        Only returns memories whose cosine distance is below the configured
        relevance threshold, avoiding injection of irrelevant context.
        """
        if not self.llm_router:
            return []

        try:
            query_embedding = await self.llm_router.embed(query)
        except Exception as e:
            logger.warning("embedding_failed", error=str(e))
            return []

        threshold = getattr(self.settings, "memory_relevance_threshold", 0.75)

        # Vector similarity search using pgvector with relevance filter
        try:
            distance_expr = MemorySummary.embedding.cosine_distance(query_embedding)
            result = await session.execute(
                select(MemorySummary)
                .where(MemorySummary.user_id == user.id)
                .where(MemorySummary.embedding.isnot(None))
                .where(distance_expr < threshold)
                .order_by(distance_expr)
                .limit(max_results)
            )
            memories = list(result.scalars().all())
            logger.info(
                "semantic_memories",
                found=len(memories),
                threshold=threshold,
            )
            return memories
        except Exception as e:
            logger.warning("semantic_search_failed", error=str(e))
            return []

    async def _get_conversation_summary(
        self,
        session: AsyncSession,
        conversation: Conversation,
    ) -> str | None:
        """Get the summary for a partially summarized conversation."""
        result = await session.execute(
            select(MemorySummary)
            .where(MemorySummary.conversation_id == conversation.id)
            .order_by(MemorySummary.created_at.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()
        return summary.summary if summary else None

    async def _get_recent_messages(
        self,
        session: AsyncSession,
        conversation: Conversation,
        full: bool = True,
    ) -> list[Message]:
        """Get the most recent messages from a conversation.

        When *full* is False only the last few messages are loaded
        (``minimal_memory_messages``, default 4) — just enough to
        maintain basic conversational flow for standalone queries.
        """
        limit = (
            self.settings.working_memory_messages
            if full
            else getattr(self.settings, "minimal_memory_messages", 4)
        )
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # Oldest first
        return messages

    @staticmethod
    def _needs_full_context(message: str) -> bool:
        """Decide whether *message* requires full conversation history.

        Returns True (load full history) when the message appears to
        reference prior context — pronouns, back-references,
        continuations, or very short follow-ups.

        Returns False (standalone) for self-contained queries like
        "get inj spot price" or "search for BTC markets".
        """
        # Very short messages are almost always follow-ups
        if len(message.split()) < _SHORT_MESSAGE_THRESHOLD:
            return True

        # Check for contextual language
        if _CONTEXTUAL_PATTERNS.search(message):
            return True

        # Otherwise treat as standalone
        return False

    def _trim_to_budget(
        self,
        messages: list[dict],
        budget: int,
        model: str,
    ) -> list[dict]:
        """Trim messages to fit within the token budget.

        Tool call/result pairs are treated as atomic groups so that
        trimming never produces an orphaned tool_result without its
        preceding tool_call (which causes API errors on all providers).
        """
        total = count_messages_tokens(messages, model)
        if total <= budget:
            return messages

        # Keep system messages and the latest user message, trim from the middle
        system_msgs = [m for m in messages if m["role"] == "system"]
        user_msg = messages[-1]  # The new user message
        middle_msgs = [m for m in messages if m["role"] != "system" and m is not user_msg]

        # Group messages so that consecutive tool_call/tool_result runs
        # are treated as a single removable unit.
        groups: list[list[dict]] = []
        for msg in middle_msgs:
            if msg["role"] in ("tool_call", "tool_result"):
                # Attach to the current tool group if one exists
                if groups and groups[-1][0]["role"] in ("tool_call", "tool_result"):
                    groups[-1].append(msg)
                else:
                    groups.append([msg])
            else:
                groups.append([msg])

        # Remove oldest groups until we fit
        while groups and count_messages_tokens(
            system_msgs + [m for g in groups for m in g] + [user_msg], model
        ) > budget:
            groups.pop(0)

        trimmed_middle = [m for g in groups for m in g]

        # Safety: strip any leading orphaned tool_result messages that
        # could remain if the DB already contained broken history.
        while trimmed_middle and trimmed_middle[0]["role"] == "tool_result":
            trimmed_middle.pop(0)

        return system_msgs + trimmed_middle + [user_msg]

    @staticmethod
    def _sanitize_tool_pairs(messages: list[dict]) -> list[dict]:
        """Remove tool_call/tool_result messages that lack a matching partner.

        All LLM providers require that every tool_result references a
        tool_use_id from a preceding tool_call (assistant) message.
        Orphans arise when the working-memory window or token trimming
        splits a pair apart.  Drop any unmatched messages so the
        payload is always valid.
        """
        # Collect all tool_use_ids from tool_call messages
        call_ids: set[str] = set()
        for msg in messages:
            if msg.get("role") == "tool_call":
                tid = msg.get("tool_use_id")
                if tid:
                    call_ids.add(tid)

        # Collect all tool_use_ids from tool_result messages
        result_ids: set[str] = set()
        for msg in messages:
            if msg.get("role") == "tool_result":
                tid = msg.get("tool_use_id")
                if tid:
                    result_ids.add(tid)

        # IDs that appear in results but have no matching call
        orphan_result_ids = result_ids - call_ids
        # IDs that appear in calls but have no matching result
        orphan_call_ids = call_ids - result_ids

        if not orphan_result_ids and not orphan_call_ids:
            return messages

        logger.warning(
            "sanitized_orphan_tool_messages",
            orphan_results=list(orphan_result_ids),
            orphan_calls=list(orphan_call_ids),
        )

        cleaned: list[dict] = []
        for msg in messages:
            role = msg.get("role")
            tid = msg.get("tool_use_id")
            if role == "tool_result" and tid in orphan_result_ids:
                continue  # drop orphaned result
            if role == "tool_call" and tid in orphan_call_ids:
                continue  # drop orphaned call
            cleaned.append(msg)
        return cleaned
