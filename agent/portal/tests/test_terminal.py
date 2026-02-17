"""Integration tests for terminal service and WebSocket endpoints."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from docker.errors import APIError, NotFound

from portal.services.terminal_service import (
    MAX_SESSIONS_PER_TASK,
    SESSION_TIMEOUT,
    TerminalService,
    TerminalSession,
)


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    client = MagicMock()
    container = MagicMock()
    container.id = "test-container-123"
    container.status = "running"
    client.containers.get.return_value = container

    exec_instance = {"Id": "exec-123"}
    client.api.exec_create.return_value = exec_instance

    mock_socket = MagicMock()
    mock_socket._sock = MagicMock()
    client.api.exec_start.return_value = mock_socket

    return client


@pytest.fixture
def terminal_service(mock_docker_client):
    """Create a TerminalService instance with mocked Docker client."""
    with patch("portal.services.terminal_service.docker") as mock_docker:
        mock_docker.from_env.return_value = mock_docker_client
        service = TerminalService()
        return service


class TestTerminalService:
    """Test cases for TerminalService."""

    def test_init_success(self, mock_docker_client):
        """Test successful initialization of TerminalService."""
        with patch("portal.services.terminal_service.docker") as mock_docker:
            mock_docker.from_env.return_value = mock_docker_client
            service = TerminalService()
            assert service.docker_client == mock_docker_client
            assert service.sessions == {}
            assert service._cleanup_task is None

    def test_init_failure(self):
        """Test TerminalService initialization failure."""
        with patch("portal.services.terminal_service.docker") as mock_docker:
            mock_docker.from_env.side_effect = Exception("Docker not available")
            with pytest.raises(Exception, match="Docker not available"):
                TerminalService()

    def test_get_container_success(self, terminal_service, mock_docker_client):
        """Test successfully retrieving a running container."""
        container = terminal_service.get_container("test-container-123")
        assert container.id == "test-container-123"
        assert container.status == "running"
        mock_docker_client.containers.get.assert_called_once_with("test-container-123")

    def test_get_container_not_found(self, terminal_service, mock_docker_client):
        """Test container not found error."""
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")
        with pytest.raises(ValueError, match="Container not found"):
            terminal_service.get_container("nonexistent-container")

    def test_get_container_not_running(self, terminal_service, mock_docker_client):
        """Test container exists but is not running."""
        container = MagicMock()
        container.status = "exited"
        container.reload = MagicMock()
        mock_docker_client.containers.get.return_value = container

        with pytest.raises(ValueError, match="is exited"):
            terminal_service.get_container("stopped-container")

    def test_get_container_api_error(self, terminal_service, mock_docker_client):
        """Test Docker API error when getting container."""
        mock_docker_client.containers.get.side_effect = APIError("API error")
        with pytest.raises(ValueError, match="Docker API error"):
            terminal_service.get_container("test-container")

    @pytest.mark.asyncio
    async def test_create_session_success(self, terminal_service, mock_docker_client):
        """Test successfully creating a terminal session."""
        session_id = "session-123"
        container_id = "container-123"
        user_id = "user-456"
        task_id = "task-789"
        working_dir = "/workspace"

        session = await terminal_service.create_session(
            session_id=session_id,
            container_id=container_id,
            user_id=user_id,
            task_id=task_id,
            working_dir=working_dir,
        )

        assert session.session_id == session_id
        assert session.container_id == "test-container-123"  # from mock
        assert session.user_id == user_id
        assert session.task_id == task_id
        assert session.exec_id == "exec-123"
        assert session.active is True
        assert session_id in terminal_service.sessions

        # Verify exec_create was called with correct parameters
        mock_docker_client.api.exec_create.assert_called_once()
        call_kwargs = mock_docker_client.api.exec_create.call_args[1]
        assert call_kwargs["cmd"] == ["/bin/bash"]
        assert call_kwargs["stdin"] is True
        assert call_kwargs["tty"] is True
        assert call_kwargs["privileged"] is False
        assert call_kwargs["workdir"] == working_dir

    @pytest.mark.asyncio
    async def test_create_session_already_exists(self, terminal_service):
        """Test creating a session that already exists returns the existing session."""
        session_id = "session-123"
        existing_session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
        )
        terminal_service.sessions[session_id] = existing_session

        session = await terminal_service.create_session(
            session_id=session_id,
            container_id="different-container",
            user_id="different-user",
            task_id="different-task",
            working_dir="/workspace",
        )

        assert session == existing_session

    @pytest.mark.asyncio
    async def test_create_session_max_limit(self, terminal_service, mock_docker_client):
        """Test that creating sessions respects the per-task limit."""
        task_id = "task-123"

        # Create max sessions for the task
        for i in range(MAX_SESSIONS_PER_TASK):
            session_id = f"session-{i}"
            await terminal_service.create_session(
                session_id=session_id,
                container_id="container-123",
                user_id="user-456",
                task_id=task_id,
                working_dir="/workspace",
            )

        # Try to create one more - should fail
        with pytest.raises(ValueError, match=f"Maximum of {MAX_SESSIONS_PER_TASK}"):
            await terminal_service.create_session(
                session_id="session-overflow",
                container_id="container-123",
                user_id="user-456",
                task_id=task_id,
                working_dir="/workspace",
            )

    @pytest.mark.asyncio
    async def test_create_session_exec_creation_fails(self, terminal_service, mock_docker_client):
        """Test handling exec creation failure."""
        mock_docker_client.api.exec_create.side_effect = Exception("Exec create failed")

        with pytest.raises(ValueError, match="Failed to create terminal session"):
            await terminal_service.create_session(
                session_id="session-123",
                container_id="container-123",
                user_id="user-456",
                task_id="task-789",
                working_dir="/workspace",
            )

    @pytest.mark.asyncio
    async def test_attach_session_success(self, terminal_service, mock_docker_client):
        """Test successfully attaching to a session."""
        session_id = "session-123"
        session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
            exec_id="exec-123",
        )
        terminal_service.sessions[session_id] = session

        socket = await terminal_service.attach_session(session_id)

        assert socket is not None
        assert session.socket == socket
        mock_docker_client.api.exec_start.assert_called_once_with(
            exec_id="exec-123",
            socket=True,
            tty=True,
        )

    @pytest.mark.asyncio
    async def test_attach_session_not_found(self, terminal_service):
        """Test attaching to a non-existent session."""
        with pytest.raises(ValueError, match="Session .* not found"):
            await terminal_service.attach_session("nonexistent-session")

    @pytest.mark.asyncio
    async def test_attach_session_no_exec_id(self, terminal_service):
        """Test attaching to a session without an exec instance."""
        session_id = "session-123"
        session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
        )
        terminal_service.sessions[session_id] = session

        with pytest.raises(ValueError, match="has no exec instance"):
            await terminal_service.attach_session(session_id)

    @pytest.mark.asyncio
    async def test_attach_session_exec_start_fails(self, terminal_service, mock_docker_client):
        """Test handling exec start failure."""
        session_id = "session-123"
        session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
            exec_id="exec-123",
        )
        terminal_service.sessions[session_id] = session
        mock_docker_client.api.exec_start.side_effect = Exception("Exec start failed")

        with pytest.raises(ValueError, match="Failed to attach to session"):
            await terminal_service.attach_session(session_id)

    @pytest.mark.asyncio
    async def test_cleanup_session_success(self, terminal_service):
        """Test successfully cleaning up a session."""
        session_id = "session-123"
        mock_socket = MagicMock()
        session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
            exec_id="exec-123",
            socket=mock_socket,
        )
        terminal_service.sessions[session_id] = session

        await terminal_service.cleanup_session(session_id)

        assert session_id not in terminal_service.sessions
        assert session.active is False
        mock_socket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_session_not_found(self, terminal_service):
        """Test cleaning up a non-existent session (should not raise)."""
        await terminal_service.cleanup_session("nonexistent-session")
        # Should complete without error

    @pytest.mark.asyncio
    async def test_cleanup_session_socket_close_error(self, terminal_service):
        """Test cleanup handles socket close errors gracefully."""
        session_id = "session-123"
        mock_socket = MagicMock()
        mock_socket.close.side_effect = Exception("Socket close failed")
        session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
            socket=mock_socket,
        )
        terminal_service.sessions[session_id] = session

        await terminal_service.cleanup_session(session_id)

        assert session_id not in terminal_service.sessions
        assert session.active is False

    def test_update_session_activity(self, terminal_service):
        """Test updating session activity timestamp."""
        session_id = "session-123"
        session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
        )
        terminal_service.sessions[session_id] = session

        original_activity = session.last_activity

        # Update activity
        terminal_service.update_session_activity(session_id)

        assert session.last_activity > original_activity

    def test_update_session_activity_not_found(self, terminal_service):
        """Test updating activity for non-existent session (should not raise)."""
        terminal_service.update_session_activity("nonexistent-session")
        # Should complete without error

    def test_get_session(self, terminal_service):
        """Test retrieving a session by ID."""
        session_id = "session-123"
        session = TerminalSession(
            session_id=session_id,
            container_id="container-123",
            user_id="user-456",
            task_id="task-789",
        )
        terminal_service.sessions[session_id] = session

        retrieved = terminal_service.get_session(session_id)
        assert retrieved == session

        # Test non-existent session
        assert terminal_service.get_session("nonexistent") is None

    def test_get_user_sessions(self, terminal_service):
        """Test retrieving all sessions for a user."""
        user_id = "user-456"
        session1 = TerminalSession(
            session_id="session-1",
            container_id="container-123",
            user_id=user_id,
            task_id="task-1",
        )
        session2 = TerminalSession(
            session_id="session-2",
            container_id="container-456",
            user_id=user_id,
            task_id="task-2",
        )
        session3 = TerminalSession(
            session_id="session-3",
            container_id="container-789",
            user_id="different-user",
            task_id="task-3",
        )

        terminal_service.sessions["session-1"] = session1
        terminal_service.sessions["session-2"] = session2
        terminal_service.sessions["session-3"] = session3

        user_sessions = terminal_service.get_user_sessions(user_id)
        assert len(user_sessions) == 2
        assert session1 in user_sessions
        assert session2 in user_sessions
        assert session3 not in user_sessions

    def test_get_task_sessions(self, terminal_service):
        """Test retrieving all sessions for a task."""
        task_id = "task-123"
        session1 = TerminalSession(
            session_id="session-1",
            container_id="container-123",
            user_id="user-1",
            task_id=task_id,
        )
        session2 = TerminalSession(
            session_id="session-2",
            container_id="container-123",
            user_id="user-2",
            task_id=task_id,
        )
        session3 = TerminalSession(
            session_id="session-3",
            container_id="container-456",
            user_id="user-1",
            task_id="different-task",
        )

        terminal_service.sessions["session-1"] = session1
        terminal_service.sessions["session-2"] = session2
        terminal_service.sessions["session-3"] = session3

        task_sessions = terminal_service.get_task_sessions(task_id)
        assert len(task_sessions) == 2
        assert session1 in task_sessions
        assert session2 in task_sessions
        assert session3 not in task_sessions


class TestTerminalSession:
    """Test cases for TerminalSession dataclass."""

    def test_session_creation(self):
        """Test creating a TerminalSession."""
        session = TerminalSession(
            session_id="session-123",
            container_id="container-456",
            user_id="user-789",
            task_id="task-abc",
        )

        assert session.session_id == "session-123"
        assert session.container_id == "container-456"
        assert session.user_id == "user-789"
        assert session.task_id == "task-abc"
        assert session.exec_id is None
        assert session.socket is None
        assert session.active is True
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.last_activity, datetime)

    def test_update_activity(self):
        """Test updating session activity timestamp."""
        session = TerminalSession(
            session_id="session-123",
            container_id="container-456",
            user_id="user-789",
            task_id="task-abc",
        )

        original_activity = session.last_activity

        # Wait a tiny bit to ensure timestamp changes
        import time
        time.sleep(0.01)

        session.update_activity()

        assert session.last_activity > original_activity

    def test_is_expired_not_expired(self):
        """Test session is not expired when recently active."""
        session = TerminalSession(
            session_id="session-123",
            container_id="container-456",
            user_id="user-789",
            task_id="task-abc",
        )

        assert not session.is_expired()

    def test_is_expired_old_session(self):
        """Test session is expired when old."""
        session = TerminalSession(
            session_id="session-123",
            container_id="container-456",
            user_id="user-789",
            task_id="task-abc",
        )

        # Manually set last_activity to old timestamp
        from datetime import timedelta
        session.last_activity = datetime.now(timezone.utc) - timedelta(seconds=SESSION_TIMEOUT + 1)

        assert session.is_expired()


class TestCleanupLoop:
    """Test cases for session cleanup background task."""

    @pytest.mark.asyncio
    async def test_cleanup_loop_starts(self, terminal_service):
        """Test that cleanup loop can be started."""
        await terminal_service.start_cleanup_loop()

        assert terminal_service._cleanup_task is not None
        assert not terminal_service._cleanup_task.done()

        # Clean up
        terminal_service._cleanup_task.cancel()
        try:
            await terminal_service._cleanup_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_cleanup_loop_removes_expired_sessions(self, terminal_service):
        """Test that cleanup loop removes expired sessions."""
        from datetime import timedelta

        # Create an expired session
        session_id = "session-123"
        session = TerminalSession(
            session_id=session_id,
            container_id="container-456",
            user_id="user-789",
            task_id="task-abc",
        )
        session.last_activity = datetime.now(timezone.utc) - timedelta(seconds=SESSION_TIMEOUT + 1)
        terminal_service.sessions[session_id] = session

        # Run one iteration of cleanup
        await terminal_service._cleanup_loop.__wrapped__(terminal_service)

        # Session should be removed
        assert session_id not in terminal_service.sessions
