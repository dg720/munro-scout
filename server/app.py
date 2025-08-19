from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from routes import register_blueprints
from config import Config


def create_app() -> Flask:
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["JSON_AS_ASCII"] = False
    CORS(app)

    register_blueprints(app)

    @app.before_first_request
    def _bootlog():
        print("🚀 Starting Munro Flask API...")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
