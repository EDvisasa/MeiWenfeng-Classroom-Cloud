import os
import tempfile
import pytest
from backend.services.agent_tools import ReadFileTool, BashTool, TOOL_REGISTRY

def test_read_file_tool_reads_file_content():
    """Test that ReadFileTool can successfully read a standard file."""
    tool = ReadFileTool()
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        f.write("Hello, World!\nThis is a test file.")
        temp_path = f.name
        
    try:
        result = tool.execute({"path": temp_path})
        assert "Hello, World!" in result
        assert "This is a test file." in result
    finally:
        os.unlink(temp_path)

def test_read_file_tool_respects_line_boundaries():
    """Test that ReadFileTool respects start_line and end_line parameters."""
    tool = ReadFileTool()
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        for i in range(1, 11): # 10 lines
            f.write(f"Line {i}\n")
        temp_path = f.name
        
    try:
        result = tool.execute({
            "path": temp_path,
            "start_line": "3",
            "end_line": "6"
        })
        
        # Verify correct lines
        assert "Line 3" in result
        assert "Line 6" in result
        
        # Verify excluded lines
        assert "Line 2" not in result
        assert "Line 7" not in result
    finally:
        os.unlink(temp_path)

def test_read_file_tool_handles_missing_file():
    """Test that ReadFileTool returns an appropriate error for missing files."""
    tool = ReadFileTool()
    result = tool.execute({"path": "/path/does/not/exist/12345.txt"})
    assert "[Error] File not found:" in result

def test_read_file_tool_truncates_large_files():
    """Test that ReadFileTool truncates files larger than 800 lines."""
    tool = ReadFileTool()
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        for i in range(1000):
            f.write(f"Line {i}\n")
        temp_path = f.name
        
    try:
        result = tool.execute({"path": temp_path})
        # Check that it contains line 0 and line 799
        assert "Line 0" in result
        assert "Line 799" in result
        # Check that it DOES NOT contain line 800
        assert "Line 800" not in result
        # Check the warning is appended
        assert "[Warning: Output truncated" in result
    finally:
        os.unlink(temp_path)

def test_bash_tool_executes_commands():
    """Test that BashTool can execute basic commands and capture output."""
    tool = BashTool()
    # Use a safe, cross-platform-ish command or specific to windows since environment is known
    result = tool.execute({"command": "echo Hello from bash"})
    assert "Hello from bash" in result

def test_tool_registry_contains_expected_tools():
    """Verify that tools are properly registered and retrievable."""
    assert "read_file" in TOOL_REGISTRY
    assert "execute_bash" in TOOL_REGISTRY
    assert isinstance(TOOL_REGISTRY["read_file"], ReadFileTool)
    assert isinstance(TOOL_REGISTRY["execute_bash"], BashTool)
