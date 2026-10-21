import pytest
from unittest.mock import patch, MagicMock
from backend.services.memory_decay import generate_summary

def test_generate_summary_preserves_local_model_routing():
    """
    TDD Test: Verify that generate_summary does not hijack local OpenAI-compatible models
    (such as ninfer+kvmem on http://127.0.0.1:8091/v1/) to remote AIRP/DeepSeek URLs.
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
    mock_choice.message.content = "【时间跨度】：今日\n【面向对象】：测试\n【详细纪要】：测试纪要。\n【学情洞察】：无。"
    mock_response.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("backend.services.memory_decay.get_active_model", return_value=mock_local_model), \
         patch("backend.services.memory_decay.OpenAI", return_value=mock_client) as mock_openai_cls, \
         patch("time.sleep"):
        result = generate_summary("这是一段测试对话内容", "请生成纪要")

    # Verify OpenAI was initialized with the LOCAL base_url, NOT https://gcli.ggchan.dev/v1
    mock_openai_cls.assert_called_once_with(
        api_key="no-key-required",
        base_url="http://127.0.0.1:8091/v1/"
    )

    # Verify the completion request was sent with the active model's selected_model_id
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "qwen3.8-27b"
    assert "测试纪要" in result
