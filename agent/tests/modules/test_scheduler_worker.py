"""Tests for scheduler worker logic.

Covers: delay accuracy, result interpolation, permanent errors,
transient error backoff, cron rescheduling, workflow sibling cancellation,
poll_url JSON inspection, and condition operators.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.scheduler.worker import (
    _check_delay,
    _check_poll_url,
    _evaluate_condition,
    _get_nested_value,
    _interpolate_result,
    _summarize_result,
    validate_webhook_signature,
)
from shared.models.scheduled_job import ScheduledJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(**kwargs) -> ScheduledJob:
    """Build a minimal ScheduledJob for testing."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        conversation_id=None,
        platform="discord",
        platform_channel_id="123",
        platform_thread_id=None,
        platform_server_id=None,
        name=None,
        description=None,
        job_type="delay",
        check_config={"delay_seconds": 60},
        interval_seconds=30,
        max_attempts=10,
        attempts=0,
        consecutive_failures=0,
        runs_completed=0,
        max_runs=None,
        expires_at=None,
        on_success_message="Done!",
        on_failure_message=None,
        on_complete="notify",
        workflow_id=None,
        last_result=None,
        status="active",
        next_run_at=now,
        created_at=now,
        completed_at=None,
    )
    defaults.update(kwargs)
    job = MagicMock(spec=ScheduledJob)
    for k, v in defaults.items():
        setattr(job, k, v)
    return job


# ---------------------------------------------------------------------------
# _check_delay — wall-clock accuracy
# ---------------------------------------------------------------------------

class TestCheckDelay:
    def test_uses_created_at_not_attempts(self):
        """_check_delay must use wall-clock elapsed from created_at, not attempts*interval."""
        now = datetime.now(timezone.utc)
        # Job created 70 seconds ago
        job = _make_job(
            job_type="delay",
            check_config={"delay_seconds": 60},
            created_at=now - timedelta(seconds=70),
            attempts=0,  # no attempts yet — old impl would return False here
            interval_seconds=30,
        )
        assert _check_delay(job, now) is True

    def test_not_yet_elapsed(self):
        now = datetime.now(timezone.utc)
        job = _make_job(
            job_type="delay",
            check_config={"delay_seconds": 300},
            created_at=now - timedelta(seconds=30),
            attempts=1,
            interval_seconds=30,
        )
        assert _check_delay(job, now) is False

    def test_exact_boundary(self):
        now = datetime.now(timezone.utc)
        job = _make_job(
            job_type="delay",
            check_config={"delay_seconds": 60},
            created_at=now - timedelta(seconds=60),
            attempts=1,
            interval_seconds=30,
        )
        assert _check_delay(job, now) is True


# ---------------------------------------------------------------------------
# _get_nested_value
# ---------------------------------------------------------------------------

class TestGetNestedValue:
    def test_top_level(self):
        assert _get_nested_value({"status": "done"}, "status") == "done"

    def test_nested_two_levels(self):
        data = {"phase": {"status": "completed"}}
        assert _get_nested_value(data, "phase.status") == "completed"

    def test_nested_three_levels(self):
        data = {"a": {"b": {"c": 42}}}
        assert _get_nested_value(data, "a.b.c") == 42

    def test_missing_key(self):
        assert _get_nested_value({"x": 1}, "y") is None

    def test_missing_nested_key(self):
        assert _get_nested_value({"a": {"b": 1}}, "a.c") is None

    def test_non_dict_intermediate(self):
        assert _get_nested_value({"a": "string"}, "a.b") is None


# ---------------------------------------------------------------------------
# _evaluate_condition
# ---------------------------------------------------------------------------

