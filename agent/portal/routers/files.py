"""File manager proxy endpoints."""

from __future__ import annotations

import base64
import uuid

import structlog
from fastapi import APIRouter, Depends, Header, Query, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from minio import Minio

from portal.auth import PortalUser, require_auth, _decode_token
from portal.services.module_client import call_tool
from shared.config import get_settings
from shared.database import get_session_factory
from shared.models.file import FileRecord
from sqlalchemy import select

logger = structlog.get_logger()

router = APIRouter(prefix="/api/files", tags=["files"])


def _get_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )


@router.get("")
async def list_files(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List files for the authenticated user, including mime_type."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(FileRecord)
            .where(FileRecord.user_id == user.user_id)
            .order_by(FileRecord.created_at.desc())
            .limit(50)
        )
        records = result.scalars().all()

    return {
        "files": [
            {
                "file_id": str(r.id),
                "filename": r.filename,
                "mime_type": r.mime_type,
                "size_bytes": r.size_bytes,
                "public_url": r.public_url,
                "created_at": r.created_at.isoformat(),
            }
            for r in records
        ]
    }


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Upload a file via multipart form."""
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"File too large (max {MAX_UPLOAD_SIZE // (1024 * 1024)} MB)")
    b64 = base64.b64encode(content).decode()

    result = await call_tool(
        module="file_manager",
        tool_name="file_manager.upload_file",
        arguments={
            "filename": file.filename or "upload",
            "base64_content": b64,
        },
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.get("/{file_id}")
async def get_file(
    file_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get file metadata. For text files, also includes content."""
    result = await call_tool(
        module="file_manager",
        tool_name="file_manager.read_document",
        arguments={"file_id": file_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    token: str | None = Query(None),
    inline: bool = Query(False),
    authorization: str | None = Header(None),
) -> StreamingResponse:
    """Stream a file from MinIO.

    Supports auth via Authorization header (normal API calls) or
    ?token=<jwt> query param (for <img> tags and direct browser links).
    Use ?inline=1 to serve for preview instead of as an attachment.
    """
    # Authenticate via header or query param
    jwt_token = None
    if authorization and authorization.startswith("Bearer "):
        jwt_token = authorization[7:]
    elif token:
        jwt_token = token
    if not jwt_token:
        raise HTTPException(401, "Missing authentication")
    user = _decode_token(jwt_token)

    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        record = await session.execute(
            select(FileRecord).where(
                FileRecord.id == uuid.UUID(file_id),
                FileRecord.user_id == user.user_id,
            )
        )
        file_record = record.scalar_one_or_none()
        if not file_record:
            return StreamingResponse(
                iter([b"File not found"]),
                status_code=404,
                media_type="text/plain",
            )

    client = _get_minio_client()
    response = client.get_object(settings.minio_bucket, file_record.minio_key)

    disposition = "inline" if inline else "attachment"
    return StreamingResponse(
        response.stream(32 * 1024),
        media_type=file_record.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'{disposition}; filename="{file_record.filename}"'
        },
    )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a file."""
    result = await call_tool(
        module="file_manager",
        tool_name="file_manager.delete_file",
        arguments={"file_id": file_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})
