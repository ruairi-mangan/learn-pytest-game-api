"""A small Flask API that serves a mock video game catalogue.

Use ``create_app()`` to build the app. Each call gets its own fresh copy of the
seed data, so tests can create an app per test and never affect each other.

Endpoints
---------
GET    /health           Liveness check, no auth needed.
GET    /games            List games. Optional filters: ?platform=, ?genre=, ?in_stock=
GET    /games/<id>       Get a single game.
POST   /games            Add games from a JSON array of game objects.
DELETE /games            Delete games by title from a JSON array of {"title": ...}.

Every /games endpoint needs an ``Authorization: Bearer <token>`` header.
"""

from __future__ import annotations

import asyncio
import copy
import os
import random
from datetime import UTC, datetime
from functools import wraps

from flask import Blueprint, Flask, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from api.games_data import ESRB_RATINGS, LIVE_PLAYER_RANGES, SEED_GAMES

API_VERSION = "2.0"
DEFAULT_TOKEN = "mysecrettoken"
EARLIEST_RELEASE_YEAR = 1958  # "Tennis for Two"

REQUIRED_FIELDS = {
    "title": str,
    "developer": str,
    "publisher": str,
    "release_year": int,
    "genre": str,
    "platforms": list,
    "price_usd": (int, float),
}
OPTIONAL_FIELDS = {
    "esrb_rating": "RP",  # Rating Pending
    "units_sold_millions": 0.0,
    "in_stock": True,
}


