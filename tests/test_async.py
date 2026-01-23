import pytest


@pytest.mark.asyncio
async def test_async_game_service_returns_data(mock_get_games_async):
    games = await mock_get_games_async()

    assert len(games) > 0
    assert all("name" in g for g in games)
