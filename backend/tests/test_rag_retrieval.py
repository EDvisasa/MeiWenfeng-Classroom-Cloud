import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.routers.chat import send_message, ChatRequest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from backend.routers.chat import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_long_file_rag_retrieval_uses_original_message(tmp_path):
    """
    Test that when @current_file expands a long file, the RAG retrieval
    still uses the short, original message, preventing ChromaDB crash or poor search results.
    """
    # Create a fake file
    fake_file = tmp_path / "fake_file.txt"
    fake_file.write_text("This is a very long file content. " * 500, encoding="utf-8")
    
    # Payload simulating user sending "@current_file"
    original_msg = "宝贝，6-2干了啥？ @current_file"
    payload = {
        "messages": [{"role": "user", "content": original_msg}],
        "persona_type": "simplified",
        "current_file_path": str(fake_file),
        "cursor_line": 1
    }

    # Mock the RAG client
    with patch("backend.routers.chat.get_rag_client") as mock_get_rag:
        
        mock_rag_instance = MagicMock()
        mock_get_rag.return_value = mock_rag_instance
        
        # We don't care about the actual streaming output, just the arguments passed to retrieve
        try:
            list(send_message(ChatRequest(**payload)))
        except Exception:
            pass # Ignore streaming or DB errors
            
        # The rag client retrieve should be called with the original message, NOT the expanded one!
        # Because we only want to search the vector db with "宝贝，6-2干了啥？ @current_file", not 5000 characters of text!
        assert mock_rag_instance.retrieve.call_count >= 2
        args, kwargs = mock_rag_instance.retrieve.call_args_list[0]
        
        # This will currently FAIL because chat.py passes last_user_msg (which includes <file_content>...)
        assert "<file_content" not in args[0], "RAG retrieval query contains expanded file content!"
        assert args[0] == original_msg, f"Expected '{original_msg}', got '{args[0][:100]}...'"
