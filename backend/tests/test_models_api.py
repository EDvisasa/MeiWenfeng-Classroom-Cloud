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

def test_custom_tokens_lock():
    """Test that setting a custom max_context_tokens locks the value and sets is_custom_tokens."""
    # 1. Create a model with custom tokens
    create_res = client.post("/api/chat/models/create", json={
        "name": "custom-test-model",
        "protocol": "openai",
        "base_url": "http://localhost:8080",
        "api_key": "",
        "max_context_tokens": 131072
    })
    assert create_res.status_code == 200
    model_id = create_res.json()["id"]

    # 2. Verify it is saved correctly and is_custom_tokens is 1
    verify_res = client.get("/api/chat/models")
    models = verify_res.json()
    custom_model = next((m for m in models if m["id"] == model_id), None)
    assert custom_model is not None
    assert custom_model["max_context_tokens"] == 131072
    assert custom_model["is_custom_tokens"] == 1

    # 3. Explicitly trigger detection task directly
    from backend.routers.models import detect_and_update_max_tokens
    detect_and_update_max_tokens(model_id)

    # 4. Verify the value wasn't overwritten
    verify_res2 = client.get("/api/chat/models")
    custom_model2 = next((m for m in verify_res2.json() if m["id"] == model_id), None)
    assert custom_model2["max_context_tokens"] == 131072, "Custom value should not be overwritten"
    
    # 5. Clean up
    from backend.database import get_db_connection
    conn = get_db_connection()
    conn.execute("DELETE FROM model_config WHERE id = ?", (model_id,))
    conn.commit()
    conn.close()
