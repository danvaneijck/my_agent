"""Atlassian module tool implementations.

Wraps atlassian-python-api (synchronous) with asyncio.to_thread for
async FastAPI compatibility.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from atlassian import Confluence, Jira

from modules.atlassian.formatting import (
    build_feature_doc_page,
    build_meeting_notes_page,
    confluence_to_text,
    md_to_confluence,
)

logger = structlog.get_logger()


class AtlassianTools:
    """Tool implementations for Jira and Confluence."""

    def __init__(
        self,
        url: str,
        username: str,
        api_token: str,
        cloud: bool = True,
        default_space: str = "",
    ):
        auth_kwargs: dict = {"url": url}
        if cloud:
            auth_kwargs.update(username=username, password=api_token, cloud=True)
        else:
            # Server/DC — use personal access token
            auth_kwargs["token"] = api_token

        self.jira = Jira(**auth_kwargs)
        self.confluence = Confluence(**auth_kwargs)
        self.base_url = url.rstrip("/")
        self.cloud = cloud
        self.default_space = default_space

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _issue_url(self, key: str) -> str:
        return f"{self.base_url}/browse/{key}"

    def _page_url(self, page_id: str) -> str:
        return f"{self.base_url}/wiki/pages/{page_id}" if self.cloud else f"{self.base_url}/pages/viewpage.action?pageId={page_id}"

    def _resolve_space(self, space: str | None) -> str:
        resolved = space or self.default_space
        if not resolved:
            raise ValueError("No space provided and CONFLUENCE_DEFAULT_SPACE is not set")
        return resolved

    # ------------------------------------------------------------------
    # Jira tools
    # ------------------------------------------------------------------

    async def jira_search(self, jql: str, max_results: int = 20) -> dict:
        """Search Jira issues via JQL."""

        def _search():
            results = self.jira.jql(jql, limit=max_results, fields="summary,status,assignee,priority,issuetype,labels")
            issues = []
            for item in results.get("issues", []):
                fields = item.get("fields", {})
                assignee = fields.get("assignee") or {}
                issues.append({
                    "key": item["key"],
                    "summary": fields.get("summary"),
                    "status": (fields.get("status") or {}).get("name"),
                    "assignee": assignee.get("displayName") or assignee.get("name"),
                    "priority": (fields.get("priority") or {}).get("name"),
                    "type": (fields.get("issuetype") or {}).get("name"),
                    "labels": fields.get("labels", []),
                    "url": self._issue_url(item["key"]),
                })
            return {
                "total": results.get("total", len(issues)),
                "issues": issues,
            }

        return await asyncio.to_thread(_search)

    async def jira_get_issue(self, issue_key: str) -> dict:
        """Get full details of a Jira issue."""

        def _get():
            issue = self.jira.issue(issue_key)
            fields = issue.get("fields", {})
            assignee = fields.get("assignee") or {}
            reporter = fields.get("reporter") or {}

            # Get comments
            comments_raw = fields.get("comment", {}).get("comments", [])
            comments = []
            for c in comments_raw[-10:]:  # Last 10 comments
                author = c.get("author", {})
                comments.append({
                    "author": author.get("displayName") or author.get("name"),
                    "body": c.get("body", ""),
                    "created": c.get("created"),
                })

            return {
                "key": issue["key"],
                "summary": fields.get("summary"),
                "description": fields.get("description") or "",
                "status": (fields.get("status") or {}).get("name"),
                "assignee": assignee.get("displayName") or assignee.get("name"),
                "reporter": reporter.get("displayName") or reporter.get("name"),
                "priority": (fields.get("priority") or {}).get("name"),
                "type": (fields.get("issuetype") or {}).get("name"),
                "labels": fields.get("labels", []),
                "created": fields.get("created"),
                "updated": fields.get("updated"),
                "comments": comments,
                "url": self._issue_url(issue["key"]),
            }

        return await asyncio.to_thread(_get)

    async def jira_create_issue(
        self,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str | None = None,
        assignee: str | None = None,
        labels: str | None = None,
        priority: str | None = None,
    ) -> dict:
        """Create a new Jira issue."""

        def _create():
            fields = {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
            }
            if description:
                fields["description"] = description
            if assignee:
                if self.cloud:
                    fields["assignee"] = {"accountId": assignee}
                else:
                    fields["assignee"] = {"name": assignee}
            if labels:
                fields["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
            if priority:
                fields["priority"] = {"name": priority}

            result = self.jira.issue_create(fields)
            key = result.get("key", "")
            return {
                "key": key,
                "id": result.get("id"),
                "url": self._issue_url(key),
                "summary": summary,
            }

        return await asyncio.to_thread(_create)

    async def jira_update_issue(
        self,
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        status: str | None = None,
        comment: str | None = None,
        assignee: str | None = None,
        labels: str | None = None,
    ) -> dict:
        """Update a Jira issue — fields, status transition, and/or comment."""

        def _update():
            updated_fields = []

            # Update fields
            fields: dict = {}
            if summary:
                fields["summary"] = summary
                updated_fields.append("summary")
            if description:
                fields["description"] = description
                updated_fields.append("description")
            if labels is not None:
                fields["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
                updated_fields.append("labels")
            if assignee:
                if self.cloud:
                    fields["assignee"] = {"accountId": assignee}
                else:
                    fields["assignee"] = {"name": assignee}
                updated_fields.append("assignee")

            if fields:
                self.jira.update_issue_field(issue_key, fields)

            # Transition status
            if status:
                self.jira.set_issue_status(issue_key, status)
                updated_fields.append("status")

            # Add comment
            if comment:
                self.jira.issue_add_comment(issue_key, comment)
                updated_fields.append("comment")

            return {
                "key": issue_key,
                "updated_fields": updated_fields,
                "url": self._issue_url(issue_key),
            }

        return await asyncio.to_thread(_update)

    # ------------------------------------------------------------------
    # Confluence tools
    # ------------------------------------------------------------------

    async def confluence_search(
        self,
        query: str,
        space: str | None = None,
        max_results: int = 10,
    ) -> dict:
        """Search Confluence via CQL or plain text."""

        def _search():
            # Build CQL: if the query looks like CQL (contains = or ~), use as-is
            if any(op in query for op in ("=", "~", " AND ", " OR ")):
                cql = query
            else:
                # Plain text search
                cql = f'type=page AND text~"{query}"'

            if space:
                if "space=" not in cql.lower():
                    cql += f" AND space={space}"

            results = self.confluence.cql(cql, limit=max_results)
            pages = []
            for item in results.get("results", []):
                content = item.get("content", item)
                title = item.get("title") or content.get("title", "")
                page_id = content.get("id", "")
                space_info = content.get("_expandable", {}).get("space", "")
                # Extract space key from URL path
                space_key = ""
                if space_info and "/rest/api/space/" in space_info:
                    space_key = space_info.split("/rest/api/space/")[-1]
                excerpt = item.get("excerpt", "")
                pages.append({
                    "page_id": page_id,
                    "title": title,
                    "space": space_key or space or "",
                    "excerpt": excerpt[:300] if excerpt else "",
                    "url": self._page_url(page_id) if page_id else "",
                })
            return {
                "total": results.get("totalSize", len(pages)),
                "pages": pages,
            }

        return await asyncio.to_thread(_search)

    async def confluence_get_page(
        self,
        page_id: str | None = None,
        space: str | None = None,
        title: str | None = None,
    ) -> dict:
        """Get a Confluence page's content."""

        def _get():
            if page_id:
                page = self.confluence.get_page_by_id(page_id, expand="body.storage,version")
            elif space and title:
                page = self.confluence.get_page_by_title(space, title, expand="body.storage,version")
            else:
                raise ValueError("Provide either page_id or both space and title")

            if not page:
                raise ValueError(f"Page not found: page_id={page_id}, space={space}, title={title}")

            body_storage = page.get("body", {}).get("storage", {}).get("value", "")
            text_content = confluence_to_text(body_storage)

            return {
                "page_id": page["id"],
                "title": page.get("title", ""),
                "space": page.get("space", {}).get("key", space or ""),
                "version": page.get("version", {}).get("number"),
                "content": text_content,
                "url": self._page_url(page["id"]),
            }

        return await asyncio.to_thread(_get)

    async def confluence_create_page(
        self,
        space: str,
        title: str,
        body: str,
        parent_title: str | None = None,
    ) -> dict:
        """Create a Confluence page from markdown content."""
        space = self._resolve_space(space)

        def _create():
            html_body = md_to_confluence(body)
            parent_id = None
            if parent_title:
                parent_id = self.confluence.get_page_id(space, parent_title)

            result = self.confluence.create_page(
                space=space,
                title=title,
                body=html_body,
                parent_id=parent_id,
                representation="storage",
            )
            page_id = result.get("id", "")
            return {
                "page_id": page_id,
                "title": result.get("title", title),
                "space": space,
                "url": self._page_url(page_id),
            }

        return await asyncio.to_thread(_create)

    async def confluence_update_page(
        self,
        body: str,
        page_id: str | None = None,
        space: str | None = None,
        title: str | None = None,
        new_title: str | None = None,
        append: bool = False,
    ) -> dict:
        """Update a Confluence page."""

        def _update():
            # Resolve the page
            if page_id:
                pid = page_id
            elif space and title:
                pid = self.confluence.get_page_id(space, title)
                if not pid:
                    raise ValueError(f"Page not found: space={space}, title={title}")
            else:
                raise ValueError("Provide either page_id or both space and title")

            html_body = md_to_confluence(body)

            if append:
                # Get current page to find its title
                current = self.confluence.get_page_by_id(pid, expand="version")
                current_title = new_title or current.get("title", title or "")
                self.confluence.append_page(
                    page_id=pid,
                    title=current_title,
                    append_body=html_body,
                    representation="storage",
                )
            else:
                current = self.confluence.get_page_by_id(pid, expand="version")
                page_title = new_title or current.get("title", title or "")
                self.confluence.update_page(
                    page_id=pid,
                    title=page_title,
                    body=html_body,
                    representation="storage",
                )

            return {
                "page_id": pid,
                "title": new_title or title or "",
                "url": self._page_url(pid),
                "appended": append,
            }

        return await asyncio.to_thread(_update)

    # ------------------------------------------------------------------
    # Smart document tools
    # ------------------------------------------------------------------

    async def create_meeting_notes(
        self,
        space: str,
        title: str,
        discussion: str,
        decisions: str,
        actions: str,
        date: str | None = None,
        parent_title: str | None = None,
        jira_project: str | None = None,
    ) -> dict:
        """Create a structured meeting notes page, optionally with Jira action items."""
        space = self._resolve_space(space)
        if not date:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Create Jira issues for action items if requested
        jira_links: list[dict] = []
        if jira_project and actions.strip():
            action_lines = [
                line.strip().lstrip("-*").strip()
                for line in actions.strip().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            for action in action_lines:
                if not action:
                    continue
                result = await self.jira_create_issue(
                    project_key=jira_project,
                    summary=action[:255],
                    issue_type="Task",
                    description=f"Action item from meeting: {title}\n\n{action}",
                )
                jira_links.append({
                    "summary": action[:255],
                    "key": result["key"],
                    "url": result["url"],
                })

        # Build the page body
        page_body = build_meeting_notes_page(
            title=title,
            date=date,
            discussion=discussion,
            decisions=decisions,
            actions=actions,
            action_jira_links=jira_links if jira_links else None,
        )

        # Create the Confluence page
        def _create():
            parent_id = None
            if parent_title:
                parent_id = self.confluence.get_page_id(space, parent_title)

            result = self.confluence.create_page(
                space=space,
                title=title,
                body=page_body,
                parent_id=parent_id,
                representation="storage",
            )
            return result

        result = await asyncio.to_thread(_create)
        page_id = result.get("id", "")

        return {
            "page_id": page_id,
            "title": title,
            "space": space,
            "url": self._page_url(page_id),
            "jira_issues_created": len(jira_links),
            "jira_issues": jira_links,
        }

    async def create_feature_doc(
        self,
        space: str,
        title: str,
        notes: str,
        template: str = "feature",
        parent_title: str | None = None,
        jira_project: str | None = None,
        requirements: str | None = None,
    ) -> dict:
        """Create a structured feature/design doc, optionally with Jira stories."""
        space = self._resolve_space(space)

        # Create Jira stories for requirements if requested
        jira_links: list[dict] = []
        if jira_project and requirements:
            req_lines = [
                line.strip().lstrip("-*").strip()
                for line in requirements.strip().splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            for req in req_lines:
                if not req:
                    continue
                result = await self.jira_create_issue(
                    project_key=jira_project,
                    summary=req[:255],
                    issue_type="Story",
                    description=f"Requirement from: {title}\n\n{req}",
                )
                jira_links.append({
                    "summary": req[:255],
                    "key": result["key"],
                    "url": result["url"],
                })

        # Build the page body
        page_body = build_feature_doc_page(
            title=title,
            notes=notes,
            template=template,
            jira_links=jira_links if jira_links else None,
        )

        # Create the Confluence page
        def _create():
            parent_id = None
            if parent_title:
                parent_id = self.confluence.get_page_id(space, parent_title)

            result = self.confluence.create_page(
                space=space,
                title=title,
                body=page_body,
                parent_id=parent_id,
                representation="storage",
            )
            return result

        result = await asyncio.to_thread(_create)
        page_id = result.get("id", "")

        return {
            "page_id": page_id,
            "title": title,
            "space": space,
            "template": template,
            "url": self._page_url(page_id),
            "jira_issues_created": len(jira_links),
            "jira_issues": jira_links,
        }
