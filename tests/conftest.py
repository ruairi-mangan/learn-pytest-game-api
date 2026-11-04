"""Fixtures shared by all tests.

pytest finds fixtures in conftest.py files on its own, so tests never need to
import them. Request a fixture by naming it as a test argument.
"""

import pytest

from api.mockapi import create_app

TEST_TOKEN = "test-token"


@pytest.fixture
def app():
    """A new app with fresh seed data for every test, so tests stay independent."""
    return create_app(token=TEST_TOKEN)


@pytest.fixture
def client(app):
    """Flask's test client calls the app in-process. No server or network is needed."""
    return app.test_client()


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def make_game():
    """Factory fixture: returns a function that builds a valid game payload.

    Pass keyword arguments to change only the fields a test cares about:
        make_game(title="Hades II", price_usd=29.99)
    Pass a field with the value ``None`` to leave it out.
    """

    def _make_game(**overrides):
        game = {
            "title": "Hollow Knight: Silksong",
            "developer": "Team Cherry",
            "publisher": "Team Cherry",
            "release_year": 2025,
            "genre": "Metroidvania",
            "platforms": ["PC", "PlayStation", "Xbox", "Switch"],
            "esrb_rating": "E10+",
            "price_usd": 19.99,
            "units_sold_millions": 0.0,
            "in_stock": True,
        }
        game.update(overrides)
        return {k: v for k, v in game.items() if v is not None}

    return _make_game
