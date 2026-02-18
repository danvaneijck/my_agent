"""Skills module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="skills_modules",
    description=(
        "Skills registry for storing and managing reusable code snippets, "
        "procedures, configurations, and templates. Skills can be attached to "
        "projects and tasks for easy reference and application."
    ),
    tools=[
        # ── Skill CRUD operations ───────────────────────────────────────
        ToolDefinition(
            name="skills_modules.create_skill",
            description=(
                "Create a new skill. Skills can be code snippets, procedures, "
                "configurations, or templates with variable placeholders."
            ),
            parameters=[
                ToolParameter(name="name", type="string", description="Skill name (unique per user)."),
                ToolParameter(name="content", type="string", description="The skill content (code, config, instructions)."),
                ToolParameter(name="description", type="string", description="Description of what this skill does.", required=False),
                ToolParameter(
                    name="category", type="string",
                    description="Category: code, config, procedure, template, reference, etc.",
                    required=False,
                ),
                ToolParameter(
                    name="language", type="string",
                    description="Programming language: python, javascript, bash, markdown, etc.",
                    required=False,
                ),
                ToolParameter(
                    name="tags", type="array",
                    description="Array of tag strings for filtering and search.",
                    required=False,
                ),
                ToolParameter(
                    name="is_template", type="boolean",
                    description="Whether this skill uses Jinja2 template placeholders like {{variable}}.",
                    required=False,
                ),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.list_skills",
            description=(
                "List all skills for the user. Supports filtering by category, tags, "
                "and search query."
            ),
            parameters=[
                ToolParameter(
                    name="category_filter", type="string",
                    description="Filter by exact category match.",
                    required=False,
                ),
                ToolParameter(
                    name="tag_filter", type="string",
                    description="Filter by tag (returns skills containing this tag).",
                    required=False,
                ),
                ToolParameter(
                    name="search_query", type="string",
                    description="Search in skill name and description (case-insensitive).",
                    required=False,
                ),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.get_skill",
            description="Get full details for a single skill by ID.",
            parameters=[
                ToolParameter(name="skill_id", type="string", description="UUID of the skill."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.update_skill",
            description="Update skill fields. All parameters except skill_id are optional.",
            parameters=[
                ToolParameter(name="skill_id", type="string", description="UUID of the skill to update."),
                ToolParameter(name="name", type="string", description="New skill name.", required=False),
                ToolParameter(name="content", type="string", description="Updated content.", required=False),
                ToolParameter(name="description", type="string", description="Updated description.", required=False),
                ToolParameter(name="category", type="string", description="Updated category.", required=False),
                ToolParameter(name="language", type="string", description="Updated language.", required=False),
                ToolParameter(name="tags", type="array", description="Updated tags array.", required=False),
                ToolParameter(name="is_template", type="boolean", description="Updated template flag.", required=False),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.delete_skill",
            description=(
                "Delete a skill. This will also remove all project and task attachments "
                "for this skill (CASCADE delete)."
            ),
            parameters=[
                ToolParameter(name="skill_id", type="string", description="UUID of the skill to delete."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        # ── Project skill attachment ────────────────────────────────────
        ToolDefinition(
            name="skills_modules.attach_skill_to_project",
            description="Attach a skill to a project. The skill becomes available to all tasks in the project.",
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project."),
                ToolParameter(name="skill_id", type="string", description="UUID of the skill to attach."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.detach_skill_from_project",
            description="Detach a skill from a project.",
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project."),
                ToolParameter(name="skill_id", type="string", description="UUID of the skill to detach."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.get_project_skills",
            description="Get all skills attached to a project.",
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        # ── Task skill attachment ───────────────────────────────────────
        ToolDefinition(
            name="skills_modules.attach_skill_to_task",
            description="Attach a skill to a specific task.",
            parameters=[
                ToolParameter(name="task_id", type="string", description="UUID of the task."),
                ToolParameter(name="skill_id", type="string", description="UUID of the skill to attach."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.detach_skill_from_task",
            description="Detach a skill from a task.",
            parameters=[
                ToolParameter(name="task_id", type="string", description="UUID of the task."),
                ToolParameter(name="skill_id", type="string", description="UUID of the skill to detach."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="skills_modules.get_task_skills",
            description="Get all skills attached to a task.",
            parameters=[
                ToolParameter(name="task_id", type="string", description="UUID of the task."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        # ── Template rendering ──────────────────────────────────────────
        ToolDefinition(
            name="skills_modules.render_skill",
            description=(
                "Render a template skill with variable substitution. For skills with "
                "is_template=true, replaces {{variable}} placeholders with provided values. "
                "Returns the rendered content."
            ),
            parameters=[
                ToolParameter(name="skill_id", type="string", description="UUID of the skill to render."),
                ToolParameter(
                    name="variables", type="object",
                    description='Dictionary of variable values, e.g. {"function_name": "calculate_total", "params": "items"}.',
                    required=False,
                ),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
    ],
)
