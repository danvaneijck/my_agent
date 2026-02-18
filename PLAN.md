# Implementation Plan: Skills Registry Module

## Project Overview

This project adds a **skills registry system** to the AI agent platform. Users can define reusable skills (code snippets, procedures, configurations) that can be attached to projects and tasks. A new module (`skills_modules`) provides CRUD operations and skill application functionality, while the web portal gains a new navigation section for managing and viewing skills.

---

## Architecture Overview

### Core Components

1. **Skills Module** (`agent/modules/skills_modules/`)
   - Independent FastAPI microservice
   - Provides tools for creating, listing, updating, deleting, and applying skills
   - Integrates with PostgreSQL for persistence
   - Follows existing module patterns (research, project_planner, etc.)

2. **Database Schema** (`shared/models/`)
   - `skills` table: stores skill definitions per user
   - `project_skills` table: junction table linking skills to projects
   - `task_skills` table: junction table linking skills to tasks

3. **Portal Integration** (`agent/portal/`)
   - New `/skills` route and page
   - Navigation item in Sidebar component
   - UI for browsing, creating, editing, and deleting skills
   - Project/task detail pages show attached skills

---

## Database Schema Design

### Skills Table (`user_skills`)

```sql
CREATE TABLE user_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR,  -- e.g., "code", "config", "procedure", "template"
    content TEXT NOT NULL,  -- The actual skill content (code, config, instructions)
    language VARCHAR,  -- Optional: "python", "javascript", "bash", "markdown", etc.
    tags TEXT[],  -- Array of tag strings for filtering/search
    is_template BOOLEAN DEFAULT FALSE,  -- Whether this skill is a template with placeholders
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, name)
);

CREATE INDEX idx_user_skills_user_id ON user_skills(user_id);
CREATE INDEX idx_user_skills_category ON user_skills(category);
```

### Project Skills Junction Table (`project_skills`)

```sql
CREATE TABLE project_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES user_skills(id) ON DELETE CASCADE,
    order_index INTEGER DEFAULT 0,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(project_id, skill_id)
);

CREATE INDEX idx_project_skills_project_id ON project_skills(project_id);
CREATE INDEX idx_project_skills_skill_id ON project_skills(skill_id);
```

### Task Skills Junction Table (`task_skills`)

```sql
CREATE TABLE task_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    task_id UUID NOT NULL REFERENCES project_tasks(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES user_skills(id) ON DELETE CASCADE,
    order_index INTEGER DEFAULT 0,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(task_id, skill_id)
);

CREATE INDEX idx_task_skills_task_id ON task_skills(task_id);
CREATE INDEX idx_task_skills_skill_id ON task_skills(skill_id);
```

---

## Module Design: skills_modules

### Tool Manifest

The module provides the following tools:

1. **skills_modules.create_skill**
   - Parameters: name, description, category, content, language, tags, is_template, user_id
   - Returns: skill_id, created_at
   - Permission: `user`

2. **skills_modules.list_skills**
   - Parameters: category_filter (optional), tag_filter (optional), search_query (optional), user_id
   - Returns: list of skill summaries
   - Permission: `user`

3. **skills_modules.get_skill**
   - Parameters: skill_id, user_id
   - Returns: full skill details
   - Permission: `user`

4. **skills_modules.update_skill**
   - Parameters: skill_id, name, description, category, content, language, tags, is_template, user_id
   - Returns: success, updated_at
   - Permission: `user`

5. **skills_modules.delete_skill**
   - Parameters: skill_id, user_id
   - Returns: success
   - Permission: `user`

6. **skills_modules.attach_skill_to_project**
   - Parameters: project_id, skill_id, user_id
   - Returns: success, applied_at
   - Permission: `user`

7. **skills_modules.detach_skill_from_project**
   - Parameters: project_id, skill_id, user_id
   - Returns: success
   - Permission: `user`

8. **skills_modules.attach_skill_to_task**
   - Parameters: task_id, skill_id, user_id
   - Returns: success, applied_at
   - Permission: `user`

9. **skills_modules.detach_skill_from_task**
   - Parameters: task_id, skill_id, user_id
   - Returns: success
   - Permission: `user`

10. **skills_modules.get_project_skills**
    - Parameters: project_id, user_id
    - Returns: list of skills attached to project
    - Permission: `user`

11. **skills_modules.get_task_skills**
    - Parameters: task_id, user_id
    - Returns: list of skills attached to task
    - Permission: `user`

12. **skills_modules.render_skill**
    - Parameters: skill_id, variables (dict, optional), user_id
    - Returns: rendered content (for template skills with placeholders)
    - Permission: `user`

