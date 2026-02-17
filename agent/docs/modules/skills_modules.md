# Skills Modules Documentation

## Overview

The **skills_modules** module provides a registry system for reusable skills (code snippets, configurations, procedures) that can be attached to projects and tasks. Skills support template rendering with Jinja2 variable substitution, making them highly flexible for different contexts.

**Module Name**: `skills_modules`
**Base URL**: `http://skills-modules:8000`
**Permission Level**: `user`
**Infrastructure**: PostgreSQL

---

## Use Cases

- Store reusable code snippets (API clients, utility functions, algorithms)
- Define configuration templates for different environments
- Document step-by-step procedures for common tasks
- Create skill libraries organized by category and tags
- Attach skills to projects for team reference
- Attach skills to specific tasks for context-specific guidance
- Render template skills with custom variables

---

## Architecture

### Database Schema

#### user_skills Table
Stores skill definitions per user.

```sql
CREATE TABLE user_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR,  -- e.g., "code", "config", "procedure", "template", "reference"
    content TEXT NOT NULL,
    language VARCHAR,  -- e.g., "python", "javascript", "bash", etc.
    tags TEXT,  -- JSON array of tag strings
    is_template BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);

CREATE INDEX idx_user_skills_user_id ON user_skills(user_id);
CREATE INDEX idx_user_skills_category ON user_skills(category);
```

#### project_skills Table
Junction table linking skills to projects.

```sql
CREATE TABLE project_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES user_skills(id) ON DELETE CASCADE,
    order_index INTEGER DEFAULT 0,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, skill_id)
);
```

#### task_skills Table
Junction table linking skills to tasks.

```sql
CREATE TABLE task_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES project_tasks(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES user_skills(id) ON DELETE CASCADE,
    order_index INTEGER DEFAULT 0,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(task_id, skill_id)
);
```

---

## Tools

### 1. create_skill

Create a new skill.

**Parameters**:
- `name` (string, required): Unique skill name
- `content` (string, required): Skill content (code, config, instructions)
- `description` (string, optional): Brief description
- `category` (string, optional): Category (code, config, procedure, template, reference)
- `language` (string, optional): Programming language
- `tags` (array[string], optional): Tags for filtering/search
- `is_template` (boolean, optional): Whether skill uses Jinja2 templates

**Returns**:
```json
{
  "skill_id": "uuid",
  "name": "my_skill",
  "content": "...",
  "description": "...",
  "category": "code",
  "language": "python",
  "tags": ["api", "http"],
  "is_template": false,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

**Example**:
```python
# Via LLM
"Create a skill named 'api_client' with Python code for a reusable HTTP client"

# Direct API call
POST /api/skills
{
  "name": "api_client",
  "content": "import requests\n\nclass APIClient:\n    def __init__(self, base_url):\n        self.base_url = base_url\n        self.session = requests.Session()",
  "description": "Reusable API client",
  "category": "code",
  "language": "python",
  "tags": ["api", "http", "client"]
}
```

---

### 2. list_skills

List all skills for the current user with optional filtering.

**Parameters**:
- `category_filter` (string, optional): Filter by category
- `tag_filter` (string, optional): Filter by tag
- `search_query` (string, optional): Search in name/description

**Returns**:
```json
{
  "skills": [
    {
      "skill_id": "uuid",
      "name": "skill_name",
      "description": "...",
      "category": "code",
      "language": "python",
      "tags": ["tag1", "tag2"],
      "is_template": false,
      "created_at": "2024-01-01T12:00:00Z",
      "updated_at": "2024-01-01T12:00:00Z"
    }
  ],
  "count": 1
}
```

**Example**:
```python
# Via LLM
"List all my Python skills tagged with 'api'"

# Direct API call
GET /api/skills?category_filter=code&tag_filter=api&search_query=client
```

---

### 3. get_skill

Retrieve a specific skill by ID.

**Parameters**:
- `skill_id` (string, required): Skill UUID

**Returns**:
```json
{
  "skill_id": "uuid",
  "name": "skill_name",
  "content": "full content here...",
  "description": "...",
  "category": "code",
  "language": "python",
  "tags": ["tag1", "tag2"],
  "is_template": false,
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:00:00Z"
}
```

---

### 4. update_skill

Update an existing skill.

**Parameters**:
- `skill_id` (string, required): Skill UUID
- `name` (string, optional): New name
- `content` (string, optional): New content
- `description` (string, optional): New description
- `category` (string, optional): New category
- `language` (string, optional): New language
- `tags` (array[string], optional): New tags
- `is_template` (boolean, optional): New template flag

**Returns**: Updated skill object

**Example**:
```python
# Via LLM
"Update my api_client skill to add error handling"