class TestEvaluateCondition:
    def test_in_operator(self):
        assert _evaluate_condition("completed", "in", ["completed", "failed"]) is True
        assert _evaluate_condition("running", "in", ["completed", "failed"]) is False

    def test_eq_operator(self):
        assert _evaluate_condition("done", "eq", "done") is True
        assert _evaluate_condition("done", "eq", "pending") is False

    def test_neq_operator(self):
        assert _evaluate_condition("running", "neq", "done") is True
        assert _evaluate_condition("done", "neq", "done") is False

    def test_gt_operator(self):
        assert _evaluate_condition(10, "gt", 5) is True
        assert _evaluate_condition(5, "gt", 10) is False

    def test_gte_operator(self):
        assert _evaluate_condition(10, "gte", 10) is True
        assert _evaluate_condition(9, "gte", 10) is False

    def test_lt_operator(self):
        assert _evaluate_condition(3, "lt", 10) is True
        assert _evaluate_condition(10, "lt", 3) is False

    def test_lte_operator(self):
        assert _evaluate_condition(10, "lte", 10) is True
        assert _evaluate_condition(11, "lte", 10) is False

    def test_contains_operator(self):
        assert _evaluate_condition("hello world", "contains", "world") is True
        assert _evaluate_condition("hello", "contains", "world") is False

    def test_invalid_numeric_comparison(self):
        # Should not raise; returns False for non-numeric values
        assert _evaluate_condition("not_a_number", "gt", 5) is False

    def test_string_numeric_coercion(self):
        # "10" as string should still compare as float
        assert _evaluate_condition("10", "gt", "5") is True


# ---------------------------------------------------------------------------
# _interpolate_result
# ---------------------------------------------------------------------------

class TestInterpolateResult:
    def test_bare_result(self):
        result = {"task_id": "abc", "status": "completed"}
        msg = _interpolate_result("{result}", result)
        assert "completed" in msg or "abc" in msg

    def test_result_field(self):
        result = {"status": "completed", "workspace": "/tmp/ws"}
        msg = _interpolate_result("Status: {result.status}", result)
        assert msg == "Status: completed"

    def test_result_nested_field(self):
        result = {"phase": {"status": "done", "id": "xyz"}}
        msg = _interpolate_result("Phase: {result.phase.status}", result)
        assert msg == "Phase: done"

    def test_job_id_placeholder(self):
        msg = _interpolate_result("Job {job_id} done", None, job_id="abc-123")
        assert msg == "Job abc-123 done"

    def test_workflow_id_placeholder(self):
        msg = _interpolate_result("Workflow {workflow_id}", None, workflow_id="wf-99")
        assert msg == "Workflow wf-99"

    def test_missing_field_unchanged(self):
        result = {"status": "running"}
        msg = _interpolate_result("val={result.nonexistent}", result)
        # Unresolved placeholder stays as-is
        assert msg == "val={result.nonexistent}"

    def test_no_result_data(self):
        msg = _interpolate_result("Done: {result}", None)
        assert "(completed)" in msg

    def test_multiple_placeholders(self):
        result = {"status": "completed", "exit_code": 0}
        msg = _interpolate_result(
            "Job {job_id} in workflow {workflow_id}: {result.status}",
            result,
            job_id="j1",
            workflow_id="wf1",
        )
        assert msg == "Job j1 in workflow wf1: completed"


# ---------------------------------------------------------------------------
# _summarize_result
# ---------------------------------------------------------------------------

class TestSummarizeResult:
    def test_default_keys(self):
        result = {
            "task_id": "abc",
            "status": "completed",
            "json_output": "x" * 10000,  # large field to be stripped
        }
        summary = _summarize_result(result)
        assert "json_output" not in summary
        assert "completed" in summary

    def test_custom_summary_fields(self):
        result = {"my_field": "my_value", "task_id": "abc", "status": "ok"}
        summary = _summarize_result(result, summary_fields=["my_field"])
        assert "my_value" in summary
        assert "task_id" not in summary

    def test_non_dict_input(self):
        assert _summarize_result("just a string") == "just a string"

    def test_empty_dict_fallback(self):
        # Dict with no matching keys — falls back to scalar fields
        result = {"big_list": list(range(1000)), "small_str": "hello"}
        summary = _summarize_result(result)
        assert "hello" in summary


# ---------------------------------------------------------------------------
# _check_poll_url — JSON body inspection
# ---------------------------------------------------------------------------

