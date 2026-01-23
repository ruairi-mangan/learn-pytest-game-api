import random, asyncio

from flask import Flask, jsonify, request

app = Flask(__name__)

games = [
    {"name": "Mario", "available": random.choice([True, False]), "sales": random.randint(100, 90000)},
    {"name": "Sonic", "available": random.choice([True, False]), "sales": random.randint(100, 100000)},
    {"name": "Crash Bandicoot", "available": random.choice([True, False]), "sales": random.randint(100, 50000)},
    {"name": "Zelda", "available": random.choice([True, False]), "sales": random.randint(2000, 70000)},
    {"name": "Street Fighter", "available": random.choice([True, False]), "sales": random.randint(1000, 99000)},
]


@app.route('/games', methods=['GET'])
def get_games():
    auth_header = request.headers.get("Authorization")
    if auth_header != "Bearer mysecrettoken":
        return jsonify({"error": "Unauthorized"}), 401
    response = jsonify(games)
    response.headers["X-API-Version"] = "1.0"
    return response


@app.route('/games', methods=['POST'])
def add_games():
    data = validate_json_array(request)
    global games
    new_games = [game for game in data if "name" in game]
    games.extend(new_games)
    return jsonify({"Games:": new_games})


@app.route('/games', methods=['DELETE'])
def delete_games():
    data = validate_json_array(request)
    global games
    names_to_delete = [game.get("name") for game in data if "name" in game]
    games = [game for game in games if game["name"] not in names_to_delete]
    return jsonify({"deleted": names_to_delete})


async def get_games_async():
    await asyncio.sleep(0.2)  # simulate network delay
    return [
        {
            "name": "Space Raiders",
            "available": random.choice([True, False]),
            "monthly_sales": random.randint(100, 5000)
        },
        {
            "name": "Dungeon Quest",
            "available": random.choice([True, False]),
            "monthly_sales": random.randint(50, 3000)
        }
    ]

def validate_json_array(req):
    data = req.get_json()
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array"}), 400
    return data


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
