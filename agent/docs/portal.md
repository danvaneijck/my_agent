# Web Portal

The portal is a web application for managing the agent system. It provides a browser-based interface for monitoring Claude Code tasks, chatting with the orchestrator, and managing files — as an alternative to interacting through Discord, Telegram, or Slack.

---

## Architecture

The portal is a single Docker service (`agent/portal/`) composed of:

- **Backend**: Python FastAPI server that exposes REST and WebSocket APIs
- **Frontend**: React SPA (TypeScript, Tailwind CSS) built with Vite and served as static files by the backend

### Communication strategy

The portal uses two communication paths:

1. **Chat** → `POST http://core:8000/message` using `platform="web"`. This runs the full agent loop (user resolution, persona selection, memory, tools, token tracking) — same as the Discord/Telegram/Slack bots.

2. **Task management & file management** → direct HTTP calls to module `/execute` endpoints (`http://claude-code:8000/execute`, `http://file-manager:8000/execute`). This bypasses the agent loop for fast CRUD operations.

### Real-time features

- **Chat**: WebSocket at `/ws/chat`. The backend POSTs to core (blocking, up to 180s), sends heartbeats every 10s while waiting, and pushes the response when ready.
- **Task logs**: WebSocket at `/api/tasks/{id}/logs/ws`. The backend polls the claude-code module's `task_logs` endpoint every 1.5s using offset-based pagination, pushing only new lines to the client.

---

## File structure

```
agent/portal/
├── __init__.py
├── Dockerfile              # Multi-stage: Node builds frontend → Python serves it
├── requirements.txt
├── main.py                 # FastAPI app, mounts routers + static files
├── auth.py                 # API key validation (HTTP header + WS query param)
├── routers/
│   ├── system.py           # GET /api/health, GET /api/system/modules
│   ├── tasks.py            # Claude Code task CRUD + WS log streaming
│   ├── chat.py             # Chat REST + WS, conversation history from DB
│   └── files.py            # File manager proxy + MinIO download streaming
├── services/
│   ├── module_client.py    # Generic HTTP client for module /execute calls
│   ├── core_client.py      # HTTP client for core /message
│   └── log_streamer.py     # WS task log polling + push logic
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx             # Auth gate + routing
        ├── index.css           # Tailwind + highlight.js theme + scrollbar
        ├── api/
        │   ├── client.ts       # fetch wrapper with API key injection
        │   └── websocket.ts    # WS connection manager with reconnection
        ├── types/index.ts      # TypeScript interfaces matching backend schemas
        ├── hooks/
        │   ├── useTasks.ts     # Task list polling hook
        │   └── useWebSocket.ts # Generic WS hook with auto-reconnect
        ├── pages/
        │   ├── TasksPage.tsx       # Task list view
        │   ├── TaskDetailPage.tsx  # Single task + log viewer
        │   ├── ChatPage.tsx        # Chat with conversation sidebar
        │   └── FilesPage.tsx       # File browser + upload + preview
        └── components/
            ├── layout/         # Sidebar, Header, Layout (responsive shell)
            ├── tasks/          # TaskList, TaskLogViewer, NewTaskForm, ContinueTaskForm
            ├── chat/           # ChatView, MessageBubble, ChatInput
            ├── files/          # FileList, FileUpload, FilePreview
            └── common/         # StatusBadge, ConfirmDialog
```

---

## API endpoints

All REST endpoints require the `X-Portal-Key` header. WebSocket endpoints accept the key as `?key=` query parameter.

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (also validates API key) |
| GET | `/api/system/modules` | Health status of all configured modules |

### Tasks (proxied to claude-code module)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/tasks` | List tasks (optional `?status=` filter) |
| POST | `/api/tasks` | Start new task `{prompt, repo_url?, branch?, timeout?}` |
| GET | `/api/tasks/{id}` | Get task status |
| GET | `/api/tasks/{id}/logs` | Get logs `?tail=100&offset=0` |
| POST | `/api/tasks/{id}/continue` | Continue task `{prompt, timeout?}` |
| DELETE | `/api/tasks/{id}` | Cancel running task |
| WS | `/api/tasks/{id}/logs/ws` | Real-time log streaming |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/chat/conversations` | List web conversations |
| GET | `/api/chat/conversations/{id}/messages` | Get message history |
| POST | `/api/chat/send` | Send message (sync REST fallback) |
| WS | `/ws/chat` | Bidirectional chat |

### Files (proxied to file-manager module)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/files` | List files |
| POST | `/api/files` | Upload file (multipart form) |
| GET | `/api/files/{id}` | File metadata + text content |
| GET | `/api/files/{id}/download` | Stream file from MinIO |
| DELETE | `/api/files/{id}` | Delete file |

