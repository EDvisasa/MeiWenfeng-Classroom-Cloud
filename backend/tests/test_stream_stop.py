import pytest
import threading
import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.stream_registry import StreamRegistry, StreamController, stream_registry
from backend.services.agent_executor import OpenAILLMClient

client = TestClient(app)

def test_stream_controller_lifecycle():
    controller = StreamController(session_id="test-session-1")
    assert not controller.is_aborted

    mock_stream = MagicMock()
    controller.set_stream(mock_stream)

    # Aborting closes the stream and sets flag
    was_aborted = controller.abort()
    assert was_aborted is True
    assert controller.is_aborted is True
    mock_stream.close.assert_called_once()

    # Second abort returns False since stream already closed
    assert controller.abort() is False

def test_stream_controller_abort_before_stream_set():
    controller = StreamController(session_id="test-session-pre-abort")
    controller.abort()
    assert controller.is_aborted is True

    # If stream is set after abort was signaled, it immediately closes it
    mock_stream = MagicMock()
    controller.set_stream(mock_stream)
    mock_stream.close.assert_called_once()

def test_stream_registry_acquire_release():
    registry = StreamRegistry()
    ctrl1 = registry.acquire("sess-a")
    assert registry.get("sess-a") is ctrl1

    # Acquiring again for same session aborts previous controller
    ctrl2 = registry.acquire("sess-a")
    assert ctrl1.is_aborted is True
    assert registry.get("sess-a") is ctrl2

    registry.release("sess-a", ctrl2)
    assert registry.get("sess-a") is None

def test_stream_registry_abort():
    registry = StreamRegistry()
    ctrl = registry.acquire("sess-b")
    mock_stream = MagicMock()
    ctrl.set_stream(mock_stream)

    res = registry.abort("sess-b")
    assert res is True
    assert ctrl.is_aborted is True
    mock_stream.close.assert_called_once()
    assert registry.get("sess-b") is None

    # Aborting non-existent session returns False
    assert registry.abort("sess-non-existent") is False

def test_api_chat_stop_endpoint():
    # 1. Register a fake active stream
    controller = stream_registry.acquire("active-stop-session")
    mock_stream = MagicMock()
    controller.set_stream(mock_stream)

    # 2. Call POST /api/chat/stop
    response = client.post("/api/chat/stop", json={"session_id": "active-stop-session"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stopped"
    assert data["session_id"] == "active-stop-session"
    assert controller.is_aborted is True
    mock_stream.close.assert_called_once()

    # 3. Call again on idle session
    response2 = client.post("/api/chat/stop", json={"session_id": "active-stop-session"})
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["status"] == "idle"

def test_openai_llm_client_finally_closes_stream():
    from unittest.mock import patch as _patch
    with _patch("backend.services.agent_executor.OpenAI"):
        llm_client = OpenAILLMClient(api_key="none", base_url="http://127.0.0.1:18200/v1", model_id="test")
    
    mock_response = MagicMock()
    mock_chunk1 = MagicMock()
    mock_chunk1.choices = [MagicMock()]
    mock_chunk1.choices[0].delta = MagicMock()
    mock_chunk1.choices[0].delta.content = "hello"
    mock_chunk1.choices[0].delta.reasoning_content = None
    mock_chunk1.choices[0].delta.tool_calls = None

    mock_response.__iter__.return_value = [mock_chunk1]
    llm_client.client = MagicMock()
    llm_client.client.chat.completions.create.return_value = mock_response

    controller = StreamController(session_id="test-client-session")
    chunks = list(llm_client.stream_completion([{"role": "user", "content": "hi"}], stream_controller=controller))

    assert len(chunks) == 1
    assert chunks[0]["text"] == "hello"
    # Guaranteed close via finally
    mock_response.close.assert_called_once()

def test_openai_llm_client_early_exit_on_abort():
    from unittest.mock import patch as _patch
    with _patch("backend.services.agent_executor.OpenAI"):
        llm_client = OpenAILLMClient(api_key="none", base_url="http://127.0.0.1:18200/v1", model_id="test")
    
    controller = StreamController(session_id="test-abort-session")

    def generator_chunks():
        for i in range(10):
            if i == 2:
                controller.abort()
            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta = MagicMock()
            mock_chunk.choices[0].delta.content = f"word_{i}"
            mock_chunk.choices[0].delta.reasoning_content = None
            mock_chunk.choices[0].delta.tool_calls = None
            yield mock_chunk

    mock_response = MagicMock()
    mock_response.__iter__.side_effect = generator_chunks
    llm_client.client = MagicMock()
    llm_client.client.chat.completions.create.return_value = mock_response

    chunks = list(llm_client.stream_completion([{"role": "user", "content": "hi"}], stream_controller=controller))

    # Should have stopped early
    assert len(chunks) <= 3
    mock_response.close.assert_called()