class ApiError(Exception):
    def __init__(self, status: int, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.details = details or []


class GameStore:
    """In-memory store for one app instance."""

    def __init__(self, seed: list[dict]):
        self._games = copy.deepcopy(seed)
        self._next_id = max((g["id"] for g in self._games), default=0) + 1

    def all(self) -> list[dict]:
        return list(self._games)

    def get(self, game_id: int) -> dict | None:
        return next((g for g in self._games if g["id"] == game_id), None)

    def find_by_title(self, title: str) -> dict | None:
        wanted = title.casefold()
        return next((g for g in self._games if g["title"].casefold() == wanted), None)

    def add(self, game: dict) -> dict:
        stored = {"id": self._next_id, **game}
        self._next_id += 1
        self._games.append(stored)
        return stored

    def delete_by_title(self, title: str) -> bool:
        game = self.find_by_title(title)
        if game is None:
            return False
        self._games.remove(game)
        return True


def validate_game(payload: object) -> tuple[dict, list[str]]:
    """Return the cleaned game and a list of validation errors."""
    if not isinstance(payload, dict):
        return {}, ["each game must be a JSON object"]

    errors = []
    for field, expected in REQUIRED_FIELDS.items():
        value = payload.get(field)
        # bool is a subclass of int in Python, so reject it explicitly.
        if value is None:
            errors.append(f"'{field}' is required")
        elif isinstance(value, bool) or not isinstance(value, expected):
            errors.append(f"'{field}' has the wrong type")

    if errors:
        return {}, errors

    max_year = datetime.now(UTC).year + 2
    if not payload["title"].strip():
        errors.append("'title' must not be blank")
    if not EARLIEST_RELEASE_YEAR <= payload["release_year"] <= max_year:
        errors.append(f"'release_year' must be between {EARLIEST_RELEASE_YEAR} and {max_year}")
    if payload["price_usd"] < 0:
        errors.append("'price_usd' must not be negative")
    platforms = payload["platforms"]
    if not platforms or not all(isinstance(p, str) and p.strip() for p in platforms):
        errors.append("'platforms' must be a non-empty list of names")
    rating = payload.get("esrb_rating", OPTIONAL_FIELDS["esrb_rating"])
    if rating not in ESRB_RATINGS:
        errors.append(f"'esrb_rating' must be one of {', '.join(ESRB_RATINGS)}")

    game = {field: payload[field] for field in REQUIRED_FIELDS}
    game["title"] = game["title"].strip()
    for field, default in OPTIONAL_FIELDS.items():
        game[field] = payload.get(field, default)
    return game, errors


def require_json_array() -> list:
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError(400, "Request body must be valid JSON")
    if not isinstance(data, list):
        raise ApiError(400, "Expected a JSON array")
    return data


def require_token(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        expected = f"Bearer {current_app.config['API_TOKEN']}"
        if request.headers.get("Authorization") != expected:
            raise ApiError(401, "Unauthorized")
        return view(*args, **kwargs)

    return wrapper


def store() -> GameStore:
    return current_app.extensions["game_store"]


def parse_bool(value: str, name: str) -> bool:
    lowered = value.lower()
    if lowered in ("true", "1", "yes"):
        return True
    if lowered in ("false", "0", "no"):
        return False
    raise ApiError(400, f"'{name}' must be true or false")


bp = Blueprint("games", __name__)


@bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@bp.get("/games")
@require_token
def list_games():
    games = store().all()

    platform = request.args.get("platform")
    if platform:
        wanted = platform.casefold()
        games = [g for g in games if wanted in (p.casefold() for p in g["platforms"])]

    genre = request.args.get("genre")
    if genre:
        games = [g for g in games if g["genre"].casefold() == genre.casefold()]

    in_stock = request.args.get("in_stock")
    if in_stock is not None:
        wanted_stock = parse_bool(in_stock, "in_stock")
        games = [g for g in games if g["in_stock"] is wanted_stock]

    return jsonify(games)


@bp.get("/games/<int:game_id>")
@require_token
def get_game(game_id: int):
    game = store().get(game_id)
    if game is None:
        raise ApiError(404, f"Game {game_id} not found")
    return jsonify(game)


@bp.post("/games")
@require_token
def add_games():
    payload = require_json_array()
    if not payload:
        raise ApiError(400, "Expected at least one game")

    # Check every game before saving any, so a bad request changes nothing.
    cleaned, errors = [], []
    seen_titles = set()
    for index, item in enumerate(payload):
        game, game_errors = validate_game(item)
        errors.extend(f"[{index}] {e}" for e in game_errors)
        if game_errors:
            continue
        key = game["title"].casefold()
        if key in seen_titles or store().find_by_title(game["title"]):
            raise ApiError(409, f"A game titled '{game['title']}' already exists")
        seen_titles.add(key)
        cleaned.append(game)

    if errors:
        raise ApiError(400, "Validation failed", errors)

    added = [store().add(game) for game in cleaned]
    return jsonify({"added": added}), 201


@bp.delete("/games")
@require_token
def delete_games():
    payload = require_json_array()
    titles = [item["title"] for item in payload if isinstance(item, dict) and "title" in item]
    if len(titles) != len(payload):
        raise ApiError(400, "Each item must be an object with a 'title'")

    deleted, not_found = [], []
    for title in titles:
        (deleted if store().delete_by_title(title) else not_found).append(title)
    return jsonify({"deleted": deleted, "not_found": not_found})


def create_app(token: str | None = None) -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False
    app.config["API_TOKEN"] = token or os.environ.get("API_TOKEN", DEFAULT_TOKEN)
    app.extensions["game_store"] = GameStore(SEED_GAMES)
    app.register_blueprint(bp)

    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        body = {"error": err.message}
        if err.details:
            body["details"] = err.details
        return jsonify(body), err.status

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        return jsonify({"error": err.description}), err.code

    @app.after_request
    def add_version_header(response):
        response.headers["X-API-Version"] = API_VERSION
        return response

    return app


async def get_live_player_counts_async(
    rng: random.Random | None = None, delay: float = 0.2
) -> list[dict]:
    """Simulate a slow call to a live-stats service.

    Counts are random within realistic ranges. Pass a seeded ``random.Random``
    to get the same results every time.
    """
    rng = rng or random.Random()
    await asyncio.sleep(delay)  # simulate network latency
    sampled_at = datetime.now(UTC).isoformat()
    return [
        {
            "title": title,
            "platform": "Steam",
            "current_players": rng.randint(low, high),
            "sampled_at": sampled_at,
        }
        for title, (low, high) in LIVE_PLAYER_RANGES.items()
    ]


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000)
