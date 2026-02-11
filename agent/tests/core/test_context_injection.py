"""Tests for orchestrator platform context injection.

The orchestrator injects conversation context (platform, platform_channel_id,
platform_thread_id) into tool call arguments for modules that send proactive
notifications. This test verifies the injection covers all required modules.

Regression context: the location module was missing from the injection check,
so location reminders were created without platform context and notifications
were silently dropped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.schemas.tools import ToolCall

# Path to agent_loop.py (resolved relative to the tests directory)
AGENT_LOOP_PATH = Path(__file__).resolve().parents[2] / "core" / "orchestrator" / "agent_loop.py"


# Modules whose tools need platform/channel context injected by the orchestrator
# for proactive notification delivery via Redis pub/sub.
NOTIFICATION_MODULES = [
    "scheduler.",
    "location.",
]


class TestContextInjectionLogic:
    """Test the platform context injection pattern used in the agent loop."""

    @pytest.mark.parametrize("tool_name", [
        "location.create_reminder",
        "location.list_reminders",
        "location.cancel_reminder",
        "scheduler.add_job",
        "scheduler.list_jobs",
        "scheduler.cancel_job",
    ])
    def test_notification_tools_receive_platform_context(self, tool_name):
        """Tools from notification modules should get platform context injected."""
        tool_call = ToolCall(
            tool_name=tool_name,
            arguments={"some_arg": "value"},
        )

        # This mirrors the injection logic from agent_loop.py
        if tool_call.tool_name.startswith(("scheduler.", "location.")):
            tool_call.arguments["platform"] = "discord"
            tool_call.arguments["platform_channel_id"] = "12345"
            tool_call.arguments["platform_thread_id"] = None

        assert "platform" in tool_call.arguments
        assert "platform_channel_id" in tool_call.arguments

    @pytest.mark.parametrize("tool_name", [
        "research.web_search",
        "file_manager.create_document",
        "knowledge.remember",
        "code_executor.run_python",
    ])
    def test_non_notification_tools_excluded(self, tool_name):
        """Tools from other modules should NOT get platform context."""
        tool_call = ToolCall(
            tool_name=tool_name,
            arguments={"query": "test"},
        )

        if tool_call.tool_name.startswith(("scheduler.", "location.")):
            tool_call.arguments["platform"] = "discord"
            tool_call.arguments["platform_channel_id"] = "12345"
            tool_call.arguments["platform_thread_id"] = None

        assert "platform" not in tool_call.arguments


class TestContextInjectionSourceCode:
    """Verify the actual agent_loop.py source includes all notification modules.

    This is a structural test that reads the source file to verify the
    startswith() tuple includes all required module prefixes. It catches
    the case where a new notification module is added but the injection
    check isn't updated.

    Reads the file directly to avoid needing the full import chain
    (agent_loop imports many heavy dependencies).
    """

    @pytest.fixture
    def agent_loop_source(self):
        """Read agent_loop.py source code."""
        return AGENT_LOOP_PATH.read_text()

    def test_all_notification_modules_in_injection(self, agent_loop_source):
        """All modules that need platform context must appear in agent_loop.py."""
        for prefix in NOTIFICATION_MODULES:
            assert f'"{prefix}"' in agent_loop_source, (
                f'Module prefix "{prefix}" not found in agent_loop.py. '
                f"Tools from this module need platform/channel context for "
                f"notification delivery. Add it to the startswith() tuple "
                f"near the 'Inject conversation context' comment."
            )

    def test_injection_uses_startswith_tuple(self, agent_loop_source):
        """The injection should use a tuple with startswith for multiple modules."""
        # Verify the pattern uses a tuple (not just a single string)
        # This catches cases where someone accidentally overwrites the tuple
        assert "startswith((" in agent_loop_source, (
            "Context injection should use startswith((...)) with a tuple "
            "to support multiple module prefixes."
        )
