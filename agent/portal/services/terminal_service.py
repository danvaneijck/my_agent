"""Terminal session management for interactive workspace shells."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import docker
import structlog
from docker.models.containers import Container

logger = structlog.get_logger()

# Session timeout in seconds (30 minutes of inactivity)
SESSION_TIMEOUT = 1800
HEARTBEAT_INTERVAL = 60  # Check for inactive sessions every minute
MAX_SESSIONS_PER_TASK = 10  # Maximum concurrent sessions per task


@dataclass
class TerminalSession:
    """Represents an active terminal exec session in a Docker container."""

    session_id: str
    container_id: str
    user_id: str
    task_id: str
    exec_id: Optional[str] = None
    socket: Optional[object] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    active: bool = True

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)

    def is_expired(self) -> bool:
        """Check if session has been inactive beyond timeout threshold."""
        elapsed = (datetime.now(timezone.utc) - self.last_activity).total_seconds()
        return elapsed > SESSION_TIMEOUT


class TerminalService:
    """Manages interactive terminal sessions in workspace containers."""

    def __init__(self):
        try:
            self.docker_client = docker.from_env()
            logger.info("terminal_service_initialized")
        except Exception as e:
            logger.error("terminal_service_init_failed", error=str(e))
            raise

        # Track active sessions: {session_id: TerminalSession}
        self.sessions: dict[str, TerminalSession] = {}

        # Track on-demand terminal containers: {task_id: container_id}
        self.terminal_containers: dict[str, str] = {}

        # Background task for session cleanup
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_loop(self) -> None:
        """Start background loop to clean up expired sessions."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("terminal_cleanup_loop_started")

    async def _cleanup_loop(self) -> None:
        """Periodically check for and cleanup expired sessions."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                expired = [
                    sid
                    for sid, session in self.sessions.items()
                    if session.is_expired()
                ]
                for session_id in expired:
                    logger.info(
                        "session_expired",
                        session_id=session_id,
                        elapsed=SESSION_TIMEOUT,
                    )
                    await self.cleanup_session(session_id)
            except Exception as e:
                logger.error("cleanup_loop_error", error=str(e))

    def get_container(self, container_id: str) -> Container:
        """Get a Docker container by ID or name.

        Args:
            container_id: Container ID or name

        Returns:
            Docker Container object

        Raises:
            ValueError: If container not found or not running
        """
        try:
            container = self.docker_client.containers.get(container_id)
            container.reload()  # Refresh container state
            if container.status != "running":
                raise ValueError(
                    f"Container exists but is {container.status}. Start the workspace first."
                )
            return container
        except docker.errors.NotFound:
            raise ValueError(f"Container not found. The workspace may have been deleted.")
        except docker.errors.APIError as e:
            raise ValueError(f"Docker API error: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to access container: {str(e)}")

    async def create_session(
        self,
        session_id: str,
        container_id: str,
        user_id: str,
        task_id: str,
        working_dir: str,
    ) -> TerminalSession:
        """Create a new terminal exec session in a container.

        Args:
            session_id: Unique session identifier
            container_id: Docker container ID or name
            user_id: User ID for session tracking
            task_id: Task ID for the workspace
            working_dir: Working directory path in container

        Returns:
            TerminalSession object

        Raises:
            ValueError: If container not found/not running or session creation fails
        """
        # Check if session already exists
        if session_id in self.sessions:
            existing = self.sessions[session_id]
            logger.info(
                "session_already_exists",
                session_id=session_id,
                task_id=task_id,
            )
            return existing

        # Check session limit per task
        task_sessions = self.get_task_sessions(task_id)
        if len(task_sessions) >= MAX_SESSIONS_PER_TASK:
            raise ValueError(
                f"Maximum of {MAX_SESSIONS_PER_TASK} concurrent terminal sessions reached for this task. "
                f"Close some terminals before opening new ones."
            )

        # Get and validate container
        container = self.get_container(container_id)

        logger.info(
            "creating_terminal_session",
            session_id=session_id,
            container_id=container_id,
            task_id=task_id,
            working_dir=working_dir,
        )

        try:
            # Create exec instance for interactive bash shell
            # tty=True enables terminal features (colors, line editing, etc.)
            # stdin=True allows sending input to the shell
            # privileged=False for security (no root capabilities)
            exec_instance = self.docker_client.api.exec_create(
                container=container.id,
                cmd=["/bin/bash"],
                stdin=True,
                tty=True,
                privileged=False,
                workdir=working_dir,
                environment={"TERM": "xterm-256color"},
            )

            exec_id = exec_instance["Id"]

            # Create session object
            session = TerminalSession(
                session_id=session_id,
                container_id=container.id,
                user_id=user_id,
                task_id=task_id,
                exec_id=exec_id,
            )

            self.sessions[session_id] = session

            logger.info(
                "terminal_session_created",
                session_id=session_id,
                exec_id=exec_id,
                container_id=container.id,
            )

            return session

        except Exception as e:
            logger.error(
                "session_creation_failed",
                session_id=session_id,
                container_id=container_id,
                error=str(e),
            )
            raise ValueError(f"Failed to create terminal session: {e}")

    async def attach_session(self, session_id: str) -> object:
        """Attach to an existing terminal session and return the socket.

        Args:
            session_id: Session identifier

        Returns:
            Docker socket for bidirectional I/O

        Raises:
            ValueError: If session not found or exec instance invalid
        """
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if not session.exec_id:
            raise ValueError(f"Session {session_id} has no exec instance")

        try:
            # Start the exec instance and get socket for I/O
            socket = self.docker_client.api.exec_start(
                exec_id=session.exec_id,
                socket=True,
                tty=True,
            )

            session.socket = socket
            session.update_activity()

            logger.info("session_attached", session_id=session_id, exec_id=session.exec_id)
            return socket

        except Exception as e:
            logger.error(
                "session_attach_failed",
                session_id=session_id,
                exec_id=session.exec_id,
                error=str(e),
            )
            raise ValueError(f"Failed to attach to session: {e}")

    async def cleanup_session(self, session_id: str) -> None:
        """Terminate and cleanup a terminal session.

        Args:
            session_id: Session identifier to cleanup
        """
        session = self.sessions.pop(session_id, None)
        if not session:
            logger.debug("cleanup_session_not_found", session_id=session_id)
            return

        try:
            session.active = False

            # Close socket if attached
            if session.socket:
                try:
                    session.socket.close()
                except Exception as e:
                    logger.debug("socket_close_error", error=str(e))

            # Note: Docker exec instances are automatically cleaned up
            # when the container stops or when the exec process exits.
            # We don't need to explicitly kill them.

            logger.info(
                "session_cleaned_up",
                session_id=session_id,
                exec_id=session.exec_id,
                duration_seconds=(
                    datetime.now(timezone.utc) - session.created_at
                ).total_seconds(),
            )

        except Exception as e:
            logger.error(
                "session_cleanup_error",
                session_id=session_id,
                error=str(e),
            )

    def update_session_activity(self, session_id: str) -> None:
        """Update the last activity timestamp for a session.

        Args:
            session_id: Session identifier
        """
        session = self.sessions.get(session_id)
        if session:
            session.update_activity()

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        """Get a session by ID.

        Args:
            session_id: Session identifier

        Returns:
            TerminalSession if found, None otherwise
        """
        return self.sessions.get(session_id)

    def get_user_sessions(self, user_id: str) -> list[TerminalSession]:
        """Get all active sessions for a user.

        Args:
            user_id: User identifier

        Returns:
            List of TerminalSession objects
        """
        return [s for s in self.sessions.values() if s.user_id == user_id]

    def get_task_sessions(self, task_id: str) -> list[TerminalSession]:
        """Get all active sessions for a task.

        Args:
            task_id: Task identifier

        Returns:
            List of TerminalSession objects
        """
        return [s for s in self.sessions.values() if s.task_id == task_id]

    async def get_or_create_terminal_container(
        self, task_id: str, workspace_path: str
    ) -> tuple[str, str]:
        """Get existing or create new on-demand terminal container for a workspace.

        Args:
            task_id: Task identifier
            workspace_path: Path to workspace directory on host

        Returns:
            Tuple of (container_id, container_status)

        Raises:
            ValueError: If container creation fails
        """
        # Check if we already have a terminal container for this task
        if task_id in self.terminal_containers:
            container_id = self.terminal_containers[task_id]
            try:
                container = self.docker_client.containers.get(container_id)
                container.reload()

                # If container exists and is running, return it
                if container.status == "running":
                    logger.info(
                        "terminal_container_exists",
                        task_id=task_id,
                        container_id=container_id,
                    )
                    return container_id, container.status

                # If container exists but not running, try to start it
                if container.status == "exited":
                    logger.info(
                        "terminal_container_starting",
                        task_id=task_id,
                        container_id=container_id,
                    )
                    container.start()
                    container.reload()
                    return container_id, container.status

            except docker.errors.NotFound:
                # Container was removed, clean up reference
                logger.info(
                    "terminal_container_removed",
                    task_id=task_id,
                    container_id=container_id,
                )
                del self.terminal_containers[task_id]

        # Create new terminal container
        try:
            logger.info(
                "creating_terminal_container",
                task_id=task_id,
                workspace_path=workspace_path,
            )

            # Mount the entire /tmp/claude_tasks directory like task containers do
            # This ensures task chains work correctly (workspace may be named after first task)
            # The workspace_path is the container path like /tmp/claude_tasks/{task_id}
            # Portal service has ./data/claude_tasks mounted at /tmp/claude_tasks
            # So we mount /tmp/claude_tasks:/tmp/claude_tasks in terminal containers too
            container = self.docker_client.containers.run(
                image="my-claude-code-image",
                command=["/bin/bash", "-c", "sleep infinity"],
                detach=True,
                remove=False,  # Don't auto-remove so we can reuse it
                name=f"terminal-{task_id}",
                working_dir=workspace_path,  # Use actual workspace path (works for task chains)
                volumes={
                    "/tmp/claude_tasks": {
                        "bind": "/tmp/claude_tasks",
                        "mode": "rw",
                    }
                },
                environment={"TERM": "xterm-256color"},
                labels={
                    "managed_by": "portal_terminal_service",
                    "task_id": task_id,
                },
            )

            container_id = container.id
            self.terminal_containers[task_id] = container_id

            logger.info(
                "terminal_container_created",
                task_id=task_id,
                container_id=container_id,
            )

            return container_id, "running"

        except Exception as e:
            logger.error(
                "terminal_container_creation_failed",
                task_id=task_id,
                workspace_path=workspace_path,
                error=str(e),
            )
            raise ValueError(f"Failed to create terminal container: {e}")

    async def cleanup_terminal_container(self, task_id: str) -> None:
        """Stop and remove on-demand terminal container for a task.

        Args:
            task_id: Task identifier
        """
        if task_id not in self.terminal_containers:
            return

        container_id = self.terminal_containers[task_id]
        try:
            container = self.docker_client.containers.get(container_id)
            logger.info(
                "stopping_terminal_container",
                task_id=task_id,
                container_id=container_id,
            )
            container.stop(timeout=5)
            container.remove()
            logger.info(
                "terminal_container_removed",
                task_id=task_id,
                container_id=container_id,
            )
        except docker.errors.NotFound:
            logger.debug(
                "terminal_container_not_found",
                task_id=task_id,
                container_id=container_id,
            )
        except Exception as e:
            logger.error(
                "terminal_container_cleanup_error",
                task_id=task_id,
                container_id=container_id,
                error=str(e),
            )
        finally:
            del self.terminal_containers[task_id]


# Global instance
_terminal_service: Optional[TerminalService] = None


def get_terminal_service() -> TerminalService:
    """Get or create the global TerminalService instance."""
    global _terminal_service
    if _terminal_service is None:
        _terminal_service = TerminalService()
    return _terminal_service
