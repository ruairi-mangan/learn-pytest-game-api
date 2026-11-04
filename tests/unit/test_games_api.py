"""Tests for the /games endpoints, using Flask's in-process test client."""

import pytest

from api.games_data import ESRB_RATINGS, SEED_GAMES
from api.mockapi import API_VERSION, create_app

EXPECTED_FIELDS = {
    "id": int,
    "title": str,
    "developer": str,
    "publisher": str,
    "release_year": int,
    "genre": str,
    "platforms": list,
    "esrb_rating": str,
    "price_usd": float,
    "units_sold_millions": float,
    "in_stock": bool,
}


# --- Authentication ---------------------------------------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer wrong-token"},
        {"Authorization": "test-token"},
        {"Authorization": "Basic dGVzdDp0ZXN0"},
    ],
    ids=["missing", "wrong-token", "no-bearer-prefix", "basic-auth"],
)
@pytest.mark.parametrize(
    "method, path",
    [("get", "/games"), ("get", "/games/1"), ("post", "/games"), ("delete", "/games")],
)
def test_endpoints_reject_bad_credentials(client, method, path, headers):
    response = getattr(client, method)(path, headers=headers, json=[])

    assert response.status_code == 401
    assert response.get_json() == {"error": "Unauthorized"}


def test_health_check_needs_no_auth(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_token_can_be_set_by_environment_variable(monkeypatch):
    # monkeypatch undoes this change when the test ends.
    monkeypatch.setenv("API_TOKEN", "from-env")
    client = create_app().test_client()

    assert client.get("/games", headers={"Authorization": "Bearer from-env"}).status_code == 200


# --- GET /games -------------------------------------------------------------


def test_list_games_returns_full_catalogue(client, auth_headers):
    response = client.get("/games", headers=auth_headers)

    assert response.status_code == 200
    assert response.headers["X-API-Version"] == API_VERSION
    assert len(response.get_json()) == len(SEED_GAMES)


@pytest.mark.parametrize("game", SEED_GAMES, ids=lambda g: g["title"])
def test_every_game_matches_schema(game):
    assert set(game) == set(EXPECTED_FIELDS)
    for field, expected_type in EXPECTED_FIELDS.items():
        assert isinstance(game[field], expected_type), f"{field} should be {expected_type}"


def test_catalogue_values_are_realistic():
    ids = [g["id"] for g in SEED_GAMES]
    titles = [g["title"].casefold() for g in SEED_GAMES]

    assert len(set(ids)) == len(ids), "ids must be unique"
    assert len(set(titles)) == len(titles), "titles must be unique"
    for game in SEED_GAMES:
        assert 1958 <= game["release_year"] <= 2030
        assert 0 <= game["price_usd"] <= 100
        assert 0 < game["units_sold_millions"] <= 400
        assert game["esrb_rating"] in ESRB_RATINGS
        assert game["platforms"], "every game needs at least one platform"


def test_catalogue_contains_some_out_of_stock_games():
    stock = {g["in_stock"] for g in SEED_GAMES}

    assert stock == {True, False}, "filters need both in-stock and out-of-stock games"


def test_best_selling_game_is_minecraft(client, auth_headers):
    games = client.get("/games", headers=auth_headers).get_json()

    top_seller = max(games, key=lambda g: g["units_sold_millions"])

    assert top_seller["title"] == "Minecraft"


@pytest.mark.parametrize(
    "title",
    ["Super Mario Bros. Wonder", "Sonic Frontiers", "Street Fighter 6", "Elden Ring"],
)
def test_known_titles_are_listed(client, auth_headers, title):
    titles = [g["title"] for g in client.get("/games", headers=auth_headers).get_json()]

    assert title in titles


@pytest.mark.parametrize(
    "platform, must_include",
    [
        ("Switch", "Mario Kart 8 Deluxe"),
        ("switch", "Mario Kart 8 Deluxe"),  # filters ignore case
        ("PC", "Elden Ring"),
        ("Wii U", "The Legend of Zelda: Breath of the Wild"),
    ],
)
def test_filter_by_platform(client, auth_headers, platform, must_include):
    response = client.get("/games", headers=auth_headers, query_string={"platform": platform})
    games = response.get_json()

    assert response.status_code == 200
    assert must_include in [g["title"] for g in games]
    for game in games:
        assert platform.casefold() in [p.casefold() for p in game["platforms"]]


def test_filter_by_genre(client, auth_headers):
    response = client.get("/games", headers=auth_headers, query_string={"genre": "platformer"})

    titles = {g["title"] for g in response.get_json()}

    assert titles == {
        "Super Mario Bros. Wonder",
        "Crash Bandicoot N. Sane Trilogy",
        "Sonic Frontiers",
    }


@pytest.mark.parametrize("value, expected", [("true", True), ("false", False), ("0", False)])
def test_filter_by_stock(client, auth_headers, value, expected):
    response = client.get("/games", headers=auth_headers, query_string={"in_stock": value})
    games = response.get_json()

    assert games, "expected at least one match"
    assert all(g["in_stock"] is expected for g in games)


def test_invalid_stock_filter_is_rejected(client, auth_headers):
    response = client.get("/games", headers=auth_headers, query_string={"in_stock": "maybe"})

    assert response.status_code == 400


def test_unknown_platform_returns_empty_list(client, auth_headers):
    response = client.get("/games", headers=auth_headers, query_string={"platform": "Dreamcast"})

    assert response.status_code == 200
    assert response.get_json() == []


# --- GET /games/<id> --------------------------------------------------------


def test_get_game_by_id(client, auth_headers):
    response = client.get("/games/4", headers=auth_headers)

    assert response.status_code == 200
    assert response.get_json()["title"] == "Mario Kart 8 Deluxe"


@pytest.mark.parametrize("game_id", [0, 999])
def test_get_unknown_game_returns_404(client, auth_headers, game_id):
    response = client.get(f"/games/{game_id}", headers=auth_headers)

    assert response.status_code == 404
    assert "not found" in response.get_json()["error"]


# --- POST /games ------------------------------------------------------------


def test_add_game(client, auth_headers, make_game):
    response = client.post("/games", headers=auth_headers, json=[make_game()])

    assert response.status_code == 201
    added = response.get_json()["added"]
    assert len(added) == 1
    assert added[0]["id"] == len(SEED_GAMES) + 1

    fetched = client.get(f"/games/{added[0]['id']}", headers=auth_headers).get_json()
    assert fetched["title"] == "Hollow Knight: Silksong"


def test_add_several_games_at_once(client, auth_headers, make_game):
    payload = [make_game(title="Hades II"), make_game(title="Balatro", genre="Roguelike")]

    response = client.post("/games", headers=auth_headers, json=payload)

    assert response.status_code == 201
    ids = [g["id"] for g in response.get_json()["added"]]
    assert ids == [len(SEED_GAMES) + 1, len(SEED_GAMES) + 2]


def test_optional_fields_get_defaults(client, auth_headers, make_game):
    payload = make_game(esrb_rating=None, units_sold_millions=None, in_stock=None)

    added = client.post("/games", headers=auth_headers, json=[payload]).get_json()["added"][0]

    assert added["esrb_rating"] == "RP"
    assert added["units_sold_millions"] == 0.0
    assert added["in_stock"] is True


@pytest.mark.parametrize(
    "overrides, expected_error",
    [
        ({"title": None}, "'title' is required"),
        ({"title": "   "}, "'title' must not be blank"),
        ({"release_year": "2025"}, "'release_year' has the wrong type"),
        ({"release_year": True}, "'release_year' has the wrong type"),
        ({"release_year": 1900}, "'release_year' must be between"),
        ({"price_usd": -5}, "'price_usd' must not be negative"),
        ({"platforms": []}, "'platforms' must be a non-empty list"),
        ({"platforms": "PC"}, "'platforms' has the wrong type"),
        ({"esrb_rating": "PG-13"}, "'esrb_rating' must be one of"),
    ],
)
def test_add_game_validation(client, auth_headers, make_game, overrides, expected_error):
    response = client.post("/games", headers=auth_headers, json=[make_game(**overrides)])

    assert response.status_code == 400
    assert any(expected_error in detail for detail in response.get_json()["details"])


def test_one_invalid_game_rejects_the_whole_request(client, auth_headers, make_game):
    payload = [make_game(title="Valid Game"), make_game(title=None)]

    response = client.post("/games", headers=auth_headers, json=payload)
    titles = [g["title"] for g in client.get("/games", headers=auth_headers).get_json()]

    assert response.status_code == 400
    assert "Valid Game" not in titles


@pytest.mark.parametrize(
    "body",
    ['{"title": "Not an array"}', "not json at all", "[]", '["just a string"]'],
    ids=["object", "malformed", "empty-array", "array-of-strings"],
)
def test_add_game_rejects_bad_body(client, auth_headers, body):
    response = client.post(
        "/games", headers=auth_headers, data=body, content_type="application/json"
    )

    assert response.status_code == 400
    assert "error" in response.get_json()


@pytest.mark.parametrize("title", ["Minecraft", "minecraft", "  Minecraft  "])
def test_duplicate_title_is_rejected(client, auth_headers, make_game, title):
    response = client.post("/games", headers=auth_headers, json=[make_game(title=title)])

    assert response.status_code == 409


# --- DELETE /games ----------------------------------------------------------


def test_delete_games(client, auth_headers):
    response = client.delete(
        "/games",
        headers=auth_headers,
        json=[{"title": "Sonic Frontiers"}, {"title": "Not A Real Game"}],
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "deleted": ["Sonic Frontiers"],
        "not_found": ["Not A Real Game"],
    }
    remaining = client.get("/games", headers=auth_headers).get_json()
    assert len(remaining) == len(SEED_GAMES) - 1


def test_each_test_gets_fresh_data(client, auth_headers):
    """test_delete_games removed a game, but this test still sees the full catalogue.

    That's because the ``app`` fixture builds a new app for every test.
    """
    titles = [g["title"] for g in client.get("/games", headers=auth_headers).get_json()]

    assert "Sonic Frontiers" in titles


def test_delete_rejects_items_without_title(client, auth_headers):
    response = client.delete("/games", headers=auth_headers, json=[{"name": "Minecraft"}])

    assert response.status_code == 400
