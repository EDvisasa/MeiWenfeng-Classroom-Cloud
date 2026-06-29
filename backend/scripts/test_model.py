import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.services.model_router import get_active_model
from backend.services.agent_executor import OpenAILLMClient, AgentExecutor
from backend.services.prompts import get_system_prompt

def test_model():
    print("Using LM Studio server at http://10.20.0.1:1234/v1")

    llm = OpenAILLMClient(
        api_key="lm-studio",
        base_url="http://10.20.0.1:1234/v1",
        model_id="deepreinforce-ai/Ornith-1.0-9B-GGUF" # LM Studio uses the loaded model automatically, but we provide an ID
    )

    executor = AgentExecutor(llm_client=llm, max_iterations=2)

    # Simplified system prompt (without RAG/Memory text to save tokens)
    sys_prompt = get_system_prompt(50, "simplified", 50, 50, 0)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": "你能不能上网搜索今天的新闻？快用你的天网查一查！"}
    ]

    print("--- Starting Execution ---")
    for chunk in executor.run(messages, max_tokens=1024):
        chunk_type = chunk.get("type")
        if chunk_type == "text":
            print(chunk.get("text", ""), end="", flush=True)
        elif chunk_type == "thinking":
            # Just print a small indicator so it doesn't flood the console
            print(".", end="", flush=True)
        elif chunk_type == "tool_start":
            print(f"\\n[TOOL START] {chunk.get('tool_name')} - {chunk.get('command')}")
        elif chunk_type == "tool_output":
            print(f"\\n[TOOL OUTPUT] {chunk.get('text')[:200]}...")
        elif chunk_type == "tool_end":
            print(f"\\n[TOOL END]")
        elif chunk_type == "tool_calls_chunk":
            # This is intercepted by executor before it prints text
            pass
        else:
            print(f"\\n[OTHER] {chunk}")
            
    print("\\n--- Execution Complete ---")

if __name__ == "__main__":
    test_model()
