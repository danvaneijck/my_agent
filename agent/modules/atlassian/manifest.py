"""Atlassian module manifest — tool definitions for Jira and Confluence."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="atlassian",
    description="Interact with Jira and Confluence — search, create, and update issues and pages.",
    tools=[
        # ---- Jira tools ----
        ToolDefinition(
            name="atlassian.jira_search",
            description=(
                "Search Jira issues using JQL (Jira Query Language). "
                "Returns a list of matching issues with key, summary, status, assignee, and priority. "
                'Example JQL: \'project = ENG AND status = "In Progress"\', '
                "'assignee = currentUser() AND resolution = Unresolved ORDER BY priority DESC'."
            ),
            parameters=[
                ToolParameter(
                    name="jql",
                    type="string",
                    description="JQL query string",
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of results to return (default 20)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="atlassian.jira_get_issue",
            description=(
                "Get full details of a Jira issue by its key (e.g. PROJ-123). "
                "Returns summary, description, status, assignee, reporter, priority, "
                "labels, comments, and linked issues."
            ),
            parameters=[
                ToolParameter(
                    name="issue_key",
                    type="string",
                    description="The Jira issue key, e.g. PROJ-123",
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="atlassian.jira_create_issue",
            description=(
                "Create a new Jira issue. Returns the new issue key and URL. "
                "Supports Task, Bug, Story, and Epic issue types."
            ),
            parameters=[
                ToolParameter(
                    name="project_key",
                    type="string",
                    description="The Jira project key, e.g. ENG",
                ),
                ToolParameter(
                    name="summary",
                    type="string",
                    description="Issue title / summary",
                ),
                ToolParameter(
                    name="issue_type",
                    type="string",
                    description="Issue type (default: Task)",
                    enum=["Task", "Bug", "Story", "Epic"],
                    required=False,
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Issue description (markdown)",
                    required=False,
                ),
                ToolParameter(
                    name="assignee",
                    type="string",
                    description="Assignee account ID or email",
                    required=False,
                ),
                ToolParameter(
                    name="labels",
                    type="string",
                    description="Comma-separated labels",
                    required=False,
                ),
                ToolParameter(
                    name="priority",
                    type="string",
                    description="Priority name (e.g. High, Medium, Low)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="atlassian.jira_update_issue",
            description=(
                "Update an existing Jira issue. Can change fields, transition status, "
                "or add a comment. Only provide the fields you want to change."
            ),
            parameters=[
                ToolParameter(
                    name="issue_key",
                    type="string",
                    description="The Jira issue key, e.g. PROJ-123",
                ),
                ToolParameter(
                    name="summary",
                    type="string",
                    description="New summary / title",
                    required=False,
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="New description (markdown)",
                    required=False,
                ),
                ToolParameter(
                    name="status",
                    type="string",
                    description="Transition to this status (e.g. 'In Progress', 'Done')",
                    required=False,
                ),
                ToolParameter(
                    name="comment",
                    type="string",
                    description="Add a comment to the issue",
                    required=False,
                ),
                ToolParameter(
                    name="assignee",
                    type="string",
                    description="New assignee account ID or email",
                    required=False,
                ),
                ToolParameter(
                    name="labels",
                    type="string",
                    description="Comma-separated labels to set",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        # ---- Confluence tools ----
        ToolDefinition(
            name="atlassian.confluence_search",
            description=(
                "Search Confluence pages using CQL (Confluence Query Language) or plain text. "
                "Returns page titles, IDs, space keys, and excerpts. "
                'Example CQL: \'type=page AND space=ENG AND title~"architecture"\', '
                "or just pass a plain search term."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="CQL query string or plain text search term",
                ),
                ToolParameter(
                    name="space",
                    type="string",
                    description="Limit search to this space key (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of results (default 10)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="atlassian.confluence_get_page",
            description=(
                "Get the content of a Confluence page. Look up by page ID, "
                "or by space key + title. Returns the page content as readable text."
            ),
            parameters=[
                ToolParameter(
                    name="page_id",
                    type="string",
                    description="Confluence page ID",
                    required=False,
                ),
                ToolParameter(
                    name="space",
                    type="string",
                    description="Space key (used with title for lookup)",
                    required=False,
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="Page title (used with space for lookup)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="atlassian.confluence_create_page",
            description=(
                "Create a new Confluence page. Content should be in markdown format — "
                "it will be automatically converted to Confluence format."
            ),
            parameters=[
                ToolParameter(
                    name="space",
                    type="string",
                    description="Space key to create the page in",
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="Page title",
                ),
                ToolParameter(
                    name="body",
                    type="string",
                    description="Page content in markdown format",
                ),
                ToolParameter(
                    name="parent_title",
                    type="string",
                    description="Title of the parent page (optional — creates as top-level page if omitted)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="atlassian.confluence_update_page",
            description=(
                "Update an existing Confluence page. Look up by page ID or by space + title. "
                "Can replace the full body or append to it."
            ),
            parameters=[
                ToolParameter(
                    name="page_id",
                    type="string",
                    description="Confluence page ID",
                    required=False,
                ),
                ToolParameter(
                    name="space",
                    type="string",
                    description="Space key (used with title for lookup)",
                    required=False,
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="Current page title (used with space for lookup)",
                    required=False,
                ),
                ToolParameter(
                    name="new_title",
                    type="string",
                    description="New page title (if renaming)",
                    required=False,
                ),
                ToolParameter(
                    name="body",
                    type="string",
                    description="New page content in markdown format",
                ),
                ToolParameter(
                    name="append",
                    type="boolean",
                    description="If true, append to existing content instead of replacing (default false)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        # ---- Smart document tools ----
        ToolDefinition(
            name="atlassian.create_meeting_notes",
            description=(
                "Create a structured Confluence page from meeting notes. "
                "Provide raw notes and the tool formats them into a structured document "
                "with sections for discussion points, decisions, and action items. "
                "Optionally auto-creates Jira issues for action items."
            ),
            parameters=[
                ToolParameter(
                    name="space",
                    type="string",
                    description="Confluence space key",
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="Page title for the meeting notes",
                ),
                ToolParameter(
                    name="discussion",
                    type="string",
                    description="Discussion points (markdown)",
                ),
                ToolParameter(
                    name="decisions",
                    type="string",
                    description="Decisions made (markdown)",
                ),
                ToolParameter(
                    name="actions",
                    type="string",
                    description="Action items — one per line",
                ),
                ToolParameter(
                    name="date",
                    type="string",
                    description="Meeting date (e.g. 2025-01-15). Defaults to today.",
                    required=False,
                ),
                ToolParameter(
                    name="parent_title",
                    type="string",
                    description="Parent page title (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="jira_project",
                    type="string",
                    description="If provided, create a Jira task for each action item in this project",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="atlassian.create_feature_doc",
            description=(
                "Create a structured feature or design document in Confluence from notes. "
                "Formats the content into a template with standard sections. "
                "Supports feature spec, RFC, and ADR templates. "
                "Optionally auto-creates Jira stories for requirements."
            ),
            parameters=[
                ToolParameter(
                    name="space",
                    type="string",
                    description="Confluence space key",
                ),
                ToolParameter(
                    name="title",
                    type="string",
                    description="Document title",
                ),
                ToolParameter(
                    name="notes",
                    type="string",
                    description="Raw design notes, requirements, or discussion content (markdown)",
                ),
                ToolParameter(
                    name="template",
                    type="string",
                    description="Document template to use (default: feature)",
                    enum=["feature", "rfc", "adr"],
                    required=False,
                ),
                ToolParameter(
                    name="parent_title",
                    type="string",
                    description="Parent page title (optional)",
                    required=False,
                ),
                ToolParameter(
                    name="jira_project",
                    type="string",
                    description="If provided, create Jira stories for key requirements in this project",
                    required=False,
                ),
                ToolParameter(
                    name="requirements",
                    type="string",
                    description="Newline-separated list of requirements to create as Jira stories (used with jira_project)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
    ],
)
