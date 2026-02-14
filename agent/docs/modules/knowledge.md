# knowledge

Persistent per-user memory with semantic search via pgvector embeddings.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `knowledge.remember` | Store a fact or piece of information | guest |
| `knowledge.recall` | Semantic search across stored memories | guest |
| `knowledge.list_memories` | List all memories, newest first | guest |
| `knowledge.forget` | Delete a memory by ID | guest |

## Tool Details

### `knowledge.remember`
- **content** (string, required) — the fact to store
- Generates a 1536-dim embedding via core `/embed` endpoint
- Creates a `MemorySummary` record with the embedding
- Returns `{memory_id, content}`

### `knowledge.recall`
- **query** (string, required) — what to search for
- **max_results** (integer, optional) — default 5
- Embeds the query, then uses pgvector cosine distance for semantic matching
- Falls back to recency-based ordering if embedding fails
- Returns list of `{id, content, created_at, relevance}`

### `knowledge.list_memories`
- **limit** (integer, optional) — default 20
- Returns all memories sorted by `created_at DESC`

### `knowledge.forget`
- **memory_id** (string, required) — UUID of memory to delete
- Raises error if not found or not owned by user

## Implementation Notes

- Embeddings are fetched from core's `/embed` endpoint (which routes to OpenAI or Gemini embedding models)
- pgvector `Vector(1536)` column enables cosine similarity search directly in PostgreSQL
- All queries filter by `user_id` — memories are strictly per-user
- The context builder also queries this table to inject relevant memories into each conversation

## Database

- **Model:** `MemorySummary` (`agent/shared/shared/models/memory.py`)
- **Fields:** `id`, `user_id`, `conversation_id` (nullable), `summary`, `embedding` (Vector(1536)), `created_at`

## Key Files

- `agent/modules/knowledge/manifest.py`
- `agent/modules/knowledge/tools.py`
- `agent/modules/knowledge/main.py`
