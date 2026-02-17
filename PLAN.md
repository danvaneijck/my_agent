# Implementation Plan: Interactive Terminal for Code Workspaces

## Project Overview

**Project Name:** Extend Code Functionality in Portal
**Branch:** `project/extend-code-functionality-in-portal`
**Date:** 2026-02-17

### Goal

Enhance the portal's Code page by adding an interactive terminal feature that allows users to run commands directly in the Docker containers where their code workspaces live. This will transform the Code page from a read-only file browser into a full development environment accessible through the web browser.

### Current State Analysis

The portal currently provides:
- **File Browser**: Users can browse workspace directories and view file contents
- **Read-Only Access**: Files can be viewed in raw or preview mode (markdown, HTML)
- **Task Management**: Link to task details and workspace deletion
- **WebSocket Streaming**: Real-time log streaming for task execution

**Key Infrastructure:**
- Frontend: React + TypeScript + Tailwind CSS + Vite
- Backend: FastAPI with WebSocket support
- Claude Code Module: Manages workspaces in Docker containers at `/tmp/claude_tasks/<task_id>`
- Docker Socket Access: `claude-code` service has `/var/run/docker.sock` mounted
- Existing WebSocket Pattern: Already implemented for task log streaming

### Proposed Solution

Add an interactive terminal that:
1. **Executes commands** in the workspace's Docker container
2. **Streams output** in real-time using WebSockets
3. **Supports interactive shells** (bash/sh) with pseudo-TTY
4. **Persists sessions** so users can maintain shell state during a session
5. **Provides full terminal emulation** with ANSI color support and cursor control

## Architecture Design

### Technology Stack

#### Frontend
- **xterm.js** - Terminal emulator library with full ANSI support
- **xterm-addon-fit** - Auto-resize terminal to fit container
- **xterm-addon-web-links** - Clickable URLs in terminal output
- **WebSocket** - Bidirectional communication for terminal I/O

#### Backend
- **FastAPI WebSocket** - Handle terminal connections
- **Docker Python SDK** - Execute commands in containers via Docker API
- **asyncio streams** - Handle bidirectional terminal I/O streaming

### Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (Frontend)                      │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CodePage.tsx                                          │ │
│  │  ├── WorkspaceSelector (existing)                      │ │
│  │  ├── FileBrowser (existing)                            │ │
│  │  └── TerminalPanel (NEW)                               │ │
│  │      └── TerminalView (xterm.js component)             │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           │ WebSocket                        │
│                           ▼                                  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                   Portal Backend (FastAPI)                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  routers/tasks.py                                      │ │
│  │  └── /api/tasks/{task_id}/terminal/ws (NEW)           │ │
│  └────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  services/terminal_service.py (NEW)                    │ │
│  │  ├── create_terminal_session()                         │ │
│  │  ├── execute_command()                                 │ │
│  │  └── cleanup_session()                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                           │                                  │
│                           │ HTTP (Docker API)                │
│                           ▼                                  │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│              Docker Daemon (via unix socket)                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Container: claude_code_<task_id>                      │ │
│  │  Working Dir: /tmp/claude_tasks/<task_id>              │ │
│  │  Shell: /bin/bash -c "cd /workspace && exec bash"     │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Security Considerations

1. **Authentication**: Reuse existing `X-Portal-Key` auth (via WebSocket query param)
2. **Container Isolation**: Only allow access to workspace containers owned by authenticated user
3. **Command Restrictions**: None - users have full shell access to their own workspaces
4. **Session Management**: One terminal session per user per workspace (prevent resource exhaustion)
5. **Timeout**: Auto-disconnect idle sessions after 30 minutes
6. **Container Verification**: Verify container exists and is for a workspace owned by the user

### Data Flow

#### Terminal Session Initialization
1. User clicks "Terminal" button on Code page
2. Frontend opens WebSocket: `wss://portal/api/tasks/{task_id}/terminal/ws?key=<api_key>`
3. Backend validates API key and task ownership
4. Backend calls `claude_code.get_task_container` to get container ID
5. Backend creates exec instance in container with PTY
6. Backend sends "ready" message to frontend
7. Frontend renders xterm.js terminal and sends initial commands

#### Bidirectional Communication
1. User types in terminal → Frontend sends input via WebSocket
2. Backend writes to container's stdin
3. Container outputs to stdout/stderr → Backend reads via Docker stream
4. Backend forwards output to frontend via WebSocket
5. Frontend writes to xterm.js terminal

#### Session Cleanup
1. User closes terminal or navigates away → Frontend closes WebSocket
2. Backend detects disconnect, kills exec process
3. Container remains running (workspace persists)

