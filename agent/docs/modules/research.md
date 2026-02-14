# research

Web search, news search, webpage fetching, and text summarization.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `research.web_search` | Search the web, returns titles/URLs/snippets | guest |
| `research.news_search` | Search recent news articles | guest |
| `research.fetch_webpage` | Extract text content from a URL | guest |
| `research.summarize_text` | Summarize long text into a shorter version | guest |

## Tool Details

### `research.web_search`
- **query** (string, required) — search query
- **max_results** (integer, optional) — default 5
- Returns list of `{title, url, snippet}`
- Uses DuckDuckGo (`DDGS` library)

### `research.news_search`
- **query** (string, required) — news search query
- **max_results** (integer, optional) — default 5
- Returns list of `{title, url, source, date}`

### `research.fetch_webpage`
- **url** (string, required) — URL to fetch
- Parses HTML with BeautifulSoup, strips script/style/nav/footer/header tags
- Output truncated to 8000 chars

### `research.summarize_text`
- **text** (string, required) — text to summarize
- **max_length** (integer, optional) — max summary length in words (default 500)
- Calls core `/message` endpoint for LLM-powered summarization
- Falls back to simple word-count truncation if LLM call fails

## Implementation Notes

- DuckDuckGo library is `ddgs` (renamed from `duckduckgo-search`), imported as `from ddgs import DDGS`
- Summarization uses the orchestrator's own LLM endpoint as a backend
- No database or external credentials required

## Key Files

- `agent/modules/research/manifest.py`
- `agent/modules/research/tools.py`
- `agent/modules/research/main.py`
