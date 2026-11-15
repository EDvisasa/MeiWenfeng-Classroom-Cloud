import pytest
from backend.routers.models import resolve_max_tokens

def test_resolve_max_tokens_mapping():
    """Verify resolve_max_tokens across provider overrides, larger API values, defaults, and target_model heuristics."""
    cases = [
        ("DeepSeek (在线)", "deepseek-chat", "https://api.deepseek.com", 8192, 1000000),
        ("qwen2.5-coder", "qwen", "http://localhost:11434", 8192, 262144),
        ("unknown-model", "", "https://api.openai.com", 16384, 16384),
        ("unknown-model", "", "https://api.openai.com", None, 8192),
        ("GG公益站 (在线)", "gemini-3.1-pro-preview", "https://api.google.com", 8192, 1000000),
    ]
    for model_name, target_model, base_url, api_tokens, expected in cases:
        assert resolve_max_tokens(model_name, target_model, base_url, api_tokens) == expected
