"""Telegram message normalizer."""

from __future__ import annotations

import re

from telegram import Update

from shared.schemas.messages import AgentResponse, IncomingMessage


class TelegramNormalizer:
    """Normalize Telegram messages to/from the common format."""

    def to_incoming(self, update: Update) -> IncomingMessage:
        """Convert a Telegram update to the normalized format."""
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat

        thread_id = None
        if message and message.message_thread_id:
            thread_id = str(message.message_thread_id)

        server_id = None
        if chat and chat.type in ("group", "supergroup"):
            server_id = str(chat.id)

        # Attachments are ingested by the bot (not the normalizer)
        return IncomingMessage(
            platform="telegram",
            platform_user_id=str(user.id) if user else "unknown",
            platform_username=user.username if user else None,
            platform_channel_id=str(chat.id) if chat else "unknown",
            platform_thread_id=thread_id,
            platform_server_id=server_id,
            content=message.text or message.caption or "" if message else "",
        )

    def format_response(self, response: AgentResponse) -> str:
        """Format an AgentResponse for Telegram with markdown.

        File attachments are sent separately as native Telegram documents.
        """
        content = response.content
        if response.error:
            content += f"\n\n⚠️ Error: {response.error}"

        content = to_telegram_markdown(content)

        # Telegram message limit is 4096
        if len(content) > 4096:
            content = content[:4090] + "\n..."

        return content


def to_telegram_markdown(text: str) -> str:
    """Convert GitHub-flavored markdown to Telegram v1 Markdown.

    Telegram v1 uses *bold* and _italic_, whereas GitHub-flavored markdown
    uses **bold** and *italic*.  This converts the most common patterns
    so text renders correctly in Telegram.
    """
    # **bold** → *bold*  (must be done before single * handling)
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

    # ~~strikethrough~~ → ~strikethrough~ (Telegram v1 doesn't support it,
    # but stripping one layer of tildes makes it less noisy)
    text = re.sub(r"~~(.+?)~~", r"\1", text)

    return text
