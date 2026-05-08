import asyncio
import logging
from urllib.parse import urlparse

import aiohttp

from scraper.core.rate_limiter import DomainRateLimiter
from scraper.core.proxy import ProxyPool

logger = logging.getLogger(__name__)


class FetchResult:
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
    def __init__(self, concurrency=10, rate=5.0, capacity=10.0, proxy_urls=None, retries=3, timeout=30):
        self._semaphore = asyncio.Semaphore(concurrency)
        self._rate_limiter = DomainRateLimiter(rate=rate, capacity=capacity)
        self._proxy_pool = ProxyPool(proxy_urls or [])
        self._retries = retries
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session = None

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    def _extract_domain(self, url: str) -> str:
        return urlparse(url).netloc

    async def fetch(self, url: str) -> FetchResult:
        domain = self._extract_domain(url)
        for attempt in range(self._retries):
            await self._rate_limiter.acquire(domain)
            proxy = self._proxy_pool.get_proxy()
            proxy_url = proxy.url if proxy else None
            async with self._semaphore:
                try:
                    async with self._session.get(url, proxy=proxy_url) as response:
                        html = await response.text()
                        if proxy:
                            self._proxy_pool.report_success(proxy)
                        return FetchResult(url=url, status=response.status, html=html, proxy_used=proxy_url)
                except aiohttp.ClientError as e:
                    logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                    if proxy:
                        self._proxy_pool.report_failure(proxy)
                    if attempt < self._retries - 1:
                        await asyncio.sleep(2 ** attempt)
        return FetchResult(url=url, status=0, html="", proxy_used=None, error="Max retries exceeded")

    async def fetch_many(self, urls: list) -> list:
        tasks = [self.fetch(url) for url in urls]
        return await asyncio.gather(*tasks)
