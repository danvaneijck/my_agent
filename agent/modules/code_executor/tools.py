"""Code Executor tool implementations."""

from __future__ import annotations

import asyncio
import os
import re
import tempfile

import structlog

logger = structlog.get_logger()

MAX_OUTPUT = 8000  # chars

# Shell commands that are explicitly blocked (destructive / escape risk)
_BLOCKED_SHELL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\brm\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bdd\b"),
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\bkill\b"),
    re.compile(r"\bchmod\b"),
    re.compile(r"\bchown\b"),
    re.compile(r"\bmount\b"),
    re.compile(r"\bumount\b"),
    re.compile(r"\bmkdir\b"),
    re.compile(r"\brmdir\b"),
    re.compile(r"\bmv\b"),
    re.compile(r"\bcp\b"),
    re.compile(r"\bln\b"),
    re.compile(r"\bsudo\b"),
    re.compile(r"\bsu\b"),
    re.compile(r"\bapt\b"),
    re.compile(r"\byum\b"),
    re.compile(r"\bpip\b"),
    re.compile(r"\bnpm\b"),
    re.compile(r"\bdocker\b"),
    re.compile(r"\bsystemctl\b"),
    re.compile(r"\bservice\b"),
    re.compile(r"\biptables\b"),
    re.compile(r">\s*/"),  # redirect to root-level paths
    re.compile(r"\beval\b"),
    re.compile(r"\bexec\b"),
    re.compile(r"\bsource\b"),
    re.compile(r"\bnc\b"),
    re.compile(r"\bncat\b"),
    re.compile(r"\btelnet\b"),
    re.compile(r"\bssh\b"),
]


def _truncate(text: str) -> str:
    if len(text) > MAX_OUTPUT:
        return text[:MAX_OUTPUT] + "\n... [truncated]"
    return text


def _validate_shell_command(command: str) -> str | None:
    """Return an error message if the command is blocked, else None."""
    for pattern in _BLOCKED_SHELL_PATTERNS:
        if pattern.search(command):
            return f"Blocked command pattern: {pattern.pattern}"
    return None


class CodeExecutorTools:
    """Tool implementations for sandboxed code execution."""

    async def run_python(self, code: str, timeout: int = 30) -> dict:
        """Execute Python code in an isolated subprocess."""
        timeout = min(max(timeout, 1), 60)

        # Write code to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir="/tmp"
        ) as f:
            f.write(code)
            script_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": "/tmp",
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout}s",
                    "exit_code": -1,
                }

            stdout = _truncate(stdout_bytes.decode("utf-8", errors="replace"))
            stderr = _truncate(stderr_bytes.decode("utf-8", errors="replace"))

            return {
                "success": proc.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode,
            }
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    async def run_shell(self, command: str, timeout: int = 30) -> dict:
        """Execute a shell command in an isolated subprocess."""
        timeout = min(max(timeout, 1), 60)

        # Validate command
        error = _validate_shell_command(command)
        if error:
            return {
                "success": False,
                "stdout": "",
                "stderr": error,
                "exit_code": -1,
            }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": "/tmp",
                },
                cwd="/tmp",
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Execution timed out after {timeout}s",
                    "exit_code": -1,
                }

            stdout = _truncate(stdout_bytes.decode("utf-8", errors="replace"))
            stderr = _truncate(stderr_bytes.decode("utf-8", errors="replace"))

            return {
                "success": proc.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
            }
