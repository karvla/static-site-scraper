from httpx import Client
import asyncio
import sys
import logging
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urljoin

logger = logging.getLogger(__name__)
logger.setLevel(level=logging.DEBUG)
logger.addHandler(logging.StreamHandler(sys.stdout))


def get_document_links(page: BeautifulSoup) -> list[str]:
    utf8_docs = [
        node["src"] for node in page.find_all(src=True, attrs={"charset": "utf-8"})
    ]
    href_docs = [node["href"] for node in page.find_all(href=True)]
    return list(set(utf8_docs + href_docs))


def get_asset_links(page: BeautifulSoup) -> set[str]:
    return set([node["src"] for node in page.find_all(src=True)])


def get_site(base_url: str) -> dict[str, str]:
    max_pages = 100

    pages: dict[str, str] = {}

    async def recursive_fetch(url: str, session: Client):
        if url in pages:
            return

        if len(pages.keys()) >= max_pages:
            return

        logger.debug(f"GET {url}")
        response = session.get(url)

        if not response.status_code == 200:
            logger.warning(
                f"Failed fetching {url}, got status code {response.status_code}"
            )
        source = response.text

        pages["index.html" if url == base_url else url] = source
        page = BeautifulSoup(source, "html.parser")

        next_links = get_document_links(page)
        next_links = [link for link in next_links if not link.startswith("http")]
        next_links = [urljoin(url, link) for link in next_links]
        asyncio.gather(
            *[recursive_fetch(link, session) for link in next_links],
            return_exceptions=True,
        )

    with Client() as session:
        asyncio.run(recursive_fetch(base_url, session))
    return pages


if __name__ == "__main__":
    base_url = sys.argv[1]
    res = get_site(base_url)

    for url, source in res.items():
        path = Path(url.replace(base_url, "./out"))
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(source)
