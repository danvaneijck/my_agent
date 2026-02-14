# code_executor

Sandboxed Python code and shell command execution with automatic file upload.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `code_executor.run_python` | Execute Python code with file generation support | guest |
| `code_executor.load_file` | Download a stored file into `/tmp/` for use in code | guest |
| `code_executor.run_shell` | Execute read-only shell commands | guest |

## Tool Details

### `code_executor.run_python`
- **code** (string, required) — Python code to execute
- **timeout** (integer, optional) — max seconds (default 30, max 60)
- Available libraries: `math`, `json`, `datetime`, `collections`, `itertools`, `re`, `statistics`, `numpy`, `pandas`, `matplotlib`, `requests`, `scipy`, `sympy`
- Files saved to `/tmp/` or `/tmp/output/` are auto-uploaded to MinIO
- Generated files are registered as `FileRecord` entries in the database
- Output truncated to 8000 chars
- Returns `{stdout, stderr, exit_code, files: [{filename, url}]}`

### `code_executor.load_file`
- **file_id** (string, required) — UUID from `file_manager.list_files`
- Downloads the file to `/tmp/{filename}`
- Returns `{local_path, filename}`

### `code_executor.run_shell`
- **command** (string, required) — shell command to execute
- **timeout** (integer, optional) — max seconds (default 30, max 60)
- Read-only whitelist only: `curl`, `wget`, `jq`, `wc`, `sort`, etc.
- Blocked patterns: `rm`, `mkfs`, `dd`, `chmod`, `chown`, `docker`, `sudo`, `eval`, `ssh`, `nc`, and ~50 more
- Returns `{stdout, stderr, exit_code}`

## Implementation Notes

- Execution via `asyncio.create_subprocess_exec` with isolated env vars
- `MPLBACKEND=Agg` is set so matplotlib renders to files without a display
- File tracking: snapshots `/tmp/` before execution, diffs after to find new files
- New files with recognized extensions are uploaded to MinIO under `generated/{uuid}_{filename}`
- Each uploaded file gets a `FileRecord` in the database so it appears in `file_manager.list_files`
- On timeout: process is killed, returns `exit_code=-1`
- File URLs are appended to stdout in the result

## Database

- **Model:** `FileRecord` (shared with file_manager)
- Created for each generated file during Python execution

## Key Files

- `agent/modules/code_executor/manifest.py`
- `agent/modules/code_executor/tools.py`
- `agent/modules/code_executor/main.py`
