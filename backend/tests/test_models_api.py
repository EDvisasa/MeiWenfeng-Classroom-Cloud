import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_get_models_includes_max_tokens():
    """Test the /api/chat/models endpoint returns max_context_tokens."""
    response = client.get("/api/chat/models")
    
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
    if len(models) > 0:
        first_model = models[0]
        assert "id" in first_model
        assert "name" in first_model
        assert "max_context_tokens" in first_model

def test_switch_model_endpoint():
    """Test the /api/chat/switch_model endpoint."""
    response = client.get("/api/chat/models")
    models = response.json()
    if len(models) > 0:
        model_id = models[0]["id"]
        switch_res = client.post("/api/chat/switch_model", json={"id": model_id})
        assert switch_res.status_code == 200, "Switching model should succeed and synchronously detect tokens"
        data = switch_res.json()
        assert "active_model" in data
        
        # Verify that max_context_tokens can be fetched immediately after
        verify_res = client.get("/api/chat/models")
        assert verify_res.status_code == 200
        updated_models = verify_res.json()
        updated_model = next((m for m in updated_models if m["id"] == model_id), None)
        assert updated_model is not None
        assert "max_context_tokens" in updated_model
        assert updated_model["max_context_tokens"] >= 8192, "Should have correctly detected or fallback to tokens"
