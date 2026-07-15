from __future__ import annotations

import asyncio

import httpx
import pytest

from research_evidence_agent.providers.arxiv import (
    ArxivPaperProvider,
    ArxivRequestError,
)


ATOM_RESPONSE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <updated>2024-01-03T12:00:00Z</updated>
    <published>2024-01-01T12:00:00Z</published>
    <title>  Evidence-Aware\n  Research Agents </title>
    <summary> We study agents that aggregate research evidence. </summary>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
    <category term="cs.AI" />
    <category term="cs.CL" />
    <link href="http://arxiv.org/abs/2401.12345v2" rel="alternate" />
    <link href="http://arxiv.org/pdf/2401.12345v2" rel="related"
          type="application/pdf" title="pdf" />
  </entry>
</feed>
"""


def test_arxiv_provider_builds_query_and_parses_atom() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(request.url.params)
        return httpx.Response(200, content=ATOM_RESPONSE)

    provider = ArxivPaperProvider(
        min_interval_seconds=0,
        transport=httpx.MockTransport(handler),
    )
    papers = asyncio.run(
        provider.search('all:"research agents"', max_results=7)
    )

    assert captured == {
        "search_query": 'all:"research agents"',
        "start": "0",
        "max_results": "7",
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    assert len(papers) == 1
    paper = papers[0]
    assert paper["arxiv_id"] == "2401.12345"
    assert paper["title"] == "Evidence-Aware Research Agents"
    assert paper["authors"] == ["Alice Example", "Bob Example"]
    assert paper["categories"] == ["cs.AI", "cs.CL"]
    assert paper["abs_url"] == "https://arxiv.org/abs/2401.12345v2"
    assert paper["pdf_url"] == "https://arxiv.org/pdf/2401.12345v2"
    assert paper["matched_queries"] == ['all:"research agents"']


def test_arxiv_provider_retries_transient_timeout() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("", request=request)
        return httpx.Response(200, content=ATOM_RESPONSE)

    provider = ArxivPaperProvider(
        min_interval_seconds=0,
        max_attempts=2,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    papers = asyncio.run(provider.search('all:"research agents"', max_results=2))

    assert attempts == 2
    assert papers[0]["arxiv_id"] == "2401.12345"


def test_arxiv_provider_reports_timeout_type_and_retry_budget() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("", request=request)

    provider = ArxivPaperProvider(
        timeout_seconds=12,
        min_interval_seconds=0,
        max_attempts=2,
        retry_backoff_seconds=0,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        ArxivRequestError,
        match=r"timed out after 12s \(ReadTimeout, after 2 attempts\)",
    ):
        asyncio.run(provider.search('all:"research agents"', max_results=2))
