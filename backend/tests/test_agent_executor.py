import pytest
from unittest.mock import patch
from backend.services.agent_executor import AgentExecutor

class MockLLMClient:
    def __init__(self, responses):
        self.responses = responses
        self.iteration_count = 0
        self.received_messages = []

    def stream_completion(self, messages, **kwargs):
        self.received_messages.append(messages.copy())
        if self.iteration_count < len(self.responses):
            chunks = self.responses[self.iteration_count]
            self.iteration_count += 1
            for chunk in chunks:
                yield chunk
        else:
            yield {"type": "text", "text": "End of mock responses."}

class MockTool:
    name = "execute_bash"
    description = "Execute a local terminal command."
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"}
        }
    }
    def execute(self, params):
        if params.get("command") == "echo hello":
            return "hello"
        return "mock result"

mock_registry = {"execute_bash": MockTool()}

def test_agent_executor_no_tools():
    mock_llm = MockLLMClient([
        [{"type": "text", "text": "Hello world!"}]
    ])

    executor = AgentExecutor(llm_client=mock_llm, max_iterations=3)
    messages = [{"role": "user", "content": "Hi"}]

    results = list(executor.run(messages))

    combined = "".join([r["text"] for r in results if r.get("type") == "text"])
    assert combined == "Hello world!"
    assert mock_llm.iteration_count == 1

def test_agent_executor_with_tool_call():
    iter1 = [
        {"type": "thinking", "text": "I should run a command."},
        {"type": "text", "text": "Here I go:"},
        {"type": "tool_calls_chunk", "tool_calls": [
            {"index": 0, "id": "call_123", "type": "function", "function": {"name": "execute_bash", "arguments": '{"command": "echo hello"}'}}
        ]}
    ]
    iter2 = [
        {"type": "text", "text": "The command returned hello."}
    ]

    mock_llm = MockLLMClient([iter1, iter2])
    with patch("backend.services.agent_executor.TOOL_REGISTRY", mock_registry), \
         patch("backend.services.tool_engine.TOOL_REGISTRY", mock_registry):
        executor = AgentExecutor(llm_client=mock_llm, max_iterations=3)
        messages = [{"role": "user", "content": "Run echo hello"}]

        results = list(executor.run(messages))

        types = [r.get("type") for r in results if isinstance(r, dict)]

        assert "thinking" in types
        assert "tool_start" in types
        assert "tool_output" in types
        assert "tool_end" in types

        tool_outputs = [r.get("text") for r in results if isinstance(r, dict) and r.get("type") == "tool_output"]
        assert tool_outputs[0] == "hello"

        assert mock_llm.iteration_count == 2

        last_request_msgs = mock_llm.received_messages[-1]
        assert last_request_msgs[-2]["role"] == "assistant"
        assert last_request_msgs[-2].get("tool_calls")
        assert last_request_msgs[-1]["role"] == "tool"
        assert "hello" in last_request_msgs[-1]["content"]
