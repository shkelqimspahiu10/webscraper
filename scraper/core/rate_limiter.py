import asyncio
import time


class RateLimiter:
    """
    Token bucket rate limiter.

    Allows up to `rate` requests per second with a burst
    capacity of `capacity` tokens. Each domain gets its
    own limiter so we never mix limits across sites.
    """

    def __init__(self, rate: float, capacity: float):
        # rate  = tokens added per second  (e.g. 5.0)
        # capacity = maximum tokens in bucket (e.g. 10.0)
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity          # start full
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()      # prevents race conditions

    def _refill(self):
        """Add tokens based on how much time has passed."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        added = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + added)
        self._last_refill = now

    async def acquire(self):
        """
        Wait until a token is available, then consume one.
        This is what every request calls before firing.
        """
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Calculate exact sleep time needed for 1 token
                wait_time = (1.0 - self._tokens) / self.rate
                await asyncio.sleep(wait_time)


class DomainRateLimiter:
    """
    Manages one RateLimiter per domain.
    So scraping google.com and reddit.com have separate buckets.
    """

    def __init__(self, rate: float = 5.0, capacity: float = 10.0):
        self.rate = rate
        self.capacity = capacity
        self._limiters: dict[str, RateLimiter] = {}

    def get_limiter(self, domain: str) -> RateLimiter:
        if domain not in self._limiters:
            self._limiters[domain] = RateLimiter(self.rate, self.capacity)
        return self._limiters[domain]

    async def acquire(self, domain: str):
        limiter = self.get_limiter(domain)
        await limiter.acquire()