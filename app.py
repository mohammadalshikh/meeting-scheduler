from flask import Flask
from controllers.game_controller import game_blueprint


app = Flask(__name__)
app.register_blueprint(game_blueprint)

if __name__ == '__main__':
    app.run(debug=True)   