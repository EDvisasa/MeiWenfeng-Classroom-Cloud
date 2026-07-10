import os
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.openclaw_client import send_to_openclaw, check_openclaw_status, clear_openclaw_status_cache

client = TestClient(app)

def test_send_to_openclaw_mock():
    """Test that send_to_openclaw correctly formats command and handles success response."""
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"reply": "Hello from BaiTizi"}'
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        res = send_to_openclaw("Hello Tizi", agent="main", timeout=30)
        assert res["status"] == "success"
        assert res["data"] == {"reply": "Hello from BaiTizi"}
        
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["wsl", "-d", "OpenClawGateway", "-u", "openclaw", "--", "openclaw", "agent", "--agent", "main", "--message", "Hello Tizi", "--json"]

def test_send_to_openclaw_empty():
    """Test that sending an empty message returns an error without running subprocess."""
    res = send_to_openclaw("   ")
    assert res["status"] == "error"
    assert "empty" in res["message"].lower()

def test_openclaw_sandbox_write_list_read():
    """Test the complete cycle of writing, listing, and reading a sandbox file via OpenClaw REST API."""
    test_fname = "test_openclaw_bridge.txt"
    test_content = "Bridge integration test content."
    
    # 1. Write file
    w_res = client.post("/api/openclaw/sandbox/write", json={"filename": test_fname, "content": test_content})
    assert w_res.status_code == 200, w_res.text
    assert w_res.json()["status"] == "success"
    
    # 2. List files
    l_res = client.get("/api/openclaw/sandbox/list")
    assert l_res.status_code == 200
    files = l_res.json()["files"]
    assert any(test_fname in f for f in files)
    
    # 3. Read file
    r_res = client.post("/api/openclaw/sandbox/read", json={"filename": test_fname})
    assert r_res.status_code == 200
    assert r_res.json()["content"] == test_content
    
    # Clean up
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sandbox_dir = os.path.realpath(os.path.join(project_root, "data", "materials", "Sandbox"))
    file_path = os.path.join(sandbox_dir, test_fname)
    if os.path.exists(file_path):
        os.remove(file_path)

def test_openclaw_sandbox_guardrail_violation():
    """Test that attempting to access files outside Sandbox directory triggers HTTP 403."""
    # Attempt directory traversal write
    w_res = client.post("/api/openclaw/sandbox/write", json={"filename": "../../secret_test.txt", "content": "hacked"})
    assert w_res.status_code == 403
    assert "GUARDRAIL BLOCKED" in w_res.json()["detail"]

    # Attempt directory traversal read
    r_res = client.post("/api/openclaw/sandbox/read", json={"filename": "../../../Windows/win.ini"})
    assert r_res.status_code == 403
    assert "GUARDRAIL BLOCKED" in r_res.json()["detail"]

def test_mcp_tools_exposure():
    """Test that MCP tools in mcp_server can be invoked and return expected strings."""
    from backend.mcp_server import sandbox_write, sandbox_read, sandbox_list
    
    test_fname = "test_mcp_bridge.txt"
    test_content = "MCP bridge tool content."
    
    # Write via MCP tool
    w_msg = sandbox_write(test_fname, test_content)
    assert "Successfully wrote" in w_msg
    
    # List via MCP tool
    l_msg = sandbox_list()
    assert test_fname in l_msg
    
    # Read via MCP tool
    r_msg = sandbox_read(test_fname)
    assert r_msg == test_content
    
    # Clean up
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sandbox_dir = os.path.realpath(os.path.join(project_root, "data", "materials", "Sandbox"))
    file_path = os.path.join(sandbox_dir, test_fname)
    if os.path.exists(file_path):
        os.remove(file_path)

def test_check_openclaw_status_online():
    """Test check_openclaw_status returns online=True when WSL command succeeds."""
    clear_openclaw_status_cache()
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OpenClaw CLI version 1.2.0"
        mock_run.return_value = mock_result

        res = check_openclaw_status(timeout=3, ttl=5)
        assert res["online"] is True
        assert "ONLINE" in res["status_str"]

def test_check_openclaw_status_offline():
    """Test check_openclaw_status returns online=False when CLI fails or throws error."""
    clear_openclaw_status_cache()
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Gateway not found"
        mock_run.return_value = mock_result

        res = check_openclaw_status(timeout=3, ttl=5)
        assert res["online"] is False
        assert "OFFLINE" in res["status_str"]

def test_check_openclaw_status_ttl_cache():
    """Test check_openclaw_status caches result for ttl seconds."""
    clear_openclaw_status_cache()
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "OpenClaw CLI version 1.2.0"
        mock_run.return_value = mock_result

        first = check_openclaw_status(timeout=3, ttl=5)
        second = check_openclaw_status(timeout=3, ttl=5)
        assert first == second
        # subprocess.run should only be called once because of TTL cache
        assert mock_run.call_count == 1


def test_openclaw_agent_tool_offline():
    """Test OpenClawAgentTool graceful offline response when check_openclaw_status reports offline."""
    from backend.services.agent_tools import TOOL_REGISTRY
    tool = TOOL_REGISTRY.get("call_openclaw_agent")
    assert tool is not None

    clear_openclaw_status_cache()
    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "WSL offline"
        mock_run.return_value = mock_result

        res = tool.execute({"task_message": "test task"})
        assert "[Status: Offline]" in res
        assert "离线或未运行" in res


def test_openclaw_agent_tool_online():
    """Test OpenClawAgentTool invokes send_to_openclaw when check_openclaw_status reports online."""
    from backend.services.agent_tools import TOOL_REGISTRY
    tool = TOOL_REGISTRY.get("call_openclaw_agent")
    assert tool is not None

    clear_openclaw_status_cache()
    with patch("subprocess.run") as mock_run:
        # First call is for check_openclaw_status, second call is for send_to_openclaw
        status_mock = MagicMock()
        status_mock.returncode = 0
        status_mock.stdout = "OpenClaw CLI version 1.2.0"

        send_mock = MagicMock()
        send_mock.returncode = 0
        send_mock.stdout = '{"status": "ok"}'

        mock_run.side_effect = [status_mock, send_mock]

        res = tool.execute({"task_message": "test task"})
        assert "success" in res
        assert "ok" in res


