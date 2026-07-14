from __future__ import annotations

import asyncio
import sys

from research_evidence_agent.providers.arxiv import ArxivPaperProvider


async def main() -> None:
    query = " ".join(sys.argv[1:]) or 'all:"retrieval augmented generation"'
    papers = await ArxivPaperProvider(
        min_interval_seconds=0,
        max_attempts=1,
    ).search(query, max_results=2)
    for paper in papers:
        print(f"{paper['arxiv_id']}\t{paper['title']}")


if __name__ == "__main__":
    asyncio.run(main())
