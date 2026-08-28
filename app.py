from flask import Flask

from config import Config
from controllers.api import api
from controllers.web import web


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(web)
    app.register_blueprint(api)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True, port=5001)
