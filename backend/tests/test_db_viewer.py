import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_list_tables():
    response = client.get("/api/chat/db/tables")
    assert response.status_code == 200
    data = response.json()
    assert "tables" in data
    assert isinstance(data["tables"], list)
    assert len(data["tables"]) > 0

def test_get_table_data_pagination():
    # Use 'affection' or 'chat_messages' table which is always present
    tables_res = client.get("/api/chat/db/tables")
    table_name = tables_res.json()["tables"][0]

    # Test default pagination
    res_default = client.get(f"/api/chat/db/tables/{table_name}")
    assert res_default.status_code == 200
    body_default = res_default.json()
    assert "columns" in body_default
    assert "data" in body_default
    assert "total" in body_default
    assert "limit" in body_default
    assert "offset" in body_default
    assert body_default["limit"] == 200
    assert body_default["offset"] == 0
    assert isinstance(body_default["total"], int)
    assert body_default["total"] >= len(body_default["data"])

    # Test explicit limit and offset
    res_page = client.get(f"/api/chat/db/tables/{table_name}?limit=2&offset=0")
    assert res_page.status_code == 200
    body_page = res_page.json()
    assert body_page["limit"] == 2
    assert body_page["offset"] == 0
    assert len(body_page["data"]) <= 2

def test_get_table_data_not_found():
    response = client.get("/api/chat/db/tables/non_existent_table_xyz")
    assert response.status_code == 404
