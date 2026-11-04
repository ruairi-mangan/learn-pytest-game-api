# learn-pytest-game-api

[![CI](https://github.com/ruairi-mangan/learn-pytest-game-api/actions/workflows/ci.yml/badge.svg)](https://github.com/ruairi-mangan/learn-pytest-game-api/actions/workflows/ci.yml)

A practice project for learning **pytest**. It contains a small Flask API that
serves a mock video game catalogue, plus a test suite that shows common pytest
patterns. Everything runs in Docker, both locally and in GitHub Actions.

- [What's inside](#whats-inside)
- [The mock API](#the-mock-api)
- [pytest techniques demonstrated](#pytest-techniques-demonstrated)
- [Running the tests](#running-the-tests)
- [Debugging](#debugging)

## What's inside

```
api/
  games_data.py        Seed catalogue: 14 real games with approximate sales figures
  mockapi.py           Flask app factory, validation, and an async "live stats" function
  client.py            HTTP client for the API: custom exceptions, retries, logging
tests/
  conftest.py          Shared fixtures: app, client, auth_headers, make_game
  unit/                Fast, isolated tests using Flask's in-process test client
  integration/         HTTP tests against the mockapi container (needs API_BASE_URL)
Dockerfile             Python 3.13 image that runs the API and the tests
docker-compose.yaml    mockapi service (with healthcheck) + test service
pyproject.toml         Dependencies plus pytest, coverage, and ruff settings
```

## The mock API

Each game record looks like this:

```json
{
  "id": 4,
  "title": "Mario Kart 8 Deluxe",
  "developer": "Nintendo EPD",
  "publisher": "Nintendo",
  "release_year": 2017,
  "genre": "Racing",
  "platforms": ["Switch"],
  "esrb_rating": "E",
  "price_usd": 59.99,
  "units_sold_millions": 68.0,
  "in_stock": true
}
```

Sales figures are approximate lifetime units, rounded from publicly reported
numbers. They are realistic test data, not an authoritative source.

| Method   | Path           | Description                                                        |
|----------|----------------|--------------------------------------------------------------------|
| `GET`    | `/health`      | Liveness check (no auth)                                           |
| `GET`    | `/games`       | List games. Optional filters: `?platform=`, `?genre=`, `?in_stock=` |
| `GET`    | `/games/<id>`  | Get one game, or `404` if not found                                |
| `POST`   | `/games`       | Add games from a JSON array. Returns `201`, `400` (invalid) or `409` (duplicate title) |
| `DELETE` | `/games`       | Delete by title: `[{"title": "..."}]`. Returns `deleted` and `not_found` lists |

Every `/games` request needs `Authorization: Bearer mysecrettoken`. You can
change the token with the `API_TOKEN` environment variable. Every response
includes an `X-API-Version` header.

`get_live_player_counts_async()` simulates a slow call to a live-stats service.
It returns concurrent Steam player counts that are random within realistic
ranges. This makes it useful for practising tests on data that changes every
time you read it.

Try the API by hand:

```bash
docker compose up mockapi
curl -H "Authorization: Bearer mysecrettoken" "localhost:5000/games?platform=switch&in_stock=true"
```

## pytest techniques demonstrated

| Technique | Where |
|-----------|-------|
| Fixtures and fixture composition (`client` depends on `app`) | `tests/conftest.py` |
| Test isolation (a fresh app per test, no shared state) | `app` fixture, `test_each_test_gets_fresh_data` |
| Factory fixtures | `make_game` |
| `yield` fixtures with teardown | `created_game` in `tests/integration/conftest.py` |
| Session-scoped fixtures | `base_url`, `api` |
| `@pytest.mark.parametrize`, stacked, with custom `ids` | `test_endpoints_reject_bad_credentials`, `test_add_game_validation` |
| Parametrizing over data | `test_every_game_matches_schema` |
| `monkeypatch` for environment variables | `test_token_can_be_set_by_environment_variable` |
| Async tests with `pytest-asyncio` | `tests/unit/test_live_players.py` |
| Testing random data with range checks and seeded RNGs | `test_player_counts_stay_within_range`, `test_seeded_rng_gives_repeatable_results` |
| Custom markers + `--strict-markers` | `integration` marker in `pyproject.toml` |
| Skipping tests when the environment isn't available | `base_url` fixture |
| Retrying flaky tests (`pytest-rerunfailures`) | `test_response_time_within_sla` |
| `pytest.raises`: `match=`, `exc_info`, subclasses, `__cause__` | `tests/unit/test_errors_and_logging.py`, `test_unknown_game_raises_not_found` |
| `caplog`: `set_level`, `at_level`, `records`, `record_tuples`, `messages` | `test_rejected_request_logs_a_warning`, `test_retries_are_logged` |
| Mocking with `pytest-mock`: `mocker.patch`, `patch.object`, `Mock(spec=...)` | `tests/unit/test_client_mocking.py` |
| `side_effect` for failure sequences, asserting calls | `test_retries_until_the_request_succeeds`, `test_gives_up_after_max_retries` |
| Patching `time.sleep` so retry tests run instantly | `sleep` fixture |
| Spies (`mocker.spy`) | `test_spy_records_calls_but_keeps_real_behaviour` |
| `AsyncMock` for async functions | `test_most_played_now_with_async_mock` |
| The same client tested with mocks and against the real server | `test_client_against_live_api` |
| Coverage and HTML reports | `pytest-cov`, `pytest-html` |

## Running the tests

### With Docker (recommended)

```bash
docker compose build
docker compose run --rm test pytest
```

Or open a shell in the test container and run commands from there:

```bash
docker compose run --rm test sh
```

```bash
pytest                                  # everything
pytest tests/unit                       # just the fast unit tests
pytest -m integration                   # only tests marked "integration"
pytest -m "not integration"             # everything except integration tests
pytest -k validation                    # tests whose name matches "validation"
pytest -vv -l                           # verbose output, show local variables on failure
pytest --cov --cov-report=term-missing  # coverage report
pytest --html=artifacts/report.html --self-contained-html
ruff check . && ruff format --check .   # lint
exit
```

When you're done, stop the API container with `docker compose down`.

### Without Docker

Requires Python 3.11+. The integration tests are skipped unless the API is running.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"
pytest
```

To run the integration tests too, start the API and point the tests at it:

```bash
docker compose up -d mockapi
API_BASE_URL=http://localhost:5000 pytest
```

### CI

GitHub Actions (`.github/workflows/ci.yml`) builds the images, runs `ruff`, then
runs the full suite with coverage. The HTML report is uploaded as the
`pytest-report` artifact.

## Debugging

- Add `breakpoint()` anywhere in a test or in the app, then run
  `pytest -s` to stop in the `pdb` debugger. Useful commands:
  ```
  p response.get_json()   # print a value
  pp games[0]             # pretty-print
  type(games)             # inspect a type
  n / s / c / q           # next line / step into / continue / quit
  ```
- `pytest --pdb` opens the debugger automatically when a test fails.
- `pytest --lf` re-runs only the tests that failed last time.
- If your terminal stops responding after scrolling in the Docker shell, press `q`.
