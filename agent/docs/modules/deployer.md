# deployer

Deploy projects to live containers with allocated ports and environment variable injection.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `deployer.deploy` | Deploy a project to a running container with a live URL | user |
| `deployer.list_deployments` | List active deployments with URLs and status | user |
| `deployer.teardown` | Stop and remove a deployment | admin |
| `deployer.teardown_all` | Stop and remove all deployments | admin |
| `deployer.get_logs` | Get container logs for a deployment | user |

## Tool Details

### `deployer.deploy`
- **project_path** (string, required) — absolute path to project (e.g. `/tmp/claude_tasks/{task_id}/`)
- **project_name** (string, required) — human-readable name
- **project_type** (string, optional) — `react`, `nextjs`, `static`, `node`, `docker` (default: react)
- **container_port** (integer, optional) — auto-detected: 80 for react/static, 3000 for nextjs/node, 8000 for docker
- **env_vars** (object, optional) — environment variables to inject (e.g. `{"REACT_APP_API_URL": "http://localhost:4001"}`)
- Auto-detects project subdirectory if path is a workspace root
- Returns `{deploy_id, url, port}`

### `deployer.list_deployments`
- No parameters
- Returns all active deployments with `{deploy_id, name, url, port, status, created_at}`

### `deployer.teardown`
- **deploy_id** (string, required)
- Stops container and frees the allocated port

### `deployer.teardown_all`
- No parameters
- Stops all active deployment containers

### `deployer.get_logs`
- **deploy_id** (string, required)
- **lines** (integer, optional) — default 50

## Implementation Notes

- Port allocation: tracks used ports, assigns next available from a range
- Auto-detection: if `project_path` contains a single subdirectory with `package.json`, it uses that
- Docker integration: builds a Dockerfile or runs an existing image
- The workspace path from `claude_code` tasks is passed directly as `project_path`
- Dockerfile installs Docker CLI for managing sibling containers via mounted Docker socket

## Key Files

- `agent/modules/deployer/manifest.py`
- `agent/modules/deployer/tools.py`
- `agent/modules/deployer/main.py`
