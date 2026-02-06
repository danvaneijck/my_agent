"""Token counting utilities."""

from __future__ import annotations

import tiktoken


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Count tokens in text using tiktoken.

    Uses cl100k_base encoding as a reasonable approximation for most models.
    For Anthropic models, this gives a close-enough estimate.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def count_messages_tokens(messages: list[dict], model: str = "gpt-4o") -> int:
    """Estimate token count for a list of chat messages."""
    total = 0
    for msg in messages:
        # ~4 tokens overhead per message for role, separators
        total += 4
        content = msg.get("content", "")
        if isinstance(content, str):
            total += count_tokens(content, model)
        elif isinstance(content, list):
            # Handle multimodal content blocks
            for block in content:
                if isinstance(block, dict) and "text" in block:
                    total += count_tokens(block["text"], model)
    return total
