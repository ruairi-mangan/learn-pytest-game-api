"""Mocking with pytest-mock, using GamesClient as the code under test.

GamesClient sends real HTTP requests. Here they are replaced with mocks, so
the tests run without a server and can produce situations that are hard to
create for real: timeouts, 503s, and failures followed by success.

The ``mocker`` fixture comes from pytest-mock. It wraps ``unittest.mock``
and undoes every patch when the test ends, so you never need to clean up.

Rule of thumb: patch a name where it is *looked up*, not where it is defined.
api/client.py runs ``from api.mockapi import get_live_player_counts_async``,
so tests patch ``api.client.get_live_player_counts_async``.
"""

import logging

import pytest
import requests

from api.client import (
    AuthenticationError,
    DuplicateGameError,
    GameNotFoundError,
    GamesApiError,
    GamesClient,
    GameValidationError,
    ServiceUnavailableError,
    most_played_now,
)

BASE_URL = "http://games.test"


# --- Fixtures ---------------------------------------------------------------


@pytest.fixture
def session(mocker):
    """A fake requests.Session.

    ``spec=requests.Session`` makes the mock reject attributes the real class
    doesn't have, so a typo like ``session.reqest`` fails instead of passing.
    ``headers`` is created in Session.__init__, not on the class, so the spec
    doesn't include it. We add it by hand.
    """
    fake = mocker.Mock(spec=requests.Session)
    fake.headers = {}
    return fake


@pytest.fixture
def make_response(mocker):
    """Factory fixture that builds fake requests.Response objects."""

    def _make_response(status=200, body=None):
        response = mocker.Mock(spec=requests.Response)
        response.status_code = status
        response.json.return_value = body
        response.content = b"" if body is None else b"{...}"
        return response

    return _make_response


@pytest.fixture
def client(session):
    return GamesClient(BASE_URL, "secret", session=session, backoff_seconds=0.5)


@pytest.fixture
def sleep(mocker):
    """Patch out time.sleep so retry tests run instantly, and record the delays."""
    return mocker.patch("api.client.time.sleep")


# --- Basic stubbing and asserting calls -------------------------------------


def test_list_games_sends_filters_and_auth(client, session, make_response):
    session.request.return_value = make_response(body=[{"title": "Elden Ring"}])

    games = client.list_games(platform="PC")

    assert games == [{"title": "Elden Ring"}]
    # Check how the mock was called, not only what came back.
    session.request.assert_called_once_with(
        "GET", f"{BASE_URL}/games", timeout=5, params={"platform": "PC"}
    )
    assert session.headers["Authorization"] == "Bearer secret"


def test_add_games_posts_json(client, session, make_response, make_game):
    game = make_game()
    session.request.return_value = make_response(201, {"added": [{"id": 15, **game}]})

    added = client.add_games([game])

    assert added[0]["id"] == 15
    method, url = session.request.call_args.args
    assert (method, url) == ("POST", f"{BASE_URL}/games")
    assert session.request.call_args.kwargs["json"] == [game]


def test_delete_games_wraps_titles(client, session, make_response):
    session.request.return_value = make_response(body={"deleted": ["Dota 2"], "not_found": []})

    client.delete_games(["Dota 2"])

    assert session.request.call_args.kwargs["json"] == [{"title": "Dota 2"}]


# --- side_effect: a sequence of results, including exceptions ---------------


def test_retries_until_the_request_succeeds(client, session, make_response, sleep):
    # Each call to the mock returns (or raises) the next item in the list.
    session.request.side_effect = [
        requests.ConnectionError("connection refused"),
        make_response(503),
        make_response(body=[]),
    ]

    assert client.list_games() == []
    assert session.request.call_count == 3
    # The delay doubles after each failure (exponential backoff).
    assert sleep.call_args_list == [((0.5,),), ((1.0,),)]


def test_gives_up_after_max_retries(client, session, sleep):
    # A single exception (not a list) is raised on every call.
    session.request.side_effect = requests.Timeout("read timed out")

    with pytest.raises(ServiceUnavailableError, match="GET /games failed") as exc_info:
        client.list_games()

    # ``raise ... from exc`` keeps the original error as __cause__.
    assert isinstance(exc_info.value.__cause__, requests.Timeout)
    assert session.request.call_count == 3
    assert sleep.call_count == 2


def test_persistent_503_raises_service_unavailable(client, session, make_response, sleep):
    session.request.return_value = make_response(503)

    with pytest.raises(ServiceUnavailableError, match="returned 503"):
        client.list_games()


