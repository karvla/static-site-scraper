from httpx import Client
import asyncio
import sys
import logging
from typing import Optional
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse
import tqdm
import click

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
logger.addHandler(logging.FileHandler(".scrape.log"))


def get_document_links(page: BeautifulSoup) -> set[str]:
    utf8_docs = [
        node["src"] for node in page.find_all(src=True, attrs={"charset": "utf-8"})
    ]
    href_docs = [node["href"] for node in page.find_all(href=True)]
    return set(utf8_docs + href_docs)


def get_asset_links(page: BeautifulSoup) -> set[str]:
    return set([node["src"] for node in page.find_all(src=True)]) - get_document_links(
        page
    )


async def fetch_document(url: str, session: Client) -> Optional[str]:
    logger.debug(f"GET {url}")
    response = session.get(url)

    if not response.status_code == 200:
        logger.warning(f"Failed fetching {url}, got status code {response.status_code}")
        return None
    return response.text


async def fetch_bytes(url: str, session: Client) -> Optional[bytes]:
    logger.debug(f"GET {url}")
    response = session.get(url)

    if not response.status_code == 200:
        logger.warning(f"Failed fetching {url}, got status code {response.status_code}")
        return None
    return response.read()


def get_site(base_url: str, page_limit: int) -> tuple[dict[str, str], set[str]]:
    pages: dict[str, str] = {}
    asset_links: set[str] = set()
    progress_bar = tqdm.tqdm(desc="Scraping website", unit=" pages")

    async def recursive_fetch(url: str, session: Client):
        if url in pages:
            return
        progress_bar.refresh()

        if len(pages.keys()) >= page_limit:
            return

        source = await fetch_document(url, session)
        progress_bar.update()

        if source is None:
            return

        pages[url] = source
        page = BeautifulSoup(source, "html.parser")

        next_links = [
            urljoin(url, link)
            for link in get_document_links(page)
            if not link.startswith("http")
        ]
        asset_links.update(
            set(
                [
                    urljoin(url, asset_link)
                    for asset_link in get_asset_links(page)
                    if not asset_link.startswith("http")
                ]
            )
        )
        await asyncio.gather(
            *[recursive_fetch(link, session) for link in next_links],
        )

    with Client() as session:
        asyncio.run(recursive_fetch(base_url, session))

    return pages, asset_links


async def save_all_assets(asset_links: set[str], out_dir: Path, session: Client):
    progress_bar = tqdm.tqdm(
        total=len(asset_links), desc="Downloading assets", unit=" assets"
    )

    async def fetch_and_save_asset(url: str, path: Path, session: Client):
        asset = await fetch_bytes(url, session)
        if asset is None:
            return

        asset_path = path / urlparse(url).path[1:]
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        with open(asset_path, "wb") as f:
            f.write(asset)

        progress_bar.update()

    asyncio.gather(
        *[
            asyncio.create_task(fetch_and_save_asset(url, out_dir, session))
            for url in asset_links
        ]
    )


@click.command()
@click.argument("url")
@click.argument("output", type=click.Path(exists=False))
@click.option("--page-limit", default=200, help="Max number of pages to scrape.")
@click.option(
    "--verbose", is_flag=True, default=False, help="Verbose logging to stdout."
)
def cli(url, output, page_limit, verbose):
    if verbose:
        logger.addHandler(logging.StreamHandler(sys.stdout))
    pages, assets = get_site(url, page_limit)

    out_path = Path(output)
    for page_url, source in pages.items():
        path = out_path / urlparse(page_url).path[1:]
        if path.suffix == "":
            path /= "index.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(source)

    with Client() as session:
        asyncio.run(save_all_assets(assets, out_path, session))


if __name__ == "__main__":
    cli()
