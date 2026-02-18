"""Research module tool implementations."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import structlog
from bs4 import BeautifulSoup
from ddgs import DDGS

import httpx

from shared.auth import get_service_auth_headers

logger = structlog.get_logger()


# Internal Docker service hostnames that must never be fetched
_BLOCKED_HOSTNAMES = {
    "core", "postgres", "redis", "minio", "localhost",
    "file-manager", "code-executor", "knowledge", "scheduler",
    "deployer", "claude-code", "location", "research",
    "project-planner", "skills-modules", "git-platform",
    "atlassian", "garmin", "myfitnesspal", "renpho-biometrics",
    "injective", "weather", "portal", "dashboard",
    "discord-bot", "telegram-bot", "slack-bot",
}


def _validate_url_for_ssrf(url: str) -> str | None:
    """Return an error message if the URL targets an internal/private resource."""
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL"

    # Only allow http and https schemes
    if parsed.scheme not in ("http", "https"):
        return f"Blocked URL scheme: {parsed.scheme}"

    hostname = parsed.hostname or ""
    if not hostname:
        return "No hostname in URL"

    # Block known internal Docker hostnames
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        return f"Blocked internal hostname: {hostname}"

    # Resolve DNS and check for private/internal IPs
    try:
        resolved = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in resolved:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return f"Blocked private/internal IP: {ip}"
    except socket.gaierror:
        return f"DNS resolution failed for: {hostname}"

    return None


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

    async def news_search(self, query: str, max_results: int = 5) -> list[dict]:
        """Search recent news articles using DuckDuckGo."""
        try:
            with DDGS() as ddgs:
                results = list(ddgs.news(query, max_results=max_results))
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", r.get("link", "")),
                    "snippet": r.get("body", ""),
                    "source": r.get("source", ""),
                    "date": r.get("date", ""),
                }
                for r in results
            ]
        except Exception as e:
            logger.error("news_search_error", query=query, error=str(e))
            raise RuntimeError(f"News search failed: {str(e)}")

    async def fetch_webpage(self, url: str) -> dict:
        """Fetch and extract text content from a URL."""
        # SSRF protection: block internal/private URLs
        ssrf_error = _validate_url_for_ssrf(url)
        if ssrf_error:
            raise RuntimeError(f"URL blocked: {ssrf_error}")

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
            async with httpx.AsyncClient(timeout=30.0, headers=get_service_auth_headers()) as client:
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
