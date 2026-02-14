# file_manager

File CRUD on MinIO (S3-compatible) storage with PostgreSQL metadata tracking.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `file_manager.create_document` | Create a text document (md, txt, json, csv, html, py, js, etc.) | guest |
| `file_manager.upload_file` | Upload binary file from base64 data | guest |
| `file_manager.read_document` | Read contents of a stored text file | guest |
| `file_manager.list_files` | List all files for the current user | guest |
| `file_manager.get_file_link` | Get public download URL for a file | guest |
| `file_manager.delete_file` | Delete a file from storage and DB | user |

## Tool Details

### `file_manager.create_document`
- **title** (string, required) — document title, used as filename
- **content** (string, required) — document content
- **format** (string, optional) — file extension: `md`, `txt`, `json`, `csv`, `html`, `xml`, `yaml`, `py`, `js`, `ts`, `css`, `sql`, `sh`, `toml`, `ini`, `log`, `svg`
- Returns public URL and file_id

### `file_manager.upload_file`
- **filename** (string, required) — filename with extension (e.g. `chart.png`)
- **data_base64** (string, required) — base64-encoded file content
- Returns public URL and file_id

### `file_manager.read_document`
- **file_id** (string, required) — UUID of the file record
- Returns full text content, truncated at 10,000 chars with "... [truncated]" suffix

### `file_manager.list_files`
- No parameters
- Returns up to 50 most recent files: `{id, filename, mime_type, size_bytes, url, created_at}`

### `file_manager.get_file_link`
- **file_id** (string, required) — UUID of the file record
- Returns `{url, filename}`

### `file_manager.delete_file`
- **file_id** (string, required) — UUID of the file record
- Deletes from both MinIO and the `FileRecord` database table

## Implementation Notes

- MinIO bucket is auto-created on startup if it doesn't exist
- MIME type detection via comprehensive extension-to-type mapping (49 types)
- Filename sanitization: removes special chars, replaces spaces with underscores
- All queries filter by `user_id` for isolation
- `code_executor` also creates `FileRecord` entries for generated files, so they appear in `list_files`

## Database

- **Model:** `FileRecord` (`agent/shared/shared/models/file.py`)
- **Fields:** `id`, `user_id`, `filename`, `minio_key`, `mime_type`, `size_bytes`, `public_url`, `created_at`

## Key Files

- `agent/modules/file_manager/manifest.py`
- `agent/modules/file_manager/tools.py`
- `agent/modules/file_manager/main.py`
