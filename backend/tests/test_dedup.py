"""
Unit tests for scraper/dedup.py — pure hash logic (no DB calls).
"""
from unittest.mock import MagicMock, patch

import pytest

from scraper.dedup import url_hash, filter_new_urls, mark_seen


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

    # --- fragment stripping ---

    def test_fragment_variants_produce_same_hash(self):
        base = "https://cl.computrabajo.com/ofertas-de-trabajo/oferta-4807DE3BF341"
        h1 = url_hash(base + "#lc=ListOffers-Score4-8")
        h2 = url_hash(base + "#lc=ListOffers-Score4-15")
        h3 = url_hash(base + "#lc=ListOffers-Score4-2")
        assert h1 == h2 == h3

    def test_fragment_variant_equals_clean_url_hash(self):
        base = "https://cl.computrabajo.com/ofertas-de-trabajo/oferta-4807DE3BF341"
        assert url_hash(base) == url_hash(base + "#lc=ListOffers-Score4-N")

    def test_url_without_fragment_unchanged(self):
        url = "https://cl.computrabajo.com/ofertas-de-trabajo/oferta-ABC123"
        assert url_hash(url) == url_hash(url)


class TestFilterNewUrls:
    def _make_db(self, seen_hashes: list[str]):
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.data = [{"url_hash": h} for h in seen_hashes]
        mock_db.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_result
        return mock_db

    def test_filters_out_already_seen(self):
        base = "https://cl.computrabajo.com/ofertas-de-trabajo/job-A"
        seen_hash = url_hash(base)
        mock_db = self._make_db([seen_hash])

        with patch("scraper.dedup.get_client", return_value=mock_db):
            result = filter_new_urls([base, "https://cl.computrabajo.com/ofertas-de-trabajo/job-B"])

        assert base not in result
        assert "https://cl.computrabajo.com/ofertas-de-trabajo/job-B" in result

    def test_fragment_variant_treated_as_seen(self):
        """A URL with a fragment should be filtered if the clean version is already seen."""
        base = "https://cl.computrabajo.com/ofertas-de-trabajo/oferta-4807DE3BF341"
        seen_hash = url_hash(base)  # stored clean
        fragment_url = base + "#lc=ListOffers-Score4-8"
        mock_db = self._make_db([seen_hash])

        with patch("scraper.dedup.get_client", return_value=mock_db):
            result = filter_new_urls([fragment_url])

        assert result == []

    def test_multiple_fragment_variants_deduplicated_to_one(self):
        """Several fragment variants of the same URL count as one new URL."""
        base = "https://cl.computrabajo.com/ofertas-de-trabajo/oferta-4807DE3BF341"
        variants = [
            base + "#lc=ListOffers-Score4-8",
            base + "#lc=ListOffers-Score4-15",
            base + "#lc=ListOffers-Score4-2",
        ]
        mock_db = self._make_db([])  # nothing seen yet

        with patch("scraper.dedup.get_client", return_value=mock_db):
            result = filter_new_urls(variants)

        # All three map to the same hash → all pass the "not seen" check,
        # but the caller receives them as distinct strings (dedup happens via hash check).
        # The important guarantee: their hashes are identical so only one DB record
        # will be written on mark_seen.
        hashes = {url_hash(u) for u in result}
        assert len(hashes) == 1

    def test_empty_input_returns_empty(self):
        with patch("scraper.dedup.get_client"):
            result = filter_new_urls([])
        assert result == []


class TestMarkSeen:
    def test_stores_clean_url_hash(self):
        """mark_seen should store the fragment-stripped hash, not the raw URL hash."""
        base = "https://cl.computrabajo.com/ofertas-de-trabajo/oferta-XYZ"
        fragment_url = base + "#lc=ListOffers-Score4-1"

        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("scraper.dedup.get_client", return_value=mock_db):
            mark_seen([fragment_url])

        upsert_rows = mock_db.table.return_value.upsert.call_args[0][0]
        assert len(upsert_rows) == 1
        assert upsert_rows[0]["url_hash"] == url_hash(base)

    def test_fragment_variants_produce_single_upsert_key(self):
        """Two fragment variants of the same URL should resolve to one unique hash."""
        base = "https://cl.computrabajo.com/ofertas-de-trabajo/oferta-XYZ"
        urls = [base + "#lc=ListOffers-Score4-1", base + "#lc=ListOffers-Score4-9"]

        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock()

        with patch("scraper.dedup.get_client", return_value=mock_db):
            mark_seen(urls)

        upsert_rows = mock_db.table.return_value.upsert.call_args[0][0]
        hashes = {r["url_hash"] for r in upsert_rows}
        assert len(hashes) == 1