## Implementation Plan

### Phase 1: Backend Infrastructure

**Goal:** Implement terminal execution infrastructure in the portal backend and claude_code module.

#### Task 1.1: Add container ID tracking to claude_code module
**File:** `agent/modules/claude_code/tools.py`

**Description:**
Currently, tasks track workspace paths but not the running container IDs. We need to associate each task with its container so the terminal can attach to it.

**Approach:**
- Add `container_id` field to task metadata (stored in task dict)
- Populate `container_id` when launching containers in `run_task()`
- Add new tool `claude_code.get_task_container` to retrieve container ID by task_id

**Acceptance Criteria:**
- [ ] `run_task()` stores container ID in task metadata
- [ ] New tool `get_task_container(task_id)` returns `{container_id: str, workspace: str, status: str}`
- [ ] Container ID persists across task status queries

#### Task 1.2: Add get_task_container tool to manifest
**File:** `agent/modules/claude_code/manifest.py`

**Description:**
Define the new tool in the module manifest so it can be called via the portal.

**Acceptance Criteria:**
- [ ] New `ToolDefinition` for `claude_code.get_task_container` added
- [ ] Tool requires `admin` permission level
- [ ] Tool accepts `task_id` parameter

#### Task 1.3: Create terminal service
**File:** `agent/portal/services/terminal_service.py` (new file)

**Description:**
Core service for managing terminal sessions using the Docker SDK.

**Features:**
- Create exec instances in containers with PTY support
- Handle bidirectional streaming (stdin/stdout/stderr)
- Session lifecycle management (create, attach, cleanup)
- Error handling for container not found, exec failures

**Implementation Details:**
```python
import asyncio
import docker
from docker.models.containers import Container

class TerminalService:
    def __init__(self):
        self.client = docker.from_env()
        self.sessions: dict[str, ExecSession] = {}

    async def create_session(self, container_id: str, session_id: str, working_dir: str) -> ExecSession:
        """Create a new terminal exec session in the container."""

    async def attach_session(self, session_id: str) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Attach to an existing session and return streams."""

    async def cleanup_session(self, session_id: str):
        """Terminate exec and cleanup resources."""
```

**Acceptance Criteria:**
- [ ] Can create exec instances with `tty=True, stdin=True, privileged=False`
- [ ] Exec command: `/bin/bash` (interactive shell)
- [ ] Working directory set to workspace path
- [ ] Async stream handling for stdin/stdout
- [ ] Proper error handling and logging

#### Task 1.4: Add WebSocket endpoint for terminal
**File:** `agent/portal/routers/tasks.py`

**Description:**
Add WebSocket endpoint `/api/tasks/{task_id}/terminal/ws` that bridges xterm.js and the Docker container.

**WebSocket Protocol:**
- Client → Server: `{"type": "input", "data": "command text"}`
- Server → Client: `{"type": "output", "data": "terminal output"}`
- Server → Client: `{"type": "ready"}` (after connection established)
- Server → Client: `{"type": "error", "message": "error details"}`

**Flow:**
1. Validate auth and task ownership
2. Get container ID via `call_tool("claude_code.get_task_container")`
3. Create terminal session
4. Start bidirectional stream relay
5. Handle disconnect/cleanup

**Acceptance Criteria:**
- [ ] WebSocket endpoint requires authentication
- [ ] Validates user owns the task
- [ ] Checks container is running before creating session
- [ ] Relays input/output with <100ms latency
- [ ] Handles WebSocket disconnect gracefully
- [ ] Cleans up exec session on disconnect

#### Task 1.5: Add terminal session management
**File:** `agent/portal/services/terminal_service.py`

**Description:**
Implement session tracking to prevent multiple terminals per workspace and enforce timeouts.

**Features:**
- Track active sessions by `(user_id, task_id)`
- Limit to 1 session per user per workspace
- Auto-disconnect after 30 min of inactivity
- Heartbeat monitoring

**Acceptance Criteria:**
- [ ] Opening second terminal to same workspace reuses or closes first session
- [ ] Sessions auto-cleanup after 30 min idle
- [ ] Session state tracked in memory (no DB persistence needed)

### Phase 2: Frontend Terminal Component

**Goal:** Build the React/xterm.js terminal UI and integrate with backend WebSocket.

#### Task 2.1: Add xterm.js dependencies
**File:** `agent/portal/frontend/package.json`

**Description:**
Install xterm.js and required addons.

**Dependencies:**
```json
"xterm": "^5.5.0",
"@xterm/addon-fit": "^0.10.0",
"@xterm/addon-web-links": "^0.11.0"
```

