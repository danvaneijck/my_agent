"""Shared file ingestion utility for communication bots."""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone

import structlog
from minio import Minio
from sqlalchemy.ext.asyncio import async_sessionmaker

from shared.models.file import FileRecord

logger = structlog.get_logger()

MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "svg": "image/svg+xml",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "csv": "text/csv",
    "json": "application/json",
    "html": "text/html",
    "txt": "text/plain",
    "md": "text/markdown",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "zip": "application/zip",
    "xml": "application/xml",
    "yaml": "application/x-yaml",
    "yml": "application/x-yaml",
    "py": "text/x-python",
    "js": "text/javascript",
    "ts": "text/typescript",
    "css": "text/css",
    "sql": "application/sql",
    "sh": "text/x-shellscript",
}


async def ingest_attachment(
    minio_client: Minio,
    session_factory: async_sessionmaker,
    bucket: str,
    public_url_base: str,
    raw_bytes: bytes,
    filename: str,
    user_id: str | None,
) -> dict:
    """Upload a user-attached file to MinIO and create a FileRecord.

    Returns a dict suitable for IncomingMessage.attachments:
        {file_id, filename, url, mime_type, size_bytes}
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    mime_type = MIME_MAP.get(ext, "application/octet-stream")

    safe_name = "".join(c if c.isalnum() or c in "-_. " else "" for c in filename)
    safe_name = safe_name.strip().replace(" ", "_") or "file"

    minio_key = f"attachments/{uuid.uuid4().hex[:8]}_{safe_name}"

    # Upload to MinIO
    minio_client.put_object(
        bucket,
        minio_key,
        io.BytesIO(raw_bytes),
        length=len(raw_bytes),
        content_type=mime_type,
    )

    public_url = f"{public_url_base}/{minio_key}"
    uid = uuid.UUID(user_id) if user_id else uuid.UUID("00000000-0000-0000-0000-000000000000")

    file_id = uuid.uuid4()
    async with session_factory() as session:
        record = FileRecord(
            id=file_id,
            user_id=uid,
            filename=safe_name,
            minio_key=minio_key,
            mime_type=mime_type,
            size_bytes=len(raw_bytes),
            public_url=public_url,
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.commit()

    logger.info("attachment_ingested", filename=safe_name, size=len(raw_bytes))
    return {
        "file_id": str(file_id),
        "filename": safe_name,
        "url": public_url,
        "mime_type": mime_type,
        "size_bytes": len(raw_bytes),
    }
