import os


class Config:
    DB_PATH = os.getenv("DB_PATH", "db.sqlite")
    MUNRO_CHAT_MODEL = os.getenv("MUNRO_CHAT_MODEL", "gpt-4o-mini")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
