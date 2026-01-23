import unittest
import requests
import time
import logging
import pytest
import flaky

logging.basicConfig(level=logging.INFO)
SLA_MS = 5000


class TestMockAPI(unittest.TestCase):
    def test_get_characters_endpoint(self):
        response = get_games_with_auth()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
        names = [char['name'] for char in data]
        self.assertIn('Mario', names)
        self.assertIn('Sonic', names)

        mario_value = next((char['sales'] for char in data if char['name'] == 'Mario'), None)
        self.assertIsNotNone(mario_value)

    @flaky.flaky(max_runs=4, min_passes=1)
    def test_api_response(self):
        start = time.monotonic()
        r = get_games_with_auth()
        r.raise_for_status()
        _ = r.json()  # include JSON parsing in the measured path if you want
        elapsed_ms = (time.monotonic() - start) * 1000
        logging.info(f"API response time: {elapsed_ms:.1f} ms")
        assert elapsed_ms <= SLA_MS, f"Elapsed {elapsed_ms:.1f} ms (> {SLA_MS} ms)"

    def test_sales_within_reasonable_range(self):
        response = get_games_with_auth()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        for sale in data:
            assert 100 <= sale["sales"] <= 100000

    def test_at_least_one_game_available(self):
        response = get_games_with_auth()
        data = response.json()
        available_count = sum(1 for g in data if g["available"])

        assert available_count >= 1

    def test_top_seller_threshold(self):
        response = get_games_with_auth()
        data = response.json()

        top_sellers = [
            g for g in data if g["sales"] > 10000
        ]

        assert len(top_sellers) >= 1

    def test_sales_stability_over_runs(self):
        totals = []

        for _ in range(5):
            response = get_games_with_auth()
            data = response.json()
            totals.append(sum(g["sales"] for g in data))

        assert min(totals) > 0
        assert max(totals) < 300_000

    def test_add_games(self):
        response = get_games_with_auth()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 5)

        response = requests.post('http://mockapi:5000/games', json=[
            {"name": "New Game", "available": True, "sales": 5000}
        ])
        self.assertEqual(response.status_code, 200)

    @pytest.mark.mocked
    def test_delete_games(self):
        response = get_games_with_auth()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 6)

        response = requests.delete('http://mockapi:5000/games', json=[
            {"name": "New Game", "available": True, "sales": 5000}
        ])
        self.assertEqual(response.status_code, 200)
        response = get_games_with_auth()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 5)

    def test_headers(self):
        response = get_games_with_auth()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-API-Version"), "1.0")


def get_games_with_auth():
    headers = {"Authorization": "Bearer mysecrettoken"}
    response = requests.get('http://mockapi:5000/games', headers=headers)
    return response


if __name__ == '__main__':
    unittest.main()
