import asyncio
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.model_router import stream_chat

def main():
    messages = [
        {"role": "user", "content": "现在是什么时间？过了几点？请不要使用工具，直接告诉我。"}
    ]
    
    from datetime import datetime
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    system_prompt = f"当前用户系统真实时间是：{time_str}\n\n你是一个时间感知测试机器人，回答简短。"

    print(f"Testing with system time injected: {time_str}")
    print("AI Response stream:")
    
    response_chunks = stream_chat(messages, system_prompt)
    for chunk in response_chunks:
        if isinstance(chunk, dict) and chunk.get("type") == "text":
            print(chunk.get("text"), end="")
        elif isinstance(chunk, dict) and chunk.get("type") == "thinking":
            print(f"[Thinking: {chunk.get('text')}]", end="")
        else:
            print(f"\n[Raw Chunk]: {chunk}\n")
            
    print("\n\nTest finished.")

if __name__ == "__main__":
    main()