### File Structure

```
agent/modules/skills_modules/
├── __init__.py           # Empty
├── Dockerfile            # Python 3.12-slim base
├── requirements.txt      # FastAPI, SQLAlchemy, asyncpg, jinja2 (for templates)
├── main.py               # FastAPI app with /manifest, /execute, /health
├── manifest.py           # Tool definitions
└── tools.py              # Async tool implementations
```

---

## Portal Integration Design

### Navigation Changes

**File**: `agent/portal/frontend/src/components/layout/Sidebar.tsx`

Add new navigation item to `NAV_ITEMS`:

```typescript
{
  to: "/skills",
  icon: Lightbulb,  // or Layers, BookOpen, etc.
  label: "Skills"
}
```

### New Route and Page

**File**: `agent/portal/frontend/src/App.tsx`

Add route:
```typescript
const SkillsPage = lazy(() => import("@/pages/SkillsPage"));

// In Routes
<Route path="/skills" element={<SkillsPage />} />
<Route path="/skills/:skillId" element={<SkillDetailPage />} />
```

### Skills Page Components

1. **SkillsPage.tsx**
   - Main skills browser
   - Filter by category, tags
   - Search functionality
   - Grid/list view of skill cards
   - "New Skill" button

2. **SkillDetailPage.tsx**
   - View/edit skill details
   - Syntax highlighting for content
   - Show where skill is applied (projects/tasks)
   - Delete skill option

3. **NewSkillModal.tsx**
   - Form for creating new skills
   - Fields: name, description, category, content, language, tags
   - Template toggle

4. **SkillCard.tsx**
   - Display skill summary
   - Category badge
   - Tag pills
   - Click to open detail

5. **SkillPicker.tsx** (for project/task detail pages)
   - Modal or dropdown to select skills
   - Filter by category
   - Attach/detach actions

### API Client Methods

**File**: `agent/portal/frontend/src/api/client.ts`

Add methods:
- `getSkills(filters)`
- `getSkill(id)`
- `createSkill(data)`
- `updateSkill(id, data)`
- `deleteSkill(id)`
- `attachSkillToProject(projectId, skillId)`
- `detachSkillFromProject(projectId, skillId)`
- `attachSkillToTask(taskId, skillId)`
- `detachSkillFromTask(taskId, skillId)`
- `getProjectSkills(projectId)`
- `getTaskSkills(taskId)`

### Portal Backend Routes

**File**: `agent/portal/routers/skills.py`

Proxy routes to skills module:
- `GET /api/skills` - list skills
- `POST /api/skills` - create skill
- `GET /api/skills/{skill_id}` - get skill
- `PUT /api/skills/{skill_id}` - update skill
- `DELETE /api/skills/{skill_id}` - delete skill
- `POST /api/projects/{project_id}/skills/{skill_id}` - attach
- `DELETE /api/projects/{project_id}/skills/{skill_id}` - detach
- `GET /api/projects/{project_id}/skills` - list project skills
- `POST /api/tasks/{task_id}/skills/{skill_id}` - attach
- `DELETE /api/tasks/{task_id}/skills/{skill_id}` - detach
- `GET /api/tasks/{task_id}/skills` - list task skills

### Enhanced Project/Task Detail Pages

**Files**:
- `agent/portal/frontend/src/pages/ProjectDetailPage.tsx`
- `agent/portal/frontend/src/pages/ProjectTaskDetailPage.tsx`

Add sections:
- "Applied Skills" list
- "Add Skill" button
- Skill badges with remove option

---

## Implementation Phases

### Phase 1: Database Foundation
**Goal**: Create database schema and models

**Tasks**:
1. Create `UserSkill` model in `agent/shared/shared/models/user_skill.py`
   - Description: Define SQLAlchemy ORM model for user_skills table
   - Acceptance criteria: Model has all fields, proper relationships, UUID primary key, timestamps

2. Create `ProjectSkill` junction model in `agent/shared/shared/models/project_skill.py`
   - Description: Define SQLAlchemy ORM model for project_skills junction table
   - Acceptance criteria: Foreign keys to projects and user_skills, unique constraint

3. Create `TaskSkill` junction model in `agent/shared/shared/models/task_skill.py`
   - Description: Define SQLAlchemy ORM model for task_skills junction table
   - Acceptance criteria: Foreign keys to project_tasks and user_skills, unique constraint

4. Update `agent/shared/shared/models/__init__.py`
   - Description: Export new models
   - Acceptance criteria: All three new models in __all__ list and imported

