import random
import time
from dataclasses import dataclass, field


@dataclass
class Proxy:
    """
    Represents a single proxy with health tracking.
    A dataclass auto-generates __init__, __repr__, __eq__
    based on the fields we declare.
    """
    url: str                        # e.g. "http://1.2.3.4:8080"
    failures: int = 0               # how many times it has failed
    last_failure: float = 0.0       # timestamp of last failure
    max_failures: int = 3           # failures before marked dead
    cooldown: float = 60.0          # seconds to wait after a failure

    @property
    def is_dead(self) -> bool:
        return self.failures >= self.max_failures

    @property
    def is_cooling(self) -> bool:
        if self.last_failure == 0.0:
            return False
        return (time.monotonic() - self.last_failure) < self.cooldown

    @property
    def is_healthy(self) -> bool:
        return not self.is_dead and not self.is_cooling

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.monotonic()

    def record_success(self):
        """Reset failure count on success — proxy has recovered."""
        self.failures = 0
        self.last_failure = 0.0


class ProxyPool:
    """
    Manages a collection of proxies with health-aware rotation.

    Design decisions:
    - Random selection among healthy proxies distributes load evenly
    - Dead proxies stay in the list so we can inspect them later
    - Cooldown gives temporarily blocked proxies time to recover
    """

    def __init__(self, proxy_urls: list[str], max_failures: int = 3, cooldown: float = 60.0):
        self._proxies = [
            Proxy(url=url, max_failures=max_failures, cooldown=cooldown)
            for url in proxy_urls
        ]

    def get_proxy(self) -> Proxy | None:
        """Return a random healthy proxy, or None if none available."""
        healthy = [p for p in self._proxies if p.is_healthy]
        if not healthy:
            return None
        return random.choice(healthy)

    def report_failure(self, proxy: Proxy):
        proxy.record_failure()

    def report_success(self, proxy: Proxy):
        proxy.record_success()

    @property
    def stats(self) -> dict:
        """Useful for logging and debugging."""
        return {
            "total": len(self._proxies),
            "healthy": sum(1 for p in self._proxies if p.is_healthy),
            "cooling": sum(1 for p in self._proxies if p.is_cooling),
            "dead": sum(1 for p in self._proxies if p.is_dead),
        }