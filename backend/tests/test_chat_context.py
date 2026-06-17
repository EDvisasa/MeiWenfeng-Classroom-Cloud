import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_system_context_endpoint():
    """Test the /api/chat/system_context endpoint calculates tokens properly."""
    payload = {
        "messages": [
            {"role": "user", "content": "Hello, Mei Wenfeng"}
        ],
        "persona_type": "simplified",
        "current_file_path": "",
        "cursor_line": 0,
        "custom_max_tokens": 8192
    }
    
    response = client.post("/api/chat/system_context", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "baseSystemTokens" in data
    # Tokens should be greater than 0 since the system prompt has some baseline content
    assert data["baseSystemTokens"] > 0
    assert isinstance(data["baseSystemTokens"], int)
