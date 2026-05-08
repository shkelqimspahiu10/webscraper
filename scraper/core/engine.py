import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp

from scraper.core.rate_limiter import DomainRateLimiter
from scraper.core.proxy import ProxyPool, Proxy

logger = logging.getLogger(__name__)


@dataclass_like = None  # placeholder so the import block is clean


class FetchResult:
    """
    Everything the engine returns for a single URL.
    Keeping it in one object makes it easy to pass around.
    """
    def __init__(self, url: str, status: int, html: str, proxy_used: str | None, error: str | None = None):
        self.url = url
        self.status = status
        self.html = html
        self.proxy_used = proxy_used
        self.error = error

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status < 300

    def __repr__(self):
        return f"<FetchResult url={self.url!r} status={self.status} ok={self.ok}>"


class ScraperEngine:
    """
    Async HTTP engine with:
    - Concurrency control via asyncio.Semaphore
    - Per-domain rate limiting
    - Proxy rotation with failure reporting
    - Automatic retries with exponential backoff
    """

    def __init__(
        self,
        concurrency: int = 10,
        rate: float = 5.0,
        capacity: float = 10.0,
        proxy_urls: list[str] | None = None,
        retries: int = 3,
        timeout: int = 30,
    ):
        # Semaphore limits how many requests run at once
        self._semaphore = asyncio.Semaphore(concurrency)
        self._rate_limiter = DomainRateLimiter(rate=rate, capacity=capacity)
        self._proxy_pool = ProxyPool(proxy_urls or [])
        self._retries = retries
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Called when used as: async with ScraperEngine() as engine"""
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *args):
        """Always close the session cleanly, even if an error occurred."""
        if self._session:
            await self._session.close()

    def _extract_domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch a single URL with rate limiting, proxy rotation, and retries.
        This is the core method everything else builds on.
        """
        domain = self._extract_domain(url)

        for attempt in range(self._retries):
            # Wait for rate limiter — politely throttle per domain
            await self._rate_limiter.acquire(domain)

            proxy = self._proxy_pool.get_proxy()
            proxy_url = proxy.url if proxy else None

            # Semaphore ensures max `concurrency` requests run simultaneously
            async with self._semaphore:
                try:
                    async with self._session.get(url, proxy=proxy_url) as response:
                        html = await response.text()
                        if proxy:
                            self._proxy_pool.report_success(proxy)
                        return FetchResult(
                            url=url,
                            status=response.status,
                            html=html,
                            proxy_used=proxy_url,
                        )

                except aiohttp.ClientError as e:
                    logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                    if proxy:
                        self._proxy_pool.report_failure(proxy)

                    if attempt < self._retries - 1:
                        # Exponential backoff: wait 1s, 2s, 4s between retries
                        await asyncio.sleep(2 ** attempt)

        return FetchResult(url=url, status=0, html="", proxy_used=None, error="Max retries exceeded")

    async def fetch_many(self, urls: list[str]) -> list[FetchResult]:
        """
        Fetch multiple URLs concurrently.
        asyncio.gather runs all coroutines simultaneously,
        respecting the semaphore limit.
        """
        tasks = [self.fetch(url) for url in urls]
        return await asyncio.gather(*tasks)