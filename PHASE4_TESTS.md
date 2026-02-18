# Phase 4: Portal Backend API - Test Commands

## Prerequisites
- Services must be running: `make up`
- Obtain authentication token from portal login

## Environment Setup
```bash
export API_BASE="http://localhost:8080/api/skills"
export AUTH_TOKEN="<your_auth_token>"
```

## Test Commands

### 1. Create a Skill
```bash
curl -X POST "$API_BASE" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_skill",
    "content": "print(\"Hello from {{ name }}\")",
    "description": "A test skill",
    "category": "testing",
    "language": "python",
    "tags": ["test", "example"],
    "is_template": true
  }'
```

Expected response:
```json
{
  "skill_id": "<uuid>",
  "name": "test_skill",
  "content": "print(\"Hello from {{ name }}\")",
  "description": "A test skill",
  "category": "testing",
  "language": "python",
  "tags": ["test", "example"],
  "is_template": true,
  "created_at": "<timestamp>",
  "updated_at": "<timestamp>"
}
```

### 2. List Skills
```bash
curl "$API_BASE" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

With filters:
```bash
curl "$API_BASE?category_filter=testing&tag_filter=example&search_query=test" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "skills": [
    {
      "skill_id": "<uuid>",
      "name": "test_skill",
      "description": "A test skill",
      "category": "testing",
      "language": "python",
      "tags": ["test", "example"],
      "is_template": true,
      "created_at": "<timestamp>",
      "updated_at": "<timestamp>"
    }
  ],
  "count": 1
}
```

### 3. Get Single Skill
```bash
export SKILL_ID="<skill_id_from_create>"
curl "$API_BASE/$SKILL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "skill_id": "<uuid>",
  "name": "test_skill",
  "content": "print(\"Hello from {{ name }}\")",
  "description": "A test skill",
  "category": "testing",
  "language": "python",
  "tags": ["test", "example"],
  "is_template": true,
  "created_at": "<timestamp>",
  "updated_at": "<timestamp>"
}
```

### 4. Update Skill
```bash
curl -X PUT "$API_BASE/$SKILL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "An updated test skill",
    "tags": ["test", "example", "updated"]
  }'
```

Expected response: Updated skill object

### 5. Render Template Skill
```bash
curl -X POST "$API_BASE/$SKILL_ID/render" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "variables": {
      "name": "World"
    }
  }'
```

Expected response:
```json
{
  "rendered": "print(\"Hello from World\")"
}
```

### 6. Attach Skill to Project
```bash
export PROJECT_ID="<your_project_id>"
curl -X POST "$API_BASE/projects/$PROJECT_ID/skills/$SKILL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "project_id": "<uuid>",
  "skill_id": "<uuid>",
  "attached_at": "<timestamp>"
}
```

### 7. Get Project Skills
```bash
curl "$API_BASE/projects/$PROJECT_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "project_id": "<uuid>",
  "skills": [
    {
      "skill_id": "<uuid>",
      "name": "test_skill",
      "description": "An updated test skill",
      "attached_at": "<timestamp>"
    }
  ],
  "count": 1
}
```

### 8. Detach Skill from Project
```bash
curl -X DELETE "$API_BASE/projects/$PROJECT_ID/skills/$SKILL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "success": true,
  "message": "Skill detached from project"
}
```

### 9. Attach Skill to Task
```bash
export TASK_ID="<your_task_id>"
curl -X POST "$API_BASE/tasks/$TASK_ID/skills/$SKILL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "task_id": "<uuid>",
  "skill_id": "<uuid>",
  "attached_at": "<timestamp>"
}
```

### 10. Get Task Skills
```bash
curl "$API_BASE/tasks/$TASK_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "task_id": "<uuid>",
  "skills": [
    {
      "skill_id": "<uuid>",
      "name": "test_skill",
      "description": "An updated test skill",
      "attached_at": "<timestamp>"
    }
  ],
  "count": 1
}
```

### 11. Detach Skill from Task
```bash
curl -X DELETE "$API_BASE/tasks/$TASK_ID/skills/$SKILL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "success": true,
  "message": "Skill detached from task"
}
```

### 12. Delete Skill
```bash
curl -X DELETE "$API_BASE/$SKILL_ID" \
  -H "Authorization: Bearer $AUTH_TOKEN"
```

Expected response:
```json
{
  "success": true,
  "message": "Skill deleted successfully"
}
```

## Error Cases to Test

### Authentication Required
```bash
curl "$API_BASE"
# Expected: 401 Unauthorized or 403 Forbidden
```

### Skill Not Found
```bash
curl "$API_BASE/00000000-0000-0000-0000-000000000000" \
  -H "Authorization: Bearer $AUTH_TOKEN"
# Expected: 404 Not Found with error message
```

### Invalid Skill Data
```bash
curl -X POST "$API_BASE" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "test"
  }'
# Expected: 400 Bad Request (missing required 'name' field)
```

### Duplicate Skill Name
```bash
# Create first skill
curl -X POST "$API_BASE" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "duplicate", "content": "test"}'

# Try to create another with same name
curl -X POST "$API_BASE" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "duplicate", "content": "test2"}'
# Expected: 400 Bad Request with error about duplicate name
```

## Acceptance Criteria
- ✓ All routes return proper JSON responses
- ✓ Authentication is enforced on all endpoints
- ✓ User ownership validation works (can't access other users' skills)
- ✓ Error responses include helpful messages
- ✓ Template rendering works with Jinja2 variables
- ✓ Project/task attachments enforce referential integrity
