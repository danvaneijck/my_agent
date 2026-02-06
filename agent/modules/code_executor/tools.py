"""Code Executor tool implementations."""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone

import structlog
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from shared.config import Settings
from shared.models.file import FileRecord

logger = structlog.get_logger()

MAX_OUTPUT = 8000  # chars
OUTPUT_DIR = "/tmp/output"

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

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".json": "application/json",
    ".html": "text/html",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".zip": "application/zip",
}


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

    def __init__(self, settings: Settings, session_factory: async_sessionmaker):
        self.settings = settings
        self.session_factory = session_factory
        self.minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        bucket = settings.minio_bucket
        if not self.minio.bucket_exists(bucket):
            self.minio.make_bucket(bucket)

    # File extensions we consider as generated output (not temp/system files)
    _OUTPUT_EXTENSIONS = set(MIME_TYPES.keys())

    def _snapshot_tmp(self) -> set[str]:
        """Record existing files in /tmp before execution."""
        try:
            return {
                f for f in os.listdir("/tmp")
                if os.path.isfile(os.path.join("/tmp", f))
            }
        except OSError:
            return set()

    def _collect_output_files(self, pre_snapshot: set[str]) -> list[dict]:
        """Find new files generated during execution and upload to MinIO.

        Checks both /tmp/output/ (explicit) and /tmp/ (for files with known
        extensions that didn't exist before execution).
        """
        uploaded = []

        # 1. Collect files from /tmp/output/ (explicit saves)
        if os.path.isdir(OUTPUT_DIR):
            for fname in os.listdir(OUTPUT_DIR):
                fpath = os.path.join(OUTPUT_DIR, fname)
                if os.path.isfile(fpath):
                    uploaded.extend(self._upload_file(fpath, fname))

        # 2. Scan /tmp for NEW files with known extensions
        try:
            current_files = set(os.listdir("/tmp"))
        except OSError:
            current_files = set()

        new_files = current_files - pre_snapshot
        for fname in new_files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in self._OUTPUT_EXTENSIONS:
                continue
            fpath = os.path.join("/tmp", fname)
            if os.path.isfile(fpath):
                uploaded.extend(self._upload_file(fpath, fname))

        return uploaded

    def _upload_file(self, fpath: str, fname: str) -> list[dict]:
        """Upload a single file to MinIO. Returns a list with one item, or empty on failure."""
        ext = os.path.splitext(fname)[1].lower()
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        minio_key = f"generated/{uuid.uuid4().hex[:8]}_{fname}"

        try:
            file_size = os.path.getsize(fpath)
            with open(fpath, "rb") as f:
                self.minio.put_object(
                    self.settings.minio_bucket,
                    minio_key,
                    f,
                    length=file_size,
                    content_type=mime,
                )
            url = f"{self.settings.minio_public_url}/{minio_key}"
            logger.info("output_file_uploaded", filename=fname, size=file_size)
            return [{
                "filename": fname,
                "url": url,
                "size_bytes": file_size,
                "mime_type": mime,
                "minio_key": minio_key,
            }]
        except Exception as e:
            logger.warning("output_file_upload_failed", filename=fname, error=str(e))
            return []
        finally:
            try:
                os.unlink(fpath)
            except OSError:
                pass

    async def _register_file_records(self, files: list[dict], user_id: str | None) -> None:
        """Create FileRecord entries so generated files appear in file_manager.list_files."""
        if not files:
            return

        uid = uuid.UUID(user_id) if user_id else uuid.UUID("00000000-0000-0000-0000-000000000000")

        try:
            async with self.session_factory() as session:
                for f in files:
                    record = FileRecord(
                        id=uuid.uuid4(),
                        user_id=uid,
                        filename=f["filename"],
                        minio_key=f["minio_key"],
                        mime_type=f.get("mime_type"),
                        size_bytes=f.get("size_bytes"),
                        public_url=f["url"],
                        created_at=datetime.now(timezone.utc),
                    )
                    session.add(record)
                await session.commit()
            logger.info("file_records_registered", count=len(files))
        except Exception as e:
            logger.error("file_record_registration_failed", error=str(e))

    def _clean_output_dir(self):
        """Ensure output dir exists and is empty before execution."""
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        for fname in os.listdir(OUTPUT_DIR):
            try:
                os.unlink(os.path.join(OUTPUT_DIR, fname))
            except OSError:
                pass

    async def load_file(self, file_id: str) -> dict:
        """Download a file from the file manager into /tmp so Python code can use it."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(FileRecord).where(FileRecord.id == uuid.UUID(file_id))
            )
            record = result.scalar_one_or_none()
            if not record:
                raise ValueError(f"File not found: {file_id}")

        # Download from MinIO into /tmp
        local_path = f"/tmp/{record.filename}"
        resp = self.minio.get_object(self.settings.minio_bucket, record.minio_key)
        try:
            with open(local_path, "wb") as f:
                for chunk in resp.stream(8192):
                    f.write(chunk)
        finally:
            resp.close()
            resp.release_conn()

        logger.info("file_loaded", file_id=file_id, filename=record.filename, path=local_path)
        return {
            "file_id": str(record.id),
            "filename": record.filename,
            "local_path": local_path,
            "size_bytes": record.size_bytes,
            "mime_type": record.mime_type,
        }

    async def run_python(self, code: str, timeout: int = 30, user_id: str | None = None) -> dict:
        """Execute Python code in an isolated subprocess."""
        timeout = min(max(timeout, 1), 60)

        self._clean_output_dir()
        pre_snapshot = self._snapshot_tmp()

        # Write code to a temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir="/tmp"
        ) as f:
            f.write(code)
            script_path = f.name

        # Add the script itself to the snapshot so it's not treated as output
        pre_snapshot.add(os.path.basename(script_path))

        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": "/tmp",
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "MPLBACKEND": "Agg",
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
                    "files": [],
                }

            stdout = _truncate(stdout_bytes.decode("utf-8", errors="replace"))
            stderr = _truncate(stderr_bytes.decode("utf-8", errors="replace"))

            # Upload files from /tmp/output/ AND any new files in /tmp with known extensions
            files = self._collect_output_files(pre_snapshot)

            # Register files in the DB so they appear in file_manager.list_files
            await self._register_file_records(files, user_id)

            # Append file URLs to stdout so the LLM always sees them
            if files:
                file_lines = "\n\n--- Generated Files ---\n"
                for f in files:
                    file_lines += f"[{f['filename']}]({f['url']})\n"
                stdout = stdout + file_lines

            return {
                "success": proc.returncode == 0,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": proc.returncode,
                "files": files,
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
