import os
import sys
import unittest.mock as mock

# Ensure backend can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.model_router import stream_chat
import openai

def test_prompt():
    print("--- STARTING TEST ---")
    
    # We will mock the OpenAI client to intercept the messages
    original_openai = openai.OpenAI
    
    class MockCompletions:
        def create(self, **kwargs):
            messages = kwargs.get("messages", [])
            print("==== INTERCEPTED MESSAGES ARRAY SENT TO LLM ====")
            for i, msg in enumerate(messages):
                print(f"\n[Message {i}] Role: {msg['role']}")
                content = msg.get('content', '')
                print(content)
            print("=================================================")
            
            # Yield a fake chunk to satisfy the generator
            class FakeDelta:
                content = "Fake response"
                reasoning_content = ""
            class FakeChoice:
                delta = FakeDelta()
            class FakeChunk:
                choices = [FakeChoice()]
                
            yield FakeChunk()
            
    class MockChat:
        completions = MockCompletions()
        
    class MockClient:
        def __init__(self, *args, **kwargs):
            pass
        chat = MockChat()

    with mock.patch('services.model_router.OpenAI', MockClient):
        # Call stream_chat with a basic system prompt and user message
        generator = stream_chat(
            messages=[{"role": "user", "content": "What are your rules?"}],
            system_prompt="Base System Prompt: You are a fox demon.",
            max_tokens=100
        )
        
        # Consume the generator to trigger the mock
        for chunk in generator:
            pass

    print("--- TEST COMPLETE ---")

if __name__ == "__main__":
    test_prompt()
