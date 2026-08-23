import asyncio
import os
from pathlib import Path

# crawl4ai tries to create ~/.crawl4ai at import time, which fails on
# read-only home directories.  Point it at the project directory instead.
if "CRAWL4_AI_BASE_DIRECTORY" not in os.environ:
    os.environ["CRAWL4_AI_BASE_DIRECTORY"] = str(Path(__file__).resolve().parent.parent)

from ddgs import DDGS
from crawl4ai import AsyncWebCrawler
from .base import ResearchProvider, ResearchReport, SearchResult

class Crawl4AiProvider(ResearchProvider):
    def __init__(self, config: dict = None):
        self.config = config or {}

    def search(self, query: str) -> ResearchReport:
        return asyncio.run(self._async_search(query))

    async def _async_search(self, query: str) -> ResearchReport:
        report = ResearchReport(query=query)
        try:
            # 1. Search DDG to get top URLs (get more results for better coverage)
            with DDGS() as ddgs:
                # Use lite backend if auto fails or returns 0 inconsistently, but auto is usually fine.
                # Changing to 'lite' specifically to bypass '0 results' bot protections on datacenter IPs.
                results = list(ddgs.text(query, max_results=3, backend="lite"))
                if not results:
                    return report
                
                # Crawl multiple URLs concurrently
                async with AsyncWebCrawler() as crawler:
                    async def crawl_item(r):
                        url = r.get("href", "")
                        title = r.get("title", "")
                        snippet = r.get("body", "")
                        if not url:
                            return None
                        try:
                            result = await crawler.arun(url=url)
                            content = result.markdown if result and result.markdown else snippet
                            if content.strip():
                                return SearchResult(
                                    url=url,
                                    title=title,
                                    content=content,
                                    snippet=snippet
                                )
                        except Exception as e:
                            print(f"Failed to crawl {url}: {e}")
                            if snippet.strip():
                                return SearchResult(
                                    url=url,
                                    title=title,
                                    content=snippet,
                                    snippet=snippet
                                )
                        return None

                    tasks = [crawl_item(r) for r in results[:3] if r.get("href")]
                    crawled = await asyncio.gather(*tasks, return_exceptions=False)
                    for item in crawled:
                        if item:
                            report.results.append(item)
                            
        except Exception as e:
            print(f"Crawl4AI search failed: {e}")
            
        return report