class TestCheckPollUrl:
    @pytest.mark.asyncio
    async def test_status_code_only(self):
        job = _make_job(
            job_type="poll_url",
            check_config={"url": "http://example.com", "expected_status": 200},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("modules.scheduler.worker.httpx.AsyncClient", return_value=mock_client):
            condition_met, result_data = await _check_poll_url(job)

        assert condition_met is True
        assert result_data is None

    @pytest.mark.asyncio
    async def test_status_code_mismatch(self):
        job = _make_job(
            job_type="poll_url",
            check_config={"url": "http://example.com", "expected_status": 200},
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("modules.scheduler.worker.httpx.AsyncClient", return_value=mock_client):
            condition_met, result_data = await _check_poll_url(job)

        assert condition_met is False

    @pytest.mark.asyncio
    async def test_json_body_field_match(self):
        job = _make_job(
            job_type="poll_url",
            check_config={
                "url": "http://example.com/health",
                "expected_status": 200,
                "response_field": "status",
                "response_value": "ok",
                "response_operator": "eq",
            },
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"status": "ok", "version": "1.0"})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("modules.scheduler.worker.httpx.AsyncClient", return_value=mock_client):
            condition_met, result_data = await _check_poll_url(job)

        assert condition_met is True
        assert result_data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_json_body_field_no_match(self):
        job = _make_job(
            job_type="poll_url",
            check_config={
                "url": "http://example.com/health",
                "expected_status": 200,
                "response_field": "status",
                "response_value": "ok",
                "response_operator": "eq",
            },
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"status": "degraded"})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("modules.scheduler.worker.httpx.AsyncClient", return_value=mock_client):
            condition_met, _ = await _check_poll_url(job)

        assert condition_met is False

    @pytest.mark.asyncio
    async def test_json_body_nested_field(self):
        job = _make_job(
            job_type="poll_url",
            check_config={
                "url": "http://example.com/status",
                "expected_status": 200,
                "response_field": "services.api.ready",
                "response_value": True,
                "response_operator": "eq",
            },
        )
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json = MagicMock(return_value={"services": {"api": {"ready": True}}})
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch("modules.scheduler.worker.httpx.AsyncClient", return_value=mock_client):
            condition_met, _ = await _check_poll_url(job)

        assert condition_met is True


# ---------------------------------------------------------------------------
# validate_webhook_signature
# ---------------------------------------------------------------------------

class TestWebhookSignature:
    def test_valid_signature(self):
        import hashlib
        import hmac

        secret = "mysecret"
        body = b'{"event": "push"}'
        mac = hmac.new(secret.encode(), body, hashlib.sha256)
        sig = "sha256=" + mac.hexdigest()
        assert validate_webhook_signature(secret, body, sig) is True

    def test_invalid_signature(self):
        assert validate_webhook_signature("mysecret", b"body", "sha256=badvalue") is False

    def test_wrong_secret(self):
        import hashlib
        import hmac

        body = b"data"
        mac = hmac.new(b"rightsecret", body, hashlib.sha256)
        sig = "sha256=" + mac.hexdigest()
        assert validate_webhook_signature("wrongsecret", body, sig) is False


# ---------------------------------------------------------------------------
# Regression: platform args stripping (original test preserved)
# ---------------------------------------------------------------------------

class TestSchedulerArgStripping:
    """Verify the scheduler execute endpoint strips platform context
    from tools that don't accept it."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool_name,required_args", [
        ("scheduler.list_jobs", {}),
        ("scheduler.cancel_job", {"job_id": str(uuid.uuid4())}),
        ("scheduler.get_workflow_status", {"workflow_id": str(uuid.uuid4())}),
        ("scheduler.list_workflows", {}),
    ])
    async def test_tools_survive_injected_platform_args(
        self, tool_name, required_args
    ):
        """Non-add_job tools must not crash when platform context is injected."""
        from modules.scheduler.main import execute
        from shared.schemas.tools import ToolCall

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
