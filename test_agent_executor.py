import pytest
from unittest.mock import patch, MagicMock
from backend.services.agent_tools import AgentExecutor

# --- Mock LLM Client for testing ---
class MockLLMClient:
    def __init__(self, responses):
        """
        responses: list of lists of dicts.
        Each outer list represents one iteration.
        Each inner list represents the chunks yielded by the LLM in that iteration.
        """
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
            # Fallback if it loops too many times
            yield {"type": "text", "text": "End of mock responses."}

# --- Mock Tool Registry ---
class MockTool:
    def execute(self, params):
        if params.get("command") == "echo hello":
            return "hello"
        return "mock result"

mock_registry = {"execute_bash": MockTool()}


def test_agent_executor_no_tools():
    # LLM just returns normal text, no tools
    mock_llm = MockLLMClient([
        [{"type": "text", "text": "Hello world!"}]
    ])

    executor = AgentExecutor(llm_client=mock_llm, max_iterations=3)
    messages = [{"role": "user", "content": "Hi"}]

    results = list(executor.run(messages))

    # It should yield the text char by char, so we combine it
    combined = "".join([r["text"] for r in results if r.get("type") == "text"])
    assert combined == "Hello world!"
    assert mock_llm.iteration_count == 1


def test_agent_executor_with_tool_call():
    # Iteration 1: LLM thinks, then calls a tool
    iter1 = [
        {"type": "thinking", "text": "I should run a command."},
        {"type": "text", "text": "Here I go: <call_tool name=\"execute_bash\"><command>echo hello</command></call_tool>"}
    ]
    # Iteration 2: LLM sees the result and answers
    iter2 = [
        {"type": "text", "text": "The command returned hello."}
    ]

    mock_llm = MockLLMClient([iter1, iter2])

    with patch("backend.services.agent_tools.TOOL_REGISTRY", mock_registry):
        executor = AgentExecutor(llm_client=mock_llm, max_iterations=3)
        messages = [{"role": "user", "content": "Run echo hello"}]

        results = list(executor.run(messages))

        # Verify the sequence of yielded events
        types = [r.get("type") for r in results if isinstance(r, dict)]

        # Should see thinking, text (the part before the tool or intercepted text),
        # tool_start, tool_output, tool_end, and finally text from iter2
        assert "thinking" in types
        assert "tool_start" in types
        assert "tool_output" in types
        assert "tool_end" in types

        # Verify the tool output was correct
        tool_outputs = [r.get("text") for r in results if isinstance(r, dict) and r.get("type") == "tool_output"]
        assert tool_outputs[0] == "hello"

        # Verify the LLM was called twice
        assert mock_llm.iteration_count == 2

        # Verify the messages passed to iter2 contained the tool result
        last_request_msgs = mock_llm.received_messages[-1]
        assert last_request_msgs[-2]["role"] == "assistant"
        assert "<call_tool" in last_request_msgs[-2]["content"]
        assert last_request_msgs[-1]["role"] == "user"
        assert "hello" in last_request_msgs[-1]["content"]

