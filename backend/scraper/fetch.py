import time
import random
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urldefrag

BASE_URL = "https://cl.computrabajo.com"
SEARCH_QUERIES = ["enfermera", "enfermero", "nurse"]
MAX_PAGES = 3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _get(client: httpx.Client, url: str) -> httpx.Response | None:
    try:
        resp = client.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as e:
        print(f"  HTTP {e.response.status_code} — {url}")
        return None
    except httpx.RequestError as e:
        print(f"  Request error — {url}: {e}")
        return None


def get_listing_urls() -> list[str]:
    """Scrape search result pages and return all unique listing URLs."""
    urls: set[str] = set()

    with httpx.Client(headers=HEADERS) as client:
        for query in SEARCH_QUERIES:
            for page in range(1, MAX_PAGES + 1):
                if page == 1:
                    search_url = f"{BASE_URL}/trabajo-de-{query.replace(' ', '-')}"
                else:
                    search_url = f"{BASE_URL}/trabajo-de-{query.replace(' ', '-')}?p={page}"

                print(f"Searching: {search_url}")
                resp = _get(client, search_url)
                if resp is None:
                    break

                soup = BeautifulSoup(resp.text, "lxml")

                # Computrabajo listing links: <a> tags pointing to /ofertas-de-trabajo/
                links = soup.select("a[href*='/ofertas-de-trabajo/']")
                found = 0
                for a in links:
                    href = a.get("href", "")
                    if href.startswith("/"):
                        href = BASE_URL + href
                    href, _ = urldefrag(href)  # strip tracking fragment
                    if "/ofertas-de-trabajo/" in href and href not in urls:
                        urls.add(href)
                        found += 1

                print(f"  Found {found} new listings (page {page})")

                if found == 0:
                    break  # no more pages for this query

                time.sleep(random.uniform(1.5, 3.0))

    return list(urls)


def fetch_listing_html(url: str) -> str | None:
    """Fetch a single listing detail page and return its raw HTML."""
    with httpx.Client(headers=HEADERS) as client:
        resp = _get(client, url)
        if resp is None:
            return None
        return resp.text
