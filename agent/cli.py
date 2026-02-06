"""Admin CLI for the AI agent system."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import click

# Ensure shared package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "shared"))


def run_async(coro):
    """Run an async function in a new event loop."""
    return asyncio.run(coro)


@click.group()
def cli():
    """AI Agent System administration CLI."""
    pass


# --- Setup ---


@cli.command()
def setup():
    """Run migrations, create MinIO bucket, and create default persona."""
    click.echo("Running database migrations...")
    _run_migrations()

    click.echo("Creating MinIO bucket if not exists...")
    _create_minio_bucket()

    click.echo("Creating default persona if none exists...")
    run_async(_create_default_persona())

    click.echo("Setup complete.")


def _run_migrations():
    """Run Alembic migrations using the Python API."""
    from alembic import command
    from alembic.config import Config

    # Look for alembic.ini in /app (Docker) or alongside this script (local)
    for candidate in ["/app/alembic.ini", os.path.join(os.path.dirname(__file__), "alembic.ini")]:
        if os.path.exists(candidate):
            alembic_cfg = Config(candidate)
            # Override script_location to an absolute path if running from /app
            script_dir = os.path.join(os.path.dirname(candidate), "alembic")
            if os.path.isdir(script_dir):
                alembic_cfg.set_main_option("script_location", script_dir)
            # Override DB URL from env if available
            db_url = os.environ.get("DATABASE_URL")
            if db_url:
                alembic_cfg.set_main_option("sqlalchemy.url", db_url)
            command.upgrade(alembic_cfg, "head")
            return

    click.echo("  Warning: alembic.ini not found, skipping migrations.")


def _create_minio_bucket():
    """Create the MinIO bucket if it doesn't exist."""
    try:
        from minio import Minio

        endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
        access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.environ.get("MINIO_SECRET_KEY", "changeme")
        bucket = os.environ.get("MINIO_BUCKET", "agent-files")

        client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False,
        )
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            click.echo(f"  Created bucket: {bucket}")
        else:
            click.echo(f"  Bucket already exists: {bucket}")
    except Exception as e:
        click.echo(f"  Warning: Could not create MinIO bucket: {e}")


async def _create_default_persona():
    """Create a default persona if none exists."""
    from sqlalchemy import select

    from shared.database import get_engine, get_session_factory
    from shared.models.persona import Persona

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(Persona).where(Persona.is_default.is_(True))
        )
        existing = result.scalar_one_or_none()
        if existing:
            click.echo(f"  Default persona already exists: {existing.name}")
            await get_engine().dispose()
            return

        persona = Persona(
            id=uuid.uuid4(),
            name="Default Assistant",
            system_prompt=(
                "You are a helpful AI assistant. You can use various tools to help "
                "users with research, file management, and other tasks. Be concise, "
                "accurate, and helpful. If you're unsure about something, say so."
            ),
            allowed_modules=json.dumps(["research", "file_manager"]),
            is_default=True,
            created_at=datetime.now(timezone.utc),
        )
        session.add(persona)
        await session.commit()
        click.echo(f"  Created default persona: {persona.name}")

    await get_engine().dispose()


# --- User Management ---


@cli.group()
def user():
    """User management commands."""
    pass


@user.command("create-owner")
@click.option("--discord-id", default=None, help="Discord user ID")
@click.option("--telegram-id", default=None, help="Telegram user ID")
@click.option("--slack-id", default=None, help="Slack user ID")
def create_owner(discord_id, telegram_id, slack_id):
    """Create an owner user with platform links."""
    if not any([discord_id, telegram_id, slack_id]):
        click.echo("Error: At least one platform ID is required.")
        return
    run_async(_create_owner(discord_id, telegram_id, slack_id))