---

## Configuration

Add these to `agent/.env`:

```bash
# Required — portal won't start without this
PORTAL_API_KEY=your-secret-key

# UUID of the user to act as for web chat messages.
# Must match an existing user in the users table.
PORTAL_USER_ID=your-user-uuid

# Optional — defaults to 8080
PORTAL_PORT=8080
```

### Linking the portal to your user account

The portal sends chat messages with `platform="web"`. Core's user resolution needs a `UserPlatformLink` to map this to your existing user. Create one:

```sql
INSERT INTO user_platform_links (id, user_id, platform, platform_user_id)
VALUES (gen_random_uuid(), '<your-user-uuid>', 'web', '<your-user-uuid>');
```

Or through `make psql`.

---

## Build and deploy

```bash
# First time (or after frontend changes)
make restart-portal

# View logs
make logs-portal

# Rebuild everything
make build
make up
```

The Dockerfile is a multi-stage build:
1. **Stage 1** (node:20-alpine): Runs `npm ci` + `npm run build` on the frontend
2. **Stage 2** (python:3.12-slim): Installs shared package + portal requirements, copies backend code + built frontend assets

The built frontend lands at `/app/portal/static/dist/` inside the container. FastAPI serves it via `StaticFiles` mount for `/assets/` and a catch-all route for SPA routing.

---

## Development workflow

### Frontend development (hot reload)

Run the Vite dev server locally with proxy to the backend:

```bash
# Terminal 1: Start the portal backend (in Docker)
make restart-portal

# Terminal 2: Start Vite dev server (hot module replacement)
cd agent/portal/frontend
npm install
npm run dev
```

The Vite config (`vite.config.ts`) proxies `/api` and `/ws` requests to `http://localhost:8080` (the Docker portal service), so the dev server works seamlessly against the real backend.

### Backend development

Edit Python files, then rebuild:

```bash
make restart-portal
```

### Adding a new page

1. Create a page component in `frontend/src/pages/NewPage.tsx`
2. Add a route in `frontend/src/App.tsx`
3. Add a nav entry in `frontend/src/components/layout/Sidebar.tsx` (NAV_ITEMS array)
4. Add a title mapping in `frontend/src/components/layout/Layout.tsx` (PAGE_TITLES)

### Adding a new backend endpoint

1. Add the route to the appropriate router in `portal/routers/`
2. Use `Depends(require_portal_key)` for auth
3. Use `call_tool()` from `services/module_client.py` to proxy to modules
4. Use `get_session_factory()` for direct database queries

---

## Key design details

- **Authentication**: API key in `X-Portal-Key` header, stored in `localStorage`. Same pattern as the admin dashboard (`X-Admin-Key`).
- **SPA routing**: All non-`/api/`, non-`/ws/`, non-`/assets/` paths return `index.html` so React Router handles client-side navigation.
- **File downloads**: Proxied through the backend — MinIO URLs are never exposed to the browser.
- **Task stale detection**: If a task is "running" but its heartbeat is older than 90 seconds, the UI shows a warning.
- **Responsive design**: Sidebar collapses to hamburger on mobile. Task list switches from table to cards. Chat and file views adapt to narrow screens.
- **Dark theme**: Custom color palette defined in `tailwind.config.js` — `surface`, `border`, `accent` color scales.

---

## Existing files modified

Only three files outside `agent/portal/` were changed:

1. `agent/shared/shared/config.py` — Added `portal_api_key` and `portal_user_id` settings
2. `agent/docker-compose.yml` — Added `portal` service block
3. `Makefile` — Added `restart-portal` and `logs-portal` targets
