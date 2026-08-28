from flask import Flask
from controllers.controller import bp


app = Flask(__name__)
app.register_blueprint(bp)

if __name__ == '__main__':
    app.run(debug=True)   