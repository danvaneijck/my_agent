"""Telegram message normalizer."""

from __future__ import annotations

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

        attachments = []
        if message and message.document:
            attachments.append(message.document.file_id)
        if message and message.photo:
            attachments.append(message.photo[-1].file_id)

        return IncomingMessage(
            platform="telegram",
            platform_user_id=str(user.id) if user else "unknown",
            platform_username=user.username if user else None,
            platform_channel_id=str(chat.id) if chat else "unknown",
            platform_thread_id=thread_id,
            platform_server_id=server_id,
            content=message.text or message.caption or "" if message else "",
            attachments=attachments,
        )

    def format_response(self, response: AgentResponse) -> str:
        """Format an AgentResponse for Telegram with markdown."""
        content = response.content
        if response.error:
            content += f"\n\n⚠️ Error: {response.error}"

        if response.files:
            content += "\n\n📎 Files:"
            for f in response.files:
                filename = f.get("filename", "file")
                url = f.get("url", "")
                content += f"\n- [{filename}]({url})"

        # Telegram message limit is 4096
        if len(content) > 4096:
            content = content[:4090] + "\n..."

        return content
