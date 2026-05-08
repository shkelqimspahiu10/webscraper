import asyncio
import time
import pytest
from scraper.core.rate_limiter import RateLimiter, DomainRateLimiter


@pytest.mark.asyncio
async def test_token_consumed_on_acquire():
    limiter = RateLimiter(rate=10.0, capacity=10.0)
    await limiter.acquire()
    assert limiter._tokens == 9.0


@pytest.mark.asyncio
async def test_rate_limiting_slows_requests():
    limiter = RateLimiter(rate=10.0, capacity=1.0)
    start = time.monotonic()
    await limiter.acquire()  # uses the 1 token immediately
    await limiter.acquire()  # must wait for refill
    elapsed = time.monotonic() - start
    assert elapsed >= 0.09  # should have waited ~0.1s for 1 token at rate=10


def test_domain_limiter_creates_separate_buckets():
    dl = DomainRateLimiter(rate=5.0, capacity=10.0)
    a = dl.get_limiter("google.com")
    b = dl.get_limiter("reddit.com")
    c = dl.get_limiter("google.com")
    assert a is c        # same object returned for same domain
    assert a is not b    # different domains = different buckets