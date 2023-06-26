from httpx import Client
import asyncio
import sys
import logging
from typing import Optional
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))


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


def get_site(base_url: str) -> tuple[dict[str, str], set[str]]:
    max_pages = 100
    pages: dict[str, str] = {}
    asset_links: set[str] = set()

    async def recursive_fetch(url: str, session: Client):
        if url in pages:
            return

        if len(pages.keys()) >= max_pages:
            return

        source = await fetch_document(url, session)

        if source is None:
            return

        pages["index.html" if url == base_url else url] = source
        page = BeautifulSoup(source, "html.parser")

        next_links = [
            link for link in get_document_links(page) if not link.startswith("http")
        ]
        next_links = [urljoin(url, link) for link in next_links]

        asset_links.update(
            set(
                [
                    urljoin(url, asset_link)
                    for asset_link in get_asset_links(page)
                    if not asset_link.startswith("http")
                ]
            )
        )

        asyncio.gather(
            *[recursive_fetch(link, session) for link in next_links],
            return_exceptions=True,
        )

    with Client() as session:
        asyncio.run(recursive_fetch(base_url, session))

    return pages, asset_links


async def save_all_assets(asset_links: set[str], out_dir: Path, session: Client):
    async def fetch_and_save_asset(url: str, path: Path, session: Client):
        asset = await fetch_bytes(url, session)
        if asset is None:
            return

        asset_path = path / urlparse(url).path[1:]
        asset_path.parent.mkdir(parents=True, exist_ok=True)
        with open(asset_path, "wb") as f:
            f.write(asset)

    asyncio.gather(
        *[
            asyncio.create_task(fetch_and_save_asset(url, out_dir, session))
            for url in asset_links
        ]
    )


if __name__ == "__main__":
    base_url = sys.argv[1]
    pages, assets = get_site(base_url)
    out_path = Path(__file__).parent / "out"

    for url, source in pages.items():
        path = out_path / urlparse(url).path[1:]
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(source)

    with Client() as session:
        asyncio.run(save_all_assets(assets, out_path, session))
