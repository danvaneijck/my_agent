"""Helper to retrieve a user's personal LLM API keys and model preferences.

Used by the core orchestrator's AgentLoop to check whether a user has configured
their own provider keys before falling back to the global env-var credentials.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession


async def get_user_llm_overrides(
    session: AsyncSession,
    user_id: uuid.UUID,
    credential_store,  # CredentialStore | None — avoid circular import
) -> dict | None:
    """Return a dict of LLM setting overrides for the user, or None.

    The returned dict contains only the keys that are actually stored so that
    callers can merge it over the global Settings with model_copy(update=...).

    Possible keys:
        anthropic_api_key, openai_api_key, google_api_key,
        default_model, summarization_model, embedding_model

    Returns None when:
    - credential_store is None (encryption not configured)
    - no llm_settings credentials are stored for this user
    - stored credentials contain no API keys (model prefs alone don't grant
      unlimited usage)
    """
    if credential_store is None:
        return None

    creds = await credential_store.get_all(session, user_id, "llm_settings")
    if not creds:
        return None

    _key_map = {
        "anthropic_api_key": "anthropic_api_key",
        "openai_api_key": "openai_api_key",
        "google_api_key": "google_api_key",
        "default_model": "default_model",
        "summarization_model": "summarization_model",
        "embedding_model": "embedding_model",
    }

    overrides = {dst: creds[src] for src, dst in _key_map.items() if src in creds}

    # Only meaningful when at least one provider API key is present.
    # Model-name-only overrides don't change which keys are used.
    has_api_key = any(
        k in overrides
        for k in ("anthropic_api_key", "openai_api_key", "google_api_key")
    )
    return overrides if has_api_key else None