**Acceptance Criteria:**
- [ ] Dependencies added to package.json
- [ ] `npm install` succeeds
- [ ] TypeScript types available (@types/xterm may be needed)

#### Task 2.2: Create TerminalView component
**File:** `agent/portal/frontend/src/components/code/TerminalView.tsx` (new file)

**Description:**
Reusable xterm.js terminal component with WebSocket integration.

**Props:**
```typescript
interface TerminalViewProps {
  taskId: string;
  onClose?: () => void;
}
```

**Features:**
- Initialize xterm.js Terminal instance
- Auto-fit to container size (using FitAddon)
- Connect to WebSocket endpoint
- Send user input to backend
- Render backend output
- Handle connection errors and reconnection
- Show connection status (connecting, connected, disconnected)

**Acceptance Criteria:**
- [ ] Terminal renders with dark theme matching portal colors
- [ ] WebSocket connects with API key authentication
- [ ] User input sent to backend in real-time
- [ ] Output rendered with ANSI color support
- [ ] Terminal auto-resizes on window resize
- [ ] Handles WebSocket disconnect and shows reconnect option
- [ ] Clean component unmount (close WebSocket, dispose terminal)

#### Task 2.3: Create TerminalPanel component
**File:** `agent/portal/frontend/src/components/code/TerminalPanel.tsx` (new file)

**Description:**
Container component that wraps TerminalView with UI chrome (header, close button, status indicators).

**Features:**
- Header with workspace info and close button
- Connection status indicator (green dot = connected)
- Maximize/minimize toggle
- Resize handle for height adjustment

**Acceptance Criteria:**
- [ ] Header shows task ID and connection status
- [ ] Close button terminates terminal and removes from view
- [ ] Visual styling matches existing portal design
- [ ] Responsive layout (collapses to full-width on mobile)

#### Task 2.4: Integrate terminal into CodePage
**File:** `agent/portal/frontend/src/pages/CodePage.tsx`

**Description:**
Add terminal panel to the Code page layout. Update UI to accommodate both file browser and terminal.

**Layout Changes:**
- Add "Terminal" button next to workspace name
- Split view: File browser on left, terminal on bottom
- Terminal initially hidden, shows when user clicks button
- Terminal takes ~40% of vertical space when visible
- Draggable splitter between file view and terminal

**State Management:**
```typescript
const [terminalOpen, setTerminalOpen] = useState(false);
const [terminalHeight, setTerminalHeight] = useState(400);
```

**Acceptance Criteria:**
- [ ] "Terminal" button appears when workspace selected
- [ ] Clicking button opens terminal panel at bottom
- [ ] Terminal connects to selected workspace
- [ ] Switching workspaces closes/reopens terminal for new workspace
- [ ] Layout responsive and doesn't break file browser
- [ ] Terminal persists until user closes it or switches workspaces

### Phase 3: Enhanced Terminal Features

**Goal:** Add productivity features and polish the UX.

#### Task 3.1: Add command history
**File:** `agent/portal/frontend/src/components/code/TerminalView.tsx`

**Description:**
Implement up/down arrow key navigation through command history (client-side only).

**Features:**
- Track commands as user presses Enter
- Arrow up = previous command
- Arrow down = next command (or empty if at end)
- Store last 100 commands in sessionStorage
- Persist history across terminal sessions within same browser session

**Acceptance Criteria:**
- [ ] Up arrow recalls previous command
- [ ] Down arrow moves forward in history
- [ ] History survives terminal close/reopen
- [ ] History cleared on browser refresh (sessionStorage)

#### Task 3.2: Add multi-terminal support
**File:** `agent/portal/frontend/src/pages/CodePage.tsx`

**Description:**
Allow multiple terminal tabs for the same workspace (useful for running server + separate commands).

**UI Changes:**
- Terminal panel header has tab bar
- "+" button to open new terminal
- Each tab connects to separate exec session
- Close button per tab

**Backend Changes:**
- Modify session tracking to allow N sessions per (user, workspace)
- Add session_id to WebSocket query params
- Generate unique session IDs on frontend

**Acceptance Criteria:**
- [ ] User can open multiple terminals to same workspace
- [ ] Each terminal is independent (separate shell state)
- [ ] Tabs show shell status (bash, node, python process name)
- [ ] Max 5 terminals per workspace

#### Task 3.3: Add terminal themes
**File:** `agent/portal/frontend/src/components/code/TerminalView.tsx`

**Description:**
Allow users to customize terminal color scheme.

**Themes:**
- Dark (default) - matches portal
- Light - for high-contrast
- Monokai
- Dracula
- Solarized Dark