5. Create Alembic migration
   - Description: Generate and review migration for new tables
   - Acceptance criteria: Migration creates all three tables with proper indexes and constraints

6. Apply migration
   - Description: Run `make migrate` to create tables in database
   - Acceptance criteria: Tables exist in database, no migration errors

---

### Phase 2: Skills Module Core
**Goal**: Build the skills_modules microservice with CRUD operations

**Tasks**:
1. Create module directory structure
   - Description: Create `agent/modules/skills_modules/` with __init__.py
   - Acceptance criteria: Directory exists with empty __init__.py

2. Create `manifest.py` with tool definitions
   - Description: Define all 12 tools with parameters and descriptions
   - Acceptance criteria: ModuleManifest with all tools, proper naming (skills_modules.*), permission levels set

3. Create `tools.py` with SkillsTools class
   - Description: Implement all async tool methods
   - Acceptance criteria:
     - All methods accept user_id parameter
     - CRUD operations validate user ownership
     - Attach/detach operations verify both resources belong to user
     - Template rendering uses Jinja2 for variable substitution
     - Proper error handling

4. Create `main.py` FastAPI app
   - Description: Wire up /manifest, /execute, /health endpoints
   - Acceptance criteria: Follows standard module pattern, routes to tool methods, catches exceptions

5. Create `Dockerfile`
   - Description: Standard Python 3.12-slim with shared package
   - Acceptance criteria: Follows existing module Dockerfile pattern

6. Create `requirements.txt`
   - Description: List dependencies (fastapi, uvicorn, sqlalchemy, asyncpg, structlog, jinja2)
   - Acceptance criteria: All required packages listed with versions

---

### Phase 3: Module Registration
**Goal**: Register module in system configuration

**Tasks**:
1. Add module to `agent/shared/shared/config.py`
   - Description: Add "skills_modules": "http://skills-modules:8000" to module_services dict
   - Acceptance criteria: Entry added to config

2. Add service to `agent/docker-compose.yml`
   - Description: Add skills-modules service block under modules section
   - Acceptance criteria: Service block with correct build context, env_file, networks, depends_on

3. Build and start module
   - Description: Run `make build-module M=skills-modules && make up`
   - Acceptance criteria: Module builds successfully, starts without errors

4. Verify module registration
   - Description: Run `make list-modules` or check core logs
   - Acceptance criteria: skills_modules appears in discovered modules list

---

### Phase 4: Portal Backend API
**Goal**: Create portal backend routes for skills

**Tasks**:
1. Create `agent/portal/routers/skills.py`
   - Description: Create FastAPI router with proxy routes to skills module
   - Acceptance criteria:
     - All CRUD endpoints implemented
     - Attach/detach endpoints for projects and tasks
     - Proper authentication using portal API key
     - Error handling for module communication failures

2. Register router in portal main.py
   - Description: Import and include skills router
   - Acceptance criteria: Router added to FastAPI app with /api prefix

3. Test backend routes
   - Description: Use curl or httpie to test API endpoints
   - Acceptance criteria: All routes return proper responses, authentication works

---

### Phase 5: Portal Frontend - Core Components
**Goal**: Build reusable skill UI components

**Tasks**:
1. Define TypeScript types in `agent/portal/frontend/src/types/index.ts`
   - Description: Add Skill, SkillSummary, ProjectSkill, TaskSkill interfaces
   - Acceptance criteria: All fields typed, matches backend schema

2. Create API client methods in `agent/portal/frontend/src/api/client.ts`
   - Description: Add all skill-related API methods
   - Acceptance criteria: Methods match backend routes, proper error handling

3. Create `SkillCard.tsx` component
   - Description: Display skill summary with category badge, tags, preview
   - Acceptance criteria: Responsive, dark mode support, click handler

4. Create `NewSkillModal.tsx` component
   - Description: Form for creating/editing skills with validation
   - Acceptance criteria:
     - All fields with proper input types
     - Code editor for content field (Monaco or textarea)
     - Category dropdown
     - Tag input with chips
     - Template toggle
     - Validation and error display

5. Create `SkillPicker.tsx` component
   - Description: Modal for selecting skills to attach (searchable, filterable)
   - Acceptance criteria:
     - Search by name
     - Filter by category
     - Shows already-attached skills
     - Attach/detach actions

---

### Phase 6: Portal Frontend - Skills Pages
**Goal**: Build main skills browsing and management pages

**Tasks**:
1. Create `agent/portal/frontend/src/pages/SkillsPage.tsx`
   - Description: Main skills page with grid/list view, filters, search
   - Acceptance criteria:
     - Fetches skills from API
     - Filter by category dropdown
     - Search input
     - Grid of SkillCard components
     - "New Skill" button opens modal
     - Loading and error states

