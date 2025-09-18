import os


class Config:
    """Runtime configuration loaded into the Flask app context."""

    # Path to the SQLite database file used across CLI scripts and API requests.
    DB_PATH = os.getenv("DB_PATH", "db.sqlite")
    # Preferred chat model identifier for LLM-backed routes, falling back to GPT-4o mini.
    MUNRO_CHAT_MODEL = os.getenv("MUNRO_CHAT_MODEL", "gpt-4o-mini")
    # Optional OpenAI API key to support chat and tagging features when present.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
