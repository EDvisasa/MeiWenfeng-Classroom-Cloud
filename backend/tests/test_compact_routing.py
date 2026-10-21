import pytest
import os
from unittest.mock import patch, MagicMock
from backend.services.compact_service import call_llm_for_summary

def test_call_llm_for_summary_preserves_local_model_routing():
    """
    TDD Test: Verify that call_llm_for_summary does not hijack local OpenAI-compatible models
    (such as ninfer+kvmem on http://127.0.0.1:8091/v1/) to remote AIRP/DeepSeek URLs.
    Ensures ZERO database touches.
    """
    mock_local_model = {
        "id": 7034,
        "name": "ninfer+kvmem",
        "protocol": "openai",
        "base_url": "http://127.0.0.1:8091/v1/",
        "api_key": "",
        "selected_model_id": "qwen3.8-27b",
        "max_context_tokens": 131072
    }

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "【自动浓缩纪要】：测试本地模型纪要生成成功。"
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    test_messages = [
        {"role": "user", "content": "你好，测试本地模型浓缩"},
        {"role": "assistant", "content": "收到，正在为你提炼"}
    ]

    env_overrides = {
        "AIRP_MODEL_BASE_URL": "https://gcli.ggchan.dev/v1",
        "AIRP_MODEL_API_KEY": "remote-env-key-that-must-not-hijack-local",
        "DEEPSEEK_BASE_URL": "https://api.deepseek.com/v1",
        "DEEPSEEK_API_KEY": "remote-deepseek-key"
    }

    with patch.dict(os.environ, env_overrides, clear=False), \
         patch("backend.services.compact_service.get_active_model", return_value=mock_local_model), \
         patch("backend.services.compact_service.OpenAI", return_value=mock_client) as mock_openai_cls:
        result = call_llm_for_summary(test_messages)

    # Verify OpenAI was initialized with the LOCAL base_url, NOT https://gcli.ggchan.dev/v1
    mock_openai_cls.assert_called_once_with(
        api_key="no-key-required",
        base_url="http://127.0.0.1:8091/v1/"
    )

    # Verify the completion request was sent with the active model's selected_model_id
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "qwen3.8-27b"
    assert "测试本地模型纪要生成成功" in result


def test_call_llm_for_summary_remote_model_env_key_fallback():
    """
    Verify that remote model with empty api_key falls back to environment variable,
    while keeping the original base_url intact.
    """
    mock_remote_model = {
        "id": 1001,
        "name": "deepseek-chat-remote",
        "protocol": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "selected_model_id": "deepseek-chat",
        "max_context_tokens": 65536
    }

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "【远程浓缩纪要】：远程模型提炼完毕。"
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    test_messages = [
        {"role": "user", "content": "提炼会话"},
        {"role": "assistant", "content": "好的"}
    ]

    env_overrides = {
        "DEEPSEEK_API_KEY": "sk-fallback-env-key-for-deepseek",
        "AIRP_MODEL_API_KEY": "airp-fallback-key"
    }

    with patch.dict(os.environ, env_overrides, clear=False), \
         patch("backend.services.compact_service.get_active_model", return_value=mock_remote_model), \
         patch("backend.services.compact_service.OpenAI", return_value=mock_client) as mock_openai_cls:
        result = call_llm_for_summary(test_messages)

    mock_openai_cls.assert_called_once_with(
        api_key="sk-fallback-env-key-for-deepseek",
        base_url="https://api.deepseek.com/v1"
    )
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "deepseek-chat"
    assert "远程模型提炼完毕" in result
