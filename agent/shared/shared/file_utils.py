"""Shared file ingestion utility for communication bots."""

from __future__ import annotations

import io
import uuid

import structlog
from minio import Minio

logger = structlog.get_logger()

# Maximum file upload size: 50 MB
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024

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


def upload_attachment(
    minio_client: Minio,
    bucket: str,
    public_url_base: str,
    raw_bytes: bytes,
    filename: str,
) -> dict:
    """Upload a user-attached file to MinIO (no DB record — core creates that).

    Returns a dict suitable for IncomingMessage.attachments:
        {filename, url, minio_key, mime_type, size_bytes}

    Raises ValueError if file exceeds MAX_UPLOAD_SIZE_BYTES.
    """
    if len(raw_bytes) > MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"File too large: {len(raw_bytes)} bytes "
            f"(max {MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)} MB)"
        )

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

    logger.info("attachment_uploaded", filename=safe_name, size=len(raw_bytes))
    return {
        "filename": safe_name,
        "url": public_url,
        "minio_key": minio_key,
        "mime_type": mime_type,
        "size_bytes": len(raw_bytes),
    }
