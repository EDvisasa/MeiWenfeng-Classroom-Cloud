import json
import pytest
from backend.services.response_pipeline import ResponsePipeline
from backend.services.agent_tools import AgentExecutor, LLMClientProtocol
from backend.services.action_registry import action_registry
from backend.services.model_router import stream_chat

class FakeLLMClient(LLMClientProtocol):
    def __init__(self, output_text):
        self.output_text = output_text
        
    def stream_completion(self, messages, **kwargs):
        for i in range(0, len(self.output_text), 3):
            yield {"type": "text", "text": self.output_text[i:i+3]}

def test_simulate_llm_logic():
    fake_output = "Normal chat. <inner_thought>这黏人的小家伙，真想直接挤进浴室跟他一块儿洗……算了算了，他熬夜太累了</inner_thought><property_update affection_delta=\"+1\" refractory_delta=\"-1\" />"
    
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
    assert "<inner_thought>" in result
    assert "<property_update" not in result
    assert "property_update" in pipeline.interceptor.intercepted_data

def test_truncation_logic():
    messages = [
        {"role": "user", "content": "你会等我么，宝宝。想你..."}
    ]
    system_prompt = "You are a roleplay character. Use <property_update affection_delta=\"+1\" refractory_delta=\"-1\" /> in your response."
    
    # max_tokens=200 forces early truncation to test robustness
    stream = stream_chat(messages, system_prompt, max_tokens=200)
    
    pipeline = ResponsePipeline(registry=action_registry)
    
    # We just run the stream to ensure it doesn't crash
    result_chunks = []
    for chunk in pipeline.process_stream(stream):
        result_chunks.append(chunk)
        
    assert len(result_chunks) > 0