# Direct API call
PUT /api/skills/{skill_id}
{
  "description": "Updated description",
  "tags": ["api", "http", "client", "error-handling"]
}
```

---

### 5. delete_skill

Delete a skill and its attachments.

**Parameters**:
- `skill_id` (string, required): Skill UUID

**Returns**:
```json
{
  "success": true,
  "message": "Skill deleted successfully"
}
```

**Note**: Cascade deletes all project and task attachments.

---

### 6. attach_skill_to_project

Attach a skill to a project.

**Parameters**:
- `project_id` (string, required): Project UUID
- `skill_id` (string, required): Skill UUID

**Returns**:
```json
{
  "project_id": "uuid",
  "skill_id": "uuid",
  "attached_at": "2024-01-01T12:00:00Z"
}
```

**Example**:
```python
# Via LLM
"Attach my api_client skill to the backend_api project"
```

---

### 7. detach_skill_from_project

Remove a skill from a project.

**Parameters**:
- `project_id` (string, required): Project UUID
- `skill_id` (string, required): Skill UUID

**Returns**:
```json
{
  "success": true,
  "message": "Skill detached from project"
}
```

---

### 8. attach_skill_to_task

Attach a skill to a specific task.

**Parameters**:
- `task_id` (string, required): Task UUID
- `skill_id` (string, required): Skill UUID

**Returns**:
```json
{
  "task_id": "uuid",
  "skill_id": "uuid",
  "attached_at": "2024-01-01T12:00:00Z"
}
```

---

### 9. detach_skill_from_task

Remove a skill from a task.

**Parameters**:
- `task_id` (string, required): Task UUID
- `skill_id` (string, required): Skill UUID

**Returns**:
```json
{
  "success": true,
  "message": "Skill detached from task"
}
```

---

### 10. get_project_skills

List all skills attached to a project.

**Parameters**:
- `project_id` (string, required): Project UUID

**Returns**:
```json
{
  "project_id": "uuid",
  "skills": [
    {
      "skill_id": "uuid",
      "skill_name": "api_client",
      "skill_description": "...",
      "skill_category": "code",
      "skill_language": "python",
      "attached_at": "2024-01-01T12:00:00Z"
    }
  ],
  "count": 1
}
```

---

### 11. get_task_skills

List all skills attached to a task.

**Parameters**:
- `task_id` (string, required): Task UUID

**Returns**:
```json
{
  "task_id": "uuid",
  "skills": [
    {
      "skill_id": "uuid",
      "skill_name": "api_client",
      "skill_description": "...",
      "skill_category": "code",
      "skill_language": "python",
      "attached_at": "2024-01-01T12:00:00Z"
    }
  ],
  "count": 1
}
```

---

### 12. render_skill

Render a template skill with variable substitution.

**Parameters**:
- `skill_id` (string, required): Skill UUID
- `variables` (object, optional): Key-value pairs for template variables

**Returns**:
```json
{
  "rendered": "def test_user_login():\n    \"\"\"Test user authentication\"\"\"\n    ..."
}
```

**Example**:

**Template Skill Content**:
```python
def test_{{function_name}}():
    """Test {{description}}"""
    # Arrange
    {{arrange_code}}

    # Act
    result = {{function_call}}

    # Assert
    assert result == {{expected_result}}
```

**Render Request**:
```python
# Via LLM
"Render my test_function_template skill for testing user login"

