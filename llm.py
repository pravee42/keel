"""Unified LLM client — routes to Anthropic, OpenAI, OpenRouter, Gemini, Mistral."""

from typing import Optional
import config as cfg


def complete(messages: list[dict], max_tokens: int = 1024) -> str:
    """Single completion — returns text. Used for JSON extractions."""
    provider = cfg.get_provider()
    if provider == "anthropic":
        return _anthropic_complete(messages, max_tokens)
    return _openai_compat_complete(provider, messages, max_tokens)


def stream_complete(messages: list[dict], max_tokens: int = 2048) -> str:
    """Streaming completion — returns full text. Uses thinking on Anthropic."""
    provider = cfg.get_provider()
    if provider == "anthropic":
        return _anthropic_stream(messages, max_tokens)
    return _openai_compat_complete(provider, messages, max_tokens)


# ─────────────────────────────────────────────
# Anthropic (native SDK — supports thinking)
# ─────────────────────────────────────────────

def _anthropic_complete(messages: list[dict], max_tokens: int) -> str:
    import anthropic as sdk
    api_key = cfg.get_api_key("anthropic")
    client = sdk.Anthropic(api_key=api_key)

    # Extract optional system message
    system, msgs = _split_system(messages)
    kwargs = dict(
        model=cfg.get_model(),
        max_tokens=max_tokens,
        messages=msgs,
    )
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text


def _anthropic_stream(messages: list[dict], max_tokens: int) -> str:
    import anthropic as sdk
    api_key = cfg.get_api_key("anthropic")
    client = sdk.Anthropic(api_key=api_key)

    system, msgs = _split_system(messages)
    kwargs = dict(
        model=cfg.get_model(),
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        messages=msgs,
    )
    if system:
        kwargs["system"] = system

    with client.messages.stream(**kwargs) as stream:
        msg = stream.get_final_message()
        return next(b.text for b in reversed(msg.content) if b.type == "text")


# ─────────────────────────────────────────────
# OpenAI-compatible (OpenAI, OpenRouter, Gemini, Mistral)
# ─────────────────────────────────────────────

def _openai_compat_complete(provider: str, messages: list[dict], max_tokens: int) -> str:
    from openai import OpenAI

    provider_cfg = cfg.PROVIDERS[provider]
    api_key = cfg.get_api_key(provider)
    if not api_key:
        raise RuntimeError(
            f"No API key for {provider}. Run: decide config key {provider} <your-key>"
        )

    extra_headers = {}
    if provider == "openrouter":
        extra_headers["HTTP-Referer"] = "https://github.com/decide-tool"
        extra_headers["X-Title"] = "decide"

    client = OpenAI(
        api_key=api_key,
        base_url=provider_cfg["base_url"],
        default_headers=extra_headers if extra_headers else None,
    )

    response = client.chat.completions.create(
        model=cfg.get_model(),
        messages=messages,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _split_system(messages: list[dict]) -> tuple[Optional[str], list[dict]]:
    """Extract system message for Anthropic SDK (which takes it as a separate param)."""
    system = None
    rest = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            rest.append(m)
    return system, rest


def test_connection() -> tuple[bool, str]:
    """Quick connectivity test — returns (ok, message)."""
    try:
        result = complete(
            [{"role": "user", "content": "Reply with just the word: OK"}],
            max_tokens=16,
        )
        return True, result.strip()
    except Exception as e:
        return False, str(e)
