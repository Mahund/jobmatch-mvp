"""
Unit tests for scraper/extract.py and scraper/extract_run.py logic.
No Anthropic API calls — tests HTML parsing, pre-filtering, and DB routing.
"""
from unittest.mock import MagicMock, patch

import pytest
from bs4 import BeautifulSoup

from scraper.extract import build_batch_request, html_to_text, _soup_to_text
from scraper.extract_run import (
    _extract_title_from_soup,
    _is_enfermeria_role as extract_is_enfermeria,
    get_unextracted_files,
    write_listing,
)


# ---------------------------------------------------------------------------
# _is_enfermeria_role (extract_run copy — must match engine.py behaviour)
# ---------------------------------------------------------------------------

class TestExtractIsEnfermeriaRole:
    """Verify the duplicated copy in extract_run.py behaves identically to engine.py."""

    def test_accepts_enfermera(self):
        assert extract_is_enfermeria("Enfermera") is True

    def test_accepts_with_accent(self):
        assert extract_is_enfermeria("Enfermería Clínica") is True

    def test_rejects_tens(self):
        assert extract_is_enfermeria("TENS Enfermería") is False

    def test_rejects_tecnico(self):
        assert extract_is_enfermeria("Técnico en Enfermería") is False

    def test_rejects_auxiliar(self):
        assert extract_is_enfermeria("Auxiliar de Enfermería") is False

    def test_rejects_paramedic(self):
        assert extract_is_enfermeria("Paramédico con manejo de enfermería") is False

    def test_rejects_estudiante(self):
        assert extract_is_enfermeria("Estudiante de Enfermería") is False

    def test_rejects_none(self):
        assert extract_is_enfermeria(None) is False

    def test_rejects_empty(self):
        assert extract_is_enfermeria("") is False

    def test_rejects_no_enfermer(self):
        assert extract_is_enfermeria("Médico Cirujano") is False


# ---------------------------------------------------------------------------
# _extract_title_from_soup
# ---------------------------------------------------------------------------

class TestExtractTitleFromSoup:
    def test_extracts_h1_text(self):
        soup = BeautifulSoup("<html><body><h1>Enfermera UCI</h1></body></html>", "lxml")
        assert _extract_title_from_soup(soup) == "Enfermera UCI"

    def test_strips_whitespace(self):
        soup = BeautifulSoup("<h1>  Enfermera  </h1>", "lxml")
        assert _extract_title_from_soup(soup) == "Enfermera"

    def test_returns_none_when_no_h1(self):
        soup = BeautifulSoup("<html><body><h2>Not a title</h2></body></html>", "lxml")
        assert _extract_title_from_soup(soup) is None

    def test_returns_none_on_empty_html(self):
        soup = BeautifulSoup("", "lxml")
        assert _extract_title_from_soup(soup) is None


# ---------------------------------------------------------------------------
# _soup_to_text / html_to_text
# ---------------------------------------------------------------------------

class TestHtmlToText:
    def test_strips_script_tags(self):
        html = "<html><body><script>alert('x')</script><p>Job description</p></body></html>"
        text = html_to_text(html)
        assert "alert" not in text
        assert "Job description" in text

    def test_strips_style_tags(self):
        html = "<html><body><style>body{color:red}</style><p>Content</p></body></html>"
        text = html_to_text(html)
        assert "color" not in text
        assert "Content" in text

    def test_strips_nav_tags(self):
        html = "<html><body><nav>Menu items</nav><main>Main content</main></body></html>"
        text = html_to_text(html)
        assert "Menu items" not in text
        assert "Main content" in text

    def test_truncates_at_3000_chars(self):
        long_content = "x" * 5000
        html = f"<html><body><p>{long_content}</p></body></html>"
        text = html_to_text(html)
        assert len(text) <= 3000

    def test_short_content_not_truncated(self):
        html = "<html><body><p>Short content</p></body></html>"
        text = html_to_text(html)
        assert "Short content" in text

    def test_empty_html_returns_empty_or_short(self):
        text = html_to_text("")
        assert len(text) <= 3000


# ---------------------------------------------------------------------------
# build_batch_request
# ---------------------------------------------------------------------------