2. Create `agent/portal/frontend/src/pages/SkillDetailPage.tsx`
   - Description: Single skill detail view/edit page
   - Acceptance criteria:
     - Shows full skill details
     - Code syntax highlighting for content
     - Edit mode toggle
     - Shows projects/tasks using this skill
     - Delete confirmation
     - Back navigation

3. Create `agent/portal/frontend/src/hooks/useSkills.ts`
   - Description: React hook for fetching and managing skills
   - Acceptance criteria: Handles loading, error, refetch, caching

4. Create `agent/portal/frontend/src/hooks/useSkill.ts`
   - Description: React hook for single skill fetch
   - Acceptance criteria: Handles loading, error, refetch

---

### Phase 7: Portal Frontend - Navigation
**Goal**: Add skills to portal navigation

**Tasks**:
1. Update `agent/portal/frontend/src/components/layout/Sidebar.tsx`
   - Description: Add Skills nav item to NAV_ITEMS array
   - Acceptance criteria:
     - Icon imported (Lightbulb, BookOpen, or Layers from lucide-react)
     - Item added in logical position (after Projects, before Repos)
     - Active state works

2. Update `agent/portal/frontend/src/App.tsx`
   - Description: Add lazy-loaded routes for /skills and /skills/:skillId
   - Acceptance criteria: Routes registered, lazy loading works

3. Test navigation
   - Description: Click through portal, verify skills pages load
   - Acceptance criteria: Navigation works, pages render, no console errors

---

### Phase 8: Portal Frontend - Project/Task Integration
**Goal**: Show and manage skills on project and task detail pages

**Tasks**:
1. Update `agent/portal/frontend/src/pages/ProjectDetailPage.tsx`
   - Description: Add "Skills" section showing attached skills
   - Acceptance criteria:
     - Fetches project skills on load
     - Displays skill badges/cards
     - "Add Skill" button opens SkillPicker
     - Remove skill option
     - Refetches after changes

2. Update `agent/portal/frontend/src/pages/ProjectTaskDetailPage.tsx`
   - Description: Add "Skills" section showing attached skills
   - Acceptance criteria:
     - Fetches task skills on load
     - Displays skill badges/cards
     - "Add Skill" button opens SkillPicker
     - Remove skill option
     - Refetches after changes

3. Create `agent/portal/frontend/src/hooks/useProjectSkills.ts`
   - Description: React hook for project skills
   - Acceptance criteria: Fetch, attach, detach operations

4. Create `agent/portal/frontend/src/hooks/useTaskSkills.ts`
   - Description: React hook for task skills
   - Acceptance criteria: Fetch, attach, detach operations

---

### Phase 9: Testing and Polish
**Goal**: Test all functionality and fix bugs

**Tasks**:
1. End-to-end skill lifecycle test
   - Description: Create skill via portal, attach to project, verify in DB
   - Acceptance criteria: Full workflow works, data persists correctly

2. Test skill templates with rendering
   - Description: Create template skill with {{variable}} placeholders, render with variables
   - Acceptance criteria: Template rendering works via API

3. Test permission boundaries
   - Description: Verify users can only see/edit their own skills
   - Acceptance criteria: User isolation works, no cross-user access

4. UI polish and responsiveness
   - Description: Test on mobile, tablet, desktop; dark/light themes
   - Acceptance criteria: Responsive layout, proper theme colors, no visual glitches

5. Error handling and edge cases
   - Description: Test delete skill used by projects, invalid inputs, network errors
   - Acceptance criteria: Proper error messages, graceful degradation

6. Update documentation
   - Description: Add skills_modules to CLAUDE.md and create module doc
   - Acceptance criteria: Module listed in quick reference, usage examples added

---

## Technical Decisions

### Template System
Skills marked as `is_template=true` support Jinja2 variable substitution. Example:

```python
# Skill content
"""
def {{function_name}}({{params}}):
    \"\"\"{{description}}\"\"\"
    return {{implementation}}
"""

# Rendered with variables
{
  "function_name": "calculate_total",
  "params": "items: list",
  "description": "Calculate total price",
  "implementation": "sum(item.price for item in items)"
}
```

### Skill Categories
Suggested categories (not enforced at DB level):
- `code` - Code snippets, functions, classes
- `config` - Configuration files, settings
- `procedure` - Step-by-step instructions
- `template` - Reusable templates with placeholders
- `reference` - Documentation, examples

