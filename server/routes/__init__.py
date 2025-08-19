from flask import Flask
from .health import bp as health_bp
from .munros import bp as munros_bp
from .tags import bp as tags_bp
from .search import bp as search_bp
from .chat import bp as chat_bp
from db import init_app as init_db


def register_blueprints(app: Flask):
    init_db(app)
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(munros_bp, url_prefix="/api")
    app.register_blueprint(tags_bp, url_prefix="/api")
    app.register_blueprint(search_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