async def _create_owner(discord_id, telegram_id, slack_id):
    from shared.database import get_engine, get_session_factory
    from shared.models.user import User, UserPlatformLink

    session_factory = get_session_factory()
    async with session_factory() as session:
        user = User(
            id=uuid.uuid4(),
            permission_level="owner",
            token_budget_monthly=None,  # unlimited
            budget_reset_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        session.add(user)

        platform_ids = [
            ("discord", discord_id),
            ("telegram", telegram_id),
            ("slack", slack_id),
        ]
        for platform, pid in platform_ids:
            if pid:
                link = UserPlatformLink(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    platform=platform,
                    platform_user_id=pid,
                )
                session.add(link)

        await session.commit()
        click.echo(f"Created owner user: {user.id}")
        for platform, pid in platform_ids:
            if pid:
                click.echo(f"  Linked {platform}: {pid}")

    engine = get_engine()
    await engine.dispose()


@user.command("promote")
@click.option("--platform", required=True, type=click.Choice(["discord", "telegram", "slack"]))
@click.option("--platform-id", required=True, help="Platform user ID")
@click.option("--level", required=True, type=click.Choice(["admin", "user", "guest"]))
def promote(platform, platform_id, level):
    """Change a user's permission level."""
    run_async(_promote(platform, platform_id, level))


async def _promote(platform, platform_id, level):
    from sqlalchemy import select

    from shared.database import get_engine, get_session_factory
    from shared.models.user import User, UserPlatformLink

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(UserPlatformLink).where(
                UserPlatformLink.platform == platform,
                UserPlatformLink.platform_user_id == platform_id,
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            click.echo(f"Error: No user found for {platform}:{platform_id}")
            return

        result = await session.execute(select(User).where(User.id == link.user_id))
        user = result.scalar_one()
        user.permission_level = level
        await session.commit()
        click.echo(f"User {user.id} promoted to {level}")

    engine = get_engine()
    await engine.dispose()


@user.command("set-budget")
@click.option("--platform", required=True, type=click.Choice(["discord", "telegram", "slack"]))
@click.option("--platform-id", required=True, help="Platform user ID")
@click.option("--tokens", required=True, type=int, help="Monthly token budget")
def set_budget(platform, platform_id, tokens):
    """Set monthly token budget for a user."""
    run_async(_set_budget(platform, platform_id, tokens))


async def _set_budget(platform, platform_id, tokens):
    from sqlalchemy import select

    from shared.database import get_engine, get_session_factory
    from shared.models.user import User, UserPlatformLink

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(UserPlatformLink).where(
                UserPlatformLink.platform == platform,
                UserPlatformLink.platform_user_id == platform_id,
            )
        )
        link = result.scalar_one_or_none()
        if not link:
            click.echo(f"Error: No user found for {platform}:{platform_id}")
            return

        result = await session.execute(select(User).where(User.id == link.user_id))
        user = result.scalar_one()
        user.token_budget_monthly = tokens
        await session.commit()
        click.echo(f"User {user.id} budget set to {tokens} tokens/month")

    engine = get_engine()
    await engine.dispose()


@user.command("list")
def list_users():
    """List all users with platform links and permission levels."""
    run_async(_list_users())


async def _list_users():
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from shared.database import get_engine, get_session_factory
    from shared.models.user import User

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(User).options(selectinload(User.platform_links))
        )
        users = result.scalars().all()

        if not users:
            click.echo("No users found.")
            return

        for u in users:
            budget = u.token_budget_monthly or "unlimited"
            click.echo(
                f"User {u.id} | {u.permission_level} | "
                f"Budget: {budget} | Used: {u.tokens_used_this_month}"
            )
            for link in u.platform_links:
                click.echo(
                    f"  {link.platform}: {link.platform_user_id}"
                    f" ({link.platform_username or 'no username'})"
                )

    engine = get_engine()
    await engine.dispose()


# --- Persona Management ---


@cli.group()
def persona():
    """Persona management commands."""
    pass


