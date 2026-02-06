"""Research module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="research",
    description="Research the web, fetch pages, and summarize information.",
    tools=[
        ToolDefinition(
            name="research.web_search",
            description="Search the web for information. Returns a list of results with titles, URLs, and snippets.",
            parameters=[
                ToolParameter(name="query", type="string", description="The search query"),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of results to return (default 5)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="research.fetch_webpage",
            description="Fetch and extract the text content from a URL.",
            parameters=[
                ToolParameter(name="url", type="string", description="The URL to fetch"),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="research.summarize_text",
            description="Summarize a long piece of text into a shorter version.",
            parameters=[
                ToolParameter(name="text", type="string", description="The text to summarize"),
                ToolParameter(
                    name="max_length",
                    type="integer",
                    description="Maximum length of summary in words (default 500)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
    ],
)
