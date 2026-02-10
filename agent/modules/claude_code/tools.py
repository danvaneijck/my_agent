"""Claude Code tool implementations."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = int(os.environ.get("CLAUDE_CODE_TIMEOUT", "600"))
CLAUDE_CODE_IMAGE = os.environ.get("CLAUDE_CODE_IMAGE", "my-claude-code-image")
CLAUDE_AUTH_PATH = os.environ.get("CLAUDE_AUTH_PATH", "")
SSH_KEY_PATH = os.environ.get("SSH_KEY_PATH", "")
GH_CONFIG_PATH = os.environ.get("GH_CONFIG_PATH", "")
GIT_CONFIG_PATH = os.environ.get("GIT_CONFIG_PATH", "")
TASK_VOLUME = os.environ.get("CLAUDE_TASK_VOLUME", "claude-tasks")

# Bot git identity — overrides any mounted .gitconfig for commits
CLAUDE_CODE_GIT_AUTHOR_NAME = os.environ.get("CLAUDE_CODE_GIT_AUTHOR_NAME", "claude-agent[bot]")
CLAUDE_CODE_GIT_AUTHOR_EMAIL = os.environ.get("CLAUDE_CODE_GIT_AUTHOR_EMAIL", "claude-agent[bot]@noreply.github.com")
TASK_BASE_DIR = "/tmp/claude_tasks"

MAX_OUTPUT = 50_000  # chars kept from stdout/stderr


# ---------------------------------------------------------------------------
# Task data model
# ---------------------------------------------------------------------------
@dataclass
class Task:
    id: str
    prompt: str
    repo_url: str | None = None
    branch: str | None = None
    workspace: str = ""
    status: str = "queued"  # queued | running | completed | failed
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    heartbeat: datetime | None = None
    result: dict | None = None
    error: str | None = None
    _asyncio_task: asyncio.Task | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "task_id": self.id,
            "prompt": self.prompt,
            "repo_url": self.repo_url,
            "branch": self.branch,
            "workspace": self.workspace,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "heartbeat": self.heartbeat.isoformat() if self.heartbeat else None,
            "elapsed_seconds": self._elapsed(),
            "result": self.result,
            "error": self.error,
        }

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
        os.makedirs(TASK_BASE_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Public tools (called by orchestrator)
    # ------------------------------------------------------------------

    async def run_task(
        self,
        prompt: str,
        repo_url: str | None = None,
        branch: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        user_id: str | None = None,
    ) -> dict:
        """Submit a coding task. Returns immediately with task_id."""
        task_id = uuid.uuid4().hex[:12]
        workspace = os.path.join(TASK_BASE_DIR, task_id)
        os.makedirs(workspace, exist_ok=True)

        task = Task(id=task_id, prompt=prompt, repo_url=repo_url, branch=branch, workspace=workspace)
        self.tasks[task_id] = task

        # Fire-and-forget background execution
        task._asyncio_task = asyncio.create_task(self._execute_task(task, timeout))

        logger.info("task_submitted", task_id=task_id, repo_url=repo_url)
        return {
            "task_id": task_id,
            "status": "queued",
            "workspace": workspace,
            "message": (
                f"Task submitted. Use claude_code.task_status with "
                f"task_id='{task_id}' to check progress. "
                f"When the task completes, use deployer.deploy with "
                f"project_path='{workspace}' to deploy it."
            ),
        }

    async def task_status(self, task_id: str, user_id: str | None = None) -> dict:
        """Return the current status of a task."""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        return task.to_dict()

    async def list_tasks(
        self, status_filter: str | None = None, user_id: str | None = None
    ) -> dict:
        """List all tasks, optionally filtered by status."""
        tasks = list(self.tasks.values())
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        return {
            "tasks": [t.to_dict() for t in tasks],
            "total": len(tasks),
        }

    # ------------------------------------------------------------------
    # Background execution
    # ------------------------------------------------------------------

    async def _execute_task(self, task: Task, timeout: int) -> None:
        """Background coroutine: run the Claude Code Docker container."""
        container_name = f"claude-task-{task.id}"
        task.status = "running"
        task.started_at = datetime.now(timezone.utc)
        task.heartbeat = task.started_at

        cmd = self._build_docker_cmd(task, container_name)
        logger.info("task_starting", task_id=task.id, container=container_name)
        logger.debug("task_docker_cmd", task_id=task.id, cmd=" ".join(cmd))

        heartbeat_handle: asyncio.Task | None = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            heartbeat_handle = asyncio.create_task(self._heartbeat_loop(task))

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("task_timeout", task_id=task.id, timeout=timeout)
                await self._kill_container(container_name)
                task.status = "failed"
                task.error = f"Task timed out after {timeout}s"
                return

            stdout = stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT]

            if proc.returncode == 0:
                task.status = "completed"
                task.result = self._parse_output(stdout)
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

        except Exception as e:
            logger.error("task_execution_error", task_id=task.id, error=str(e))
            task.status = "failed"
            task.error = str(e)
        finally:
            task.completed_at = datetime.now(timezone.utc)
            if heartbeat_handle:
                heartbeat_handle.cancel()
            await self._remove_container(container_name)
            logger.info(
                "task_finished",
                task_id=task.id,
                status=task.status,
                elapsed=task._elapsed(),
            )

    # ------------------------------------------------------------------
    # Docker helpers
    # ------------------------------------------------------------------

    def _build_docker_cmd(self, task: Task, container_name: str) -> list[str]:
        """Assemble the ``docker run`` argument list."""
        cmd: list[str] = [
            "docker", "run", "--rm",
            "--name", container_name,
            "-v", f"{TASK_VOLUME}:{TASK_BASE_DIR}",
            "-w", f"{TASK_BASE_DIR}/{task.id}",
            "-e", f"PROMPT={task.prompt}",
        ]

        if task.repo_url:
            cmd.extend(["-e", f"REPO_URL={task.repo_url}"])
        if task.branch:
            cmd.extend(["-e", f"BRANCH={task.branch}"])

        # Mount credentials read-only at staging paths (entrypoint copies them)
        if CLAUDE_AUTH_PATH:
            cmd.extend(["-v", f"{CLAUDE_AUTH_PATH}:/tmp/.claude-ro:ro"])
        if SSH_KEY_PATH:
            cmd.extend(["-v", f"{SSH_KEY_PATH}:/root/.ssh:ro"])
        if GH_CONFIG_PATH:
            cmd.extend(["-v", f"{GH_CONFIG_PATH}:/root/.config/gh:ro"])
        if GIT_CONFIG_PATH:
            cmd.extend(["-v", f"{GIT_CONFIG_PATH}:/root/.gitconfig:ro"])

        # Override git identity so commits are attributed to the bot
        cmd.extend([
            "-e", f"GIT_AUTHOR_NAME={CLAUDE_CODE_GIT_AUTHOR_NAME}",
            "-e", f"GIT_AUTHOR_EMAIL={CLAUDE_CODE_GIT_AUTHOR_EMAIL}",
            "-e", f"GIT_COMMITTER_NAME={CLAUDE_CODE_GIT_AUTHOR_NAME}",
            "-e", f"GIT_COMMITTER_EMAIL={CLAUDE_CODE_GIT_AUTHOR_EMAIL}",
        ])

        cmd.extend([
            CLAUDE_CODE_IMAGE,
            "sh", "-c", self._entrypoint_script(),
        ])
        return cmd

    @staticmethod
    def _entrypoint_script() -> str:
        """Shell script executed inside the worker container."""
        return (
            'set -e\n'
            '# Copy read-only auth to writable location\n'
            'if [ -d /tmp/.claude-ro ]; then\n'
            '    cp -r /tmp/.claude-ro /root/.claude\n'
            '    chmod -R 600 /root/.claude 2>/dev/null || true\n'
            'fi\n'
            'if [ -n "$REPO_URL" ]; then\n'
            '    git clone "$REPO_URL" . 2>&1\n'
            '    if [ -n "$BRANCH" ]; then\n'
            '        git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"\n'
            '    fi\n'
            'fi\n'
            'claude -p "$PROMPT" --output-format json\n'
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

    async def _heartbeat_loop(self, task: Task) -> None:
        """Update heartbeat timestamp every 30 s while the task runs."""
        try:
            while True:
                await asyncio.sleep(30)
                task.heartbeat = datetime.now(timezone.utc)
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
