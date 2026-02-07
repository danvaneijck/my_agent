import re
from typing import List, Dict, Any, Optional


class BlockBuilder:
    """
    Advanced Markdown to Slack Block Kit converter.
    Handles: Headers, Tables, Lists, Code Blocks, Blockquotes, Images, and Dividers.
    """

    @staticmethod
    def text_to_blocks(text: str) -> List[Dict[str, Any]]:
        blocks = []
        if not text:
            return blocks

        lines = text.split("\n")

        # Buffers for state machine
        section_buffer: List[str] = []
        table_buffer: List[str] = []
        list_buffer: List[str] = []

        # State flags
        in_code_block = False
        in_table = False
        in_list = False
        list_type = None  # 'bullet' or 'ordered'

        for line in lines:
            stripped = line.strip()

            # --- 1. HANDLE CODE BLOCKS (Priority High) ---
            if "```" in line:
                in_code_block = not in_code_block
                section_buffer.append(line)
                continue

            if in_code_block:
                section_buffer.append(line)
                continue

            # --- 2. HANDLE TABLES ---
            # Detect table row: starts/ends with pipe |
            is_table_row = stripped.startswith("|") and stripped.endswith("|")

            if is_table_row:
                if not in_table:
                    # Switch state: Flush text -> Start Table
                    BlockBuilder._flush_section(blocks, section_buffer)
                    section_buffer = []
                    in_table = True
                table_buffer.append(stripped)
                continue
            elif in_table:
                # Table ended
                in_table = False
                blocks.append(BlockBuilder._create_table_block(table_buffer))
                table_buffer = []

            # --- 3. HANDLE LISTS ---
            # Detect Bullet (- item, * item) or Numbered (1. item)
            is_bullet = stripped.startswith(("- ", "* "))
            is_number = re.match(r"^\d+\.\s", stripped)

            current_list_type = (
                "bullet" if is_bullet else ("ordered" if is_number else None)
            )

            if current_list_type:
                if not in_list:
                    # Switch state: Flush text -> Start List
                    BlockBuilder._flush_section(blocks, section_buffer)
                    section_buffer = []
                    in_list = True
                    list_type = current_list_type

                # If list type changes (bullet -> number), flush current list and start new
                if list_type != current_list_type:
                    blocks.append(
                        BlockBuilder._create_list_block(list_buffer, list_type)
                    )
                    list_buffer = []
                    list_type = current_list_type

                list_buffer.append(stripped)
                continue
            elif in_list:
                # List ended
                in_list = False
                blocks.append(BlockBuilder._create_list_block(list_buffer, list_type))
                list_buffer = []

            # --- 4. HANDLE HEADERS (### Text) ---
            header_match = re.match(r"^(#{1,6})\s+(.+)", line)
            if header_match:
                BlockBuilder._flush_section(blocks, section_buffer)
                section_buffer = []

                heading_text = header_match.group(2).replace("*", "")
                blocks.append(
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": heading_text[:150],  # Slack limit
                            "emoji": True,
                        },
                    }
                )
                continue

            # --- 5. HANDLE IMAGES (![Alt](Url)) ---
            img_match = re.match(r"^!\[(.*?)\]\((.*?)\)", line)
            if img_match:
                BlockBuilder._flush_section(blocks, section_buffer)
                section_buffer = []

                alt_text = img_match.group(1) or "Image"
                img_url = img_match.group(2)
                blocks.append(
                    {"type": "image", "image_url": img_url, "alt_text": alt_text}
                )
                continue

            # --- 6. HANDLE BLOCKQUOTES (> Text) ---
            if line.startswith("> "):
                BlockBuilder._flush_section(blocks, section_buffer)
                section_buffer = []

                # Context block looks like a grey footer/quote
                blocks.append(
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": line.lstrip("> ")}],
                    }
                )
                continue

            # --- 7. HANDLE DIVIDERS (---) ---
            if set(stripped) == {"-"} and len(stripped) >= 3:
                BlockBuilder._flush_section(blocks, section_buffer)
                section_buffer = []
                blocks.append({"type": "divider"})
                continue

            # --- 8. DEFAULT TEXT ---
            section_buffer.append(line)

        # --- FLUSH REMAINING BUFFERS ---
        if in_table and table_buffer:
            blocks.append(BlockBuilder._create_table_block(table_buffer))
        elif in_list and list_buffer:
            blocks.append(BlockBuilder._create_list_block(list_buffer, list_type))
        else:
            BlockBuilder._flush_section(blocks, section_buffer)

        return blocks

    @staticmethod
    def _flush_section(blocks: List[Dict], buffer: List[str]):
        """Converts buffered text lines into a standard Section block."""
        if not buffer:
            return

        text = "\n".join(buffer).strip()
        if not text:
            return

        # Simple Markdown Cleanup for Slack mrkdwn format
        # Convert **bold** to *bold*
        text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
        # Convert [Link](URL) to <URL|Link>
        text = re.sub(r"\[(.*?)\]\((.*?)\)", r"<\2|\1>", text)

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text[:3000]},  # Slack char limit
            }
        )

    @staticmethod
    def _create_table_block(rows: List[str]) -> Dict:
        """Parses markdown table into Slack Rich Text Table."""
        parsed_rows = []
        for row in rows:
            # Clean outer pipes and split
            content = row.strip().strip("|")
            cells = [c.strip() for c in content.split("|")]

            # Skip separator rows like |---|---|
            if all(set(c).issubset({"-", ":"}) for c in cells if c):
                continue
            parsed_rows.append(cells)

        if not parsed_rows:
            return {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "Empty Table"},
            }

        rich_text_rows = []
        for row_cells in parsed_rows:
            columns = []
            for cell_text in row_cells:
                columns.append(
                    {
                        "type": "rich_text_section",
                        "elements": [{"type": "text", "text": cell_text}],
                    }
                )
            rich_text_rows.append({"type": "rich_text_table_row", "columns": columns})

        return {
            "type": "rich_text",
            "elements": [{"type": "rich_text_table", "rows": rich_text_rows}],
        }

    @staticmethod
    def _create_list_block(items: List[str], style: str) -> Dict:
        """Parses markdown list items into Slack Rich Text List."""
        elements = []

        for item in items:
            # Remove bullet symbols (- , 1. ) to get raw text
            clean_text = re.sub(r"^(\d+\.|-|\*)\s+", "", item)

            elements.append(
                {
                    "type": "rich_text_section",
                    "elements": [{"type": "text", "text": clean_text}],
                }
            )

        return {
            "type": "rich_text",
            "elements": [
                {
                    "type": "rich_text_list",
                    "style": style,  # 'bullet' or 'ordered'
                    "elements": elements,
                }
            ],
        }
