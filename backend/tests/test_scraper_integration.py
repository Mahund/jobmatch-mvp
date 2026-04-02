"""
Integration smoke tests — hit the live Computrabajo website to verify
the scraper's HTML parsing assumptions still hold after site changes.

Run manually:  pytest -m integration -v
Skipped in CI: pytest -m "not integration"
"""
import pytest
import httpx
from bs4 import BeautifulSoup

from scraper.extract import html_to_text

BASE_URL = "https://cl.computrabajo.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
SEARCH_URL = f"{BASE_URL}/trabajo-de-enfermera"


@pytest.fixture(scope="module")
def search_page_html():
    """Fetch the enfermera search page once and share across tests in this module."""
    with httpx.Client(headers=HEADERS, timeout=20) as client:
        resp = client.get(SEARCH_URL, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


@pytest.fixture(scope="module")
def first_listing_url(search_page_html):
    """Extract the first listing URL from the search results page."""
    soup = BeautifulSoup(search_page_html, "lxml")
    links = soup.select("a[href*='/ofertas-de-trabajo/']")
    for a in links:
        href = a.get("href", "")
        if href.startswith("/"):
            href = BASE_URL + href
        if "/ofertas-de-trabajo/" in href:
            return href
    return None


@pytest.mark.integration
def test_search_page_returns_listing_urls(search_page_html):
    """Search results page must contain parseable listing links.
    Failure means Computrabajo redesigned their HTML and the scraper is broken."""
    soup = BeautifulSoup(search_page_html, "lxml")
    links = [
        a.get("href", "")
        for a in soup.select("a[href*='/ofertas-de-trabajo/']")
    ]
    assert len(links) > 0, (
        "No listing URLs found on search page — Computrabajo may have changed "
        "their HTML structure. Check the CSS selector in scraper/fetch.py."
    )


@pytest.mark.integration
def test_listing_page_has_h1(first_listing_url):
    """A listing detail page must have an <h1> tag.
    The extractor relies on this for pre-filtering before calling Claude."""
    assert first_listing_url is not None, "Could not find any listing URL on search page"

    with httpx.Client(headers=HEADERS, timeout=20) as client:
        resp = client.get(first_listing_url, follow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    h1 = soup.find("h1")
    assert h1 is not None, (
        f"No <h1> found on listing page {first_listing_url} — "
        "the pre-filter title extraction in extract_run.py will always return None."
    )
    assert h1.get_text(strip=True), "h1 tag is empty"


@pytest.mark.integration
def test_listing_html_to_text_roundtrip(first_listing_url):
    """Fetching a listing and running it through html_to_text() must produce
    non-empty text within the 3000-char budget sent to Claude."""
    assert first_listing_url is not None, "Could not find any listing URL on search page"

    with httpx.Client(headers=HEADERS, timeout=20) as client:
        resp = client.get(first_listing_url, follow_redirects=True)
    resp.raise_for_status()

    text = html_to_text(resp.text)
    assert text, "html_to_text returned empty string for a real listing"
    assert len(text) <= 3000, f"html_to_text output exceeds 3000 chars: {len(text)}"
