import json
import pytest
from pathlib import Path
from requests import Response

from app.libs import http_strategy_selector

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "app" / "libs" / "data" / "beacon-data.json"

@pytest.fixture
def expected_fixture_data():
    with open(FIXTURE_PATH, "r") as f:
        return json.load(f)


def test_mock_http_get_returns_expected_data(expected_fixture_data):
    url = "https://example.com/test"
    headers = {"Authorization": "Bearer token"}

    response: Response = http_strategy_selector.mock_http_get(url, headers)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.url == url

    parsed = response.json()
    assert parsed == expected_fixture_data
    assert parsed["total"] == 3
    assert isinstance(parsed["results"], list)
    assert parsed["results"][2]["entity"]["attachments"][0]["id"] == "a937b75b-9764-4a39-afc6-432084faf622"


def test_real_http_get_makes_request(monkeypatch):
    """Mock requests.get so we don't actually hit the network"""
    called = {}

    def fake_get(url, headers, timeout):
        called["url"] = url
        called["headers"] = headers
        called["timeout"] = timeout
        fake_response = Response()
        fake_response.status_code = 204
        return fake_response

    monkeypatch.setattr("requests.get", fake_get)

    url = "https://example.com/api"
    headers = {"User-Agent": "test-client"}

    response = http_strategy_selector.real_http_get(url, headers)

    assert called["url"] == url
    assert called["headers"] == headers
    assert called["timeout"] == 10
    assert isinstance(response, Response)
    assert response.status_code == 204



