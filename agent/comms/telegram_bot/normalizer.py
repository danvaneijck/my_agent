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
        """Format an AgentResponse for Telegram with MarkdownV2.

        File attachments are sent separately as native Telegram documents.
        """
        content = response.content
        if response.error:
            content += f"\n\n⚠️ Error: {response.error}"

        content = to_telegram_markdown_v2(content)

        # Telegram message limit is 4096
        if len(content) > 4096:
            content = content[:4090] + "\n\\.\\.\\."

        return content


# MarkdownV2 special characters that must be escaped in plain text.
# Inside pre/code entities only ` and \ need escaping.
_ESC_RE = re.compile(r'([_*\[\]()~`>#\+\-=|{}.!\\])')

# Regex matching markdown constructs we want to preserve, in priority order.
_MD_PATTERN = re.compile(
    r'(?P<fence>```[\s\S]*?```)'                 # fenced code block
    r'|(?P<code>`[^`\n]+`)'                      # inline code
    r'|(?P<bold>\*\*(?!\s)(?:(?!\*\*).)+?\*\*)'  # bold **text**
    r'|(?P<strike>~~(?!\s).+?~~)'                # strikethrough ~~text~~
    r'|(?P<link>\[[^\]]+\]\([^)]+\))'            # [text](url)
)


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters in plain text."""
    return _ESC_RE.sub(r'\\\1', text)


def to_telegram_markdown_v2(text: str) -> str:
    """Convert GitHub-flavored markdown to Telegram MarkdownV2.

    - **bold** → *bold* (MarkdownV2 bold)
    - ~~strike~~ → ~strike~ (MarkdownV2 strikethrough)
    - `code` and ```blocks``` preserved with correct escaping
    - [text](url) links preserved
    - All special characters in plain text are escaped
    """
    parts: list[str] = []
    last = 0

    for m in _MD_PATTERN.finditer(text):
        # Escape plain text before this match
        if m.start() > last:
            parts.append(_esc(text[last:m.start()]))

        if m.group("fence"):
            inner = m.group("fence")[3:-3]
            inner = inner.replace("\\", "\\\\").replace("`", "\\`")
            parts.append(f"```{inner}```")

        elif m.group("code"):
            inner = m.group("code")[1:-1]
            inner = inner.replace("\\", "\\\\").replace("`", "\\`")
            parts.append(f"`{inner}`")

        elif m.group("bold"):
            inner = m.group("bold")[2:-2]
            parts.append(f"*{_esc(inner)}*")

        elif m.group("strike"):
            inner = m.group("strike")[2:-2]
            parts.append(f"~{_esc(inner)}~")

        elif m.group("link"):
            lm = re.match(r"\[(.+?)\]\((.+?)\)", m.group("link"))
            link_text = _esc(lm.group(1))
            url = lm.group(2).replace("\\", "\\\\").replace(")", "\\)")
            parts.append(f"[{link_text}]({url})")

        last = m.end()

    # Escape remaining plain text
    if last < len(text):
        parts.append(_esc(text[last:]))

    return "".join(parts)
