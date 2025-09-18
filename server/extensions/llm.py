from typing import Optional
from flask import current_app
import os

# Lazily load to avoid import errors when not configured
_llm = None
_use_llm = None


def get_llm():
    """Instantiate and cache the configured ChatOpenAI client if available."""
    global _llm, _use_llm
    if _use_llm is not None:
        return _llm, _use_llm

    try:
        from langchain_openai import ChatOpenAI  # type: ignore

        model = current_app.config.get("MUNRO_CHAT_MODEL", "gpt-4o-mini")
        key = current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        # Lazily construct the client once we have all configuration values.
        _llm = ChatOpenAI(model=model, temperature=0, openai_api_key=key)
        _use_llm = True
    except Exception:
        _llm = None
        _use_llm = False
    return _llm, _use_llm
