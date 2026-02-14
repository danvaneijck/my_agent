"""Encrypted credential storage backed by the user_credentials table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.user_credential import UserCredential


class CredentialStore:
    """Encrypt/decrypt user credentials with Fernet, backed by user_credentials table."""

    def __init__(self, encryption_key: str) -> None:
        if not encryption_key:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY must be set. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        self.fernet = Fernet(encryption_key.encode())

    def _encrypt(self, value: str) -> str:
        return self.fernet.encrypt(value.encode()).decode()

    def _decrypt(self, token: str) -> str:
        return self.fernet.decrypt(token.encode()).decode()

    async def get(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        service: str,
        key: str,
    ) -> str | None:
        """Decrypt and return a single credential value, or None."""
        result = await session.execute(
            select(UserCredential).where(
                UserCredential.user_id == user_id,
                UserCredential.service == service,
                UserCredential.credential_key == key,
            )
        )
        cred = result.scalar_one_or_none()
        if cred is None:
            return None
        return self._decrypt(cred.encrypted_value)

    async def get_all(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        service: str,
    ) -> dict[str, str]:
        """Get all decrypted credentials for a service. Returns {key: value}."""
        result = await session.execute(
            select(UserCredential).where(
                UserCredential.user_id == user_id,
                UserCredential.service == service,
            )
        )
        creds = result.scalars().all()
        return {c.credential_key: self._decrypt(c.encrypted_value) for c in creds}

    async def set(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        service: str,
        key: str,
        value: str,
    ) -> None:
        """Encrypt and upsert a credential."""
        result = await session.execute(
            select(UserCredential).where(
                UserCredential.user_id == user_id,
                UserCredential.service == service,
                UserCredential.credential_key == key,
            )
        )
        existing = result.scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if existing:
            existing.encrypted_value = self._encrypt(value)
            existing.updated_at = now
        else:
            session.add(
                UserCredential(
                    user_id=user_id,
                    service=service,
                    credential_key=key,
                    encrypted_value=self._encrypt(value),
                    created_at=now,
                    updated_at=now,
                )
            )
        await session.commit()

    async def set_many(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        service: str,
        credentials: dict[str, str],
    ) -> None:
        """Encrypt and upsert multiple credentials for a service."""
        now = datetime.now(timezone.utc)
        for key, value in credentials.items():
            result = await session.execute(
                select(UserCredential).where(
                    UserCredential.user_id == user_id,
                    UserCredential.service == service,
                    UserCredential.credential_key == key,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                existing.encrypted_value = self._encrypt(value)
                existing.updated_at = now
            else:
                session.add(
                    UserCredential(
                        user_id=user_id,
                        service=service,
                        credential_key=key,
                        encrypted_value=self._encrypt(value),
                        created_at=now,
                        updated_at=now,
                    )
                )
        await session.commit()

    async def delete(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        service: str,
        key: str | None = None,
    ) -> int:
        """Delete one key or all keys for a service. Returns count deleted."""
        stmt = delete(UserCredential).where(
            UserCredential.user_id == user_id,
            UserCredential.service == service,
        )
        if key is not None:
            stmt = stmt.where(UserCredential.credential_key == key)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount  # type: ignore[return-value]

    async def list_services(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
    ) -> list[dict]:
        """List services with configured credentials (no values returned).

        Returns: [{service, keys: [str], configured_at: str}]
        """
        result = await session.execute(
            select(UserCredential).where(UserCredential.user_id == user_id)
        )
        creds = result.scalars().all()

        services: dict[str, dict] = {}
        for c in creds:
            if c.service not in services:
                services[c.service] = {
                    "service": c.service,
                    "keys": [],
                    "configured_at": c.updated_at.isoformat(),
                }
            services[c.service]["keys"].append(c.credential_key)
            # Use the most recent updated_at
            if c.updated_at.isoformat() > services[c.service]["configured_at"]:
                services[c.service]["configured_at"] = c.updated_at.isoformat()

        return list(services.values())
