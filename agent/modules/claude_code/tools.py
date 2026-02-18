"""Claude Code tool implementations."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = int(os.environ.get("CLAUDE_CODE_TIMEOUT", "1800"))
CLAUDE_CODE_IMAGE = os.environ.get("CLAUDE_CODE_IMAGE", "my-claude-code-image")
CLAUDE_AUTH_PATH = os.environ.get("CLAUDE_AUTH_PATH", "")
SSH_KEY_PATH = os.environ.get("SSH_KEY_PATH", "")
GH_CONFIG_PATH = os.environ.get("GH_CONFIG_PATH", "")
GIT_CONFIG_PATH = os.environ.get("GIT_CONFIG_PATH", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
TASK_VOLUME = os.environ.get("CLAUDE_TASK_VOLUME", "")  # absolute host path to bind-mount

# Bot git identity — overrides any mounted .gitconfig for commits
CLAUDE_CODE_GIT_AUTHOR_NAME = os.environ.get("CLAUDE_CODE_GIT_AUTHOR_NAME", "claude-agent[bot]")
CLAUDE_CODE_GIT_AUTHOR_EMAIL = os.environ.get("CLAUDE_CODE_GIT_AUTHOR_EMAIL", "claude-agent[bot]@noreply.github.com")
TASK_BASE_DIR = "/tmp/claude_tasks"

MAX_OUTPUT = 50_000  # chars kept from stdout/stderr
MAX_FILE_READ = 100_000  # max chars returned by read_workspace_file
LOG_TAIL_DEFAULT = 100  # lines returned by task_logs when no limit given

# Auto-continuation thresholds
CONTEXT_THRESHOLD_PCT = 0.80  # trigger continuation at 80% of model context
MAX_CONTINUATIONS = 5  # safety limit on auto-continuations


def _get_model_context_limit(model: str | None) -> int:
    """Return the context window size for a given model name."""
    if model and "gemini" in model.lower():
        return 1_000_000
    return 200_000
TASK_META_FILE = "task_meta.json"  # persisted in each task workspace
GIT_CMD_TIMEOUT = 60  # seconds for git operations (push, status, etc.)
USER_CREDS_DIR = os.path.join(TASK_BASE_DIR, ".user_creds")  # per-user credentials
MAX_WORKSPACES_PER_USER = 10  # maximum number of workspaces a user can have

_GIT_REF_PATTERN = re.compile(r"^[a-zA-Z0-9._/:\-]+$")

WORKER_NETWORK = "worker-net"


async def _resolve_network_name(hint: str = WORKER_NETWORK) -> str:
    """Find the real Docker network name matching *hint*.

    Docker Compose prefixes network names with the project name, so a
    compose-defined ``worker-net`` becomes e.g. ``agent_worker-net`` on the
    host.  We pick the first network whose name ends with the hint.
    Falls back to the hint unchanged.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "network", "ls", "--format", "{{.Name}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await proc.communicate()
        for name in stdout.decode().splitlines():
            if name == hint or name.endswith(f"_{hint}"):
                return name
    except Exception:
        pass
    return hint

# Anthropic OAuth constants (same as Claude Code CLI uses)
_CLAUDE_CODE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
_CLAUDE_OAUTH_TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
_TOKEN_REFRESH_THRESHOLD_MS = 30 * 60 * 1000  # refresh if < 30 min remaining


def _validate_git_ref(value: str, label: str) -> None:
    """Reject values that could be used for command injection."""
    if not _GIT_REF_PATTERN.match(value):
        raise ValueError(f"Invalid {label}: {value!r}")


async def _maybe_refresh_credentials(user_id: str, credentials_json: str) -> str:
    """Proactively refresh Claude OAuth tokens if expiring within 30 minutes.

    Returns the (possibly updated) credentials JSON string.  On refresh failure,
    returns the original credentials so the task can still attempt to run.
    Also persists refreshed tokens to the database for future tasks.
    """
    try:
        creds = json.loads(credentials_json)
        oauth = creds.get("claudeAiOauth", {})
        if not oauth:
            return credentials_json

        expires_at_ms = oauth.get("expiresAt") or oauth.get("expires_at", 0)
        now_ms = int(time.time() * 1000)

        if expires_at_ms and (expires_at_ms - now_ms) > _TOKEN_REFRESH_THRESHOLD_MS:
            # Token is still fresh — no refresh needed
            return credentials_json

        refresh_tok = oauth.get("refreshToken") or oauth.get("refresh_token")
        if not refresh_tok:
            logger.warning("token_expiring_no_refresh_token", user_id=user_id)
            return credentials_json

        logger.info(
            "proactive_token_refresh",
            user_id=user_id,
            expires_in_ms=max(0, expires_at_ms - now_ms) if expires_at_ms else 0,
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _CLAUDE_OAUTH_TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": _CLAUDE_CODE_CLIENT_ID,
                },
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning(
                    "proactive_token_refresh_failed",
                    user_id=user_id,
                    status=resp.status_code,
                )
                return credentials_json

            new_tokens = resp.json()

        # Update the credentials structure
        new_now_ms = int(time.time() * 1000)
        expires_in = new_tokens.get("expires_in", 28800)
        oauth["accessToken"] = new_tokens["access_token"]
        if new_tokens.get("refresh_token"):
            oauth["refreshToken"] = new_tokens["refresh_token"]
        oauth["expiresAt"] = new_now_ms + (expires_in * 1000)
        creds["claudeAiOauth"] = oauth
        updated_json = json.dumps(creds)

        # Persist refreshed tokens to DB so future tasks use them
        try:
            from shared.config import get_settings
            from shared.credential_store import CredentialStore
            from shared.database import get_session_factory

            settings = get_settings()
            if settings.credential_encryption_key:
                store = CredentialStore(settings.credential_encryption_key)
                factory = get_session_factory()
                async with factory() as session:
                    await store.set(
                        session, user_id, "claude_code", "credentials_json",
                        updated_json,
                    )
                logger.info("proactive_token_refresh_persisted", user_id=user_id)
        except Exception as e:
            logger.warning("proactive_token_refresh_persist_failed", error=str(e))

        logger.info("proactive_token_refresh_success", user_id=user_id)
        return updated_json

    except Exception as e:
        logger.warning("proactive_token_refresh_error", user_id=user_id, error=str(e))
        return credentials_json


