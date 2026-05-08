from abc import ABC, abstractmethod
from scraper.core.engine import FetchResult


class BaseParser(ABC):
    """
    Abstract base class that every parser plugin must inherit from.

    ABC = Abstract Base Class. Any class that inherits from this
    MUST implement the abstract methods or Python raises a TypeError
    at instantiation time — catching mistakes early.
    """

    # Every parser declares which URLs it can handle
    name: str = ""
    domains: list[str] = []

    @abstractmethod
    def parse(self, result: FetchResult) -> list[dict]:
        """
        Extract structured data from a FetchResult.

        Args:
            result: The raw HTML response from the engine

        Returns:
            A list of dicts, one per extracted item.
            e.g. [{"title": "...", "price": "..."}, ...]
        """
        raise NotImplementedError

    def can_handle(self, url: str) -> bool:
        """Check if this parser handles the given URL."""
        return any(domain in url for domain in self.domains)