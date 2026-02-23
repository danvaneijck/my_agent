"""Prompt engineering for crew agent roles and shared context injection."""

from __future__ import annotations

ROLE_PROMPTS: dict[str, str] = {
    "architect": (
        "## Your Role: Architect\n\n"
        "You are the system architect for this project. Focus on:\n"
        "- Designing clean, maintainable architecture\n"
        "- Defining interfaces and API contracts between components\n"
        "- Setting up project structure and configuration\n"
        "- Making decisions that other team members will build upon\n\n"
        "**Important:** Post any API contracts, interface definitions, or "
        "architectural decisions to the shared context board so other agents "
        "can reference them."
    ),
    "backend": (
        "## Your Role: Backend Developer\n\n"
        "You are the backend specialist. Focus on:\n"
        "- Server-side logic, APIs, and data models\n"
        "- Database schemas and migrations\n"
        "- Authentication, authorization, and security\n"
        "- Business logic and service layer\n\n"
        "**Important:** Post API endpoint specifications (routes, request/response "
        "schemas) to the shared context board so frontend agents can integrate."
    ),
    "frontend": (
        "## Your Role: Frontend Developer\n\n"
        "You are the frontend specialist. Focus on:\n"
        "- UI components, pages, and user interactions\n"
        "- State management and data fetching\n"
        "- Responsive design and accessibility\n"
        "- Integration with backend APIs\n\n"
        "**Important:** Check the shared context board for API contracts "
        "posted by backend agents before implementing data fetching."
    ),
    "tester": (
        "## Your Role: Test Engineer\n\n"
        "You are the quality assurance specialist. Focus on:\n"
        "- Writing comprehensive unit and integration tests\n"
        "- Testing edge cases and error handling\n"
        "- Ensuring code coverage for critical paths\n"
        "- Validating that acceptance criteria are met\n\n"
        "**Important:** Reference the task acceptance criteria carefully "
        "and test against the actual implementations."
    ),
    "reviewer": (
        "## Your Role: Code Reviewer\n\n"
        "You are the code review specialist. Focus on:\n"
        "- Reviewing all code for correctness and quality\n"
        "- Identifying bugs, security issues, and performance problems\n"
        "- Ensuring consistency across the codebase\n"
        "- Fixing issues you find directly\n\n"
        "**Important:** Review all files in the workspace and fix any "
        "issues, inconsistencies, or missing test coverage."
    ),
}

COORDINATION_INSTRUCTIONS = (
    "## Coordination Guidelines\n\n"
    "You are part of a multi-agent crew working on this project simultaneously. "
    "Other agents are working on different tasks in parallel on their own branches.\n\n"
    "**Rules:**\n"
    "1. Stay focused on YOUR assigned task — do not implement work assigned to others.\n"
    "2. If you define an API, data model, or interface that others will use, "
    "document it clearly in your code.\n"
    "3. Write clean, well-structured code that integrates naturally with the project.\n"
    "4. Commit frequently with clear commit messages.\n"
    "5. Ensure your code compiles/runs without errors before finishing.\n"
    "6. Do NOT modify configuration files or shared dependencies unless your task requires it.\n"
)


def build_agent_prompt(
    *,
    task_title: str,
    task_description: str | None,
    acceptance_criteria: str | None,
    role: str | None,
    context_entries: list[dict],
    project_name: str | None = None,
    design_document: str | None = None,
    branch_name: str,
    wave_number: int,
    total_waves: int,
) -> str:
    """Assemble the full prompt for a crew agent."""
    sections: list[str] = []

    # 1. Role
    if role and role in ROLE_PROMPTS:
        sections.append(ROLE_PROMPTS[role])

    # 2. Project context
    if project_name:
        header = f"## Project: {project_name}"
        if design_document:
            # Truncate very long design docs to keep prompt manageable
            doc = design_document[:8000]
            if len(design_document) > 8000:
                doc += "\n\n[... design document truncated for brevity ...]"
            header += f"\n\n{doc}"
        sections.append(header)

    # 3. Shared context board
    if context_entries:
        lines = ["## Shared Context Board", "", "Other agents have posted the following:"]
        for entry in context_entries:
            entry_type = entry.get("entry_type", "note")
            title = entry.get("title", "Untitled")
            content = entry.get("content", "")
            lines.append(f"\n### [{entry_type.upper()}] {title}\n{content}")
        sections.append("\n".join(lines))

    # 4. Task assignment
    task_lines = [f"## Your Task: {task_title}"]
    if task_description:
        task_lines.append(f"\n{task_description}")
    if acceptance_criteria:
        task_lines.append(f"\n### Acceptance Criteria\n{acceptance_criteria}")
    sections.append("\n".join(task_lines))

    # 5. Coordination instructions
    sections.append(COORDINATION_INSTRUCTIONS)

    # 6. Wave info
    sections.append(
        f"## Execution Context\n\n"
        f"- You are in **wave {wave_number + 1} of {total_waves}**\n"
        f"- Work on branch: `{branch_name}`\n"
        f"- Commit and push your changes when done: `git push -u origin HEAD`\n"
        f"- Do NOT create pull requests — the crew coordinator handles merges."
    )

    return "\n\n---\n\n".join(sections)
