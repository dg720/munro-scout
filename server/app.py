from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from routes import register_blueprints
from config import Config
import os


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    load_dotenv()
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["JSON_AS_ASCII"] = False
    CORS(app)

    # Register all API blueprints and shared teardown handlers.
    register_blueprints(app)

    # Emit a startup log for container platforms without process logs.
    print("🚀 Starting Munro Flask API...")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
