from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def _mock_db(data):
    mock_result = MagicMock()
    mock_result.data = data
    mock_rpc = MagicMock()
    mock_rpc.execute.return_value = mock_result
    mock_db = MagicMock()
    mock_db.rpc.return_value = mock_rpc
    return mock_db


def test_get_specialties_returns_list():
    mock_db = _mock_db([{"specialty": "Emergencia"}, {"specialty": "Pediatría"}])
    with patch("routes.specialties.get_client", return_value=mock_db):
        response = client.get("/specialties")

    assert response.status_code == 200
    assert response.json() == ["Emergencia", "Pediatría"]


def test_get_specialties_cache_control_header():
    mock_db = _mock_db([{"specialty": "Emergencia"}])
    with patch("routes.specialties.get_client", return_value=mock_db):
        response = client.get("/specialties")

    assert "public" in response.headers["cache-control"]
    assert "max-age=300" in response.headers["cache-control"]


def test_get_specialties_empty_data():
    mock_db = _mock_db([])
    with patch("routes.specialties.get_client", return_value=mock_db):
        response = client.get("/specialties")

    assert response.status_code == 200
    assert response.json() == []


def test_get_specialties_scalar_data():
    """Handles RPC returning plain strings rather than dicts."""
    mock_db = _mock_db(["Emergencia", "Pediatría"])
    with patch("routes.specialties.get_client", return_value=mock_db):
        response = client.get("/specialties")

    assert response.status_code == 200
    assert response.json() == ["Emergencia", "Pediatría"]
