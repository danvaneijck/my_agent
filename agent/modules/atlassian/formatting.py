"""Content formatting utilities for the Atlassian module.

Handles markdown-to-HTML conversion for Confluence storage format,
HTML-to-text stripping for reading pages, and document templates.
"""

from __future__ import annotations

import re

import markdown
from bs4 import BeautifulSoup


def md_to_confluence(md_text: str) -> str:
    """Convert markdown text to Confluence storage format (XHTML).

    Uses the Python markdown library with common extensions, then
    passes the result as Confluence storage representation.
    """
    html = markdown.markdown(
        md_text,
        extensions=[
            "tables",
            "fenced_code",
            "toc",
            "sane_lists",
            "nl2br",
        ],
    )
    return html


def confluence_to_text(storage_html: str) -> str:
    """Strip HTML tags from Confluence storage format to plain text.

    Returns a clean text representation suitable for an LLM to read.
    """
    if not storage_html:
        return ""
    soup = BeautifulSoup(storage_html, "html.parser")

    # Convert <li> to bullet points for readability
    for li in soup.find_all("li"):
        li.insert_before("- ")

    # Convert headers to markdown-style
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            prefix = "#" * level + " "
            h.insert_before(f"\n{prefix}")
            h.append("\n")

    # Convert <br> to newlines
    for br in soup.find_all("br"):
        br.replace_with("\n")

    text = soup.get_text(separator="\n")
    # Collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---- Document templates ----


MEETING_NOTES_TEMPLATE = """<h1>{title}</h1>
<ac:structured-macro ac:name="info">
  <ac:rich-text-body><p><strong>Date:</strong> {date}</p></ac:rich-text-body>
</ac:structured-macro>

<h2>Discussion Points</h2>
{discussion_html}

<h2>Decisions</h2>
{decisions_html}

<h2>Action Items</h2>
{actions_html}
"""


def build_meeting_notes_page(
    title: str,
    date: str,
    discussion: str,
    decisions: str,
    actions: str,
    action_jira_links: list[dict] | None = None,
) -> str:
    """Build a Confluence page body for meeting notes.

    Args:
        title: Meeting title.
        date: Date string.
        discussion: Markdown-formatted discussion points.
        decisions: Markdown-formatted decisions.
        actions: Markdown-formatted action items.
        action_jira_links: Optional list of {"summary": ..., "key": ...} dicts
            for Jira issues created from action items.
    """
    discussion_html = md_to_confluence(discussion) if discussion.strip() else "<p>None recorded.</p>"
    decisions_html = md_to_confluence(decisions) if decisions.strip() else "<p>None recorded.</p>"

    if action_jira_links:
        # Build a list with Jira links
        items = []
        for link in action_jira_links:
            items.append(
                f'<li>{link["summary"]} &mdash; '
                f'<a href="{link["url"]}">{link["key"]}</a></li>'
            )
        actions_html = "<ul>" + "\n".join(items) + "</ul>"
    elif actions.strip():
        actions_html = md_to_confluence(actions)
    else:
        actions_html = "<p>None.</p>"

    return MEETING_NOTES_TEMPLATE.format(
        title=title,
        date=date,
        discussion_html=discussion_html,
        decisions_html=decisions_html,
        actions_html=actions_html,
    )


FEATURE_DOC_SECTIONS = {
    "feature": [
        ("Overview", "High-level summary of the feature."),
        ("Problem Statement", "What problem does this solve?"),
        ("Proposed Solution", "How will this be implemented?"),
        ("Requirements", "Specific requirements and acceptance criteria."),
        ("Out of Scope", "What is explicitly not included."),
        ("Open Questions", "Unresolved items needing discussion."),
    ],
    "rfc": [
        ("Summary", "Brief overview of the proposal."),
        ("Motivation", "Why is this change needed?"),
        ("Detailed Design", "Technical design and implementation details."),
        ("Drawbacks", "Potential downsides or risks."),
        ("Alternatives", "Other approaches considered."),
        ("Unresolved Questions", "Open items."),
    ],
    "adr": [
        ("Status", "Proposed / Accepted / Deprecated / Superseded"),
        ("Context", "What is the issue motivating this decision?"),
        ("Decision", "What is the change being proposed?"),
        ("Consequences", "What are the resulting effects?"),
    ],
}


def build_feature_doc_page(
    title: str,
    notes: str,
    template: str = "feature",
    jira_links: list[dict] | None = None,
) -> str:
    """Build a Confluence page body for a feature/design document.

    The notes content is placed in the first content section. Remaining
    sections get placeholder text the author can fill in.

    Args:
        title: Document title.
        notes: The raw design notes / requirements (markdown).
        template: One of "feature", "rfc", "adr".
        jira_links: Optional list of {"summary": ..., "key": ..., "url": ...}
            for auto-created Jira issues.
    """
    sections = FEATURE_DOC_SECTIONS.get(template, FEATURE_DOC_SECTIONS["feature"])

    parts = [f"<h1>{title}</h1>"]

    # Table of contents macro
    parts.append(
        '<ac:structured-macro ac:name="toc">'
        '<ac:parameter ac:name="maxLevel">2</ac:parameter>'
        "</ac:structured-macro>"
    )

    for i, (heading, placeholder) in enumerate(sections):
        parts.append(f"<h2>{heading}</h2>")
        if i == 0:
            # Put the actual notes content in the first section
            parts.append(md_to_confluence(notes))
        else:
            parts.append(f"<p><em>{placeholder}</em></p>")

    if jira_links:
        parts.append("<h2>Related Jira Issues</h2>")
        items = []
        for link in jira_links:
            items.append(
                f'<li><a href="{link["url"]}">{link["key"]}</a> &mdash; {link["summary"]}</li>'
            )
        parts.append("<ul>" + "\n".join(items) + "</ul>")

    return "\n\n".join(parts)