class TestBuildBatchRequest:
    def test_has_correct_custom_id(self):
        req = build_batch_request("abc123", "<html><h1>Enfermera</h1></html>")
        assert req["custom_id"] == "abc123"

    def test_has_params(self):
        req = build_batch_request("abc123", "<html><h1>Enfermera</h1></html>")
        assert "params" in req

    def test_uses_correct_model(self):
        req = build_batch_request("abc123", "<html><h1>Enfermera</h1></html>")
        assert req["params"]["model"] == "claude-haiku-4-5-20251001"

    def test_tool_choice_is_save_listing(self):
        req = build_batch_request("abc123", "<html><h1>Enfermera</h1></html>")
        assert req["params"]["tool_choice"]["name"] == "save_listing"

    def test_has_user_message(self):
        req = build_batch_request("abc123", "<html><body><p>Job listing text</p></body></html>")
        messages = req["params"]["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "Job listing text" in messages[0]["content"]


# ---------------------------------------------------------------------------
# write_listing — confidence threshold routing
# ---------------------------------------------------------------------------

class TestWriteListingConfidence:
    def _mock_db(self):
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.return_value = MagicMock()
        return mock_db

    def _get_written_row(self, mock_db):
        call_args = mock_db.table.return_value.upsert.call_args
        return call_args[0][0]  # first positional arg to upsert()

    def test_high_confidence_sets_ok(self):
        mock_db = self._mock_db()
        with patch("scraper.extract_run.get_client", return_value=mock_db):
            write_listing("hash1", "http://example.com", {"confidence": 0.9, "title": "Enfermera"})
        row = self._get_written_row(mock_db)
        assert row["extraction_status"] == "ok"

    def test_confidence_exactly_0_6_sets_ok(self):
        mock_db = self._mock_db()
        with patch("scraper.extract_run.get_client", return_value=mock_db):
            write_listing("hash1", "http://example.com", {"confidence": 0.6, "title": "Enfermera"})
        row = self._get_written_row(mock_db)
        assert row["extraction_status"] == "ok"

    def test_low_confidence_sets_low_confidence(self):
        mock_db = self._mock_db()
        with patch("scraper.extract_run.get_client", return_value=mock_db):
            write_listing("hash1", "http://example.com", {"confidence": 0.5, "title": "Enfermera"})
        row = self._get_written_row(mock_db)
        assert row["extraction_status"] == "low_confidence"

    def test_zero_confidence_sets_low_confidence(self):
        mock_db = self._mock_db()
        with patch("scraper.extract_run.get_client", return_value=mock_db):
            write_listing("hash1", "http://example.com", {"confidence": 0.0, "title": "Enfermera"})
        row = self._get_written_row(mock_db)
        assert row["extraction_status"] == "low_confidence"

    def test_missing_confidence_sets_low_confidence(self):
        mock_db = self._mock_db()
        with patch("scraper.extract_run.get_client", return_value=mock_db):
            write_listing("hash1", "http://example.com", {"title": "Enfermera"})
        row = self._get_written_row(mock_db)
        assert row["extraction_status"] == "low_confidence"

    def test_url_hash_written(self):
        mock_db = self._mock_db()
        with patch("scraper.extract_run.get_client", return_value=mock_db):
            write_listing("myhash", "http://example.com/job", {"confidence": 0.8})
        row = self._get_written_row(mock_db)
        assert row["url_hash"] == "myhash"
        assert row["url"] == "http://example.com/job"


# ---------------------------------------------------------------------------
# get_unextracted_files — chunked DB query
# ---------------------------------------------------------------------------

class TestGetUnextractedFiles:
    def _make_storage_item(self, name: str, is_folder: bool = False):
        """Simulate a Supabase Storage list() item."""
        return {"name": name, "id": None if is_folder else "some-id"}

    def _make_mock_db(self, storage_files: list[str], already_done: list[str]):
        """
        Build a mock db where:
        - storage returns one folder 'jobs' containing `storage_files`
        - the listings table reports `already_done` hashes as already extracted
        """
        mock_db = MagicMock()

        # Storage: top-level list returns one folder
        folder_items = [{"name": f, "id": "file-id"} for f in storage_files]
        mock_db.storage.from_.return_value.list.side_effect = [
            [{"name": "jobs", "id": None}],  # root listing → one folder
            folder_items,                    # folder listing → html files
        ]

        # DB: .in_() query returns already-done rows
        mock_result = MagicMock()
        mock_result.data = [{"url_hash": h} for h in already_done]
        mock_db.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_result

        return mock_db

    def test_returns_only_unextracted(self):
        files = ["abc.html", "def.html", "ghi.html"]
        done = ["abc", "ghi"]
        mock_db = self._make_mock_db(files, done)

        with patch("scraper.extract_run.get_client", return_value=mock_db):
            result = get_unextracted_files()

        hashes = [f["hash"] for f in result]
        assert hashes == ["def"]

    def test_returns_empty_when_all_extracted(self):
        files = ["abc.html", "def.html"]
        done = ["abc", "def"]
        mock_db = self._make_mock_db(files, done)

        with patch("scraper.extract_run.get_client", return_value=mock_db):
            result = get_unextracted_files()

        assert result == []

    def test_large_file_list_chunks_db_queries(self):
        """More than 200 files must trigger multiple .in_() calls (one per chunk)."""
        files = [f"hash{i:04d}.html" for i in range(450)]
        done = []
        mock_db = self._make_mock_db(files, done)

        # Make each chunk call return empty (nothing done yet)
        mock_result = MagicMock()
        mock_result.data = []
        mock_db.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_result

        # Reset side_effect so storage list works with 450 files
        mock_db.storage.from_.return_value.list.side_effect = [
            [{"name": "jobs", "id": None}],
            [{"name": f"hash{i:04d}.html", "id": "x"} for i in range(450)],
        ]

        with patch("scraper.extract_run.get_client", return_value=mock_db):
            result = get_unextracted_files()

        # 450 files → 3 chunks (200 + 200 + 50) → 3 DB calls
        assert mock_db.table.return_value.select.return_value.in_.call_count == 3
        assert len(result) == 450

    def test_ignores_non_html_files(self):
        files = ["abc.html", "readme.txt", "data.json"]
        done = []
        mock_db = self._make_mock_db(files, done)

        with patch("scraper.extract_run.get_client", return_value=mock_db):
            result = get_unextracted_files()

        hashes = [f["hash"] for f in result]
        assert hashes == ["abc"]
