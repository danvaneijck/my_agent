"""PostgreSQL-backed installation store for Slack multi-workspace OAuth."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from logging import Logger

from slack_sdk.oauth.installation_store.async_installation_store import (
    AsyncInstallationStore,
)
from slack_sdk.oauth.installation_store.models.bot import Bot
from slack_sdk.oauth.installation_store.models.installation import Installation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from shared.models.slack_installation import SlackInstallation

logger = logging.getLogger(__name__)


class PostgresInstallationStore(AsyncInstallationStore):
    def __init__(
        self,
        client_id: str,
        session_factory: async_sessionmaker,
    ):
        self.client_id = client_id
        self.session_factory = session_factory
        self._logger = logger

    @property
    def logger(self) -> Logger:
        return self._logger

    async def async_save(self, installation: Installation) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(SlackInstallation).where(
                    SlackInstallation.client_id == self.client_id,
                    SlackInstallation.team_id == (installation.team_id or ""),
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.bot_token = installation.bot_token
                existing.bot_id = installation.bot_id
                existing.bot_user_id = installation.bot_user_id
                existing.bot_scopes = ",".join(installation.bot_scopes) if installation.bot_scopes else None
                existing.team_name = installation.team_name
                existing.enterprise_id = installation.enterprise_id
                existing.enterprise_name = installation.enterprise_name
                existing.installed_by_user_id = installation.user_id
                existing.is_enterprise_install = installation.is_enterprise_install or False
                existing.app_id = installation.app_id or ""
                existing.updated_at = datetime.now(timezone.utc)
            else:
                row = SlackInstallation(
                    client_id=self.client_id,
                    app_id=installation.app_id or "",
                    enterprise_id=installation.enterprise_id,
                    enterprise_name=installation.enterprise_name,
                    team_id=installation.team_id or "",
                    team_name=installation.team_name,
                    bot_token=installation.bot_token,
                    bot_id=installation.bot_id,
                    bot_user_id=installation.bot_user_id,
                    bot_scopes=",".join(installation.bot_scopes) if installation.bot_scopes else None,
                    installed_by_user_id=installation.user_id,
                    is_enterprise_install=installation.is_enterprise_install or False,
                )
                session.add(row)

            await session.commit()

    async def async_find_bot(
        self,
        *,
        enterprise_id: str | None = None,
        team_id: str | None = None,
        is_enterprise_install: bool | None = False,
    ) -> Bot | None:
        async with self.session_factory() as session:
            query = select(SlackInstallation).where(
                SlackInstallation.client_id == self.client_id,
            )
            if is_enterprise_install and enterprise_id:
                query = query.where(SlackInstallation.enterprise_id == enterprise_id)
            elif team_id:
                query = query.where(SlackInstallation.team_id == team_id)
            else:
                return None

            query = query.order_by(SlackInstallation.updated_at.desc())
            result = await session.execute(query)
            row = result.scalar_one_or_none()

            if not row:
                return None

            return Bot(
                app_id=row.app_id,
                enterprise_id=row.enterprise_id,
                enterprise_name=row.enterprise_name,
                team_id=row.team_id,
                team_name=row.team_name,
                bot_token=row.bot_token,
                bot_id=row.bot_id,
                bot_user_id=row.bot_user_id,
                bot_scopes=row.bot_scopes,
                is_enterprise_install=row.is_enterprise_install,
                installed_at=row.installed_at.timestamp(),
            )

    async def async_find_installation(
        self,
        *,
        enterprise_id: str | None = None,
        team_id: str | None = None,
        user_id: str | None = None,
        is_enterprise_install: bool | None = False,
    ) -> Installation | None:
        bot = await self.async_find_bot(
            enterprise_id=enterprise_id,
            team_id=team_id,
            is_enterprise_install=is_enterprise_install,
        )
        if not bot:
            return None
        return Installation(
            app_id=bot.app_id,
            enterprise_id=bot.enterprise_id,
            enterprise_name=bot.enterprise_name,
            team_id=bot.team_id,
            team_name=bot.team_name,
            bot_token=bot.bot_token,
            bot_id=bot.bot_id,
            bot_user_id=bot.bot_user_id,
            bot_scopes=bot.bot_scopes,
            is_enterprise_install=bot.is_enterprise_install,
            installed_at=bot.installed_at,
            user_id=user_id or bot.bot_user_id,
        )

    async def async_delete_installation(
        self,
        *,
        enterprise_id: str | None = None,
        team_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(SlackInstallation).where(
                    SlackInstallation.client_id == self.client_id,
                    SlackInstallation.team_id == (team_id or ""),
                )
            )
            row = result.scalar_one_or_none()
            if row:
                await session.delete(row)
                await session.commit()