def test_client_errors_are_not_retried(client, session, make_response, sleep):
    session.request.return_value = make_response(400, {"error": "Validation failed"})

    with pytest.raises(GameValidationError):
        client.add_games([{}])

    session.request.assert_called_once()
    sleep.assert_not_called()


def test_retries_are_logged(client, session, make_response, sleep, caplog):
    caplog.set_level(logging.WARNING, logger="api.client")
    session.request.side_effect = [make_response(502), make_response(502), make_response(body=[])]

    client.list_games()

    assert [r.levelname for r in caplog.records] == ["WARNING", "WARNING"]
    assert "GET /games failed (HTTP 502), retry 1/2 in 0.5s" in caplog.text
    assert "retry 2/2 in 1.0s" in caplog.text


# --- pytest.raises: turning HTTP errors into exceptions ---------------------


@pytest.mark.parametrize(
    "status, body, expected_exception",
    [
        (401, {"error": "Unauthorized"}, AuthenticationError),
        (400, {"error": "Validation failed", "details": []}, GameValidationError),
        (409, {"error": "already exists"}, DuplicateGameError),
        (500, None, GamesApiError),
    ],
)
def test_error_statuses_raise_matching_exception(
    client, session, make_response, status, body, expected_exception
):
    session.request.return_value = make_response(status, body)

    with pytest.raises(expected_exception):
        client.add_games([{"title": "Anything"}])


def test_unknown_game_raises_not_found(client, session, make_response):
    session.request.return_value = make_response(404, {"error": "Game 99 not found"})

    # ``match`` is a regular expression searched in str(exception).
    with pytest.raises(GameNotFoundError, match=r"^Game 99 not found$") as exc_info:
        client.get_game(99)

    # exc_info.value is the exception object, so you can check its attributes.
    assert exc_info.value.game_id == 99


def test_validation_error_includes_details(client, session, make_response):
    details = ["[0] 'title' is required", "[0] 'price_usd' must not be negative"]
    session.request.return_value = make_response(
        400, {"error": "Validation failed", "details": details}
    )

    with pytest.raises(GameValidationError) as exc_info:
        client.add_games([{}])

    assert exc_info.value.details == details


def test_every_client_error_is_a_games_api_error(client, session, make_response):
    """pytest.raises also matches subclasses, so callers can catch the base class."""
    session.request.return_value = make_response(401, {"error": "Unauthorized"})

    with pytest.raises(GamesApiError):
        client.list_games()


def test_retries_must_be_positive():
    with pytest.raises(ValueError, match="at least 1"):
        GamesClient(BASE_URL, "secret", retries=0)


# --- Patching your own code, and spies --------------------------------------


def test_best_seller_with_list_games_patched(mocker, client):
    # Patch the method, not the HTTP layer, to test best_seller's own logic.
    mocker.patch.object(
        GamesClient,
        "list_games",
        return_value=[
            {"title": "Tetris", "units_sold_millions": 35.0},
            {"title": "Minecraft", "units_sold_millions": 300.0},
        ],
    )

    assert client.best_seller()["title"] == "Minecraft"


def test_best_seller_of_empty_catalogue_raises(mocker, client):
    mocker.patch.object(GamesClient, "list_games", return_value=[])

    with pytest.raises(GamesApiError, match="empty"):
        client.best_seller()


def test_spy_records_calls_but_keeps_real_behaviour(mocker, client, session, make_response):
    # A spy runs the real method and also records how it was called.
    session.request.return_value = make_response(body=[{"title": "A", "units_sold_millions": 1}])
    spy = mocker.spy(client, "list_games")

    client.best_seller()

    spy.assert_called_once_with()
    assert spy.spy_return == [{"title": "A", "units_sold_millions": 1}]


# --- Async mocks ------------------------------------------------------------


@pytest.mark.asyncio
async def test_most_played_now_with_async_mock(mocker):
    # The target is an async function, so mocker.patch creates an AsyncMock
    # automatically. Awaiting it returns ``return_value``.
    fake_fetch = mocker.patch(
        "api.client.get_live_player_counts_async",
        return_value=[
            {"title": "Dota 2", "current_players": 600_000},
            {"title": "Counter-Strike 2", "current_players": 1_400_000},
        ],
    )

    top = await most_played_now()

    assert top["title"] == "Counter-Strike 2"
    fake_fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_most_played_now_with_no_stats_raises(mocker):
    mocker.patch("api.client.get_live_player_counts_async", return_value=[])

    with pytest.raises(GamesApiError, match="No live stats"):
        await most_played_now()