# Direct API call
POST /api/skills/{skill_id}/render
{
  "variables": {
    "function_name": "user_login",
    "description": "user authentication",
    "arrange_code": "user = User('test', 'password')",
    "function_call": "user.login()",
    "expected_result": "True"
  }
}
```

**Response**:
```json
{
  "rendered": "def test_user_login():\n    \"\"\"Test user authentication\"\"\"\n    # Arrange\n    user = User('test', 'password')\n    \n    # Act\n    result = user.login()\n    \n    # Assert\n    assert result == True"
}
```

---

## Portal Integration

### Skills Page (`/skills`)

- Browse all skills in grid layout
- Search by name/description
- Filter by category
- Filter by tag
- Create new skills via modal
- Click skill card to view details

### Skill Detail Page (`/skills/:skillId`)

- View full skill content
- Edit skill (opens modal)
- Delete skill (with confirmation)
- See template indicator for template skills
- Display tags, category, language, dates

### Project Detail Page

**Skills Section** displays:
- Count of attached skills
- Skill badges with name, category
- "Add Skill" button (opens SkillPicker)
- Remove button for each skill

### Task Detail Page

**Skills Section** displays:
- Count of attached skills
- Skill badges with name, category
- "Add Skill" button (opens SkillPicker)
- Remove button for each skill

---

## Categories

Suggested categories (not enforced, user-defined):

- **code**: Code snippets, functions, classes
- **config**: Configuration files, settings
- **procedure**: Step-by-step instructions
- **template**: Reusable templates with placeholders
- **reference**: Documentation, examples

---

## Template System

Skills with `is_template=true` support Jinja2 variable substitution.

### Template Syntax

Use `{{ variable_name }}` for variable placeholders:

```python
# Simple variable
name = "{{user_name}}"

# In strings
message = "Hello {{name}}, welcome to {{app_name}}!"

# In code
def {{function_name}}({{params}}):
    return {{implementation}}
```

### Variable Scope

Variables are passed as a flat dictionary:

```json
{
  "user_name": "Alice",
  "app_name": "MyApp",
  "function_name": "calculate_total",
  "params": "items: list",
  "implementation": "sum(item.price for item in items)"
}
```

### Advanced Templates

Jinja2 supports conditionals and loops:

```python
def {{function_name}}({{params}}):
    """{{description}}"""
    {% if validate %}
    if not {{validation_check}}:
        raise ValueError("Invalid input")
    {% endif %}

    {% for step in steps %}
    # Step {{loop.index}}: {{step}}
    {% endfor %}

    return {{return_value}}
```

---

## User Isolation

All skill operations enforce user ownership:

- Users can only see their own skills
- Cannot attach other users' skills
- Cannot modify other users' skills
- Enforced at both API and module levels

---

## Best Practices

### Naming

- Use descriptive, unique names: `api_client`, `test_function_template`
- Avoid generic names: `code1`, `snippet`
- Use underscores, not spaces: `my_skill` not `my skill`

### Organization

- Use categories consistently
- Tag liberally for searchability
- Add clear descriptions
- Specify language when applicable

### Templates

- Mark skills as templates when they contain `{{ variables }}`
- Document required variables in description
- Test template rendering before deploying
- Use clear variable names: `{{api_key}}` not `{{x}}`

### Content

- Keep skills focused and modular
- Include comments in code skills
- Format content for readability
- Update regularly

### Attachments

- Attach skills to projects for team visibility
- Attach skills to specific tasks for context
- Remove skills when no longer relevant
- Use skills as reference, not dependencies

---

## Common Workflows

### Create and Attach Skill

```python
# 1. Create skill
"Create a skill named 'error_handler' with Python error handling code"

# 2. Attach to project
"Attach my error_handler skill to the backend_api project"

# 3. Attach to specific task
"Attach my error_handler skill to the task for implementing user login"
```

### Search and Filter

```python
# Search
"Show me all skills with 'api' in the name"

# Filter by category
"List my code skills"

# Filter by tag
"Show skills tagged with 'testing'"

# Combined
"Find Python code skills tagged with 'api'"
```

### Template Workflow

```python
# 1. Create template skill
"Create a template skill for test functions with placeholders for function name and test logic"

# 2. Render with variables
"Render my test_function_template for testing user authentication"

