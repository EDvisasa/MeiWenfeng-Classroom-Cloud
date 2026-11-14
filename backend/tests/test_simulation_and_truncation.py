import json
import pytest
from unittest.mock import patch
from backend.services.response_pipeline import ResponsePipeline
from backend.services.agent_executor import AgentExecutor, LLMClientProtocol
from backend.services.action_registry import action_registry
from backend.services.model_router import stream_chat

class FakeLLMClient(LLMClientProtocol):
    def __init__(self, output_text):
        self.output_text = output_text
        self.seen_max_tokens = None

    def stream_completion(self, messages, **kwargs):
        self.seen_max_tokens = kwargs.get("max_tokens")
        for i in range(0, len(self.output_text), 3):
            yield {"type": "text", "text": self.output_text[i:i+3]}

def test_simulate_llm_logic():
    fake_output = "Normal chat. <monologue>这黏人的小家伙，真想直接挤进浴室跟他一块儿洗……算了算了，他熬夜太累了</monologue><property_update affection_delta=\"+1\" refractory_delta=\"-1\" />"
    
    client = FakeLLMClient(fake_output)
    executor = AgentExecutor(llm_client=client, max_iterations=1)
    
    pipeline = ResponsePipeline()
    pipeline.interceptor.target_tags = {"property_update"}
    
    stream = pipeline.process_stream(executor.run([]))
    
    result = ""
    for chunk in stream:
        if chunk.startswith("data: "):
            try:
                data = json.loads(chunk[6:].strip())
                if isinstance(data, dict) and "text" in data:
                    result += data["text"]
            except:
                pass
                
    assert "Normal chat." in result
    assert "<monologue>" in result
    assert "<property_update" in result
    assert "property_update" in pipeline.interceptor.intercepted_data

def test_truncation_logic(mock_rag_client):
    messages = [
        {"role": "user", "content": "你会等我么，宝宝。想你..."}
    ]
    system_prompt = "You are a roleplay character. Use <property_update affection_delta=\"+1\" refractory_delta=\"-1\" /> in your response."

    truncated_output = "我会一直等你的，别太熬夜了。<property_update affection_delta=\"+1\" refractory_delta=\"-1\""
    fake_client = FakeLLMClient(truncated_output)

    # max_tokens=200 forces early truncation; mock OpenAILLMClient so pytest stays offline
    with patch("backend.services.model_router.OpenAILLMClient", return_value=fake_client):
        stream = stream_chat(messages, system_prompt, max_tokens=200)
        pipeline = ResponsePipeline(registry=action_registry, dry_run=True)

        result_chunks = list(pipeline.process_stream(stream))

    assert fake_client.seen_max_tokens == 200
    assert len(result_chunks) > 0
    combined = "".join(
        json.loads(c[6:].strip()).get("text", "")
        for c in result_chunks
        if c.startswith("data: ") and not c.startswith("data: [DONE]")
    )
    assert "我会一直等你的" in combined
