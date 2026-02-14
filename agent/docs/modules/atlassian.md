# atlassian

Jira and Confluence integration — search, create, and update issues and pages, plus smart document generation.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `atlassian.jira_search` | Search issues via JQL | user |
| `atlassian.jira_get_issue` | Get full issue details by key | user |
| `atlassian.jira_create_issue` | Create a Task/Bug/Story/Epic | user |
| `atlassian.jira_update_issue` | Update fields, transition status, add comment | user |
| `atlassian.confluence_search` | Search pages via CQL or plain text | user |
| `atlassian.confluence_get_page` | Read a page by ID or space+title | user |
| `atlassian.confluence_create_page` | Create a new page in a space | user |
| `atlassian.confluence_update_page` | Update page body (replace or append) | user |
| `atlassian.create_meeting_notes` | Create structured meeting notes page | user |
| `atlassian.create_feature_doc` | Create feature/RFC/ADR document | user |

## Tool Details

### `atlassian.jira_search`
- **jql** (string, required) — JQL query (e.g. `project = ENG AND status = "In Progress"`)
- **max_results** (integer, optional) — default 20
- Returns `{key, summary, status, assignee, priority, issue_type, labels, url}`

### `atlassian.jira_get_issue`
- **issue_key** (string, required) — e.g. `PROJ-123`
- Returns full details with last 10 comments, linked issues

### `atlassian.jira_create_issue`
- **project_key** (string, required) — e.g. `ENG`
- **summary** (string, required)
- **issue_type** (string, optional) — `Task`, `Bug`, `Story`, `Epic` (default: Task)
- **description** (string, optional) — markdown
- **assignee** (string, optional) — account ID or email
- **labels** (string, optional) — comma-separated
- **priority** (string, optional) — e.g. `High`, `Medium`, `Low`

### `atlassian.jira_update_issue`
- **issue_key** (string, required)
- All other fields optional: `summary`, `description`, `status`, `comment`, `assignee`, `labels`
- Status changes use Jira transitions (finds matching transition name)

### `atlassian.confluence_search`
- **query** (string, required) — CQL or plain text
- **space** (string, optional) — limit to space key
- **max_results** (integer, optional) — default 10

### `atlassian.confluence_get_page`
- **page_id** (string, optional) — Confluence page ID
- **space** (string, optional) — used with title for lookup
- **title** (string, optional) — used with space for lookup
- Converts Confluence storage format to readable text

### `atlassian.confluence_create_page`
- **space** (string, required) — space key
- **title** (string, required)
- **body** (string, required) — markdown, auto-converted to Confluence format
- **parent_title** (string, optional) — creates as child page

### `atlassian.confluence_update_page`
- **page_id** or **space**+**title** — lookup method
- **body** (string, required) — new content in markdown
- **new_title** (string, optional) — rename the page
- **append** (boolean, optional) — append instead of replace (default false)

### `atlassian.create_meeting_notes`
- **space**, **title** (required) — where to create
- **discussion**, **decisions**, **actions** (string, required) — structured content
- **date** (string, optional) — defaults to today
- **parent_title** (string, optional)
- **jira_project** (string, optional) — auto-creates Jira tasks for each action item

### `atlassian.create_feature_doc`
- **space**, **title**, **notes** (required)
- **template** (string, optional) — `feature`, `rfc`, or `adr`
- **parent_title** (string, optional)
- **jira_project** (string, optional) — auto-creates Jira stories
- **requirements** (string, optional) — newline-separated list for Jira story creation

## Implementation Notes

- Uses `atlassian-python-api` library (synchronous), wrapped with `asyncio.to_thread()` for async
- Auth: Cloud mode (username + API token) or Server/DC mode (personal access token)
- Markdown-to-Confluence conversion via `md_to_confluence()` helper
- Confluence-to-text conversion via `confluence_to_text()` helper
- URL building differs between Cloud and Server/DC deployments

## Key Files

- `agent/modules/atlassian/manifest.py`
- `agent/modules/atlassian/tools.py`
- `agent/modules/atlassian/main.py`
