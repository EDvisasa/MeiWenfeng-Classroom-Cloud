import pytest
from pydantic import ValidationError
from backend.routers.chat import ChatRequest, Message

def test_chat_request_validation():
    # Test that valid complete data passes
    valid_data = {
        "messages": [{"role": "user", "content": "hello", "timestamp": "123"}],
        "persona_type": "simplified",
        "current_file_path": "/path/to/file.js",
        "cursor_line": 264,
        "custom_max_tokens": 8192
    }
    req = ChatRequest.model_validate(valid_data)
    assert req.cursor_line == 264

def test_chat_request_validation_with_nulls():
    # Test that Pydantic V2 correctly handles explicitly passed null values (None)
    # for optional fields without raising 422 Unprocessable Content.
    null_data = {
        "messages": [{"role": "user", "content": None, "timestamp": None}],
        "persona_type": None,
        "current_file_path": None,
        "cursor_line": None,
        "custom_max_tokens": None
    }
    
    req = ChatRequest.model_validate(null_data)
    
    # Assert that fields are properly defaulted or set to None
    assert req.persona_type is None
    assert req.current_file_path is None
    assert req.cursor_line is None
    assert req.custom_max_tokens is None
    assert req.messages[0].content is None
    assert req.messages[0].timestamp is None
