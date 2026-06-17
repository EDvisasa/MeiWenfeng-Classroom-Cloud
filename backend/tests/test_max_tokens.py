import pytest
from backend.routers.models import resolve_max_tokens

def test_resolve_max_tokens_deepseek_overrides_proxy_default():
    """
    Test that for DeepSeek models, the hardcoded large context window (1000000)
    is not overwritten by a smaller default proxy value like 8192.
    """
    # Simulate proxy returning 8192 for a DeepSeek model
    result = resolve_max_tokens("DeepSeek (在线)", "deepseek-chat", "https://api.deepseek.com", 8192)
    assert result == 1000000, "Should use the known large context window for DeepSeek, ignoring small proxy defaults"

def test_resolve_max_tokens_qwen_overrides_proxy_default():
    """
    Test that for Qwen models, the hardcoded context window (262144)
    is not overwritten by 8192.
    """
    result = resolve_max_tokens("qwen2.5-coder", "qwen", "http://localhost:11434", 8192)
    assert result == 262144, "Should use known Qwen context window"

def test_resolve_max_tokens_uses_api_if_larger():
    """
    Test that if the API returns a genuinely larger value than our default 8192,
    it uses the API value.
    """
    result = resolve_max_tokens("unknown-model", "", "https://api.openai.com", 16384)
    assert result == 16384, "Should use the larger API value"

def test_resolve_max_tokens_default():
    """
    Test fallback behavior.
    """
    result = resolve_max_tokens("unknown-model", "", "https://api.openai.com", None)
    assert result == 8192, "Should default to 8192"

def test_resolve_max_tokens_target_model_heuristic():
    """
    Test that if model_name does not match, but target_model does, it gets the correct max_tokens.
    """
    result = resolve_max_tokens("GG公益站 (在线)", "gemini-3.1-pro-preview", "https://api.google.com", 8192)
    assert result == 1000000, "Should detect gemini from target_model"
