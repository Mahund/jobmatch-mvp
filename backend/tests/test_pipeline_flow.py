"""
Pipeline flow tests — orchestration logic with mocked DB/storage.
Verifies that pipeline steps connect correctly and handle edge cases.
"""
from unittest.mock import MagicMock, call, patch

import pytest

from matching.engine import Profile, run_matching
from scraper.extract_run import _extract_title_from_soup, _is_enfermeria_role
from scraper.extract import build_batch_request
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_listing(**overrides):
    defaults = dict(
        url_hash="h1",
        title="Enfermera UCI",
        region="Región Metropolitana",
        years_experience=1,
        contract_type="full-time",
        specialty="UCI adulto",
    )
    return {**defaults, **overrides}


def _make_profile(**overrides):
    defaults = dict(
        user_id="u1",
        specialty="UCI",
        years_experience=1,
        region="Metropolitana",
        accepted_contracts=["full-time"],
        preferred_schedule=None,
        min_salary=None,
        licensure_held=[],
    )
    return Profile(**{**defaults, **overrides})


# ---------------------------------------------------------------------------
# Pre-filter: non-enfermeria is caught before building a batch request
# ---------------------------------------------------------------------------

class TestExtractPreFilter:
    """
    The extractor checks the h1 title before calling Claude.
    These tests verify the filter fires on the right inputs.
    """

    def _soup(self, h1_text):
        return BeautifulSoup(f"<html><body><h1>{h1_text}</h1></body></html>", "lxml")

    def test_enfermera_passes_prefilter(self):
        soup = self._soup("Enfermera UCI")
        title = _extract_title_from_soup(soup)
        assert _is_enfermeria_role(title) is True

    def test_tens_blocked_by_prefilter(self):
        soup = self._soup("TENS Enfermería")
        title = _extract_title_from_soup(soup)
        assert _is_enfermeria_role(title) is False

    def test_no_h1_blocked_by_prefilter(self):
        soup = BeautifulSoup("<html><body><p>Some text</p></body></html>", "lxml")
        title = _extract_title_from_soup(soup)
        assert _is_enfermeria_role(title) is False

    def test_batch_request_only_built_for_passing_listings(self):
        """Simulate the extract_run loop: build requests only for enfermeria roles."""
        listings = [
            {"title": "Enfermera UCI", "html": "<html><h1>Enfermera UCI</h1><p>Details</p></html>"},
            {"title": "TENS Enfermería", "html": "<html><h1>TENS Enfermería</h1><p>Details</p></html>"},
            {"title": "Médico General", "html": "<html><h1>Médico General</h1><p>Details</p></html>"},
        ]

        requests = []
        for i, item in enumerate(listings):
            soup = BeautifulSoup(item["html"], "lxml")
            title = _extract_title_from_soup(soup)
            if _is_enfermeria_role(title):
                requests.append(build_batch_request(f"hash{i}", item["html"]))

        assert len(requests) == 1
        assert requests[0]["custom_id"] == "hash0"


# ---------------------------------------------------------------------------
# Matching: full filter → score → sort pipeline (mocked DB)
# ---------------------------------------------------------------------------

class TestMatchingFullFlow:
    def _mock_db(self, listings):
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = listings
        return mock_db

    def test_only_enfermeria_listings_pass(self):
        listings = [
            _make_listing(url_hash="ok", title="Enfermera UCI"),
            _make_listing(url_hash="bad", title="TENS Enfermería"),
        ]
        with patch("matching.engine.get_client", return_value=self._mock_db(listings)):
            results = run_matching(_make_profile(), write_results=False)
        hashes = [r["listing_hash"] for r in results]
        assert "ok" in hashes
        assert "bad" not in hashes

    def test_region_filter_applied(self):
        listings = [
            _make_listing(url_hash="correct", region="Región Metropolitana"),
            _make_listing(url_hash="wrong", region="Valparaíso"),
        ]
        with patch("matching.engine.get_client", return_value=self._mock_db(listings)):
            results = run_matching(_make_profile(region="Metropolitana"), write_results=False)
        hashes = [r["listing_hash"] for r in results]
        assert "correct" in hashes
        assert "wrong" not in hashes

    def test_experience_filter_applied(self):
        listings = [
            _make_listing(url_hash="ok", years_experience=1),
            _make_listing(url_hash="too_high", years_experience=5),
        ]
        with patch("matching.engine.get_client", return_value=self._mock_db(listings)):
            results = run_matching(_make_profile(years_experience=2), write_results=False)
        hashes = [r["listing_hash"] for r in results]
        assert "ok" in hashes
        assert "too_high" not in hashes

    def test_results_sorted_score_descending(self):
        listings = [
            _make_listing(url_hash="general", specialty="CESFAM"),
            _make_listing(url_hash="exact", specialty="UCI adulto"),
            _make_listing(url_hash="related", specialty="urgencias"),
        ]
        with patch("matching.engine.get_client", return_value=self._mock_db(listings)):
            results = run_matching(_make_profile(specialty="UCI"), write_results=False)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_specialty_tiers_assigned_correctly(self):
        listings = [
            _make_listing(url_hash="exact", specialty="UCI adulto"),
            _make_listing(url_hash="related", specialty="urgencias"),
            _make_listing(url_hash="general", specialty="CESFAM"),
        ]
        with patch("matching.engine.get_client", return_value=self._mock_db(listings)):
            results = run_matching(_make_profile(specialty="UCI"), write_results=False)
        tier_map = {r["listing_hash"]: r["specialty_tier"] for r in results}
        assert tier_map["exact"] == "exact"
        assert tier_map["related"] == "related"
        assert tier_map["general"] == "general"

    def test_write_results_false_skips_db_writes(self):
        listings = [_make_listing()]
        mock_db = self._mock_db(listings)
        with patch("matching.engine.get_client", return_value=mock_db):
            run_matching(_make_profile(), write_results=False)
        # delete and upsert should NOT be called
        delete_called = mock_db.table.return_value.delete.called
        assert not delete_called

    def test_empty_db_returns_empty_results(self):
        with patch("matching.engine.get_client", return_value=self._mock_db([])):
            results = run_matching(_make_profile(), write_results=False)
        assert results == []


# ---------------------------------------------------------------------------
# Confidence routing: ok vs low_confidence status
# ---------------------------------------------------------------------------

class TestConfidenceRouting:
    """Verify the confidence threshold determines extraction_status correctly."""

    def _run_write(self, confidence):
        from scraper.extract_run import write_listing
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        with patch("scraper.extract_run.get_client", return_value=mock_db):
            write_listing("h1", "http://example.com", {"confidence": confidence, "title": "Enfermera"})
        return mock_db.table.return_value.upsert.call_args[0][0]

    def test_confidence_0_9_ok(self):
        assert self._run_write(0.9)["extraction_status"] == "ok"

    def test_confidence_0_6_ok(self):
        assert self._run_write(0.6)["extraction_status"] == "ok"

    def test_confidence_0_59_low(self):
        assert self._run_write(0.59)["extraction_status"] == "low_confidence"

    def test_confidence_0_low(self):
        assert self._run_write(0.0)["extraction_status"] == "low_confidence"
