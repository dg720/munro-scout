from typing import Optional
from flask import current_app
import os

# Lazily load to avoid import errors when not configured
_llm = None
_use_llm = None


def get_llm():
    """Return a cached LangChain ChatOpenAI instance and flag if it is usable."""

    global _llm, _use_llm
    if _use_llm is not None:
        return _llm, _use_llm

    try:
        from langchain_openai import ChatOpenAI  # type: ignore

        # Pull configuration from Flask first, then fall back to environment.
        model = current_app.config.get("MUNRO_CHAT_MODEL", "gpt-4o-mini")
        key = current_app.config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

        # Zero temperature keeps answers deterministic for the assistant persona.
        _llm = ChatOpenAI(model=model, temperature=0, openai_api_key=key)
        _use_llm = True
    except Exception:
        # If the dependency is missing or credentials aren't present, disable LLM flows.
        _llm = None
        _use_llm = False
    return _llm, _use_llm
