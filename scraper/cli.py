import asyncio
import json
import logging
import click
from scraper.core.engine import ScraperEngine
from scraper.plugins.example import PluginRegistry


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@click.group()
def main():
    """A distributed async web scraping framework."""
    pass


@main.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--concurrency", "-c", default=10, help="Max simultaneous requests")
@click.option("--rate", "-r", default=5.0, help="Requests per second per domain")
@click.option("--proxy", "-p", multiple=True, help="Proxy URL (can repeat for multiple)")
@click.option("--output", "-o", default="results.json", help="Output file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def scrape(urls, concurrency, rate, proxy, output, verbose):
    """
    Scrape one or more URLs and save extracted data to JSON.

    Example:
        webscraper scrape https://news.ycombinator.com
    """
    setup_logging(verbose)
    asyncio.run(_scrape(list(urls), concurrency, rate, list(proxy), output))


async def _scrape(urls, concurrency, rate, proxies, output):
    """The actual async work — Click can't be async so we bridge here."""
    registry = PluginRegistry.with_defaults()
    all_results = []

    async with ScraperEngine(
        concurrency=concurrency,
        rate=rate,
        proxy_urls=proxies or None,
    ) as engine:
        click.echo(f"Fetching {len(urls)} URL(s)...")
        results = await engine.fetch_many(urls)

        for result in results:
            click.echo(f"  {result.status} {result.url}")

            parser = registry.get_parser(result.url)
            if parser:
                items = parser.parse(result)
                all_results.extend(items)
                click.echo(f"    → Parsed {len(items)} items with '{parser.name}'")
            else:
                click.echo(f"    → No parser registered for this URL")
                if result.ok:
                    all_results.append({"url": result.url, "html_length": len(result.html)})

    with open(output, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    click.echo(f"\nDone. {len(all_results)} items saved to '{output}'")


@main.command()
def plugins():
    """List all registered parser plugins."""
    registry = PluginRegistry.with_defaults()
    click.echo("Registered parsers:")
    for parser in registry._parsers:
        click.echo(f"  • {parser.name} → {', '.join(parser.domains)}")