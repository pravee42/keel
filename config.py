"""Persistent config — stored at ~/.keel/config.json"""

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".keel" / "config.json"

PROVIDERS = {
    "anthropic": {
        "label":         "Anthropic",
        "default_model": "claude-opus-4-6",
        "base_url":      None,                  # uses native Anthropic SDK
        "key_env":       "ANTHROPIC_API_KEY",
        "models": [
            "claude-opus-4-6",
            "claude-sonnet-4-6",
            "claude-haiku-4-5",
        ],
    },
    "openai": {
        "label":         "OpenAI",
        "default_model": "gpt-4o",
        "base_url":      "https://api.openai.com/v1",
        "key_env":       "OPENAI_API_KEY",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "o3-mini",
        ],
    },
    "openrouter": {
        "label":         "OpenRouter",
        "default_model": "anthropic/claude-opus-4-6",
        "base_url":      "https://openrouter.ai/api/v1",
        "key_env":       "OPENROUTER_API_KEY",
        "models": [
            "anthropic/claude-opus-4-6",
            "anthropic/claude-sonnet-4-6",
            "openai/gpt-4o",
            "google/gemini-2.0-flash-001",
            "mistralai/mistral-large",
            "meta-llama/llama-3.3-70b-instruct",
        ],
    },
    "gemini": {
        "label":         "Google Gemini",
        "default_model": "gemini-2.0-flash",
        "base_url":      "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env":       "GEMINI_API_KEY",
        "models": [
            "gemini-2.0-flash",
            "gemini-2.5-pro-preview-05-06",
            "gemini-1.5-pro",
        ],
    },
    "mistral": {
        "label":         "Mistral",
        "default_model": "mistral-large-latest",
        "base_url":      "https://api.mistral.ai/v1",
        "key_env":       "MISTRAL_API_KEY",
        "models": [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "codestral-latest",
        ],
    },
}

INTEGRATIONS = {
    "slack":  {"label": "Slack User Token"},
    "github": {"label": "GitHub PAT"},
    "teams":  {"label": "Teams App Token"},
}

_DEFAULTS = {
    "provider": "anthropic",
    "model":    "claude-opus-4-6",
    "api_keys": {},
}


def load() -> dict:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(_DEFAULTS, indent=2))
        return dict(_DEFAULTS)
    return json.loads(CONFIG_PATH.read_text())


def save(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))


def get_provider() -> str:
    return load().get("provider", "anthropic")


def get_model() -> str:
    return load().get("model", PROVIDERS[get_provider()]["default_model"])


def get_api_key(provider: Optional[str] = None) -> Optional[str]:
    """Key lookup order: stored config → environment variable."""
    provider = provider or get_provider()
    cfg = load()
    stored = cfg.get("api_keys", {}).get(provider)
    if stored:
        return stored
    env_var = PROVIDERS[provider]["key_env"]
    return os.environ.get(env_var)


def set_provider(provider: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}. Choose from: {', '.join(PROVIDERS)}")
    cfg = load()
    cfg["provider"] = provider
    cfg["model"] = PROVIDERS[provider]["default_model"]
    save(cfg)


def set_model(model: str) -> None:
    cfg = load()
    cfg["model"] = model
    save(cfg)


def set_api_key(provider: str, key: str) -> None:
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    cfg = load()
    cfg.setdefault("api_keys", {})[provider] = key
    save(cfg)