**Implementation:**
- Theme picker in terminal header dropdown
- Save preference to localStorage
- Apply xterm.js theme object

**Acceptance Criteria:**
- [ ] Theme picker renders 5 theme options
- [ ] Selecting theme applies immediately
- [ ] Theme persists across sessions (localStorage)
- [ ] Default theme matches portal dark mode

#### Task 3.4: Add file upload/download from terminal
**File:** Multiple files

**Description:**
Add buttons to upload files to workspace or download files generated in terminal.

**Features:**
- "Upload" button in terminal header → file picker → uploads to current directory
- Auto-detect when terminal outputs file path → show "Download" icon next to path
- Integrate with existing file_manager module for uploads

**Implementation:**
- Use existing `/api/files` upload endpoint
- After upload, inject `ls` command to show new file
- For downloads, detect patterns like "Created file: /path/to/file" and make path clickable

**Acceptance Criteria:**
- [ ] Upload button prompts for file, uploads to workspace
- [ ] File appears in workspace directory
- [ ] Download links appear for recognized file paths in output
- [ ] Clicking download link fetches file via file_manager

### Phase 4: Testing and Documentation

**Goal:** Ensure reliability, handle edge cases, and document the new feature.

#### Task 4.1: Error handling and edge cases
**Files:** Various

**Test Cases:**
- Container not running → show friendly error
- Container deleted mid-session → detect and show error
- WebSocket disconnects → show reconnect button
- Network latency → buffer output to prevent UI lag
- Very long output lines → handle gracefully (no DOM crash)
- Binary output → handle without breaking terminal
- User spams commands → rate limit or queue properly

**Acceptance Criteria:**
- [ ] All error cases show user-friendly messages
- [ ] No crashes or unhandled promise rejections
- [ ] Terminal stays responsive with slow/fast output
- [ ] Reconnect works after temporary network loss

#### Task 4.2: Add integration tests
**File:** `agent/portal/tests/test_terminal.py` (new file)

**Description:**
Pytest tests for terminal backend functionality.

**Test Coverage:**
- Create terminal session
- Execute command and verify output
- Bidirectional I/O
- Session cleanup
- Multiple concurrent sessions
- Auth validation

**Acceptance Criteria:**
- [ ] Test suite passes in CI
- [ ] Coverage >80% for terminal service code

#### Task 4.3: Update documentation
**Files:**
- `agent/docs/portal.md`
- `agent/docs/modules/claude_code.md`

**Description:**
Document the new terminal feature for developers and users.

**Documentation Updates:**
- Add "Terminal" section to portal.md with screenshots
- Update claude_code.md with new `get_task_container` tool
- Add WebSocket protocol documentation
- Update architecture diagram in portal.md

**Acceptance Criteria:**
- [ ] portal.md has "Terminal Feature" section
- [ ] WebSocket endpoint documented with message formats
- [ ] Tool manifest updated in claude_code docs
- [ ] Architecture diagram shows terminal flow

#### Task 4.4: User testing and polish
**Description:**
Manual testing and UX refinement.

**Testing Checklist:**
- [ ] Terminal opens quickly (<500ms)
- [ ] Commands execute and show output correctly
- [ ] Colors and formatting look good
- [ ] Copy/paste works (Ctrl+C/V or Cmd+C/V)
- [ ] Mobile layout is usable (shows terminal full-screen)
- [ ] Keyboard shortcuts don't conflict with browser
- [ ] Terminal scrollback works (scroll up to see old output)

**Polish Items:**
- [ ] Loading spinner while connecting
- [ ] Empty state message before connection
- [ ] Smooth animations for open/close
- [ ] Focus terminal input on open
- [ ] Clear screen button (Ctrl+L alternative)

## Technical Specifications

### Backend API Additions

#### New Tool: `claude_code.get_task_container`
```python
{
  "task_id": "abc-123",
  "container_id": "docker_container_xyz",
  "workspace": "/tmp/claude_tasks/abc-123",
  "status": "running"  # or "stopped", "not_found"
}
```

#### WebSocket Endpoint: `GET /api/tasks/{task_id}/terminal/ws`

**Query Parameters:**
- `key` - Portal API key (required)

**Message Types:**

Client → Server:
```json
{"type": "input", "data": "ls -la\n"}
{"type": "resize", "rows": 40, "cols": 120}
```

Server → Client:
```json
{"type": "ready"}
{"type": "output", "data": "total 48\ndrwxr-xr-x..."}
{"type": "error", "message": "Container not running"}
```

### Frontend Component Structure

