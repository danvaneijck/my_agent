"""Research module tool implementations."""

from __future__ import annotations

import structlog
from bs4 import BeautifulSoup
from ddgs import DDGS

import httpx

logger = structlog.get_logger()


class ResearchTools:
    """Tool implementations for web research."""

    def __init__(self, orchestrator_url: str = "http://core:8000"):
        self.orchestrator_url = orchestrator_url

    async def web_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search the web using DuckDuckGo."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("link", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                }
                for r in results
            ]
        except Exception as e:
            logger.error("web_search_error", query=query, error=str(e))
            raise RuntimeError(f"Web search failed: {str(e)}")

    async def fetch_webpage(self, url: str) -> dict:
        """Fetch and extract text content from a URL."""
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AgentBot/1.0)"},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Clean up whitespace
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            # Truncate to 8000 chars
            if len(text) > 8000:
                text = text[:8000] + "\n... [truncated]"

            return {
                "url": url,
                "title": soup.title.string if soup.title else "",
                "content": text,
                "length": len(text),
            }
        except Exception as e:
            logger.error("fetch_webpage_error", url=url, error=str(e))
            raise RuntimeError(f"Failed to fetch webpage: {str(e)}")

    async def summarize_text(self, text: str, max_length: int = 500) -> dict:
        """Summarize text using the LLM router via the core service."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Use the core orchestrator's LLM endpoint
                # We send a summarization request through the message endpoint
                # For simplicity, we do a direct internal summarization
                resp = await client.post(
                    f"{self.orchestrator_url}/message",
                    json={
                        "platform": "internal",
                        "platform_user_id": "system",
                        "platform_channel_id": "summarization",
                        "content": (
                            f"Please summarize the following text in approximately "
                            f"{max_length} words. Return only the summary, nothing else.\n\n"
                            f"{text[:6000]}"
                        ),
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "summary": data.get("content", ""),
                        "original_length": len(text),
                    }
                else:
                    # Fallback: simple truncation-based summary
                    return self._simple_summary(text, max_length)
        except Exception as e:
            logger.warning("llm_summarize_failed", error=str(e))
            return self._simple_summary(text, max_length)

    def _simple_summary(self, text: str, max_length: int) -> dict:
        """Fallback summary: extract first N words."""
        words = text.split()
        if len(words) <= max_length:
            return {"summary": text, "original_length": len(text)}
        summary = " ".join(words[:max_length]) + "..."
        return {"summary": summary, "original_length": len(text)}
