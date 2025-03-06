import asyncio
from crawl4ai import *

async def main():
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(
            url="https://www.linkedin.com/search/results/all/?keywords=hr%20manager%20google&origin=GLOBAL_SEARCH_HEADER&sid=n!L",
        )
        print(result.markdown)

if __name__ == "__main__":
    asyncio.run(main())