```
src/components/code/
├── TerminalView.tsx        # Core xterm.js wrapper
├── TerminalPanel.tsx       # UI chrome (header, status)
└── TerminalTabs.tsx        # Multi-tab support (Phase 3)

src/hooks/
└── useTerminal.ts          # WebSocket + xterm state management

src/types/
└── terminal.ts             # TypeScript interfaces
```

### Docker Exec Configuration

```python
container.exec_run(
    cmd=["/bin/bash"],
    stdin=True,
    tty=True,
    privileged=False,
    user="claude",  # match workspace file permissions
    workdir="/tmp/claude_tasks/<task_id>",
    environment={"TERM": "xterm-256color"},
    demux=False,  # stream output as-is
    stream=True
)
```

### Security Model

1. **Authentication**: Portal API key required for WebSocket
2. **Authorization**: Task ownership verified via user_id
3. **Isolation**: Each exec runs in isolated container namespace
4. **Privilege**: exec runs as non-root user (matches Claude Code container user)
5. **Network**: Container has no network access (unless workspace needs it)
6. **Resource Limits**: Inherit from container resource limits

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Resource exhaustion (too many terminals) | Service degradation | Limit to 5 terminals per user, 30-min timeout |
| Container escape | Security breach | Run exec as non-root, no privileged mode |
| Long-running processes consuming memory | Container OOM | Container memory limits already enforced |
| WebSocket connection storms | Backend overload | Rate limit WS connections per user |
| User accidentally deletes workspace files | Data loss | Read-only warning on terminal (optional), no automatic backups |

## Success Metrics

1. **Functionality**: User can run shell commands and see output in <100ms
2. **Reliability**: <1% WebSocket disconnect rate under normal conditions
3. **Performance**: Terminal stays responsive with >1000 lines/sec output
4. **UX**: 90%+ user satisfaction in testing feedback
5. **Adoption**: 50%+ of Code page users try the terminal feature within first week

## Future Enhancements (Out of Scope)

These features are not included in this plan but could be added later:

1. **File editor integration** - Open files from terminal in a Monaco editor
2. **Git integration** - Visual git status/diff in terminal UI
3. **Collaborative terminals** - Multiple users in same terminal (like tmux sharing)
4. **Terminal recording/playback** - Save terminal sessions as replays
5. **Custom command shortcuts** - User-defined buttons for common commands
6. **Process tree view** - Visual display of running processes
7. **SSH to external servers** - Use workspace as jump host
8. **Mobile-optimized keyboard** - Virtual keyboard with common keys (Tab, Ctrl, Esc)

## Dependencies and Prerequisites

### External Dependencies
- Docker daemon accessible via `/var/run/docker.sock`
- Claude Code containers must have `/bin/bash` installed (already true)
- Python Docker SDK (`docker>=7.0.0`)

### Internal Dependencies
- Portal authentication system (already implemented)
- Claude Code module `get_task_container` tool (new - Phase 1)
- WebSocket support in portal backend (already implemented for logs)

### Environment Requirements
- No new environment variables needed
- No new database tables needed (session state in memory)
- No new infrastructure services needed

## Rollout Plan

### Development
1. Create feature branch from `project/extend-code-functionality-in-portal`
2. Implement Phase 1 (backend) first → test with curl/wscat
3. Implement Phase 2 (frontend) → test with real tasks
4. Implement Phase 3 (enhancements) → gather internal feedback
5. Implement Phase 4 (testing/docs) → prepare for release

### Testing Stages
1. **Local Development**: Test with local Docker setup
2. **Integration Testing**: Full portal + claude_code stack
3. **User Acceptance Testing**: Invite 5-10 beta users
4. **Production Deployment**: Merge to main, deploy to prod

### Rollback Plan
If the feature causes issues:
1. Terminal feature is isolated to Code page (won't break other pages)
2. Can disable by removing "Terminal" button via feature flag
3. Backend endpoint can be disabled via router commenting
4. No database migrations, so rollback is clean

## Conclusion

This plan provides a comprehensive roadmap for adding an interactive terminal feature to the portal's Code page. The implementation is broken into 4 phases with 17 concrete tasks, each with clear acceptance criteria. The architecture leverages existing infrastructure (Docker socket, WebSocket support) and follows established patterns in the codebase.

The terminal feature will transform the Code page from a passive file viewer into an active development environment, enabling users to:
- Run commands directly in their workspaces
- Test code changes interactively
- Debug issues in real-time
- Perform git operations (commit, push, etc.)
- Install dependencies and run builds

With proper security controls (authentication, authorization, resource limits) and thoughtful UX design (responsive layout, error handling, themes), this feature will significantly enhance the developer experience in the portal.
