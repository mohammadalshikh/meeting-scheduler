import random
from flask import Blueprint,jsonify,request
from datetime import datetime
from service.game_service import GameService

game_blueprint = Blueprint('game', __name__, url_prefix='/')
service = GameService()
@game_blueprint.route('')

def hello():
    return "Hello, World!"

# jazib
@game_blueprint.route('/begin',methods=['GET'])
def begin():
    answer = random.randint(1000, 9999)
    gameid=service.create_game(answer)
    
    return jsonify({"game_id": gameid}), 201


# jazib
@game_blueprint.route('/game/<game_id>', methods=['GET'])
def get_game(game_id):
    if game_id not in service.get_all_games():
        return jsonify({"error": "Game not found"}), 404

    game_data = service.get_game(game_id)
    return jsonify(game_data), 200


# mohammad
@game_blueprint.route('/game', methods=['GET'])
def game():
    all_games = service.get_all_games()
    return jsonify(all_games), 200


# mehrin
@game_blueprint.route('/guess', methods=['POST'])
def guess():
    data = request.get_json()

    game_id = str(data["gameID"])
    user_guess = str(data["guess"])
    game = service.get_game(game_id, get_answer=True)
    answer = str(game["answer"])
    result = service.calculate_result(user_guess, answer)
    service.add_guess(game_id, user_guess)

    return jsonify({
        "gameId": game_id,
        "guessTime": datetime.now().isoformat(),
        "result": result
        }), 200


# yong
@game_blueprint.route('/rounds/<game_id>', methods=['GET'])
def get_rounds(game_id):

    game_obj = service.get_game(game_id)
    game_rounds = game_obj["rounds"]

    return jsonify(game_rounds)
