import random
from flask import Blueprint, jsonify
from service.api_service import ApiService

bp = Blueprint("game", __name__, url_prefix="/")


@bp.route("/")
def index_page():
    return jsonify({"message": "API is running"}), 200


@bp.route("/begin", methods=["GET"])
def begin():
    answer = random.randint(1000, 9999)
    game_id = ApiService.create_game(answer)

    return jsonify({"game_id": game_id}), 200
