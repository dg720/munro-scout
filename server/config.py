import os


class Config:
    """Default configuration values for the Flask application."""

    DB_PATH = os.getenv("DB_PATH", "db.sqlite")
    MUNRO_CHAT_MODEL = os.getenv("MUNRO_CHAT_MODEL", "gpt-4o-mini")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
