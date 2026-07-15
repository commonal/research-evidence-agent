from __future__ import annotations

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx

from research_evidence_agent.research.state import Paper


_ATOM = "http://www.w3.org/2005/Atom"
_NS = {"atom": _ATOM}


class ArxivRequestError(RuntimeError):
    """Raised after a live arXiv request exhausts its retry budget."""


class ArxivPaperProvider:
    """Small async client for the official Arxiv Atom API."""

    name = "arxiv"

    def __init__(
        self,
        *,
        api_url: str = "https://export.arxiv.org/api/query",
        timeout_seconds: float = 30.0,
        min_interval_seconds: float = 3.0,
        max_attempts: int = 3,
        retry_backoff_seconds: float = 0.5,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_url = api_url
        self.timeout_seconds = timeout_seconds
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self.max_attempts = max(1, max_attempts)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)
        self.transport = transport
        self._request_lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def search(self, query: str, *, max_results: int) -> list[Paper]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        payload = await self._request(
            {
                "search_query": normalized_query,
                "start": 0,
                "max_results": max(1, min(max_results, 50)),
                "sortBy": "relevance",
                "sortOrder": "descending",
            }
        )
        return parse_arxiv_atom(payload, matched_query=normalized_query)

    async def _request(self, params: dict[str, Any]) -> bytes:
        async with self._request_lock:
            error: Exception | None = None
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
                headers={
                    "User-Agent": (
                        "research-evidence-agent/0.1 "
                        "(+https://github.com/commonal/research-evidence-agent)"
                    )
                },
            ) as client:
                for attempt in range(self.max_attempts):
                    elapsed = time.monotonic() - self._last_request_at
                    if elapsed < self.min_interval_seconds:
                        await asyncio.sleep(self.min_interval_seconds - elapsed)
                    self._last_request_at = time.monotonic()
                    try:
                        response = await client.get(self.api_url, params=params)
                        response.raise_for_status()
                        return response.content
                    except httpx.HTTPError as exc:
                        error = exc
                        if attempt + 1 < self.max_attempts:
                            await asyncio.sleep(
                                self.retry_backoff_seconds * (2**attempt)
                            )
            assert error is not None
            raise ArxivRequestError(self._error_message(error)) from error

    def _error_message(self, error: Exception) -> str:
        attempts = f"after {self.max_attempts} attempts"
        if isinstance(error, httpx.TimeoutException):
            return (
                f"arXiv request timed out after {self.timeout_seconds:g}s "
                f"({type(error).__name__}, {attempts})"
            )
        if isinstance(error, httpx.HTTPStatusError):
            return (
                f"arXiv API returned HTTP {error.response.status_code} "
                f"({attempts})"
            )
        detail = str(error).strip() or "request failed without details"
        return f"arXiv request failed: {type(error).__name__}: {detail} ({attempts})"


def parse_arxiv_atom(payload: bytes | str, *, matched_query: str) -> list[Paper]:
    root = ET.fromstring(payload)
    papers: list[Paper] = []
    for rank, entry in enumerate(root.findall("atom:entry", _NS), start=1):
        abs_url = _text(entry, "atom:id")
        arxiv_id = _arxiv_id(abs_url)
        if not arxiv_id:
            continue
        links = entry.findall("atom:link", _NS)
        pdf_url = next(
            (
                str(link.attrib.get("href", ""))
                for link in links
                if link.attrib.get("type") == "application/pdf"
                or link.attrib.get("title") == "pdf"
            ),
            f"https://arxiv.org/pdf/{arxiv_id}",
        )
        papers.append(
            Paper(
                arxiv_id=arxiv_id,
                title=_clean(_text(entry, "atom:title")),
                authors=[
                    _clean(_text(author, "atom:name"))
                    for author in entry.findall("atom:author", _NS)
                    if _text(author, "atom:name")
                ],
                abstract=_clean(_text(entry, "atom:summary")),
                published_at=_text(entry, "atom:published"),
                updated_at=_text(entry, "atom:updated"),
                categories=[
                    str(category.attrib.get("term", ""))
                    for category in entry.findall("atom:category", _NS)
                    if category.attrib.get("term")
                ],
                abs_url=abs_url.replace("http://", "https://"),
                pdf_url=pdf_url.replace("http://", "https://"),
                matched_queries=[matched_query],
                rank=rank,
            )
        )
    return papers


def _text(node: ET.Element, path: str) -> str:
    child = node.find(path, _NS)
    return child.text.strip() if child is not None and child.text else ""


def _clean(value: str) -> str:
    return " ".join(value.split())


def _arxiv_id(url: str) -> str:
    identifier = url.rstrip("/").rsplit("/", 1)[-1]
    return re.sub(r"v\d+$", "", identifier)
