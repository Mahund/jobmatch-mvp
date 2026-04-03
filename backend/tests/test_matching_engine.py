"""
Unit tests for matching/engine.py — the core pipeline business logic.
No DB or network calls; all pure functions.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from matching.engine import (
    NEWNESS_WINDOW,
    SPECIALTY_TIERS,
    Profile,
    _get_specialty_group,
    _is_enfermeria_role,
    _is_recent,
    _normalize_text,
    _passes_hard_filters,
    _score,
    _specialty_tier,
    run_matching,
)


# ---------------------------------------------------------------------------
# _normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_strips_accents(self):
        assert _normalize_text("Enfermería") == "enfermeria"

    def test_lowercases(self):
        assert _normalize_text("ENFERMERA") == "enfermera"

    def test_none_returns_empty(self):
        assert _normalize_text(None) == ""

    def test_empty_string_returns_empty(self):
        assert _normalize_text("") == ""

    def test_mixed_accents_and_case(self):
        assert _normalize_text("Técnico en Enfermería") == "tecnico en enfermeria"


# ---------------------------------------------------------------------------
# _is_enfermeria_role
# ---------------------------------------------------------------------------

class TestIsEnfermeriaRole:
    def test_accepts_enfermera(self):
        assert _is_enfermeria_role("Enfermera") is True

    def test_accepts_enfermero(self):
        assert _is_enfermeria_role("Enfermero UCI") is True

    def test_accepts_with_accent(self):
        assert _is_enfermeria_role("Enfermería Clínica") is True

    def test_accepts_enfermera_jefe(self):
        assert _is_enfermeria_role("Enfermera Jefe de Turno") is True

    def test_rejects_tens(self):
        assert _is_enfermeria_role("TENS Enfermería") is False

    def test_rejects_tecnico(self):
        assert _is_enfermeria_role("Técnico en Enfermería") is False

    def test_rejects_tecnica(self):
        assert _is_enfermeria_role("Técnica en Enfermería") is False

    def test_rejects_auxiliar(self):
        assert _is_enfermeria_role("Auxiliar de Enfermería") is False

    def test_rejects_paramedic(self):
        assert _is_enfermeria_role("Paramédico con manejo de enfermería") is False

    def test_rejects_kinesiolog(self):
        assert _is_enfermeria_role("Kinesiólogo / Enfermería") is False

    def test_rejects_estudiante(self):
        assert _is_enfermeria_role("Estudiante de Enfermería") is False

    def test_rejects_intern(self):
        assert _is_enfermeria_role("Intern Enfermería") is False

    def test_rejects_no_enfermer(self):
        assert _is_enfermeria_role("Médico General") is False

    def test_rejects_none(self):
        assert _is_enfermeria_role(None) is False

    def test_rejects_empty(self):
        assert _is_enfermeria_role("") is False


# ---------------------------------------------------------------------------
# _get_specialty_group
# ---------------------------------------------------------------------------

class TestGetSpecialtyGroup:
    def test_uci(self):
        assert _get_specialty_group("UCI adulto") == "uci"

    def test_uti(self):
        assert _get_specialty_group("UTI") == "uci"

    def test_urgencias(self):
        assert _get_specialty_group("Urgencias pediátricas") == "urgencias"

    def test_emergencia(self):
        assert _get_specialty_group("Emergencia") == "urgencias"

    def test_pediatria(self):
        assert _get_specialty_group("Pediatría general") == "pediatría"

    def test_pabellon(self):
        assert _get_specialty_group("Pabellón quirúrgico") == "pabellón"

    def test_oncologia(self):
        assert _get_specialty_group("Oncología") == "oncología"

    def test_domiciliaria(self):
        assert _get_specialty_group("Atención domiciliaria") == "domiciliaria"

    def test_maternidad(self):
        assert _get_specialty_group("Ginecología y Obstetricia") == "maternidad"

    def test_aps(self):
        assert _get_specialty_group("CESFAM") == "aps"

    def test_unknown_returns_none(self):
        assert _get_specialty_group("Dermatología") is None

    def test_empty_returns_none(self):
        assert _get_specialty_group("") is None


# ---------------------------------------------------------------------------
# _specialty_tier
# ---------------------------------------------------------------------------

class TestSpecialtyTier:
    def test_exact_match_same_group(self):
        assert _specialty_tier("UCI", "UTI adulto") == "exact"

    def test_exact_match_urgencias(self):
        assert _specialty_tier("urgencias", "emergencia") == "exact"

    def test_related_urgencias_uci(self):
        assert _specialty_tier("urgencias", "UCI") == "related"

    def test_related_uci_coronaria(self):
        assert _specialty_tier("UCI", "coronaria") == "related"

    def test_related_maternidad_neonatologia(self):
        assert _specialty_tier("maternidad", "neonato") == "related"

    def test_unrelated_returns_general(self):
        assert _specialty_tier("oncología", "CESFAM") == "general"

    def test_none_listing_specialty_returns_general(self):
        assert _specialty_tier("urgencias", None) == "general"

    def test_empty_listing_specialty_returns_general(self):
        assert _specialty_tier("urgencias", "") == "general"

    def test_unknown_user_specialty_returns_general(self):
        assert _specialty_tier("Dermatología", "UCI") == "general"

    def test_both_unknown_returns_general(self):
        assert _specialty_tier("Dermatología", "Cardiología intervencionista avanzada") == "general"


# ---------------------------------------------------------------------------
# _passes_hard_filters
# ---------------------------------------------------------------------------

def _make_profile(**overrides):
    defaults = dict(
        user_id="u1",
        specialty="UCI",
        years_experience=2,
        region="Metropolitana",
        accepted_contracts=["full-time", "part-time"],
        preferred_schedule=None,
        min_salary=None,
        licensure_held=[],
    )
    return Profile(**{**defaults, **overrides})


def _make_listing(**overrides):
    defaults = dict(
        url_hash="abc123",
        title="Enfermera UCI",
        region="Región Metropolitana",
        years_experience=2,
        contract_type="full-time",
        specialty="UCI adulto",
    )
    return {**defaults, **overrides}


class TestPassesHardFilters:
    def test_all_passing(self):
        passes, reason = _passes_hard_filters(_make_listing(), _make_profile())
        assert passes is True
        assert reason is None

    def test_non_enfermeria_title_rejected(self):
        passes, reason = _passes_hard_filters(
            _make_listing(title="Técnico en Enfermería"), _make_profile()
        )
        assert passes is False
        assert "non-enfermeria" in reason

    def test_region_mismatch_rejected(self):
        passes, reason = _passes_hard_filters(
            _make_listing(region="Valparaíso"), _make_profile(region="Metropolitana")
        )
        assert passes is False
        assert "region" in reason

    def test_region_match_substring(self):
        # profile region is substring of listing region
        passes, _ = _passes_hard_filters(
            _make_listing(region="Región Metropolitana de Santiago"),
            _make_profile(region="Metropolitana"),
        )
        assert passes is True

    def test_insufficient_experience_rejected(self):
        passes, reason = _passes_hard_filters(
            _make_listing(years_experience=5), _make_profile(years_experience=2)
        )
        assert passes is False
        assert "experience" in reason

    def test_zero_required_experience_always_passes(self):
        passes, _ = _passes_hard_filters(
            _make_listing(years_experience=0), _make_profile(years_experience=0)
        )
        assert passes is True

    def test_contract_type_not_accepted_rejected(self):
        passes, reason = _passes_hard_filters(
            _make_listing(contract_type="per diem"),
            _make_profile(accepted_contracts=["full-time"]),
        )
        assert passes is False
        assert "contract" in reason

    def test_contract_unknown_always_passes(self):
        passes, _ = _passes_hard_filters(
            _make_listing(contract_type="unknown"),
            _make_profile(accepted_contracts=["full-time"]),
        )
        assert passes is True

    def test_contract_contract_type_always_passes(self):
        passes, _ = _passes_hard_filters(
            _make_listing(contract_type="contract"),
            _make_profile(accepted_contracts=["full-time"]),
        )
        assert passes is True

    def test_missing_listing_region_skips_region_filter(self):
        passes, _ = _passes_hard_filters(
            _make_listing(region=None), _make_profile(region="Metropolitana")
        )
        assert passes is True

    def test_missing_contract_type_skips_contract_filter(self):
        passes, _ = _passes_hard_filters(
            _make_listing(contract_type=None),
            _make_profile(accepted_contracts=["full-time"]),
        )
        assert passes is True


# ---------------------------------------------------------------------------
# _score
# ---------------------------------------------------------------------------

class TestScore:
    def test_exact_score(self):
        score, tier = _score(_make_listing(specialty="UCI adulto"), _make_profile(specialty="UCI"))
        assert tier == "exact"
        assert score == SPECIALTY_TIERS["exact"]

    def test_related_score(self):
        score, tier = _score(_make_listing(specialty="urgencias"), _make_profile(specialty="UCI"))
        assert tier == "related"
        assert score == SPECIALTY_TIERS["related"]

    def test_general_score(self):
        score, tier = _score(_make_listing(specialty="CESFAM"), _make_profile(specialty="UCI"))
        assert tier == "general"
        assert score == SPECIALTY_TIERS["general"]


# ---------------------------------------------------------------------------
# run_matching — full pipeline with mocked DB
# ---------------------------------------------------------------------------

def _mock_db_with_listings(listings):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = listings
    return mock_db


class TestRunMatching:
    def _profile(self):
        return _make_profile(region="Metropolitana", specialty="UCI", years_experience=2)

    def test_returns_matching_listings(self):
        listings = [_make_listing(url_hash="h1", specialty="UCI adulto")]
        with patch("matching.engine.get_client", return_value=_mock_db_with_listings(listings)):
            results = run_matching(self._profile(), write_results=False)
        assert len(results) == 1
        assert results[0]["listing_hash"] == "h1"

    def test_filters_out_non_enfermeria(self):
        listings = [_make_listing(title="Técnico en Enfermería")]
        with patch("matching.engine.get_client", return_value=_mock_db_with_listings(listings)):
            results = run_matching(self._profile(), write_results=False)
        assert results == []

    def test_filters_out_wrong_region(self):
        listings = [_make_listing(region="Antofagasta")]
        with patch("matching.engine.get_client", return_value=_mock_db_with_listings(listings)):
            results = run_matching(self._profile(), write_results=False)
        assert results == []

    def test_filters_out_insufficient_experience(self):
        listings = [_make_listing(years_experience=5)]
        with patch("matching.engine.get_client", return_value=_mock_db_with_listings(listings)):
            results = run_matching(_make_profile(years_experience=2), write_results=False)
        assert results == []

    def test_sorted_by_score_descending(self):
        listings = [
            _make_listing(url_hash="general", specialty="CESFAM"),
            _make_listing(url_hash="exact", specialty="UCI adulto"),
            _make_listing(url_hash="related", specialty="urgencias"),
        ]
        with patch("matching.engine.get_client", return_value=_mock_db_with_listings(listings)):
            results = run_matching(self._profile(), write_results=False)
        tiers = [r["specialty_tier"] for r in results]
        assert tiers == ["exact", "related", "general"]

    def test_empty_listings_returns_empty(self):
        with patch("matching.engine.get_client", return_value=_mock_db_with_listings([])):
            results = run_matching(self._profile(), write_results=False)
        assert results == []


# ---------------------------------------------------------------------------
# _is_recent
# ---------------------------------------------------------------------------


class TestIsRecent:
    def test_within_window_returns_true(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        assert _is_recent(recent) is True

    def test_outside_window_returns_false(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        assert _is_recent(old) is False

    def test_just_past_boundary_returns_false(self):
        # One second beyond the newness window
        boundary = (datetime.now(timezone.utc) - NEWNESS_WINDOW - timedelta(seconds=1)).isoformat()
        assert _is_recent(boundary) is False

    def test_none_returns_false(self):
        assert _is_recent(None) is False

    def test_empty_string_returns_false(self):
        assert _is_recent("") is False

    def test_invalid_iso_returns_false(self):
        assert _is_recent("not-a-date") is False

    def test_z_suffix_handled(self):
        recent = (datetime.now(timezone.utc) - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert _is_recent(recent) is True

    def test_naive_datetime_treated_as_utc(self):
        recent_naive = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat()
        assert _is_recent(recent_naive) is True


# ---------------------------------------------------------------------------
# run_matching — write_results=True path
# ---------------------------------------------------------------------------

def _mock_db_full(listings, seen_rows=None):
    """Mock DB that handles listings select, seen_urls select, upsert, and delete chains."""
    mock_db = MagicMock()

    # listings query: table("listings").select("*").eq(...).execute()
    listings_table = MagicMock()
    listings_table.select.return_value.eq.return_value.execute.return_value.data = listings

    # seen_urls query: table("seen_urls").select(...).in_(...).execute()
    seen_table = MagicMock()
    seen_table.select.return_value.in_.return_value.execute.return_value.data = seen_rows or []

    # matches table: upsert and delete chains
    matches_table = MagicMock()
    matches_table.upsert.return_value.execute.return_value = MagicMock()
    delete_chain = MagicMock()
    delete_chain.eq.return_value = delete_chain
    delete_chain.not_ = MagicMock()
    delete_chain.not_.in_.return_value = delete_chain
    delete_chain.execute.return_value = MagicMock()
    matches_table.delete.return_value = delete_chain

    _tables = {"listings": listings_table, "seen_urls": seen_table, "matches": matches_table}
    mock_db.table.side_effect = lambda name: _tables[name]
    mock_db._tables = _tables  # expose for assertions
    return mock_db


class TestRunMatchingWriteResults:
    def _profile(self):
        return _make_profile(user_id="u1", region="Metropolitana", specialty="UCI", years_experience=2)

    def test_upsert_called_with_passing_rows(self):
        listings = [_make_listing(url_hash="h1", specialty="UCI adulto")]
        mock_db = _mock_db_full(listings)
        with patch("matching.engine.get_client", return_value=mock_db):
            results = run_matching(self._profile(), write_results=True)
        assert len(results) == 1
        matches_table = mock_db._tables["matches"]
        upsert_call = matches_table.upsert.call_args
        rows = upsert_call[0][0]
        assert len(rows) == 1
        assert rows[0]["listing_hash"] == "h1"
        assert "_listing" not in rows[0]

    def test_delete_called_scoped_to_user(self):
        listings = [_make_listing(url_hash="h1")]
        mock_db = _mock_db_full(listings)
        with patch("matching.engine.get_client", return_value=mock_db):
            run_matching(self._profile(), write_results=True)
        delete_chain = mock_db._tables["matches"].delete.return_value
        delete_chain.eq.assert_called_with("user_id", "u1")

    def test_stale_delete_excludes_passing_hashes(self):
        listings = [_make_listing(url_hash="h1")]
        mock_db = _mock_db_full(listings)
        with patch("matching.engine.get_client", return_value=mock_db):
            run_matching(self._profile(), write_results=True)
        delete_chain = mock_db._tables["matches"].delete.return_value
        not_in_call = delete_chain.eq.return_value.not_.in_.call_args
        assert not_in_call[0] == ("listing_hash", ["h1"])

    def test_is_new_true_when_first_seen_recent(self):
        listings = [_make_listing(url_hash="h1")]
        recent_iso = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        seen_rows = [{"url_hash": "h1", "first_seen": recent_iso}]
        mock_db = _mock_db_full(listings, seen_rows)
        with patch("matching.engine.get_client", return_value=mock_db):
            results = run_matching(self._profile(), write_results=True)
        assert results[0]["is_new"] is True

    def test_is_new_false_when_first_seen_old(self):
        listings = [_make_listing(url_hash="h1")]
        old_iso = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        seen_rows = [{"url_hash": "h1", "first_seen": old_iso}]
        mock_db = _mock_db_full(listings, seen_rows)
        with patch("matching.engine.get_client", return_value=mock_db):
            results = run_matching(self._profile(), write_results=True)
        assert results[0]["is_new"] is False

    def test_is_new_false_when_not_in_seen_urls(self):
        listings = [_make_listing(url_hash="h1")]
        mock_db = _mock_db_full(listings, seen_rows=[])
        with patch("matching.engine.get_client", return_value=mock_db):
            results = run_matching(self._profile(), write_results=True)
        assert results[0]["is_new"] is False

    def test_no_upsert_when_no_passing_listings(self):
        # All listings fail hard filters
        listings = [_make_listing(title="Técnico en Enfermería")]
        mock_db = _mock_db_full(listings)
        with patch("matching.engine.get_client", return_value=mock_db):
            run_matching(self._profile(), write_results=True)
        mock_db._tables["matches"].upsert.assert_not_called()