# ---------------------------------------------------------------------------
# Task data model
# ---------------------------------------------------------------------------
@dataclass
class Task:
    id: str
    prompt: str
    repo_url: str | None = None
    branch: str | None = None
    source_branch: str | None = None
    workspace: str = ""
    status: str = "queued"  # queued | running | completed | failed | timed_out | cancelled | awaiting_input
    mode: str = "execute"  # "execute" or "plan"
    auto_push: bool = False  # automatically push branch to remote after successful completion
    parent_task_id: str | None = None  # links tasks in a planning chain (points to chain root)
    group_id: str | None = None  # groups related tasks (e.g. project workflow phases)
    continue_session: bool = False  # whether to use --continue for CLI session resumption
    user_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    heartbeat: datetime | None = None
    result: dict | None = None
    error: str | None = None
    _asyncio_task: asyncio.Task | None = field(default=None, repr=False)

    # Context tracking (updated live during streaming)
    peak_context_tokens: int = 0
    latest_context_tokens: int = 0
    num_compactions: int = 0
    num_turns_tracked: int = 0
    num_continuations: int = 0
    context_model: str | None = None

    @property
    def log_file(self) -> str:
        return os.path.join(self.workspace, f"task_{self.id}.log")

    @property
    def meta_file(self) -> str:
        return os.path.join(self.workspace, f"task_meta_{self.id}.json")

    @property
    def container_name(self) -> str:
        """Get the Docker container name for this task.

        The container name includes the continuation count to handle
        auto-continuations that spawn new containers.
        """
        return f"claude-task-{self.id}-{self.num_continuations}"

    def to_dict(self) -> dict:
        return {
            "task_id": self.id,
            "prompt": self.prompt,
            "repo_url": self.repo_url,
            "branch": self.branch,
            "source_branch": self.source_branch,
            "workspace": self.workspace,
            "log_file": self.log_file,
            "container_name": self.container_name,
            "status": self.status,
            "mode": self.mode,
            "auto_push": self.auto_push,
            "parent_task_id": self.parent_task_id,
            "group_id": self.group_id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "heartbeat": self.heartbeat.isoformat() if self.heartbeat else None,
            "elapsed_seconds": self._elapsed(),
            "result": self.result,
            "error": self.error,
            "context_tracking": {
                "peak_context_tokens": self.peak_context_tokens,
                "latest_context_tokens": self.latest_context_tokens,
                "num_compactions": self.num_compactions,
                "num_turns": self.num_turns_tracked,
                "num_continuations": self.num_continuations,
                "context_model": self.context_model,
            },
        }

    def save(self) -> None:
        """Persist task metadata to disk so it survives restarts."""
        try:
            with open(self.meta_file, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        except OSError:
            pass

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        """Reconstruct a Task from a persisted metadata dict."""
        def _parse_dt(val: str | None) -> datetime | None:
            if not val:
                return None
            return datetime.fromisoformat(val)

        ct = data.get("context_tracking", {})
        return cls(
            id=data["task_id"],
            prompt=data.get("prompt", ""),
            repo_url=data.get("repo_url"),
            branch=data.get("branch"),
            source_branch=data.get("source_branch"),
            workspace=data.get("workspace", ""),
            status=data.get("status", "unknown"),
            mode=data.get("mode", "execute"),
            auto_push=data.get("auto_push", False),
            parent_task_id=data.get("parent_task_id"),
            group_id=data.get("group_id"),
            user_id=data.get("user_id"),
            created_at=_parse_dt(data.get("created_at")) or datetime.now(timezone.utc),
            started_at=_parse_dt(data.get("started_at")),
            completed_at=_parse_dt(data.get("completed_at")),
            result=data.get("result"),
            error=data.get("error"),
            peak_context_tokens=ct.get("peak_context_tokens", 0),
            latest_context_tokens=ct.get("latest_context_tokens", 0),
            num_compactions=ct.get("num_compactions", 0),
            num_turns_tracked=ct.get("num_turns", 0),
            num_continuations=ct.get("num_continuations", 0),
            context_model=ct.get("context_model"),
        )

    def _elapsed(self) -> float | None:
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now(timezone.utc)
        return round((end - self.started_at).total_seconds(), 1)


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------
class ClaudeCodeTools:
    """Tool implementations for Claude Code task execution."""

    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}
        self._worker_network: str = WORKER_NETWORK
        os.makedirs(TASK_BASE_DIR, exist_ok=True)
        self._load_persisted_tasks()
        if not TASK_VOLUME:
            logger.warning(
                "CLAUDE_TASK_VOLUME not set — worker containers need the "
                "absolute host path to the task directory for bind mounts"
            )

    async def async_init(self) -> None:
        """Resolve Docker network names (must be called after __init__)."""
        self._worker_network = await _resolve_network_name(WORKER_NETWORK)
        logger.info("resolved_worker_network", network=self._worker_network)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_persisted_tasks(self) -> None:
        """Reload task metadata from disk on startup.

        Scans for ``task_meta_<id>.json`` files (current format) and the
        legacy ``task_meta.json`` (old format) within each workspace
        directory.
        """
        loaded = 0
        for entry in os.scandir(TASK_BASE_DIR):
            if not entry.is_dir():
                continue

            # Collect all meta files: new per-task format + legacy single file
            meta_files: list[str] = []
            try:
                for f in os.scandir(entry.path):
                    if f.is_file() and f.name.startswith("task_meta") and f.name.endswith(".json"):
                        meta_files.append(f.path)
            except OSError:
                continue

            # Fallback: legacy task_meta.json
            legacy = os.path.join(entry.path, TASK_META_FILE)
            if not meta_files and os.path.isfile(legacy):
                meta_files.append(legacy)

            for meta_path in meta_files:
                try:
                    with open(meta_path) as fh:
                        data = json.load(fh)
                    task = Task.from_dict(data)
                    if task.id in self.tasks:
                        continue
                    # Tasks that were running when we crashed are now dead
                    if task.status in ("queued", "running"):
                        task.status = "failed"
                        task.error = task.error or "Interrupted by module restart"
                        task.completed_at = task.completed_at or datetime.now(timezone.utc)
                        task.save()
                    self.tasks[task.id] = task
                    loaded += 1
                except Exception as exc:
                    logger.warning("skip_persisted_task", path=meta_path, error=str(exc))
        if loaded:
            logger.info("loaded_persisted_tasks", count=loaded)

    # ------------------------------------------------------------------
    # Ownership helper
    # ------------------------------------------------------------------

    def _get_task(self, task_id: str, user_id: str | None = None) -> Task:
        """Look up a task, always enforcing ownership when user_id is provided."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        if user_id and task.user_id != user_id:
            raise ValueError(f"Task not found: {task_id}")
        return task

    def _count_user_workspaces(self, user_id: str) -> int:
        """Count unique workspaces owned by a user.

        Task chains (multiple tasks sharing the same workspace via parent_task_id)
        count as a single workspace.
        """
        user_tasks = [t for t in self.tasks.values() if t.user_id == user_id]

        # Group by chain root to count unique workspaces
        unique_chain_roots = set()
        for task in user_tasks:
            chain_root = task.parent_task_id or task.id
            unique_chain_roots.add(chain_root)

        return len(unique_chain_roots)

    # ------------------------------------------------------------------
    # Public tools (called by orchestrator)
    # ------------------------------------------------------------------

    async def run_task(
        self,
        prompt: str,
        repo_url: str | None = None,
        branch: str | None = None,
        source_branch: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        mode: str = "execute",
        auto_push: bool = False,
        group_id: str | None = None,
        user_id: str | None = None,
        user_credentials: dict[str, dict[str, str]] | None = None,
    ) -> dict:
        """Submit a coding task. Returns immediately with task_id.

        When ``mode="plan"``, the prompt is augmented to instruct Claude to
        produce a plan without implementing.  The task will finish with
        ``awaiting_input`` status so the user can review before proceeding.
        """
        if mode not in ("execute", "plan"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'execute' or 'plan'.")

        # Check workspace limit for user
        if user_id:
            current_workspace_count = self._count_user_workspaces(user_id)
            if current_workspace_count >= MAX_WORKSPACES_PER_USER:
                raise ValueError(
                    f"Workspace limit reached. You have {current_workspace_count} active workspaces "
                    f"(limit: {MAX_WORKSPACES_PER_USER}). Please delete old workspaces using "
                    f"claude_code.delete_workspace or claude_code.delete_all_workspaces before creating new ones."
                )

        task_id = uuid.uuid4().hex[:12]
        workspace = os.path.join(TASK_BASE_DIR, task_id)
        os.makedirs(workspace, exist_ok=True)

        effective_prompt = prompt
        if mode == "plan":
            effective_prompt = (
                "Create a detailed implementation plan for the following task. "
                "Do NOT implement anything yet. Write the complete plan to PLAN.md "
                "in the repository root and commit it. "
                "Analyze the codebase, identify files to modify, and describe "
                "your approach step by step.\n\n"
                f"Task: {prompt}"
            )

        task = Task(
            id=task_id, prompt=prompt, repo_url=repo_url, branch=branch,
            source_branch=source_branch, workspace=workspace, mode=mode,
            auto_push=auto_push, group_id=group_id, user_id=user_id,
        )
        self.tasks[task_id] = task
        task.save()

        # Fire-and-forget background execution
        task._asyncio_task = asyncio.create_task(
            self._execute_task(
                task, timeout, effective_prompt=effective_prompt,
                user_credentials=user_credentials, user_id=user_id,
            )
        )

        logger.info("task_submitted", task_id=task_id, repo_url=repo_url, mode=mode)
        return {
            "task_id": task_id,
            "status": "queued",
            "mode": mode,
            "workspace": workspace,
            "log_file": task.log_file,
            "message": (
                f"Task submitted (mode={mode}). Use claude_code.task_logs with "
                f"task_id='{task_id}' to stream live output. "
                f"Use claude_code.task_status to check completion."
            ),
        }

    async def continue_task(
        self,
        task_id: str,
        prompt: str,
        timeout: int = DEFAULT_TIMEOUT,
        mode: str | None = None,
        auto_push: bool | None = None,
        user_id: str | None = None,
        user_credentials: dict[str, dict[str, str]] | None = None,
    ) -> dict:
        """Run a follow-up prompt against an existing task's workspace.

        This lets you make edits to a project that was created by a previous
        ``run_task`` call.  The original workspace is reused so all existing
        files are visible to Claude Code.

        Uses ``--continue`` to resume the Claude CLI session, preserving full
        conversation context from previous runs in the same workspace.

        ``mode`` can be set to override the parent task's mode (e.g. switch
        from ``"plan"`` to ``"execute"`` when approving a plan).
        """
        original = self._get_task(task_id, user_id)
        if original.status in ("queued", "running"):
            raise ValueError(
                f"Task {task_id} is still {original.status} — wait for it "
                f"to finish or cancel it before continuing."
            )
        if not os.path.isdir(original.workspace):
            raise ValueError(
                f"Workspace no longer exists: {original.workspace}"
            )

        # Determine chain root for linking
        chain_root = original.parent_task_id or original.id
        effective_mode = mode if mode else original.mode
        effective_auto_push = auto_push if auto_push is not None else original.auto_push

        # Create a new task that shares the original workspace
        new_id = uuid.uuid4().hex[:12]
        new_workspace = original.workspace  # reuse existing project dir

        task = Task(
            id=new_id,
            prompt=prompt,
            repo_url=original.repo_url,
            branch=original.branch,
            workspace=new_workspace,
            mode=effective_mode,
            auto_push=effective_auto_push,
            parent_task_id=chain_root,
            group_id=original.group_id,
            continue_session=True,
            user_id=user_id,
        )
        self.tasks[new_id] = task

        # Persist metadata under the shared workspace with a task-specific name
        # so it doesn't clobber the original task_meta.json
        task.save()

        # Build context-enriched prompt with workspace file listing
        tree = self._workspace_tree(new_workspace)
        enriched_prompt = (
            f"Workspace files from previous tasks in this chain:\n"
            f"{tree}\n\n"
            f"{prompt}"
        )

        # Fire-and-forget background execution (no repo clone — workspace
        # already has the project files)
        task._asyncio_task = asyncio.create_task(
            self._execute_task(
                task, timeout, effective_prompt=enriched_prompt,
                user_credentials=user_credentials, user_id=user_id,
            )
        )

        logger.info(
            "continue_task_submitted",
            new_task_id=new_id,
            original_task_id=task_id,
            workspace=new_workspace,
            mode=effective_mode,
            continue_session=True,
        )
        return {
            "task_id": new_id,
            "original_task_id": task_id,
            "status": "queued",
            "mode": effective_mode,
            "workspace": new_workspace,
            "log_file": task.log_file,
            "message": (
                f"Continuation task submitted against workspace from task "
                f"'{task_id}'. Use claude_code.task_status with "
                f"task_id='{new_id}' to check progress."
            ),
        }

    async def task_status(self, task_id: str, user_id: str | None = None) -> dict:
        """Return the current status of a task."""
        task = self._get_task(task_id, user_id)
        return task.to_dict()

    async def task_logs(
        self,
        task_id: str,
        tail: int = LOG_TAIL_DEFAULT,
        offset: int = 0,
        user_id: str | None = None,
    ) -> dict:
        """Return recent lines from a task's live log file."""
        task = self._get_task(task_id, user_id)

        log_path = task.log_file
        if not os.path.exists(log_path):
            return {
                "task_id": task_id,
                "status": task.status,
                "lines": [],
                "total_lines": 0,
                "message": "No log output yet.",
            }

        with open(log_path) as f:
            all_lines = f.readlines()

        total = len(all_lines)
        if offset:
            selected = all_lines[offset : offset + tail]
        else:
            # Default: return the last `tail` lines
            selected = all_lines[-tail:] if tail < total else all_lines

        return {
            "task_id": task_id,
            "status": task.status,
            "log_file": log_path,
            "total_lines": total,
            "showing_from": max(0, total - tail) if not offset else offset,
            "lines": [l.rstrip("\n") for l in selected],
        }

    async def cancel_task(self, task_id: str, user_id: str | None = None) -> dict:
        """Cancel a running or queued task by killing its Docker container."""
        task = self._get_task(task_id, user_id)

        if task.status in ("completed", "failed", "timed_out"):
            return {
                "task_id": task_id,
                "status": task.status,
                "message": f"Task already {task.status}, nothing to cancel.",
            }

        # Cancel the asyncio task (stops streaming, triggers finally block)
        if task._asyncio_task and not task._asyncio_task.done():
            task._asyncio_task.cancel()

        # Kill containers for all possible continuation numbers
        for i in range(MAX_CONTINUATIONS + 1):
            await self._kill_container(f"claude-task-{task.id}-{i}")

        task.status = "failed"
        task.error = "Cancelled by user"
        task.completed_at = datetime.now(timezone.utc)
        task.save()

        logger.info("task_cancelled", task_id=task_id)
        return {
            "task_id": task_id,
            "status": "failed",
            "message": "Task has been cancelled.",
        }

    async def list_tasks(
        self,
        status_filter: str | None = None,
        latest_per_chain: bool = False,
        user_id: str | None = None,
    ) -> dict:
        """List tasks for the given user, optionally filtered by status."""
        if not user_id:
            return {"tasks": [], "total": 0}
        tasks = [t for t in self.tasks.values() if t.user_id == user_id]
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]

        if latest_per_chain:
            # Group by chain root, keep only the most recent task per chain
            chains: dict[str, Task] = {}
            for t in tasks:
                chain_key = t.parent_task_id or t.id
                existing = chains.get(chain_key)
                if existing is None or t.created_at > existing.created_at:
                    chains[chain_key] = t
            tasks = list(chains.values())

        return {
            "tasks": [t.to_dict() for t in tasks],
            "total": len(tasks),
        }

    async def delete_workspace(self, task_id: str, user_id: str | None = None) -> dict:
        """Delete a task's workspace directory and remove all tasks in the chain from memory."""
        task = self._get_task(task_id, user_id)

        if task.status in ("queued", "running"):
            raise ValueError(f"Task {task_id} is still {task.status} — cancel it first.")

        # Find all tasks sharing this workspace (chain siblings)
        workspace = task.workspace
        chain_root = task.parent_task_id or task.id
        related_ids = [
            t.id for t in self.tasks.values()
            if t.workspace == workspace or t.id == chain_root or t.parent_task_id == chain_root
        ]

        # Cancel any that are still running
        for tid in related_ids:
            t = self.tasks.get(tid)
            if t and t.status in ("queued", "running"):
                if t._asyncio_task and not t._asyncio_task.done():
                    t._asyncio_task.cancel()
                container_name = f"claude-task-{t.id}"
                await self._kill_container(container_name)

        # Remove workspace directory
        deleted_dir = False
        if workspace and os.path.isdir(workspace):
            shutil.rmtree(workspace, ignore_errors=True)
            deleted_dir = True

        # Remove from in-memory registry
        for tid in related_ids:
            self.tasks.pop(tid, None)

        logger.info("workspace_deleted", task_id=task_id, workspace=workspace, related_tasks=len(related_ids))
        return {
            "task_id": task_id,
            "workspace": workspace,
            "deleted_directory": deleted_dir,
            "removed_tasks": related_ids,
            "message": f"Deleted workspace and {len(related_ids)} associated task(s).",
        }

    async def get_task_chain(self, task_id: str, user_id: str | None = None) -> dict:
        """Return all tasks in the same chain, sorted chronologically.

        Matches tasks by parent_task_id linkage, shared workspace, or
        shared group_id (e.g. project workflow phases).
        """
        root_task = self._get_task(task_id, user_id)

        chain_root = root_task.parent_task_id or root_task.id
        workspace = root_task.workspace
        group_id = root_task.group_id

        chain = [
            t.to_dict() for t in self.tasks.values()
            if t.id == chain_root
            or t.parent_task_id == chain_root
            or (workspace and t.workspace == workspace)
            or (group_id and t.group_id == group_id)
        ]
        chain.sort(key=lambda t: t["created_at"])

        return {"chain_root": chain_root, "tasks": chain, "total": len(chain)}

    async def delete_all_workspaces(self, user_id: str | None = None) -> dict:
        """Delete all workspaces and tasks for a user.

        This is a bulk cleanup operation that permanently removes all workspace
        directories and associated task metadata for the specified user.
        """
        if not user_id:
            raise ValueError("user_id is required for delete_all_workspaces (safety check)")

        # Get all tasks for this user
        user_tasks = [t for t in self.tasks.values() if t.user_id == user_id]

        if not user_tasks:
            return {
                "deleted_workspaces": 0,
                "deleted_tasks": 0,
                "message": "No workspaces found for this user.",
            }

        # Group by workspace using chain root to avoid counting duplicates
        workspaces: dict[str, dict] = {}
        for task in user_tasks:
            chain_root = task.parent_task_id or task.id
            if chain_root not in workspaces:
                workspaces[chain_root] = {
                    "workspace": task.workspace,
                    "task_ids": [],
                }
            workspaces[chain_root]["task_ids"].append(task.id)

        # Delete each workspace
        deleted_workspaces = 0
        deleted_tasks = 0

        for chain_root, info in workspaces.items():
            # Cancel any running tasks first
            for tid in info["task_ids"]:
                t = self.tasks.get(tid)
                if t and t.status in ("queued", "running"):
                    if t._asyncio_task and not t._asyncio_task.done():
                        t._asyncio_task.cancel()
                    container_name = f"claude-task-{t.id}"
                    await self._kill_container(container_name)

            # Delete workspace directory
            if info["workspace"] and os.path.isdir(info["workspace"]):
                shutil.rmtree(info["workspace"], ignore_errors=True)
                deleted_workspaces += 1

            # Remove tasks from in-memory registry
            for tid in info["task_ids"]:
                self.tasks.pop(tid, None)
                deleted_tasks += 1

        logger.info(
            "all_workspaces_deleted",
            user_id=user_id,
            workspaces=deleted_workspaces,
            tasks=deleted_tasks,
        )

        return {
            "deleted_workspaces": deleted_workspaces,
            "deleted_tasks": deleted_tasks,
            "message": f"Deleted {deleted_workspaces} workspace(s) and {deleted_tasks} task(s).",
        }

    # ------------------------------------------------------------------
    # Workspace helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _workspace_tree(workspace: str, max_files: int = 200) -> str:
        """Build a concise file tree string for a workspace directory."""
        skip = {".git", ".claude_sessions", "node_modules", "__pycache__", ".venv"}
        lines: list[str] = []
        count = 0

        for root, dirs, files in os.walk(workspace):
            # Prune skipped directories
            dirs[:] = sorted(d for d in dirs if d not in skip)
            rel = os.path.relpath(root, workspace)
            depth = 0 if rel == "." else rel.count(os.sep) + 1

            # Skip internal task files at workspace root
            if rel == ".":
                files = [
                    f for f in files
                    if not (f.startswith("task_meta") and f.endswith(".json"))
                    and not (f.startswith("task_") and f.endswith(".log"))
                ]

            for fname in sorted(files):
                if count >= max_files:
                    lines.append(f"  ... and more files (truncated at {max_files})")
                    return "\n".join(lines)
                path = f"{rel}/{fname}" if rel != "." else fname
                lines.append(f"  {path}")
                count += 1

        return "\n".join(lines) if lines else "  (empty workspace)"

    @staticmethod
    def _read_plan_file(workspace: str) -> str | None:
        """Read a plan file from the workspace, checking common name variants.

        Claude may write PLAN.md, plan.md, or other casing.  We do a
        case-insensitive scan of the workspace root for any ``plan*.md``
        file and return the largest match (most likely the full plan).
        """
        candidates: list[tuple[int, str]] = []
        try:
            for entry in os.scandir(workspace):
                if not entry.is_file():
                    continue
                lower = entry.name.lower()
                if lower.startswith("plan") and lower.endswith(".md"):
                    try:
                        size = entry.stat().st_size
                        candidates.append((size, entry.path))
                    except OSError:
                        continue
        except OSError:
            return None

        if not candidates:
            return None

        # Pick the largest plan file (most likely the full plan)
        candidates.sort(reverse=True)
        try:
            with open(candidates[0][1]) as f:
                content = f.read()
            if content.strip():
                return content
        except OSError:
            pass
        return None

    # ------------------------------------------------------------------
    # Workspace browsing
    # ------------------------------------------------------------------

    async def browse_workspace(
        self,
        task_id: str,
        path: str = "",
        user_id: str | None = None,
    ) -> dict:
        """List files and directories in a task's workspace."""
        task = self._get_task(task_id, user_id)

        base = os.path.realpath(task.workspace)
        target = os.path.realpath(os.path.join(base, path))

        # Prevent path traversal outside workspace
        if not target.startswith(base):
            raise ValueError("Path traversal not allowed")
        if not os.path.isdir(target):
            raise ValueError(f"Not a directory: {path}")

        skip = {".git", ".claude_sessions"}
        entries = []
        for entry in sorted(os.scandir(target), key=lambda e: (not e.is_dir(), e.name)):
            if entry.name in skip:
                continue
            # Skip internal task metadata / log files at workspace root
            if target == base and (
                entry.name.startswith("task_meta") and entry.name.endswith(".json")
                or entry.name.startswith("task_") and entry.name.endswith(".log")
            ):
                continue
            try:
                stat = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            entries.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": stat.st_size if entry.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })

        return {
            "task_id": task_id,
            "path": path or "/",
            "workspace": task.workspace,
            "entries": entries,
            "total": len(entries),
        }

    async def read_workspace_file(
        self,
        task_id: str,
        path: str,
        user_id: str | None = None,
    ) -> dict:
        """Read a file from a task's workspace."""
        task = self._get_task(task_id, user_id)

        base = os.path.realpath(task.workspace)
        target = os.path.realpath(os.path.join(base, path))

        if not target.startswith(base):
            raise ValueError("Path traversal not allowed")
        if not os.path.isfile(target):
            raise ValueError(f"Not a file: {path}")

        stat = os.stat(target)

        try:
            with open(target, encoding="utf-8") as f:
                content = f.read(MAX_FILE_READ)
            truncated = stat.st_size > MAX_FILE_READ
        except UnicodeDecodeError:
            return {
                "task_id": task_id,
                "path": path,
                "size": stat.st_size,
                "binary": True,
                "content": None,
                "message": "Binary file — cannot display content",
            }

        return {
            "task_id": task_id,
            "path": path,
            "size": stat.st_size,
            "binary": False,
            "content": content,
            "truncated": truncated,
        }

    async def get_task_container(
        self,
        task_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Get the Docker container information for a task.

        Returns the container ID, name, workspace path, and running status.
        The container ID can be used to attach a terminal session.
        """
        task = self._get_task(task_id, user_id)
        container_name = task.container_name

        # Check if container exists and get its ID and status
        try:
            # Use docker inspect to get container details
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect",
                "--format", "{{.Id}}|{{.State.Status}}",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                # Container doesn't exist
                return {
                    "task_id": task_id,
                    "container_name": container_name,
                    "container_id": None,
                    "workspace": task.workspace,
                    "status": "not_found",
                    "message": "Container not found. It may have been removed or task is not running.",
                }

            # Parse container ID and status
            output = stdout.decode().strip()
            container_id, container_status = output.split("|")

            # Map Docker status to our status
            if container_status == "running":
                status = "running"
            elif container_status in ("exited", "dead"):
                status = "stopped"
            else:
                status = container_status

            return {
                "task_id": task_id,
                "container_name": container_name,
                "container_id": container_id,
                "workspace": task.workspace,
                "status": status,
                "task_status": task.status,
            }

        except Exception as e:
            logger.error(
                "get_task_container_error",
                task_id=task_id,
                container_name=container_name,
                error=str(e),
            )
            return {
                "task_id": task_id,
                "container_name": container_name,
                "container_id": None,
                "workspace": task.workspace,
                "status": "error",
                "message": f"Error checking container: {e}",
            }

    async def create_terminal_container(
        self, task_id: str, user_id: str | None = None
    ) -> dict:
        """Create or get a persistent terminal container for workspace access.

        Terminal containers are lightweight Alpine Linux containers that provide
        shell access to workspaces after task execution completes. They share
        the same workspace volume as the task container but use minimal resources.

        Container specifications:
        - Image: alpine:latest with bash and git
        - Command: tail -f /dev/null (keeps container running)
        - Name: claude-terminal-{task_id}
        - Volume: Same workspace mount as task container
        - Working dir: Task workspace path
        - Labels: user_id, task_id, type=terminal, created_at

        Returns:
            {
                "container_id": str,
                "container_name": str,
                "workspace": str,
                "status": "created" | "existing" | "restarted",
                "message": str
            }
        """
        task = self._get_task(task_id, user_id)
        container_name = f"claude-terminal-{task_id}"

        # Check if terminal container already exists
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "inspect",
                "--format", "{{.Id}}|{{.State.Status}}",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                # Container exists
                output = stdout.decode().strip()
                container_id, container_status = output.split("|")

                if container_status == "running":
                    # Container already running, return it
                    logger.info(
                        "terminal_container_exists",
                        task_id=task_id,
                        container_id=container_id,
                    )
                    return {
                        "container_id": container_id,
                        "container_name": container_name,
                        "workspace": task.workspace,
                        "status": "existing",
                        "message": "Terminal container already running",
                    }
                else:
                    # Container exists but stopped, remove and recreate
                    logger.info(
                        "terminal_container_stopped",
                        task_id=task_id,
                        container_id=container_id,
                        status=container_status,
                    )
                    await self._remove_container(container_name)

        except Exception as e:
            logger.debug(
                "terminal_container_check_error",
                task_id=task_id,
                error=str(e),
            )
            # Container doesn't exist, continue to create

        # Create new terminal container
        logger.info("creating_terminal_container", task_id=task_id)

        # Mount only this task's workspace — NOT the entire TASK_VOLUME.
        host_workspace = os.path.join(TASK_VOLUME, task.id)
        container_workspace = os.path.join(TASK_BASE_DIR, task.id)

        cmd = [
            "docker", "run", "-d",  # Detached, NOT --rm
            "--name", container_name,
            "--network=none",
            "-v", f"{host_workspace}:{container_workspace}",
            "-w", task.workspace,
            "-e", "TERM=xterm-256color",
            "--label", f"user_id={user_id or 'unknown'}",
            "--label", f"task_id={task_id}",
            "--label", "type=terminal",
            "--label", f"created_at={int(time.time())}",
            "alpine:latest",
            "sh", "-c", "apk add --no-cache bash git && tail -f /dev/null",
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(
                    "terminal_container_create_failed",
                    task_id=task_id,
                    error=error_msg,
                )
                raise RuntimeError(f"Failed to create terminal container: {error_msg}")

            container_id = stdout.decode().strip()

            # Wait for bash to be installed (check up to 10 times with 1s delay)
            logger.info(
                "waiting_for_bash_installation",
                task_id=task_id,
                container_id=container_id,
            )

            for attempt in range(10):
                await asyncio.sleep(1)

                # Check if bash is available
                check_proc = await asyncio.create_subprocess_exec(
                    "docker", "exec", container_name, "which", "bash",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await check_proc.communicate()

                if check_proc.returncode == 0:
                    logger.info(
                        "bash_installation_complete",
                        task_id=task_id,
                        attempt=attempt + 1,
                    )
                    break
            else:
                logger.warning(
                    "bash_installation_timeout",
                    task_id=task_id,
                    message="Bash may not be fully installed yet",
                )

            logger.info(
                "terminal_container_created",
                task_id=task_id,
                container_id=container_id,
            )

            return {
                "container_id": container_id,
                "container_name": container_name,
                "workspace": task.workspace,
                "status": "created",
                "message": "Terminal container created successfully",
            }

        except Exception as e:
            logger.error(
                "terminal_container_creation_error",
                task_id=task_id,
                error=str(e),
            )
            raise

    async def stop_terminal_container(
        self, task_id: str, user_id: str | None = None
    ) -> dict:
        """Stop and remove a terminal container.

        Returns:
            {
                "task_id": str,
                "container_name": str,
                "removed": bool,
                "message": str
            }
        """
        task = self._get_task(task_id, user_id)
        container_name = f"claude-terminal-{task_id}"

        try:
            await self._remove_container(container_name)
            logger.info("terminal_container_removed", task_id=task_id)

            return {
                "task_id": task_id,
                "container_name": container_name,
                "removed": True,
                "message": "Terminal container stopped and removed",
            }

        except Exception as e:
            logger.warning(
                "terminal_container_stop_error",
                task_id=task_id,
                error=str(e),
            )
            return {
                "task_id": task_id,
                "container_name": container_name,
                "removed": False,
                "message": f"Container may not exist or already removed: {e}",
            }

    async def list_terminal_containers(
        self, user_id: str | None = None
    ) -> dict:
        """List all terminal containers for a user.

        Returns:
            {
                "containers": [
                    {
                        "task_id": str,
                        "container_id": str,
                        "container_name": str,
                        "workspace": str,
                        "status": str,
                        "created_at": int,
                        "idle_seconds": int
                    }
                ],
                "total": int
            }
        """
        try:
            # Find all terminal containers
            user_filter = f"--filter=label=user_id={user_id}" if user_id else ""
            cmd = [
                "docker", "ps", "-a",
                "--filter", "label=type=terminal",
            ]
            if user_filter:
                cmd.append(user_filter)
            cmd.extend(["--format", "{{.Names}}|{{.ID}}|{{.Status}}|{{.Label \"created_at\"}}|{{.Label \"task_id\"}}"])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error("list_terminal_containers_error", error=stderr.decode())
                return {"containers": [], "total": 0}

            containers = []
            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|")
                if len(parts) != 5:
                    continue

                name, container_id, status, created_at_str, task_id = parts

                # Parse status
                if "Up" in status:
                    container_status = "running"
                elif "Exited" in status:
                    container_status = "stopped"
                else:
                    container_status = "unknown"

                # Calculate idle time
                try:
                    created_at = int(created_at_str)
                    idle_seconds = int(time.time()) - created_at
                except ValueError:
                    created_at = 0
                    idle_seconds = 0

                # Get workspace from task
                workspace = ""
                try:
                    task = self.tasks.get(task_id)
                    if task:
                        workspace = task.workspace
                except Exception:
                    pass

                containers.append({
                    "task_id": task_id,
                    "container_id": container_id,
                    "container_name": name,
                    "workspace": workspace,
                    "status": container_status,
                    "created_at": created_at,
                    "idle_seconds": idle_seconds,
                })

            return {
                "containers": containers,
                "total": len(containers),
            }

        except Exception as e:
            logger.error("list_terminal_containers_exception", error=str(e))
            return {"containers": [], "total": 0}

    async def cleanup_idle_terminal_containers(self) -> dict:
        """Remove terminal containers idle for >24 hours.

        Cleanup criteria:
        - Container has label type=terminal
        - Created >24 hours ago (86400 seconds)
        - Not currently attached to any terminal session

        Returns:
            {
                "removed": [container_names],
                "count": int,
                "errors": [error_messages]
            }
        """
        IDLE_THRESHOLD = 24 * 3600  # 24 hours in seconds
        removed = []
        errors = []

        try:
            # List all terminal containers
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-a",
                "--filter", "label=type=terminal",
                "--format", "{{.Names}}|{{.Label \"created_at\"}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                errors.append(f"Failed to list containers: {stderr.decode()}")
                return {"removed": removed, "count": 0, "errors": errors}

            now = int(time.time())
            for line in stdout.decode().strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|")
                if len(parts) != 2:
                    continue

                container_name, created_at_str = parts

                try:
                    created_at = int(created_at_str)
                    idle_seconds = now - created_at

                    if idle_seconds > IDLE_THRESHOLD:
                        logger.info(
                            "cleaning_idle_terminal_container",
                            container=container_name,
                            idle_hours=idle_seconds / 3600,
                        )

                        try:
                            await self._remove_container(container_name)
                            removed.append(container_name)
                        except Exception as e:
                            error_msg = f"Failed to remove {container_name}: {e}"
                            errors.append(error_msg)
                            logger.warning("cleanup_remove_failed", error=error_msg)

                except ValueError:
                    errors.append(f"Invalid created_at for {container_name}")
                    continue

            logger.info(
                "terminal_cleanup_completed",
                removed=len(removed),
                errors=len(errors),
            )

            return {
                "removed": removed,
                "count": len(removed),
                "errors": errors,
            }

        except Exception as e:
            logger.error("cleanup_idle_containers_exception", error=str(e))
            errors.append(str(e))
            return {"removed": removed, "count": 0, "errors": errors}

    # ------------------------------------------------------------------
    # Background execution
    # ------------------------------------------------------------------

    async def _execute_task(
        self, task: Task, timeout: int, effective_prompt: str | None = None,
        user_credentials: dict[str, dict[str, str]] | None = None,
        user_id: str | None = None,
    ) -> None:
        """Background coroutine: run the Claude Code Docker container.

        Supports auto-continuation: when context usage exceeds the threshold,
        gracefully stops the container and restarts with a fresh CLI session
        on the same workspace.
        """
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        task.heartbeat = task.started_at
        task.save()

        # Prepare per-user credential mounts if provided
        user_mounts: dict[str, str] | None = None
        if user_credentials and user_id:
            try:
                user_mounts = await self._prepare_user_credentials(user_id, user_credentials)
            except Exception as e:
                logger.warning("user_credential_prep_failed", user_id=user_id, error=str(e))

        # effective_prompt allows run_task to augment the prompt (e.g. plan
        # mode instructions) while keeping the original prompt in task metadata.
        prompt_for_cli = effective_prompt or task.prompt

        # When auto_push is enabled, instruct Claude to commit and push with
        # descriptive messages.  The _auto_push_branch fallback will catch any
        # uncommitted/unpushed work if Claude doesn't handle it.
        if task.auto_push and task.repo_url:
            prompt_for_cli += (
                "\n\nIMPORTANT — Git workflow:"
                "\n- Commit your changes with descriptive commit messages as you work."
                "\n- When you are done, push your branch: git push -u origin HEAD"
                "\n- Do NOT leave uncommitted changes."
            )

        original_prompt = prompt_for_cli
        remaining_timeout = timeout
        heartbeat_handle: asyncio.Task | None = None

        try:
            heartbeat_handle = asyncio.create_task(self._heartbeat_loop(task))

            while True:  # continuation loop
                run_start = time.monotonic()
                exit_reason = await self._run_single_container(
                    task, remaining_timeout, prompt_for_cli, user_mounts,
                )
                run_elapsed = time.monotonic() - run_start
                remaining_timeout -= int(run_elapsed)

                if exit_reason != "context_threshold":
                    break

                # --- Auto-continuation ---
                if task.num_continuations >= MAX_CONTINUATIONS:
                    logger.warning(
                        "max_continuations_reached",
                        task_id=task.id,
                        num_continuations=task.num_continuations,
                    )
                    task.status = "completed"
                    if task.result is None:
                        task.result = {}
                    task.result["continuation_note"] = (
                        f"Reached maximum of {MAX_CONTINUATIONS} auto-continuations. "
                        f"Task stopped to prevent infinite loops."
                    )
                    break

                if remaining_timeout < 60:
                    logger.warning(
                        "continuation_timeout_exhausted",
                        task_id=task.id,
                        remaining=remaining_timeout,
                    )
                    task.status = "timed_out"
                    task.error = (
                        f"Context limit reached but insufficient time remaining "
                        f"for continuation ({remaining_timeout}s left)."
                    )
                    break

                task.num_continuations += 1
                logger.info(
                    "auto_continuation",
                    task_id=task.id,
                    num_continuations=task.num_continuations,
                    peak_context=task.peak_context_tokens,
                    remaining_timeout=remaining_timeout,
                )

                # Build continuation prompt (fresh session, NOT --continue)
                tree = self._workspace_tree(task.workspace)
                prompt_for_cli = (
                    f"You are continuing a coding task that was automatically restarted "
                    f"because the conversation context was getting full. This is continuation "
                    f"#{task.num_continuations} of {MAX_CONTINUATIONS} max.\n\n"
                    f"ORIGINAL TASK:\n{original_prompt}\n\n"
                    f"CURRENT WORKSPACE STATE:\n{tree}\n\n"
                    f"Review the workspace files and git log to understand what has already "
                    f"been done, then continue working on any remaining items from the "
                    f"original task. Do NOT redo work that is already complete."
                )
                task.save()

            # Auto-push on final successful exit
            if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input"):
                await self._auto_push_branch(task, user_mounts)

        except Exception as e:
            logger.error("task_execution_error", task_id=task.id, error=str(e))
            task.status = "failed"
            task.error = str(e)
        finally:
            task.completed_at = datetime.now(timezone.utc)
            task.save()
            if heartbeat_handle:
                heartbeat_handle.cancel()

            # Clean up decrypted credentials from disk — they should not
            # persist between tasks.  Workspace itself is kept for browsing.
            if user_id:
                creds_dir = os.path.join(USER_CREDS_DIR, user_id)
                try:
                    if os.path.isdir(creds_dir):
                        shutil.rmtree(creds_dir)
                        logger.info("user_credentials_cleaned", user_id=user_id)
                except Exception as cleanup_err:
                    logger.warning(
                        "user_credentials_cleanup_failed",
                        user_id=user_id,
                        error=str(cleanup_err),
                    )

            logger.info(
                "task_finished",
                task_id=task.id,
                status=task.status,
                elapsed=task._elapsed(),
                continuations=task.num_continuations,
            )

    async def _run_single_container(
        self, task: Task, timeout: int, prompt: str,
        user_mounts: dict[str, str] | None,
    ) -> str:
        """Run a single Docker container for the task.

        Returns the exit reason:
        - ``"completed"`` — container exited successfully
        - ``"failed"`` — container exited with error
        - ``"timed_out"`` — timeout exceeded
        - ``"context_threshold"`` — stopped due to context window filling up
        """
        container_name = f"claude-task-{task.id}-{task.num_continuations}"
        is_continuation = task.num_continuations > 0

        # For auto-continuations: fresh CLI session, no repo clone (workspace has files)
        # For continue_task calls (first run): preserve continue_session from original task
        run_task = Task(
            id=task.id,
            prompt=prompt,
            repo_url=task.repo_url if not is_continuation else None,
            branch=task.branch if not is_continuation else None,
            source_branch=task.source_branch if not is_continuation else None,
            workspace=task.workspace,
            continue_session=task.continue_session if not is_continuation else False,
            mode=task.mode,
            auto_push=False,  # only push on final exit
            user_id=task.user_id,
        )
        cmd = self._build_docker_cmd(run_task, container_name, prompt, user_mounts=user_mounts)
        logger.info(
            "container_starting",
            task_id=task.id,
            container=container_name,
            continuation=task.num_continuations,
        )
        logger.debug("task_docker_cmd", task_id=task.id, cmd=" ".join(cmd))

        stdout_buf: list[str] = []
        stderr_buf: list[str] = []
        context_threshold_event = asyncio.Event()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=1024 * 1024,
            )

            log_lock = asyncio.Lock()
            _prev_input_tokens = 0

            async def _stream_to_log(
                stream: asyncio.StreamReader,
                buf: list[str],
                prefix: str,
            ) -> None:
                """Read lines from a stream, write to log, parse context usage."""
                nonlocal _prev_input_tokens
                while True:
                    try:
                        line_bytes = await stream.readline()
                    except ValueError:
                        continue
                    if not line_bytes:
                        break
                    line = line_bytes.decode("utf-8", errors="replace")
                    buf.append(line)
                    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    log_line = f"[{ts}] [{prefix}] {line}"
                    try:
                        async with log_lock:
                            with open(task.log_file, "a") as f:
                                f.write(log_line)
                    except OSError:
                        pass

                    # Real-time context tracking from stdout JSON events
                    if prefix == "stdout":
                        try:
                            obj = json.loads(line.strip())
                            if obj.get("type") == "assistant":
                                msg = obj.get("message", {})
                                usage = msg.get("usage")
                                if usage:
                                    # Total context = uncached + cache_read + cache_creation
                                    # input_tokens alone is only the non-cached portion
                                    context_t = (
                                        usage.get("input_tokens", 0)
                                        + usage.get("cache_read_input_tokens", 0)
                                        + usage.get("cache_creation_input_tokens", 0)
                                    )
                                    if context_t > 0:
                                        task.num_turns_tracked += 1
                                        task.latest_context_tokens = context_t
                                        if context_t > task.peak_context_tokens:
                                            task.peak_context_tokens = context_t
                                        # Detect compaction: context drops >50K
                                        if _prev_input_tokens > 0 and (_prev_input_tokens - context_t) > 50_000:
                                            task.num_compactions += 1
                                            logger.info(
                                                "context_compaction_detected",
                                                task_id=task.id,
                                                prev=_prev_input_tokens,
                                                curr=context_t,
                                            )
                                        # Check threshold for auto-continuation
                                        if not context_threshold_event.is_set():
                                            model_limit = _get_model_context_limit(task.context_model)
                                            if context_t >= model_limit * CONTEXT_THRESHOLD_PCT:
                                                context_threshold_event.set()
                                                logger.warning(
                                                    "context_threshold_reached",
                                                    task_id=task.id,
                                                    context_tokens=context_t,
                                                    limit=model_limit,
                                                    pct=round(context_t / model_limit * 100, 1),
                                                )
                                        _prev_input_tokens = context_t
                                    if not task.context_model:
                                        task.context_model = msg.get("model")
                        except (json.JSONDecodeError, KeyError, TypeError):
                            pass

            # Monitor for context threshold — stops container gracefully
            async def _context_monitor() -> None:
                await context_threshold_event.wait()
                # Let the current turn finish before stopping
                await asyncio.sleep(5)
                logger.info("stopping_for_context_threshold", task_id=task.id)
                await self._stop_container(container_name, grace_seconds=15)

            monitor_handle = asyncio.create_task(_context_monitor())

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        _stream_to_log(proc.stdout, stdout_buf, "stdout"),
                        _stream_to_log(proc.stderr, stderr_buf, "stderr"),
                        proc.wait(),
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning("task_timeout", task_id=task.id, timeout=timeout)
                await self._stop_container(container_name, grace_seconds=15)
                task.status = "timed_out"
                task.error = (
                    f"Task timed out after {timeout}s. "
                    f"The workspace and any files written so far are preserved. "
                    f"Use claude_code.continue_task with task_id='{task.id}' "
                    f"to resume where it left off."
                )
                return "timed_out"
            finally:
                monitor_handle.cancel()

            stdout = "".join(stdout_buf)[:MAX_OUTPUT]
            stderr = "".join(stderr_buf)[:MAX_OUTPUT]

            # Check if we stopped due to context threshold
            if context_threshold_event.is_set() and proc.returncode in (143, -15, 137):
                # Parse partial output for token summary
                partial_result = self._parse_output(stdout)
                token_summary = self._compute_token_summary(partial_result, task)
                if task.result is None:
                    task.result = {}
                task.result.update(partial_result)
                if token_summary:
                    task.result["token_summary"] = token_summary

                # Write continuation marker to log
                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                try:
                    with open(task.log_file, "a") as f:
                        f.write(
                            f"[{ts}] [system] === AUTO-CONTINUATION "
                            f"#{task.num_continuations + 1} — context at "
                            f"{task.latest_context_tokens:,} tokens ===\n"
                        )
                except OSError:
                    pass

                return "context_threshold"

            if proc.returncode == 0:
                task.result = self._parse_output(stdout)
                token_summary = self._compute_token_summary(task.result, task)
                if token_summary:
                    task.result["token_summary"] = token_summary
                if task.mode == "plan":
                    task.status = "awaiting_input"
                    plan_content = self._read_plan_file(task.workspace)
                    if plan_content:
                        task.result["plan_content"] = plan_content
                    if "plan_content" not in (task.result or {}):
                        for obj in (task.result.get("json_output") or []):
                            if obj.get("type") == "result" and obj.get("result"):
                                task.result["plan_content"] = obj["result"]
                                break
                else:
                    task.status = "completed"
                return "completed"
            else:
                task.status = "failed"
                task.error = stderr or stdout or f"Process exited with code {proc.returncode}"
                task.result = {
                    "exit_code": proc.returncode,
                    "stdout": stdout[:5000],
                    "stderr": stderr[:5000],
                }
                logger.error(
                    "task_container_failed",
                    task_id=task.id,
                    exit_code=proc.returncode,
                    stderr=stderr[:2000],
                    stdout=stdout[:2000],
                )
                return "failed"

        finally:
            await self._remove_container(container_name)

    # ------------------------------------------------------------------
    # Per-user credential management
    # ------------------------------------------------------------------

    @staticmethod
    async def _prepare_user_credentials(
        user_id: str, user_credentials: dict[str, dict[str, str]],
    ) -> dict[str, str]:
        """Write decrypted per-user credentials to disk for Docker mounting.

        Creates directory structure under ``USER_CREDS_DIR/{user_id}/`` with:
        - ``.claude/.credentials.json`` — Claude CLI OAuth credentials
        - ``.ssh/id_ed25519`` — SSH private key
        - ``.gitconfig`` — Git author name/email config

        Returns a dict of mount-type → host path for use in _build_docker_cmd.
        File permissions are set restrictively (0600 for keys, 0700 for dirs).

        Proactively refreshes OAuth tokens if they expire within 30 minutes.
        """
        user_dir = os.path.join(USER_CREDS_DIR, user_id)
        os.makedirs(user_dir, exist_ok=True)
        mounts: dict[str, str] = {}

        # -- Claude CLI credentials (OAuth JSON) --
        claude_creds = user_credentials.get("claude_code", {})
        credentials_json = claude_creds.get("credentials_json", "")
        if credentials_json:
            # Proactively refresh if token is expiring soon
            credentials_json = await _maybe_refresh_credentials(
                user_id, credentials_json
            )
            claude_dir = os.path.join(user_dir, ".claude")
            os.makedirs(claude_dir, exist_ok=True)
            creds_file = os.path.join(claude_dir, ".credentials.json")
            with open(creds_file, "w") as f:
                f.write(credentials_json)
            os.chmod(creds_file, 0o600)
            # Host path: TASK_VOLUME maps to TASK_BASE_DIR, so derive host path
            host_claude_dir = os.path.join(
                TASK_VOLUME, ".user_creds", user_id, ".claude"
            )
            mounts["claude_auth"] = host_claude_dir

        # -- SSH private key --
        github_creds = user_credentials.get("github", {})
        ssh_key = github_creds.get("ssh_private_key", "")
        if ssh_key:
            ssh_dir = os.path.join(user_dir, ".ssh")
            os.makedirs(ssh_dir, exist_ok=True)
            os.chmod(ssh_dir, 0o700)
            key_file = os.path.join(ssh_dir, "id_ed25519")
            with open(key_file, "w") as f:
                f.write(ssh_key)
                if not ssh_key.endswith("\n"):
                    f.write("\n")
            os.chmod(key_file, 0o600)
            host_ssh_dir = os.path.join(
                TASK_VOLUME, ".user_creds", user_id, ".ssh"
            )
            mounts["ssh_key"] = host_ssh_dir

        # -- Git config (author name/email) --
        git_name = github_creds.get("git_author_name", "")
        git_email = github_creds.get("git_author_email", "")
        if git_name or git_email:
            lines = ["[user]"]
            if git_name:
                lines.append(f"    name = {git_name}")
            if git_email:
                lines.append(f"    email = {git_email}")
            gitconfig_file = os.path.join(user_dir, ".gitconfig")
            with open(gitconfig_file, "w") as f:
                f.write("\n".join(lines) + "\n")
            host_gitconfig = os.path.join(
                TASK_VOLUME, ".user_creds", user_id, ".gitconfig"
            )
            mounts["git_config"] = host_gitconfig
            # Store names for env var overrides too
            mounts["_git_author_name"] = git_name
            mounts["_git_author_email"] = git_email

        # -- GitHub token --
        gh_token = github_creds.get("github_token", "")
        if gh_token:
            mounts["_github_token"] = gh_token

        logger.info(
            "user_credentials_prepared",
            user_id=user_id,
            mount_keys=[k for k in mounts if not k.startswith("_")],
        )
        return mounts

    # ------------------------------------------------------------------
    # Docker helpers
    # ------------------------------------------------------------------

    def _build_docker_cmd(
        self, task: Task, container_name: str, prompt: str,
        user_mounts: dict[str, str] | None = None,
    ) -> list[str]:
        """Assemble the ``docker run`` argument list."""
        # Mount only this task's workspace — NOT the entire TASK_VOLUME.
        # This prevents cross-user workspace access.
        host_workspace = os.path.join(TASK_VOLUME, task.id)
        container_workspace = os.path.join(TASK_BASE_DIR, task.id)

        # Network isolation: tasks with repo_url need network for git;
        # all others run with no network access.
        network = self._worker_network if task.repo_url else "none"

        cmd: list[str] = [
            "docker", "run", "--rm", "--init",
            "--name", container_name,
            f"--network={network}",
            "-v", f"{host_workspace}:{container_workspace}",
            "-w", task.workspace,
            "-e", f"PROMPT={prompt}",
        ]

        if task.repo_url:
            cmd.extend(["-e", f"REPO_URL={task.repo_url}"])
        if task.source_branch:
            cmd.extend(["-e", f"SOURCE_BRANCH={task.source_branch}"])
        if task.branch:
            cmd.extend(["-e", f"BRANCH={task.branch}"])
        if task.continue_session:
            cmd.extend(["-e", "CONTINUE_SESSION=1"])

        # Mount credentials read-only at staging paths (entrypoint copies them).
        # Per-user mounts take priority over global env var paths.
        um = user_mounts or {}

        claude_auth = um.get("claude_auth") or CLAUDE_AUTH_PATH
        if claude_auth:
            cmd.extend(["-v", f"{claude_auth}:/tmp/.claude-ro:ro"])

        ssh_key = um.get("ssh_key") or SSH_KEY_PATH
        if ssh_key:
            cmd.extend(["-v", f"{ssh_key}:/tmp/.ssh-ro:ro"])

        git_config = um.get("git_config") or GIT_CONFIG_PATH
        if git_config:
            cmd.extend(["-v", f"{git_config}:/tmp/.gitconfig-ro:ro"])

        # GH CLI config (global only — no per-user equivalent yet)
        if GH_CONFIG_PATH:
            cmd.extend(["-v", f"{GH_CONFIG_PATH}:/tmp/.gh-ro:ro"])

        # Git identity — per-user overrides global bot identity
        git_author_name = um.get("_git_author_name") or CLAUDE_CODE_GIT_AUTHOR_NAME
        git_author_email = um.get("_git_author_email") or CLAUDE_CODE_GIT_AUTHOR_EMAIL
        cmd.extend([
            "-e", f"GIT_AUTHOR_NAME={git_author_name}",
            "-e", f"GIT_AUTHOR_EMAIL={git_author_email}",
            "-e", f"GIT_COMMITTER_NAME={git_author_name}",
            "-e", f"GIT_COMMITTER_EMAIL={git_author_email}",
        ])

        # Pass tokens — per-user GitHub token overrides global
        github_token = um.get("_github_token") or GITHUB_TOKEN
        if github_token:
            cmd.extend(["-e", f"GITHUB_TOKEN={github_token}"])

        cmd.extend([
            CLAUDE_CODE_IMAGE,
            "sh", "-c", self._entrypoint_script(),
        ])
        return cmd

    @staticmethod
    def _entrypoint_script() -> str:
        """Shell script executed inside the worker container.

        Environment variables used:
        - ``PROMPT``: The prompt to send to Claude Code CLI.
        - ``REPO_URL`` / ``SOURCE_BRANCH`` / ``BRANCH``: Optional git clone parameters.
        - ``CONTINUE_SESSION``: When set to ``1``, uses ``--continue`` to
          resume the most recent Claude CLI session in the workspace and
          restores persisted session data from ``.claude_sessions/``.
        """
        return (
            'set -e\n'
            'CLAUDE_HOME=/home/claude\n'
            '\n'
            '# --- Running as root: copy read-only credentials ---------------\n'
            'if [ -d /tmp/.claude-ro ]; then\n'
            '    cp -r /tmp/.claude-ro "$CLAUDE_HOME/.claude"\n'
            'fi\n'
            'if [ -d /tmp/.ssh-ro ]; then\n'
            '    cp -r /tmp/.ssh-ro "$CLAUDE_HOME/.ssh"\n'
            '    chmod 700 "$CLAUDE_HOME/.ssh"\n'
            '    chmod 600 "$CLAUDE_HOME/.ssh"/* 2>/dev/null || true\n'
            'fi\n'
            'if [ -d /tmp/.gh-ro ]; then\n'
            '    mkdir -p "$CLAUDE_HOME/.config"\n'
            '    cp -r /tmp/.gh-ro "$CLAUDE_HOME/.config/gh"\n'
            'fi\n'
            'if [ -f /tmp/.gitconfig-ro ]; then\n'
            '    cp /tmp/.gitconfig-ro "$CLAUDE_HOME/.gitconfig"\n'
            'fi\n'
            '\n'
            '# Restore persisted session data for --continue support\n'
            'SESSION_DIR="$PWD/.claude_sessions"\n'
            'if [ "$CONTINUE_SESSION" = "1" ] && [ -d "$SESSION_DIR" ]; then\n'
            '    cp -r "$SESSION_DIR/projects" "$CLAUDE_HOME/.claude/projects" 2>/dev/null || true\n'
            'fi\n'
            '\n'
            '# Fix ownership so claude user can read/write everything\n'
            'chown -R claude:claude "$CLAUDE_HOME"\n'
            '\n'
            '# Ensure workspace is writable by claude user\n'
            'chown -R claude:claude .\n'
            '\n'
            '# --- Drop to claude user for git + CLI --------------------------\n'
            'cat > /tmp/run.sh << \'INNER\'\n'
            '#!/bin/sh\n'
            'set -e\n'
            'export HOME=/home/claude\n'
            '\n'
            '# Persist session data on SIGTERM (timeout graceful stop)\n'
            'persist_session() {\n'
            '    SESSION_DIR="$PWD/.claude_sessions"\n'
            '    mkdir -p "$SESSION_DIR"\n'
            '    cp -r "$HOME/.claude/projects" "$SESSION_DIR/" 2>/dev/null || true\n'
            '}\n'
            'trap "persist_session; exit 143" TERM\n'
            '\n'
            '# Set up gh auth for HTTPS git operations when GITHUB_TOKEN is available\n'
            'if [ -n "$GITHUB_TOKEN" ]; then\n'
            '    # Configure git credential helper to use the token for HTTPS repos\n'
            '    git config --global credential.helper "!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f"\n'
            'fi\n'
            '\n'
            'if [ -n "$REPO_URL" ] && [ "$CONTINUE_SESSION" != "1" ]; then\n'
            '    # Move task metadata aside so git clone into . succeeds\n'
            '    mkdir -p /tmp/_task_meta\n'
            '    mv task_meta_* task_*.log /tmp/_task_meta/ 2>/dev/null || true\n'
            '    git clone "$REPO_URL" . 2>&1\n'
            '    # Restore metadata files\n'
            '    mv /tmp/_task_meta/* . 2>/dev/null || true\n'
            '    rm -rf /tmp/_task_meta\n'
            '    if [ -n "$SOURCE_BRANCH" ]; then\n'
            '        git checkout "$SOURCE_BRANCH" 2>/dev/null || git checkout -b "$SOURCE_BRANCH"\n'
            '    fi\n'
            '    if [ -n "$BRANCH" ]; then\n'
            '        git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"\n'
            '    fi\n'
            'fi\n'
            '\n'
            '# Build claude args with optional --continue\n'
            'CLAUDE_ARGS="--output-format stream-json --verbose --dangerously-skip-permissions"\n'
            'if [ "$CONTINUE_SESSION" = "1" ]; then\n'
            '    CLAUDE_ARGS="--continue $CLAUDE_ARGS"\n'
            'fi\n'
            '\n'
            '# Run claude; capture exit code so we can persist session data even on failure\n'
            'set +e\n'
            'claude -p "$PROMPT" $CLAUDE_ARGS &\n'
            'CLAUDE_PID=$!\n'
            'wait $CLAUDE_PID\n'
            'EXIT_CODE=$?\n'
            'set -e\n'
            '\n'
            '# Persist session data for future --continue runs\n'
            'persist_session\n'
            '\n'
            'exit $EXIT_CODE\n'
            'INNER\n'
            'chmod +x /tmp/run.sh\n'
            'exec su -p claude -c /tmp/run.sh\n'
        )

    @staticmethod
    def _parse_output(stdout: str) -> dict:
        """Parse Claude Code ``--json`` output (newline-delimited JSON)."""
        lines = stdout.strip().split("\n")
        json_objects: list[dict] = []
        raw_lines: list[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                json_objects.append(json.loads(line))
            except json.JSONDecodeError:
                raw_lines.append(line)

        return {
            "json_output": json_objects if json_objects else None,
            "raw_text": "\n".join(raw_lines) if raw_lines else None,
        }

    @staticmethod
    def _compute_token_summary(parsed: dict, task: Task | None = None) -> dict | None:
        """Aggregate token usage from Claude CLI stream-json output.

        When *task* is provided, uses its live context tracking data for
        accurate peak/compaction reporting (the post-hoc ``latest_input``
        from JSON parsing alone shows post-compaction values).
        """
        json_output = parsed.get("json_output")
        if not json_output:
            return None

        total_input = 0
        total_output = 0
        total_cache_read = 0
        total_cache_creation = 0
        latest_input = 0
        num_turns = 0
        model = None

        for obj in json_output:
            if obj.get("type") != "assistant":
                continue
            msg = obj.get("message", {})
            usage = msg.get("usage")
            if not usage:
                continue

            num_turns += 1
            input_t = usage.get("input_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_creation = usage.get("cache_creation_input_tokens", 0)
            total_input += input_t
            total_output += usage.get("output_tokens", 0)
            total_cache_read += cache_read
            total_cache_creation += cache_creation
            # Total context = uncached + cached tokens
            latest_input = input_t + cache_read + cache_creation
            if not model:
                model = msg.get("model")

        if num_turns == 0:
            return None

        return {
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_read_tokens": total_cache_read,
            "total_cache_creation_tokens": total_cache_creation,
            "latest_context_tokens": task.peak_context_tokens if task and task.peak_context_tokens else latest_input,
            "peak_context_tokens": task.peak_context_tokens if task else latest_input,
            "num_turns": task.num_turns_tracked if task and task.num_turns_tracked else num_turns,
            "num_compactions": task.num_compactions if task else 0,
            "num_continuations": task.num_continuations if task else 0,
            "model": task.context_model or model if task else model,
        }

    async def _heartbeat_loop(self, task: Task) -> None:
        """Update heartbeat timestamp every 30 s while the task runs.

        Also persists task metadata so live context tracking data is
        available via ``task_status`` during execution.
        """
        try:
            while True:
                await asyncio.sleep(30)
                task.heartbeat = datetime.now(timezone.utc)
                task.save()
        except asyncio.CancelledError:
            pass

    async def _kill_container(self, name: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "kill", name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass

    async def _stop_container(self, name: str, grace_seconds: int = 10) -> None:
        """Gracefully stop a container (SIGTERM, then SIGKILL after grace period)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stop", "-t", str(grace_seconds), name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            # Fallback to kill if stop fails
            await self._kill_container(name)

    async def _remove_container(self, name: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Auto-push
    # ------------------------------------------------------------------

    async def _auto_push_branch(
        self, task: Task, user_mounts: dict[str, str] | None = None,
    ) -> None:
        """Fallback commit+push: only acts if the Claude agent left unpushed work.

        The prompt instructs Claude to commit and push, but if it didn't
        (or left uncommitted changes), this method catches the remainder.

        Uses ``gh auth`` (via GITHUB_TOKEN) for HTTPS repos or SSH keys
        for SSH repos.  Logs the result to the task log file and stores
        push status in ``task.result["auto_push"]``.
        """
        try:
            # Check if Claude already pushed everything
            check_cmd = (
                "git fetch origin 2>/dev/null; "
                "LOCAL=$(git rev-parse HEAD); "
                "REMOTE=$(git rev-parse @{u} 2>/dev/null || echo 'none'); "
                "DIRTY=$(git status --porcelain | head -1); "
                "if [ -z \"$DIRTY\" ] && [ \"$LOCAL\" = \"$REMOTE\" ]; then "
                "echo 'UP_TO_DATE'; else echo 'NEEDS_PUSH'; fi"
            )
            check_out, _, _ = await self._run_git_in_workspace(
                task, check_cmd, user_mounts=user_mounts,
            )
            if "UP_TO_DATE" in check_out:
                logger.info("auto_push_skipped_already_pushed", task_id=task.id)
                if task.result is None:
                    task.result = {}
                task.result["auto_push"] = {
                    "success": True, "skipped": True,
                    "reason": "already pushed by agent",
                }
                return

            # Stage and commit any uncommitted changes left by the Claude agent.
            # Uses `git diff --cached --quiet` to skip the commit when there is
            # nothing new to commit (e.g. the agent already committed everything).
            commit_cmd = (
                # Exclude task system files from git staging
                "{ echo 'task_meta_*.json'; echo 'task_*.log'; echo '.claude_sessions/'; } "
                ">> .git/info/exclude && "
                "git add -A && "
                "if ! git diff --cached --quiet; then "
                f"git commit -m 'Changes from claude-code task {task.id}'; "
                "fi"
            )
            c_stdout, c_stderr, c_exit = await self._run_git_in_workspace(
                task, commit_cmd, user_mounts=user_mounts,
            )
            if c_exit != 0:
                logger.warning(
                    "auto_push_commit_failed",
                    task_id=task.id,
                    exit_code=c_exit,
                    stderr=c_stderr[:500],
                )
            else:
                commit_output = (c_stdout.strip() + "\n" + c_stderr.strip()).strip()
                if commit_output:
                    logger.info(
                        "auto_push_commit",
                        task_id=task.id,
                        output=commit_output[:300],
                    )

            # Push the branch — use -u to set upstream for new branches
            push_cmd = "git push -u origin HEAD"

            stdout, stderr, exit_code = await self._run_git_in_workspace(
                task, push_cmd, user_mounts=user_mounts,
            )

            output = (stdout.strip() + "\n" + stderr.strip()).strip()
            push_result: dict = {
                "success": exit_code == 0,
                "output": output[:2000],
            }

            if exit_code != 0:
                push_result["error"] = stderr.strip() or stdout.strip()
                logger.warning(
                    "auto_push_failed",
                    task_id=task.id,
                    exit_code=exit_code,
                    stderr=stderr[:500],
                )
            else:
                logger.info("auto_push_success", task_id=task.id)

            # Store push result in task metadata
            if task.result is None:
                task.result = {}
            task.result["auto_push"] = push_result

            # Append to task log
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            status_label = "SUCCESS" if exit_code == 0 else "FAILED"
            log_line = f"[{ts}] [auto_push] {status_label}: {output[:500]}\n"
            try:
                with open(task.log_file, "a") as f:
                    f.write(log_line)
            except OSError:
                pass

        except Exception as e:
            logger.error("auto_push_error", task_id=task.id, error=str(e))
            if task.result is None:
                task.result = {}
            task.result["auto_push"] = {"success": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Git helpers
    # ------------------------------------------------------------------

    def _validate_git_workspace(self, task_id: str, user_id: str | None = None) -> Task:
        """Validate task exists, belongs to user, and has a git repository."""
        task = self._get_task(task_id, user_id)
        if not os.path.isdir(task.workspace):
            raise ValueError(f"Workspace no longer exists: {task.workspace}")
        git_dir = os.path.join(task.workspace, ".git")
        if not os.path.isdir(git_dir):
            raise ValueError(
                f"No git repository found in workspace for task {task_id}. "
                "This task may not have been created from a git clone."
            )
        return task

    async def _run_git_in_workspace(
        self,
        task: Task,
        git_command: str,
        timeout: int = GIT_CMD_TIMEOUT,
        user_mounts: dict[str, str] | None = None,
    ) -> tuple[str, str, int]:
        """Run a git command in a task workspace via a short-lived Docker container.

        Uses the same image and credential mounting pattern as task containers.
        Returns ``(stdout, stderr, exit_code)``.
        """
        container_name = f"claude-git-{task.id}-{uuid.uuid4().hex[:6]}"

        entrypoint = (
            'set -e\n'
            'CLAUDE_HOME=/home/claude\n'
            '\n'
            '# Copy SSH keys\n'
            'if [ -d /tmp/.ssh-ro ]; then\n'
            '    cp -r /tmp/.ssh-ro "$CLAUDE_HOME/.ssh"\n'
            '    chmod 700 "$CLAUDE_HOME/.ssh"\n'
            '    chmod 600 "$CLAUDE_HOME/.ssh"/* 2>/dev/null || true\n'
            'fi\n'
            '# Copy git config\n'
            'if [ -f /tmp/.gitconfig-ro ]; then\n'
            '    cp /tmp/.gitconfig-ro "$CLAUDE_HOME/.gitconfig"\n'
            'fi\n'
            'chown -R claude:claude "$CLAUDE_HOME"\n'
            '\n'
            '# Write inner script and run as claude user\n'
            'cat > /tmp/git_run.sh << \'INNER\'\n'
            '#!/bin/sh\n'
            'set -e\n'
            'export HOME=/home/claude\n'
            '# Set up HTTPS credential helper when GITHUB_TOKEN is available\n'
            'if [ -n "$GITHUB_TOKEN" ]; then\n'
            '    git config --global credential.helper "!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f"\n'
            'fi\n'
            'eval "$GIT_CMD"\n'
            'INNER\n'
            'chmod +x /tmp/git_run.sh\n'
            'exec su -p claude -c /tmp/git_run.sh\n'
        )

        # Mount only this task's workspace for git operations
        host_workspace = os.path.join(TASK_VOLUME, task.id)
        container_workspace = os.path.join(TASK_BASE_DIR, task.id)

        cmd: list[str] = [
            "docker", "run", "--rm", "--init",
            "--name", container_name,
            f"--network={self._worker_network}",
            "-v", f"{host_workspace}:{container_workspace}",
            "-w", task.workspace,
            "-e", f"GIT_CMD={git_command}",
        ]

        # Mount credentials (read-only) — per-user overrides global
        um = user_mounts or {}

        ssh_key = um.get("ssh_key") or SSH_KEY_PATH
        if ssh_key:
            cmd.extend(["-v", f"{ssh_key}:/tmp/.ssh-ro:ro"])

        git_config = um.get("git_config") or GIT_CONFIG_PATH
        if git_config:
            cmd.extend(["-v", f"{git_config}:/tmp/.gitconfig-ro:ro"])

        # Git identity env vars — per-user overrides global bot identity
        git_author_name = um.get("_git_author_name") or CLAUDE_CODE_GIT_AUTHOR_NAME
        git_author_email = um.get("_git_author_email") or CLAUDE_CODE_GIT_AUTHOR_EMAIL
        cmd.extend([
            "-e", f"GIT_AUTHOR_NAME={git_author_name}",
            "-e", f"GIT_AUTHOR_EMAIL={git_author_email}",
            "-e", f"GIT_COMMITTER_NAME={git_author_name}",
            "-e", f"GIT_COMMITTER_EMAIL={git_author_email}",
        ])

        github_token = um.get("_github_token") or GITHUB_TOKEN
        if github_token:
            cmd.extend(["-e", f"GITHUB_TOKEN={github_token}"])

        cmd.extend([CLAUDE_CODE_IMAGE, "sh", "-c", entrypoint])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            return stdout, stderr, proc.returncode or 0
        except asyncio.TimeoutError:
            await self._kill_container(container_name)
            raise ValueError(f"Git command timed out after {timeout}s")
        finally:
            await self._remove_container(container_name)

    # ------------------------------------------------------------------
    # Git tools (called by orchestrator)
    # ------------------------------------------------------------------

    async def git_status(self, task_id: str, user_id: str | None = None) -> dict:
        """Return comprehensive git status for a task's workspace."""
        task = self._validate_git_workspace(task_id, user_id)

        git_script = (
            'echo "===BRANCH==="\n'
            'git branch --show-current\n'
            'echo "===REMOTE==="\n'
            'git remote -v 2>/dev/null || echo "no remotes"\n'
            'echo "===TRACKING==="\n'
            'git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo "no upstream"\n'
            'echo "===AHEAD_BEHIND==="\n'
            'git rev-list --left-right --count @{upstream}...HEAD 2>/dev/null || echo "unknown"\n'
            'echo "===STATUS==="\n'
            'git status --porcelain\n'
            'echo "===LOG==="\n'
            'git log --oneline -10\n'
            'echo "===END==="'
        )

        stdout, stderr, exit_code = await self._run_git_in_workspace(task, git_script)

        if exit_code != 0:
            return {
                "task_id": task_id,
                "error": f"Git command failed (exit {exit_code}): {stderr.strip()}",
            }

        # Parse sectioned output
        sections: dict[str, list[str]] = {}
        current_section: str | None = None
        current_lines: list[str] = []

        for line in stdout.split("\n"):
            stripped = line.strip()
            if stripped.startswith("===") and stripped.endswith("==="):
                if current_section is not None:
                    sections[current_section] = current_lines
                current_section = stripped.strip("=")
                current_lines = []
            elif stripped:
                current_lines.append(stripped)
        if current_section is not None:
            sections[current_section] = current_lines

        # Parse ahead/behind
        ahead: int | None = None
        behind: int | None = None
        ab_lines = sections.get("AHEAD_BEHIND", ["unknown"])
        if ab_lines and ab_lines[0] != "unknown":
            parts = ab_lines[0].split()
            if len(parts) == 2:
                try:
                    behind, ahead = int(parts[0]), int(parts[1])
                except ValueError:
                    pass

        # Parse porcelain status
        staged, unstaged, untracked = [], [], []
        for line in sections.get("STATUS", []):
            if len(line) < 2:
                continue
            idx, wt = line[0], line[1]
            filepath = line[3:] if len(line) > 3 else line[2:]
            if idx == "?":
                untracked.append(filepath)
            else:
                if idx != " ":
                    staged.append(f"{idx} {filepath}")
                if wt != " ":
                    unstaged.append(f"{wt} {filepath}")

        tracking_lines = sections.get("TRACKING", ["no upstream"])
        tracking = tracking_lines[0] if tracking_lines else "no upstream"

        branch_lines = sections.get("BRANCH", [])
        branch = branch_lines[0] if branch_lines else "(detached HEAD)"

        return {
            "task_id": task_id,
            "branch": branch,
            "tracking": tracking if tracking != "no upstream" else None,
            "ahead": ahead,
            "behind": behind,
            "remotes": sections.get("REMOTE", []),
            "staged_changes": staged,
            "unstaged_changes": unstaged,
            "untracked_files": untracked,
            "recent_commits": sections.get("LOG", []),
            "clean": not staged and not unstaged and not untracked,
        }

    async def git_push(
        self,
        task_id: str,
        remote: str = "origin",
        branch: str | None = None,
        force: bool = False,
        user_id: str | None = None,
    ) -> dict:
        """Push the task workspace's branch to a remote."""
        task = self._validate_git_workspace(task_id, user_id)

        if not SSH_KEY_PATH and not GITHUB_TOKEN:
            raise ValueError(
                "No git authentication configured. Git push requires either "
                "SSH_KEY_PATH (for SSH repos) or GITHUB_TOKEN (for HTTPS repos)."
            )

        # Validate user-supplied values to prevent injection
        _validate_git_ref(remote, "remote")
        if branch:
            _validate_git_ref(branch, "branch")

        # Get current branch for the response
        branch_stdout, _, _ = await self._run_git_in_workspace(
            task, "git branch --show-current",
        )
        current_branch = branch_stdout.strip() or "(detached HEAD)"

        # Build push command
        push_parts = ["git", "push"]
        if force:
            push_parts.append("--force-with-lease")
        push_parts.append(remote)
        if branch:
            push_parts.append(branch)

        stdout, stderr, exit_code = await self._run_git_in_workspace(
            task, " ".join(push_parts),
        )

        # Git push writes progress to stderr even on success
        output = (stdout.strip() + "\n" + stderr.strip()).strip()

        if exit_code != 0:
            error_msg = stderr.strip() or stdout.strip()
            error_lower = error_msg.lower()

            hint = None
            if "rejected" in error_lower:
                hint = (
                    "Push was rejected. The remote branch has diverging commits. "
                    "Use force=true to force push (with lease), or rebase first."
                )
            elif "permission denied" in error_lower or "publickey" in error_lower:
                hint = "Authentication failed. Check SSH_KEY_PATH or GITHUB_TOKEN credentials."
            elif "could not read from remote" in error_lower:
                hint = "Cannot reach the remote repository. Check the remote URL and network access."

            result: dict = {
                "task_id": task_id,
                "success": False,
                "branch": current_branch,
                "remote": remote,
                "error": error_msg,
            }
            if hint:
                result["hint"] = hint
            return result

        return {
            "task_id": task_id,
            "success": True,
            "branch": branch or current_branch,
            "remote": remote,
            "force": force,
            "output": output,
            "message": f"Successfully pushed {branch or current_branch} to {remote}.",
        }