### Search and Filtering
- Search by name/description using SQL ILIKE
- Filter by category (exact match)
- Filter by tags (ANY array match)
- Future: Full-text search with pgvector embeddings

### Attachment Semantics
- Project skills: Available to all tasks in project (inherited)
- Task skills: Specific to that task only
- UI shows both inherited and direct skills on task detail page

---

## Files to Create

### Backend
1. `agent/shared/shared/models/user_skill.py`
2. `agent/shared/shared/models/project_skill.py`
3. `agent/shared/shared/models/task_skill.py`
4. `agent/alembic/versions/{timestamp}_add_skills_tables.py`
5. `agent/modules/skills_modules/__init__.py`
6. `agent/modules/skills_modules/manifest.py`
7. `agent/modules/skills_modules/tools.py`
8. `agent/modules/skills_modules/main.py`
9. `agent/modules/skills_modules/Dockerfile`
10. `agent/modules/skills_modules/requirements.txt`
11. `agent/portal/routers/skills.py`

### Frontend
12. `agent/portal/frontend/src/pages/SkillsPage.tsx`
13. `agent/portal/frontend/src/pages/SkillDetailPage.tsx`
14. `agent/portal/frontend/src/components/skills/SkillCard.tsx`
15. `agent/portal/frontend/src/components/skills/NewSkillModal.tsx`
16. `agent/portal/frontend/src/components/skills/SkillPicker.tsx`
17. `agent/portal/frontend/src/hooks/useSkills.ts`
18. `agent/portal/frontend/src/hooks/useSkill.ts`
19. `agent/portal/frontend/src/hooks/useProjectSkills.ts`
20. `agent/portal/frontend/src/hooks/useTaskSkills.ts`

### Modified Files
21. `agent/shared/shared/models/__init__.py` (add skill model imports)
22. `agent/shared/shared/config.py` (add skills_modules to module_services)
23. `agent/docker-compose.yml` (add skills-modules service)
24. `agent/portal/main.py` (register skills router)
25. `agent/portal/frontend/src/types/index.ts` (add skill types)
26. `agent/portal/frontend/src/api/client.ts` (add skill API methods)
27. `agent/portal/frontend/src/components/layout/Sidebar.tsx` (add nav item)
28. `agent/portal/frontend/src/App.tsx` (add routes)
29. `agent/portal/frontend/src/pages/ProjectDetailPage.tsx` (add skills section)
30. `agent/portal/frontend/src/pages/ProjectTaskDetailPage.tsx` (add skills section)

---

## Success Criteria

1. ✅ Skills module builds and starts without errors
2. ✅ All 12 tools callable via orchestrator
3. ✅ Database tables created with proper constraints
4. ✅ Portal UI allows CRUD operations on skills
5. ✅ Skills can be attached to projects and tasks
6. ✅ Project/task detail pages show attached skills
7. ✅ Template rendering works with variable substitution
8. ✅ User isolation: users can only access their own skills
9. ✅ Navigation item appears in sidebar
10. ✅ All pages responsive and support dark mode

---

## Future Enhancements (Out of Scope)

- Skill versioning and history
- Public skill library (community-shared skills)
- Skill categories as enum/taxonomy
- Full-text search with embeddings
- Skill usage analytics
- Export/import skill collections
- Skill testing/validation framework
- Integration with claude_code for automatic skill application

---

## Estimated Complexity

- **Backend (Module + DB)**: Medium complexity, follows existing patterns
- **Frontend (Portal Integration)**: Medium complexity, standard CRUD UI
- **Testing**: Low complexity, straightforward workflows
- **Total**: ~3-4 days of focused implementation

---

## Notes for Implementation

1. Follow existing module patterns closely (reference `project_planner` module)
2. Use async/await throughout for consistency
3. All database operations should verify user ownership
4. Frontend should match existing portal design system
5. Use motion/framer-motion for page transitions (existing pattern)
6. Code editor component: consider Monaco Editor or simple textarea with syntax highlighting
7. Tag input: use a controlled component with chips (see existing form patterns)
8. Error boundaries around new pages for graceful failure

---

## Dependencies

- Python 3.12
- FastAPI >= 0.109
- SQLAlchemy >= 2.0
- asyncpg >= 0.29
- Jinja2 >= 3.1 (for template rendering)
- React 18
- TypeScript
- lucide-react (icons)
- framer-motion (animations)

---

## Git Workflow

1. Development branch: `feature/skills-modules`
2. Commit after each phase completion
3. Test thoroughly before moving to next phase
4. Create PR when all phases complete
5. Merge to `main` after review
