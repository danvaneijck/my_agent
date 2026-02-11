"""Tests for the scheduler module execute endpoint — platform context handling.

REGRESSION: the orchestrator injects platform/channel/thread into ALL
scheduler.* tool calls, but only add_job accepts them. Other tools
(list_jobs, cancel_job) crashed with 'unexpected keyword argument'.
"""

from __future__ import annotations

import uuid

import pytest

from shared.schemas.tools import ToolCall


class TestSchedulerArgStripping:
    """Verify the scheduler execute endpoint strips platform context
    from tools that don't accept it."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,required_args", [
        ("scheduler.list_jobs", {}),
        ("scheduler.cancel_job", {"job_id": str(uuid.uuid4())}),
    ])
    async def test_tools_survive_injected_platform_args(
        self, tool_name, required_args
    ):
        """Non-add_job tools must not crash when platform context is injected."""
        from modules.scheduler.main import execute

        call = ToolCall(
            tool_name=tool_name,
            arguments={
                **required_args,
                "platform": "discord",
                "platform_channel_id": "123456",
                "platform_thread_id": None,
            },
            user_id=str(uuid.uuid4()),
        )

        result = await execute(call)

        # May fail for other reasons (no DB), but NOT for unexpected kwargs
        assert "unexpected keyword argument" not in (result.error or "")
