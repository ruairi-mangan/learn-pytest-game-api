"""Fixtures for tests that call the running ``mockapi`` container over HTTP.

These tests are skipped unless API_BASE_URL is set. docker-compose sets it
for the ``test`` service.
"""

import os
import uuid

import pytest
import requests


@pytest.fixture(scope="session")
def base_url():
    url = os.environ.get("API_BASE_URL")
    if not url:
        pytest.skip("API_BASE_URL not set; start the stack with docker compose")
    return url.rstrip("/")


@pytest.fixture(scope="session")
def api(base_url):
    """One requests.Session for the whole run, with the auth header already set."""
    token = os.environ.get("API_TOKEN", "mysecrettoken")
    with requests.Session() as session:
        session.headers["Authorization"] = f"Bearer {token}"
        yield session


@pytest.fixture
def created_game(api, base_url, make_game):
    """Add a game before the test and delete it afterwards (yield fixture).

    The live server keeps its data between test runs. The unique title and
    the cleanup below let the suite run again and again without conflicts.
    """
    payload = make_game(title=f"Integration Test Game {uuid.uuid4().hex[:8]}")
    response = api.post(f"{base_url}/games", json=[payload], timeout=5)
    response.raise_for_status()
    game = response.json()["added"][0]

    yield game

    api.delete(f"{base_url}/games", json=[{"title": game["title"]}], timeout=5)
