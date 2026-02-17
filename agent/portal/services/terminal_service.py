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
            if container.status != "running":
                raise ValueError(
                    f"Container {container_id} exists but is not running (status: {container.status})"
                )
            return container
        except docker.errors.NotFound:
            raise ValueError(f"Container {container_id} not found")
        except Exception as e:
            raise ValueError(f"Error accessing container: {e}")

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


# Global instance
_terminal_service: Optional[TerminalService] = None


def get_terminal_service() -> TerminalService:
    """Get or create the global TerminalService instance."""
    global _terminal_service
    if _terminal_service is None:
        _terminal_service = TerminalService()
    return _terminal_service
