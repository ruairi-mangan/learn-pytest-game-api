"""End-to-end tests against the mock API running in its own container."""

import logging
import time

import pytest
import requests

pytestmark = pytest.mark.integration

log = logging.getLogger(__name__)
SLA_MS = 500


def test_health(api, base_url):
    assert api.get(f"{base_url}/health", timeout=5).json() == {"status": "ok"}


def test_list_games_over_http(api, base_url):
    response = api.get(f"{base_url}/games", timeout=5)

    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert "X-API-Version" in response.headers
    assert any(g["title"] == "Minecraft" for g in response.json())


# Network timing can vary, so rerun this test up to 3 times before it fails
# (marker from pytest-rerunfailures).
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_response_time_within_sla(api, base_url):
    start = time.monotonic()
    response = api.get(f"{base_url}/games", timeout=5)
    response.json()
    elapsed_ms = (time.monotonic() - start) * 1000

    log.info("GET /games took %.1f ms", elapsed_ms)
    assert elapsed_ms <= SLA_MS, f"took {elapsed_ms:.1f} ms (SLA {SLA_MS} ms)"


def test_created_game_can_be_fetched(api, base_url, created_game):
    response = api.get(f"{base_url}/games/{created_game['id']}", timeout=5)

    assert response.status_code == 200
    assert response.json()["title"] == created_game["title"]


def test_unauthenticated_request_is_rejected(base_url):
    assert requests.get(f"{base_url}/games", timeout=5).status_code == 401
