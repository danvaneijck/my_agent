"""WebSocket-based real-time log streaming for Claude Code tasks."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import WebSocket, WebSocketDisconnect

from portal.services.module_client import call_tool

logger = structlog.get_logger()

POLL_INTERVAL = 1.5  # seconds between log polls


async def stream_task_logs(websocket: WebSocket, task_id: str) -> None:
    """Stream task logs to a WebSocket client.

    Polls claude_code.task_logs with offset-based pagination to send only
    new lines. Sends status_change when the task finishes. Exits on
    disconnect or terminal task status.
    """
    offset = 0

    try:
        while True:
            try:
                result = await call_tool(
                    module="claude_code",
                    tool_name="claude_code.task_logs",
                    arguments={"task_id": task_id, "tail": 200, "offset": offset},
                    timeout=15.0,
                )
                data = result.get("result", {})
                lines = data.get("lines", [])
                total = data.get("total_lines", 0)
                task_status = data.get("status", "unknown")

                if lines:
                    await websocket.send_json(
                        {
                            "type": "log_lines",
                            "lines": lines,
                            "total_lines": total,
                            "offset": offset,
                            "status": task_status,
                        }
                    )
                    offset += len(lines)

                if task_status in ("completed", "failed", "cancelled", "awaiting_input"):
                    # Fetch final task status for result/error info
                    try:
                        status_result = await call_tool(
                            module="claude_code",
                            tool_name="claude_code.task_status",
                            arguments={"task_id": task_id},
                            timeout=10.0,
                        )
                        task_data = status_result.get("result", {})
                    except Exception:
                        task_data = {}

                    await websocket.send_json(
                        {
                            "type": "status_change",
                            "status": task_status,
                            "result": task_data.get("result"),
                            "error": task_data.get("error"),
                        }
                    )
                    break

                # Send heartbeat even when there are no new lines
                if not lines:
                    await websocket.send_json({"type": "heartbeat"})

            except RuntimeError as e:
                # Tool call failed (e.g. task not found)
                await websocket.send_json(
                    {"type": "error", "message": str(e)}
                )
                break

            await asyncio.sleep(POLL_INTERVAL)

    except WebSocketDisconnect:
        logger.info("log_stream_client_disconnected", task_id=task_id)
