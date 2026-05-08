import re
from scraper.plugins.base import BaseParser
from scraper.core.engine import FetchResult


class HackerNewsParser(BaseParser):
    """
    Example parser for Hacker News front page.
    Extracts story titles and their ranks.

    This shows exactly how to implement the plugin contract:
    inherit BaseParser, set name/domains, implement parse().
    """

    name = "hackernews"
    domains = ["news.ycombinator.com"]

    def parse(self, result: FetchResult) -> list[dict]:
        if not result.ok:
            return []

        items = []

        # Find all story titles using regex
        # In production you'd use BeautifulSoup, but this keeps deps minimal
        title_pattern = re.compile(
            r'class="titleline"[^>]*><a[^>]*>(.*?)</a>', re.DOTALL
        )
        rank_pattern = re.compile(r'class="rank">(\d+)\.')

        titles = title_pattern.findall(result.html)
        ranks = rank_pattern.findall(result.html)

        for rank, title in zip(ranks, titles):
            items.append({
                "rank": int(rank),
                "title": title.strip(),
                "source_url": result.url,
            })

        return items


class PluginRegistry:
    """
    Central registry that maps domains to parsers.
    The engine asks the registry: 'who handles this URL?'
    """

    def __init__(self):
        self._parsers: list[BaseParser] = []

    def register(self, parser: BaseParser):
        self._parsers.append(parser)

    def get_parser(self, url: str) -> BaseParser | None:
        for parser in self._parsers:
            if parser.can_handle(url):
                return parser
        return None

    @classmethod
    def with_defaults(cls) -> "PluginRegistry":
        """Factory method that pre-loads all built-in parsers."""
        registry = cls()
        registry.register(HackerNewsParser())
        return registry