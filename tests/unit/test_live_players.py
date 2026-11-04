"""Async tests for get_live_player_counts_async (needs pytest-asyncio)."""

import asyncio
import random
import time

import pytest

from api.games_data import LIVE_PLAYER_RANGES
from api.mockapi import get_live_player_counts_async

# Apply the asyncio marker to every test in this module.
pytestmark = pytest.mark.asyncio


async def test_returns_one_entry_per_tracked_game():
    stats = await get_live_player_counts_async(delay=0)

    assert [s["title"] for s in stats] == list(LIVE_PLAYER_RANGES)
    assert all(s["platform"] == "Steam" for s in stats)


@pytest.mark.parametrize("attempt", range(20))
async def test_player_counts_stay_within_range(attempt):
    # The values are random, so check the range they must fall in, not exact numbers.
    for stat in await get_live_player_counts_async(delay=0):
        low, high = LIVE_PLAYER_RANGES[stat["title"]]
        assert low <= stat["current_players"] <= high


async def test_seeded_rng_gives_repeatable_results():
    first = await get_live_player_counts_async(rng=random.Random(42), delay=0)
    second = await get_live_player_counts_async(rng=random.Random(42), delay=0)

    assert [s["current_players"] for s in first] == [s["current_players"] for s in second]


async def test_sampled_at_is_a_utc_timestamp():
    stats = await get_live_player_counts_async(delay=0)

    assert all(s["sampled_at"].endswith("+00:00") for s in stats)


async def test_calls_run_concurrently():
    start = time.monotonic()
    results = await asyncio.gather(*(get_live_player_counts_async(delay=0.2) for _ in range(5)))
    elapsed = time.monotonic() - start

    assert len(results) == 5
    # Five 0.2s calls in a row would take 1s or more. Run together, they take about 0.2s.
    assert elapsed < 0.6