# 3. Use rendered output
# Copy rendered code to your test file
```

---

## Troubleshooting

### Skill Not Found

**Symptom**: 404 error when accessing skill

**Cause**: Skill doesn't exist or belongs to another user

**Solution**: Verify skill_id and user ownership

### Template Rendering Failed

**Symptom**: Error when rendering template

**Cause**: Invalid Jinja2 syntax or missing variables

**Solution**:
- Check template syntax
- Provide all required variables
- Test with simple variables first

### Duplicate Name Error

**Symptom**: Cannot create skill with existing name

**Cause**: User already has a skill with that name

**Solution**: Choose a different name or update existing skill

### Attachment Failed

**Symptom**: Cannot attach skill to project/task

**Cause**: Project/task doesn't exist or belongs to another user

**Solution**: Verify project/task ownership and ID

---

## Permissions

**Required Permission Level**: `user`

All tools require at minimum `user` permission level. Guest users cannot access skills functionality.

---

## Infrastructure

**Database**: PostgreSQL
**Tables**: `user_skills`, `project_skills`, `task_skills`
**Dependencies**: Jinja2 for template rendering

---

## API Endpoints (Portal)

All endpoints require authentication.

```
GET    /api/skills                           # List skills
POST   /api/skills                           # Create skill
GET    /api/skills/{skill_id}                # Get skill
PUT    /api/skills/{skill_id}                # Update skill
DELETE /api/skills/{skill_id}                # Delete skill
POST   /api/skills/{skill_id}/render         # Render template

POST   /api/skills/projects/{project_id}/skills/{skill_id}  # Attach to project
DELETE /api/skills/projects/{project_id}/skills/{skill_id}  # Detach from project
GET    /api/skills/projects/{project_id}                    # Get project skills

POST   /api/skills/tasks/{task_id}/skills/{skill_id}        # Attach to task
DELETE /api/skills/tasks/{task_id}/skills/{skill_id}        # Detach from task
GET    /api/skills/tasks/{task_id}                          # Get task skills
```

---

## Module Endpoints

Internal module endpoints (not directly accessible):

```
GET  /manifest   # Returns tool definitions
POST /execute    # Executes a tool
GET  /health     # Health check
```

---

## Example Use Cases

### 1. API Client Library

Store a reusable HTTP client for consistent API calls across projects.

```python
# Skill: api_client
# Category: code
# Language: python

import requests
from typing import Optional, Dict, Any

class APIClient:
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.session = requests.Session()
        if api_key:
            self.session.headers['Authorization'] = f'Bearer {api_key}'

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        response = self.session.get(f"{self.base_url}{endpoint}", params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.session.post(f"{self.base_url}{endpoint}", json=data)
        response.raise_for_status()
        return response.json()
```

### 2. Test Function Template

Create a template for generating test functions.

```python
# Skill: test_function_template
# Category: template
# Is Template: true

def test_{{function_name}}():
    """Test {{description}}"""
    # Arrange
    {{setup_code}}

    # Act
    result = {{function_call}}

    # Assert
    assert result == {{expected_result}}, f"Expected {{expected_result}}, got {result}"
```

### 3. Deployment Checklist

Document deployment procedures.

```markdown
# Skill: deployment_checklist
# Category: procedure

## Pre-Deployment
1. Run all tests: `pytest`
2. Check code coverage: `pytest --cov`
3. Update version number in setup.py
4. Update CHANGELOG.md
5. Create git tag: `git tag -a v1.0.0 -m "Release 1.0.0"`

## Deployment
1. Build Docker image: `docker build -t app:1.0.0 .`
2. Push to registry: `docker push app:1.0.0`
3. Update k8s manifests with new image tag
4. Apply manifests: `kubectl apply -f k8s/`
5. Verify deployment: `kubectl rollout status deployment/app`

## Post-Deployment
1. Run smoke tests
2. Monitor logs for errors
3. Check metrics dashboard
4. Notify team in Slack
```

### 4. Environment Configuration

Store environment-specific configuration templates.

```yaml
# Skill: docker_compose_config
# Category: config
# Is Template: true

version: '3.8'

services:
  app:
    image: {{app_image}}
    ports:
      - "{{app_port}}:8000"
    environment:
      - DATABASE_URL={{database_url}}
      - REDIS_URL={{redis_url}}
      - API_KEY={{api_key}}
    depends_on:
      - db
      - redis

  db:
    image: postgres:16
    environment:
      - POSTGRES_DB={{db_name}}
      - POSTGRES_PASSWORD={{db_password}}

  redis:
    image: redis:7
    ports:
      - "6379:6379"
```

---

## Future Enhancements

- Skill versioning and history
- Public skill library (community-shared)
- Full-text search with embeddings
- Skill usage analytics
- Export/import skill collections
- Skill testing/validation framework
- Integration with claude_code for automatic application

---

## See Also

- [Module System Overview](overview.md)
- [Project Planner Module](project_planner.md)
- [Adding Modules Guide](ADDING_MODULES.md)
- [Database Schema Documentation](../architecture/database-schema.md)
