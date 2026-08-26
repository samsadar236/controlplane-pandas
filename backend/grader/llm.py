"""Provider-abstracted LLM factory, now per role.

Returns a langchain ChatModel for a given ROLE, so different nodes can run
on different providers/models in one pipeline:

  role="vision"  → Extractor + OCR   (must be vision-capable; Gemini by default)
  role="text"    → Scorer + Justifier (Groq by default; model A)
  role="critic"  → Critic             (Groq by default; model B, cross-model)

Routing and model ids come from settings.provider_for(role) /
settings.model_for(role). Flipping a *_provider or *_model value in .env
swaps that role's backend with no code change. Temperature is applied
uniformly from settings.grader_temperature (Lane A: 0.0 = deterministic).

Instances are cached per role. reset_llm() clears the cache (tests use it
after changing settings).

Key resolution is belt-and-braces: settings field first, then os.environ,
so a manually-set shell variable works even if pydantic-settings missed
the .env file.
"""
from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel

from ..config import settings


_llm_cache: dict[str, BaseChatModel] = {}


def _resolve_key(field_value: str, env_var: str) -> str:
    """Settings field first, then os.environ. Returns '' if neither has it."""
    if field_value:
        return field_value
    return os.environ.get(env_var, "") or ""


def _build_google(model: str, temperature: float) -> BaseChatModel:
    from langchain_google_genai import ChatGoogleGenerativeAI

    key = _resolve_key(settings.google_api_key, "GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "A role is routed to 'google' but GOOGLE_API_KEY is empty.\n"
            "Get a free key at https://aistudio.google.com/app/apikey and set "
            "GOOGLE_API_KEY in your .env (or shell env var).\n"
            "Hit GET /debug/env to see what the backend is loading."
        )
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=key,
        temperature=temperature,
        max_output_tokens=2048,
        timeout=120,
        max_retries=3,
    )


def _build_groq(model: str, temperature: float) -> BaseChatModel:
    try:
        from langchain_groq import ChatGroq
    except ImportError as e:
        raise RuntimeError(
            "A role is routed to 'groq' but langchain-groq is not installed.\n"
            "Run: pip install 'langchain-groq>=0.2'\n"
            "Or set the role's provider to 'google' in .env "
            "(text_provider / critic_provider)."
        ) from e

    key = _resolve_key(settings.groq_api_key, "GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "A role is routed to 'groq' but GROQ_API_KEY is empty.\n"
            "Get a free key at https://console.groq.com/keys and set GROQ_API_KEY "
            "in your .env, or set text_provider/critic_provider to 'google'."
        )
    # Some langchain-groq versions read the key only from the env var; set it
    # too so the key is picked up regardless of the constructor arg name.
    os.environ.setdefault("GROQ_API_KEY", key)
    return ChatGroq(
        model=model,
        api_key=key,
        temperature=temperature,
        max_tokens=2048,
        max_retries=3,
    )


def _build_anthropic(model: str, temperature: float) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    key = _resolve_key(settings.anthropic_api_key, "ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "A role is routed to 'anthropic' but ANTHROPIC_API_KEY is empty. "
            "Set it in .env, or route the role to 'google'/'groq'."
        )
    return ChatAnthropic(
        model=model,
        api_key=key,
        temperature=temperature,
        max_tokens=2000,
        timeout=120,
    )


def get_llm(role: str = "text") -> BaseChatModel:
    """Construct (and cache) the chat model for a given role.

    role: 'vision' | 'text' | 'critic'. Defaults to 'text'.
    """
    role = (role or "text").lower()
    cached = _llm_cache.get(role)
    if cached is not None:
        return cached

    provider = settings.provider_for(role)
    model = settings.model_for(role)
    temperature = float(settings.grader_temperature)

    if provider == "google":
        llm = _build_google(model, temperature)
    elif provider == "groq":
        llm = _build_groq(model, temperature)
    elif provider == "anthropic":
        llm = _build_anthropic(model, temperature)
    else:
        raise RuntimeError(
            f"Unknown provider {provider!r} for role {role!r}. "
            "Use 'google', 'groq', or 'anthropic'."
        )

    _llm_cache[role] = llm
    return llm


def reset_llm() -> None:
    """Clear all cached LLM instances (used by tests when settings change)."""
    _llm_cache.clear()
