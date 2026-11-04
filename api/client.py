"""A small HTTP client for the mock game API.

It turns HTTP error responses into Python exceptions, retries temporary
failures, and logs each retry. All three are typical client behaviour, and
each needs a different testing technique:

- exceptions -> ``pytest.raises``
- HTTP calls and ``time.sleep`` -> mocking (``pytest-mock``)
- log messages -> ``caplog``
"""

from __future__ import annotations

import logging
import time

import requests

from api.mockapi import get_live_player_counts_async

log = logging.getLogger(__name__)


class GamesApiError(Exception):
    """Base class for every error this client raises."""


class AuthenticationError(GamesApiError):
    pass


class GameNotFoundError(GamesApiError):
    def __init__(self, game_id: int):
        super().__init__(f"Game {game_id} not found")
        self.game_id = game_id


class GameValidationError(GamesApiError):
    def __init__(self, message: str, details: list[str]):
        super().__init__(message)
        self.details = details


class DuplicateGameError(GamesApiError):
    pass


class ServiceUnavailableError(GamesApiError):
    pass


class GamesClient:
    RETRYABLE_STATUSES = {502, 503, 504}

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        session: requests.Session | None = None,
        retries: int = 3,
        backoff_seconds: float = 0.5,
        timeout: float = 5,
    ):
        if retries < 1:
            raise ValueError("retries must be at least 1")
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers["Authorization"] = f"Bearer {token}"
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self.timeout = timeout

    # --- Public API ---------------------------------------------------------

    def list_games(self, **filters) -> list[dict]:
        return self._request("GET", "/games", params=filters or None).json()

    def get_game(self, game_id: int) -> dict:
        response = self._request("GET", f"/games/{game_id}", allow_404=True)
        if response.status_code == 404:
            raise GameNotFoundError(game_id)
        return response.json()

    def add_games(self, games: list[dict]) -> list[dict]:
        return self._request("POST", "/games", json=games).json()["added"]

    def delete_games(self, titles: list[str]) -> dict:
        return self._request("DELETE", "/games", json=[{"title": t} for t in titles]).json()

    def best_seller(self) -> dict:
        games = self.list_games()
        if not games:
            raise GamesApiError("The catalogue is empty")
        return max(games, key=lambda g: g["units_sold_millions"])

    # --- Internals ----------------------------------------------------------

    def _request(self, method: str, path: str, allow_404: bool = False, **kwargs):
        url = f"{self.base_url}{path}"
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt == self.retries:
                    raise ServiceUnavailableError(f"{method} {path} failed: {exc}") from exc
                reason = type(exc).__name__
            else:
                if response.status_code not in self.RETRYABLE_STATUSES:
                    self._raise_for_status(response, allow_404)
                    return response
                if attempt == self.retries:
                    raise ServiceUnavailableError(
                        f"{method} {path} returned {response.status_code}"
                    )
                reason = f"HTTP {response.status_code}"

            delay = self.backoff_seconds * 2 ** (attempt - 1)
            log.warning(
                "%s %s failed (%s), retry %d/%d in %.1fs",
                method,
                path,
                reason,
                attempt,
                self.retries - 1,
                delay,
            )
            time.sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _raise_for_status(response: requests.Response, allow_404: bool) -> None:
        status = response.status_code
        if status < 400 or (status == 404 and allow_404):
            return
        body = response.json() if response.content else {}
        message = body.get("error", f"HTTP {status}")
        if status == 401:
            raise AuthenticationError(message)
        if status == 400:
            raise GameValidationError(message, body.get("details", []))
        if status == 409:
            raise DuplicateGameError(message)
        raise GamesApiError(f"Unexpected HTTP {status}: {message}")


async def most_played_now() -> dict:
    """Return the live game with the most players right now."""
    stats = await get_live_player_counts_async()
    if not stats:
        raise GamesApiError("No live stats available")
    return max(stats, key=lambda s: s["current_players"])
