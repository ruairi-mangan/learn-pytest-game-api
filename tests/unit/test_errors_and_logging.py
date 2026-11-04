"""pytest.raises and caplog, used on the API's own code."""

import logging

import pytest

from api.games_data import SEED_GAMES
from api.mockapi import ApiError, GameStore, parse_bool

# --- pytest.raises ----------------------------------------------------------


@pytest.mark.parametrize("value", ["maybe", "", "2", "truthy"])
def test_parse_bool_rejects_unknown_values(value):
    with pytest.raises(ApiError) as exc_info:
        parse_bool(value, "in_stock")

    assert exc_info.value.status == 400
    assert exc_info.value.message == "'in_stock' must be true or false"


@pytest.mark.parametrize(
    "value, expected",
    [("true", True), ("TRUE", True), ("yes", True), ("1", True), ("false", False), ("no", False)],
)
def test_parse_bool_accepts_known_values(value, expected):
    # The counterpart to the test above: valid input must not raise.
    assert parse_bool(value, "in_stock") is expected


def test_raises_fails_if_nothing_is_raised():
    """pytest.raises is itself an assertion. If no exception is raised, the test fails."""
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
        with pytest.raises(ApiError):
            parse_bool("true", "in_stock")


def test_store_raises_key_error_for_missing_field():
    store = GameStore([{"id": 1}])  # a game record with no "title"

    with pytest.raises(KeyError, match="title"):
        store.find_by_title("Minecraft")


def test_store_copies_seed_data():
    store = GameStore(SEED_GAMES)
    store.delete_by_title("Minecraft")

    # Changing one store must not change the shared seed list.
    assert any(g["title"] == "Minecraft" for g in SEED_GAMES)


# --- caplog -----------------------------------------------------------------


def test_rejected_request_logs_a_warning(client, caplog):
    with caplog.at_level(logging.WARNING, logger="api.mockapi"):
        client.get("/games", headers={"Authorization": "Bearer nope"})

    # record_tuples is a list of (logger name, level, message) tuples.
    assert caplog.record_tuples == [
        ("api.mockapi", logging.WARNING, "Rejected GET /games: bad or missing token")
    ]


def test_adding_games_logs_titles(client, auth_headers, make_game, caplog):
    caplog.set_level(logging.INFO, logger="api.mockapi")

    client.post("/games", headers=auth_headers, json=[make_game(title="Hades II")])

    assert "Added 1 game(s): Hades II" in caplog.messages


def test_deleting_games_logs_titles(client, auth_headers, caplog):
    caplog.set_level(logging.INFO, logger="api.mockapi")

    client.delete("/games", headers=auth_headers, json=[{"title": "Elden Ring"}])

    record = caplog.records[-1]
    assert record.levelname == "INFO"
    assert record.getMessage() == "Deleted 1 game(s): Elden Ring"


def test_successful_read_logs_nothing(client, auth_headers, caplog):
    caplog.set_level(logging.DEBUG, logger="api.mockapi")

    client.get("/games", headers=auth_headers)

    assert caplog.records == []
