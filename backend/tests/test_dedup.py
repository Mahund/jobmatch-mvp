"""
Unit tests for scraper/dedup.py — pure hash logic (no DB calls).
"""
from scraper.dedup import url_hash


class TestUrlHash:
    def test_returns_32_hex_chars(self):
        h = url_hash("https://cl.computrabajo.com/ofertas-de-trabajo/example-123")
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        url = "https://cl.computrabajo.com/ofertas-de-trabajo/example-123"
        assert url_hash(url) == url_hash(url)

    def test_different_urls_produce_different_hashes(self):
        h1 = url_hash("https://cl.computrabajo.com/ofertas-de-trabajo/job-a")
        h2 = url_hash("https://cl.computrabajo.com/ofertas-de-trabajo/job-b")
        assert h1 != h2

    def test_empty_string_is_stable(self):
        h = url_hash("")
        assert len(h) == 32
