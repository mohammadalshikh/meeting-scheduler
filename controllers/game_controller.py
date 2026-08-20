import random
from flask import Blueprint,jsonify

game_blueprint = Blueprint('game', __name__, url_prefix='/')
game={}
@game_blueprint.route('')

def hello():
    return "Hello, World!"

# jazib 
@game_blueprint.route('/begin',methods=['POST'])
def begin():
    id=str(len(game)+1)
    answer=random.randint(1,100)

    game[id]={
        "id": id,
        "answer": answer,
        "status": "active"
    }
    return jsonify({"game_id": id}), 201


# mohammad 
@game_blueprint.route('/game', methods=['GET'])
def game():
    pass




#mehrin
@game_blueprint.route('/guess', methods=['POST'])
def guess():
    
    pass



#yong
@game_blueprint.route('/rounds', method=['GET'])
def get_rounds(game_id):

    game_rounds = []

    for round in rounds:
        if round.game_id()