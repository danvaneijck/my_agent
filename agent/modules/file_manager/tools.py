"""File Manager tool implementations."""

from __future__ import annotations

import io
import json
import uuid
from datetime import datetime, timezone

import structlog
from minio import Minio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import Settings
from shared.models.file import FileRecord

logger = structlog.get_logger()

MIME_TYPES = {
    "md": "text/markdown",
    "txt": "text/plain",
    "json": "application/json",
    "csv": "text/csv",
}

# MinIO anonymous read policy for the bucket
_PUBLIC_READ_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"AWS": ["*"]},
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::{bucket}/*"],
        }
    ],
}


class FileManagerTools:
    """Tool implementations for file management with MinIO."""

    def __init__(self, settings: Settings, session_factory):
        self.settings = settings
        self.session_factory = session_factory
        self.minio = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=False,
        )
        # Ensure bucket exists with public-read policy
        bucket = settings.minio_bucket
        if not self.minio.bucket_exists(bucket):
            self.minio.make_bucket(bucket)
        policy = json.loads(json.dumps(_PUBLIC_READ_POLICY).replace("{bucket}", bucket))
        self.minio.set_bucket_policy(bucket, json.dumps(policy))

    async def create_document(
        self,
        title: str,
        content: str,
        format: str = "md",
        user_id: str | None = None,
    ) -> dict:
        """Create a document and store it in MinIO."""
        file_ext = format if format in MIME_TYPES else "md"
        mime_type = MIME_TYPES.get(file_ext, "text/plain")

        # Sanitize filename
        safe_title = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
        safe_title = safe_title.strip().replace(" ", "_")
        if not safe_title:
            safe_title = "document"

        filename = f"{safe_title}.{file_ext}"
        minio_key = f"documents/{uuid.uuid4().hex[:8]}_{filename}"

        # Upload to MinIO
        data = content.encode("utf-8")
        self.minio.put_object(
            self.settings.minio_bucket,
            minio_key,
            io.BytesIO(data),
            length=len(data),
            content_type=mime_type,
        )

        public_url = f"{self.settings.minio_public_url}/{minio_key}"

        # Resolve user_id
        uid = uuid.UUID(user_id) if user_id else uuid.UUID("00000000-0000-0000-0000-000000000000")

        # Save record in database
        file_id = uuid.uuid4()
        async with self.session_factory() as session:
            record = FileRecord(
                id=file_id,
                user_id=uid,
                filename=filename,
                minio_key=minio_key,
                mime_type=mime_type,
                size_bytes=len(data),
                public_url=public_url,
                created_at=datetime.now(timezone.utc),
            )
            session.add(record)
            await session.commit()

        logger.info("file_created", filename=filename, size=len(data))
        return {
            "file_id": str(file_id),
            "filename": filename,
            "url": public_url,
            "size_bytes": len(data),
        }

    async def read_document(self, file_id: str) -> dict:
        """Read the contents of a stored document."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(FileRecord).where(FileRecord.id == uuid.UUID(file_id))
            )
            record = result.scalar_one_or_none()
            if not record:
                raise ValueError(f"File not found: {file_id}")

            # Download from MinIO
            response = self.minio.get_object(self.settings.minio_bucket, record.minio_key)
            try:
                content = response.read().decode("utf-8")
            finally:
                response.close()
                response.release_conn()

            # Truncate very large files to avoid blowing up context
            if len(content) > 10000:
                content = content[:10000] + "\n... [truncated at 10000 chars]"

            return {
                "file_id": str(record.id),
                "filename": record.filename,
                "content": content,
                "size_bytes": record.size_bytes,
            }

    async def list_files(self, user_id: str | None = None) -> list[dict]:
        """List files, optionally filtered by user."""
        async with self.session_factory() as session:
            query = select(FileRecord).order_by(FileRecord.created_at.desc())
            if user_id:
                query = query.where(FileRecord.user_id == uuid.UUID(user_id))

            result = await session.execute(query.limit(50))
            records = result.scalars().all()

            return [
                {
                    "file_id": str(r.id),
                    "filename": r.filename,
                    "url": r.public_url,
                    "size_bytes": r.size_bytes,
                    "created_at": r.created_at.isoformat(),
                }
                for r in records
            ]

    async def get_file_link(self, file_id: str) -> dict:
        """Get the public URL for a file."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(FileRecord).where(FileRecord.id == uuid.UUID(file_id))
            )
            record = result.scalar_one_or_none()
            if not record:
                raise ValueError(f"File not found: {file_id}")

            return {
                "file_id": str(record.id),
                "filename": record.filename,
                "url": record.public_url,
            }

    async def delete_file(self, file_id: str) -> dict:
        """Delete a file from MinIO and its database record."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(FileRecord).where(FileRecord.id == uuid.UUID(file_id))
            )
            record = result.scalar_one_or_none()
            if not record:
                raise ValueError(f"File not found: {file_id}")

            # Delete from MinIO
            try:
                self.minio.remove_object(self.settings.minio_bucket, record.minio_key)
            except Exception as e:
                logger.warning("minio_delete_error", error=str(e))

            # Delete database record
            await session.delete(record)
            await session.commit()

            logger.info("file_deleted", file_id=file_id)
            return {"file_id": file_id, "deleted": True}
