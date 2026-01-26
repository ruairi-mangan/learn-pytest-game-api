# pytest_docker_example

- [Background](#background)
- [Prerequisites](#prerequisites)
- [Usage](#usage)
- [Debugging](#debugging)

## Background

This project provides a suite of tests for a mocked game API, demonstrating how to use pytest and related libraries to validate endpoints, 
authentication, headers, and various HTTP methods. It includes examples of response time measurement, flaky tests, and data validation to 
showcase best practices in API testing. The goal is to help readers learn practical pytest techniques for robust and comprehensive API test coverage.

The main files are:

**mockapi.py** implements a Flask API with in-memory mock data for computer games.
Endpoints:
- GET /games: Returns the list of games if the correct Authorization header is present, adds a custom API version header.
- POST /games: Adds new games from a JSON array in the request body.
- DELETE /games: Deletes games matching names from a JSON array in the request body.
- get_games_async(): Async function simulating a delayed response with random game data.
- JSON helper ensuring that incoming JSON is an array.

**test_games.py**
contains tests for the Flask API endpoints.

- GET /games: Checks for correct response, authorization handling, and presence of custom headers.
- POST /games: Verifies adding new games and input validation.
- DELETE /games: Ensures games are deleted as expected.
- Header checks: Confirms required headers (like Authorization) are enforced.
- Retries/Flakiness: May use pytest features (like @pytest.mark.flaky) to handle or simulate flaky endpoints and test retry logic.

Uses pytest and Flask’s test client for endpoint interaction and assertions.
These files together provide a mock API and a comprehensive test suite covering endpoint functionality, input validation, header requirements, and robustness against flaky behavior.
## Prerequisites

**Install Docker**

- All dependencies for these tests are included in a Docker container.
- Python 3.7.6 was used during curation of this project. The Docker image uses Python 3.7.

## Usage

**To start a shell:**

```bash
$ docker-compose build
$ docker-compose run test sh
```


**This opens a shell in the Docker container. You can then run:**


  *Run all tests:*
    
  ``` bash
  $ pytest 
  ```

  *Run tests in files matching a keyword:*
    
  ``` bash
  $ pytest -k <test_file_name>
  ```

  *Run tests with verbose output and all variables printed:*

  ``` bash
  $ pytest -vvl
  ```

  *Check test coverage:*

  ``` bash
  $ pytest —cov
  ```

**To exit the shell**
  ```bash
  $ exit
  ```


## Debugging

1. If you scroll up `(ctrl + fn)` in the debug output when running `pytest -vvl`
    or viewing test errors, your cursor may freeze in the Docker shell. 
    Press `q` to return to entry mode.

2. To debug code, add one of the following to your code to enter the pdb debugger during pytest runs:
   * `breakpoint()`
   * `import pdb; pdb.set_trace()`

3. An example of commands when using breakpoint:
    ```bash
    $ $ type(data).  # Check type
    $ data[0].       # Get first row
    $ data[0]['Name'] # Get first row value for column name
    $ isinstance(data[0]['Name'],str) # Check if first row value name is a string
    ```
