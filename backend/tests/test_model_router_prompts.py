import pytest
from unittest import mock
from backend.services.model_router import stream_chat
from datetime import datetime

def test_stream_chat_prompt_assembly():
    """
    Test that stream_chat correctly prepends the system prompt to the messages array,
    acting as a guard against dropping critical personas or tool definitions.
    """
    # Arrange
    messages = [{"role": "user", "content": "What are your rules?"}]
    system_prompt = "Base System Prompt: You are a fox demon."
    
    # We mock AgentExecutor because we only want to test prompt assembly, not execution
    with mock.patch('backend.services.model_router.AgentExecutor') as MockExecutor:
        # Setup mock return for run()
        mock_instance = MockExecutor.return_value
        mock_instance.run.return_value = [{"type": "text", "text": "mocked response"}]
        
        # Act
        generator = stream_chat(messages=messages, system_prompt=system_prompt, max_tokens=100)
        list(generator) # Consume generator
        
        # Assert
        mock_instance.run.assert_called_once()
        args, kwargs = mock_instance.run.call_args
        formatted_messages = args[0]
        
        # Verify system prompt is at index 0
        assert len(formatted_messages) == 2
        assert formatted_messages[0]["role"] == "system"
        assert formatted_messages[0]["content"] == system_prompt
        assert formatted_messages[1]["role"] == "user"
        assert formatted_messages[1]["content"] == "What are your rules?"


def test_stream_chat_time_perception_injection():
    """
    Test that system time can be correctly injected and passed through to the AgentExecutor.
    """
    # Arrange
    messages = [{"role": "user", "content": "现在几点？"}]
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    system_prompt = f"当前时间：{time_str}"
    
    with mock.patch('backend.services.model_router.AgentExecutor') as MockExecutor:
        mock_instance = MockExecutor.return_value
        mock_instance.run.return_value = [{"type": "text", "text": "mocked response"}]
        
        # Act
        generator = stream_chat(messages=messages, system_prompt=system_prompt, max_tokens=100)
        list(generator)
        
        # Assert
        mock_instance.run.assert_called_once()
        formatted_messages = mock_instance.run.call_args[0][0]
        assert time_str in formatted_messages[0]["content"]
