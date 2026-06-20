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
    assert "replace_file_content" in TOOL_REGISTRY
    assert isinstance(TOOL_REGISTRY["read_file"], ReadFileTool)
    assert isinstance(TOOL_REGISTRY["execute_bash"], BashTool)

from backend.services.agent_tools import ReplaceFileContentTool

def test_replace_file_content_tool_success(tmp_path):
    """Test that ReplaceFileContentTool successfully replaces content inside the sandbox."""
    tool = ReplaceFileContentTool()
    
    # Mock the sandbox directory dynamically to the tmp_path for testing
    # We will override the execute method's sandbox_dir calculation just for this test
    # A cleaner way is to patch the os.path.dirname in the tool, but we can also just use the real sandbox dir
    
    # Actually, since the sandbox is hardcoded to project_root/docs/sandbox,
    # let's create a temporary file in the REAL docs/sandbox to test it safely.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sandbox_dir = os.path.abspath(os.path.join(project_root, "docs", "sandbox"))
    os.makedirs(sandbox_dir, exist_ok=True)
    
    test_file = os.path.join(sandbox_dir, "test_temp_replace.py")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def func():\n    return 'old'\n")
        
    try:
        result = tool.execute({
            "path": test_file,
            "old_content": "return 'old'",
            "new_content": "return 'new'"
        })
        
        assert "[Success]" in result
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "return 'new'" in content
        assert "return 'old'" not in content
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

def test_replace_file_content_tool_blocks_outside_sandbox():
    """Test that ReplaceFileContentTool blocks edits outside the docs/sandbox directory."""
    tool = ReplaceFileContentTool()
    
    # Try to edit a file outside sandbox, e.g., the test file itself
    test_file = os.path.abspath(__file__)
    
    result = tool.execute({
        "path": test_file,
        "old_content": "def test_tool_registry",
        "new_content": "def hacked_tool_registry"
    })
    
    assert "GUARDRAIL BLOCKED: Sandbox boundary violation" in result

def test_replace_file_content_tool_blocks_directory_prefix_bypass():
    """Test that ReplaceFileContentTool blocks directory prefix bypass (e.g., docs/sandbox_hacked)."""
    tool = ReplaceFileContentTool()
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    hacked_sandbox_dir = os.path.abspath(os.path.join(project_root, "docs", "sandbox_hacked"))
    
    result = tool.execute({
        "path": os.path.join(hacked_sandbox_dir, "test.py"),
        "old_content": "old",
        "new_content": "new"
    })
    
    assert "GUARDRAIL BLOCKED: Sandbox boundary violation" in result
