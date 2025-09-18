from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from routes import register_blueprints
from config import Config
import os


def create_app() -> Flask:
    """Instantiate and configure the Flask application for the Munro API."""

    # Load environment variables before creating the app so config picks them up.
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["JSON_AS_ASCII"] = False

    # Enable CORS for the single-page client.
    CORS(app)

    # Register blueprints, database teardown hooks, etc.
    register_blueprints(app)

    # Provide a visible boot log for container platforms.
    print("🚀 Starting Munro Flask API...")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
