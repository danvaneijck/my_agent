import re
from typing import List, Dict, Any

import structlog

logger = structlog.get_logger()


class BlockBuilder:
    """Convert LLM markdown responses to Slack's native markdown blocks.

    Uses Slack's {"type": "markdown", "text": "..."} block type which renders
    standard markdown natively. Handles chunking for Slack's 12,000 character
    cumulative limit per payload.
    """

    BLOCK_CHAR_LIMIT = 12_000

    @staticmethod
    def text_to_blocks(text: str) -> List[Dict[str, Any]]:
        """Wrap raw markdown in Slack markdown blocks.

        Returns a list of markdown blocks. If the text exceeds the block
        character limit, it is split into multiple blocks.
        """
        if not text:
            return []
        if len(text) <= BlockBuilder.BLOCK_CHAR_LIMIT:
            return [{"type": "markdown", "text": text}]
        chunks = BlockBuilder._split_text(text, BlockBuilder.BLOCK_CHAR_LIMIT)
        return [{"type": "markdown", "text": chunk} for chunk in chunks]

    @staticmethod
    def split_for_slack(
        text: str, limit: int = 12_000
    ) -> List[List[Dict[str, Any]]]:
        """Split a response into multiple message payloads if needed.

        Each payload is a List[Dict] of blocks whose cumulative text stays
        within *limit* characters. Splitting prefers paragraph breaks, then
        newlines, then hard-cuts.
        """
        if not text:
            return []
        if len(text) <= limit:
            return [[{"type": "markdown", "text": text}]]
        chunks = BlockBuilder._split_text(text, limit)
        return [[{"type": "markdown", "text": chunk}] for chunk in chunks]

    @staticmethod
    async def post_response(
        client,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
        update_ts: str | None = None,
    ) -> None:
        """Post a markdown response to Slack, chunking across messages if needed.

        Args:
            client: Slack AsyncWebClient.
            channel_id: Channel to post in.
            text: Raw markdown response from the LLM.
            thread_ts: Thread timestamp to reply in.
            update_ts: If set, the first payload updates this message
                       (replaces the "thinking" indicator).
        """
        fallback = BlockBuilder._plain_text_fallback(text)
        payloads = BlockBuilder.split_for_slack(text)

        if not payloads:
            payloads = [[{"type": "markdown", "text": "(empty response)"}]]

        for i, blocks in enumerate(payloads):
            if i == 0 and update_ts:
                await client.chat_update(
                    channel=channel_id,
                    ts=update_ts,
                    text=fallback,
                    blocks=blocks,
                )
            else:
                await client.chat_postMessage(
                    channel=channel_id,
                    text=fallback,
                    blocks=blocks,
                    thread_ts=thread_ts,
                )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _plain_text_fallback(text: str, max_len: int = 200) -> str:
        """Strip markdown formatting for the plain-text notification fallback."""
        if not text:
            return ""
        plain = text
        # Remove markdown images
        plain = re.sub(r"!\[.*?\]\(.*?\)", "", plain)
        # Convert links to just the label
        plain = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", plain)
        # Strip bold/italic markers
        plain = re.sub(r"\*{1,2}(.*?)\*{1,2}", r"\1", plain)
        # Strip heading markers
        plain = re.sub(r"^#{1,6}\s+", "", plain, flags=re.MULTILINE)
        # Collapse whitespace
        plain = re.sub(r"\n{2,}", "\n", plain).strip()
        if len(plain) > max_len:
            plain = plain[: max_len - 1] + "\u2026"
        return plain

    @staticmethod
    def _split_text(text: str, limit: int) -> List[str]:
        """Split text into chunks of at most *limit* characters.

        Splitting priority:
        1. Paragraph breaks (\\n\\n)
        2. Single newlines (\\n)
        3. Hard cut at *limit*
        """
        if len(text) <= limit:
            return [text]

        chunks: List[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break

            # Try paragraph break
            split_pos = remaining.rfind("\n\n", 0, limit)
            if split_pos > 0:
                chunks.append(remaining[:split_pos])
                remaining = remaining[split_pos + 2:]
                continue

            # Try single newline
            split_pos = remaining.rfind("\n", 0, limit)
            if split_pos > 0:
                chunks.append(remaining[:split_pos])
                remaining = remaining[split_pos + 1:]
                continue

            # Hard cut
            chunks.append(remaining[:limit])
            remaining = remaining[limit:]

        return chunks
