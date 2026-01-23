import pytest


@pytest.fixture(scope="module")
def mock_games():
    from api.mockapi import get_games
    return get_games


@pytest.fixture
def mock_get_games_async():
    from api.mockapi import get_games_async
    return get_games_async