@persona.command("create")
@click.option("--name", required=True, help="Persona name")
@click.option("--prompt", required=True, help="System prompt")
@click.option("--server-id", default=None, help="Bind to specific server/guild")
@click.option("--platform", default=None, help="Bind to specific platform")
@click.option("--modules", default="research,file_manager", help="Comma-separated module list")
def create_persona(name, prompt, server_id, platform, modules):
    """Create a new persona."""
    run_async(_create_persona(name, prompt, server_id, platform, modules))


async def _create_persona(name, prompt, server_id, platform, modules):
    from shared.database import get_engine, get_session_factory
    from shared.models.persona import Persona

    module_list = [m.strip() for m in modules.split(",")]
    session_factory = get_session_factory()
    async with session_factory() as session:
        p = Persona(
            id=uuid.uuid4(),
            name=name,
            system_prompt=prompt,
            platform=platform,
            platform_server_id=server_id,
            allowed_modules=json.dumps(module_list),
            created_at=datetime.now(timezone.utc),
        )
        session.add(p)
        await session.commit()
        click.echo(f"Created persona: {p.name} ({p.id})")

    engine = get_engine()
    await engine.dispose()


@persona.command("list")
def list_personas():
    """List all personas."""
    run_async(_list_personas())


async def _list_personas():
    from sqlalchemy import select

    from shared.database import get_engine, get_session_factory
    from shared.models.persona import Persona

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Persona))
        personas = result.scalars().all()

        if not personas:
            click.echo("No personas found.")
            return

        for p in personas:
            default = " [DEFAULT]" if p.is_default else ""
            click.echo(f"{p.id} | {p.name}{default}")
            click.echo(f"  Modules: {p.allowed_modules}")
            if p.platform:
                click.echo(f"  Platform: {p.platform}")
            if p.platform_server_id:
                click.echo(f"  Server: {p.platform_server_id}")

    engine = get_engine()
    await engine.dispose()


@persona.command("set-default")
@click.option("--id", "persona_id", required=True, help="Persona ID")
def set_default_persona(persona_id):
    """Set a persona as the default."""
    run_async(_set_default_persona(persona_id))


async def _set_default_persona(persona_id):
    from sqlalchemy import select, update

    from shared.database import get_engine, get_session_factory
    from shared.models.persona import Persona

    session_factory = get_session_factory()
    async with session_factory() as session:
        # Unset all defaults
        await session.execute(
            update(Persona).values(is_default=False)
        )
        # Set the new default
        result = await session.execute(
            select(Persona).where(Persona.id == uuid.UUID(persona_id))
        )
        p = result.scalar_one_or_none()
        if not p:
            click.echo(f"Error: Persona {persona_id} not found.")
            return

        p.is_default = True
        await session.commit()
        click.echo(f"Default persona set to: {p.name}")

    engine = get_engine()
    await engine.dispose()


# --- Module Management ---


@cli.group()
def modules():
    """Module management commands."""
    pass


@modules.command("list")
def list_modules():
    """Show all configured modules and their health status."""
    run_async(_list_modules())


async def _list_modules():
    import httpx

    from shared.config import get_settings

    settings = get_settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in settings.module_services.items():
            try:
                resp = await client.get(f"{url}/health")
                status = "healthy" if resp.status_code == 200 else f"unhealthy ({resp.status_code})"
            except Exception:
                status = "unreachable"
            click.echo(f"{name}: {url} — {status}")


@modules.command("refresh")
def refresh_modules():
    """Re-fetch all module manifests via the core API."""
    run_async(_refresh_modules())


async def _refresh_modules():
    import httpx

    from shared.config import get_settings

    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{settings.orchestrator_url}/refresh-tools")
            if resp.status_code == 200:
                click.echo("Module manifests refreshed.")
            else:
                click.echo(f"Error: {resp.status_code} — {resp.text}")
    except Exception as e:
        click.echo(f"Error connecting to orchestrator: {e}")


if __name__ == "__main__":
    cli()
