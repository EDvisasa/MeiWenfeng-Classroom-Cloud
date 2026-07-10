import os
import pytest
from backend.services.sandbox_vfs import SandboxVFS, SandboxVFSError

def test_sandbox_vfs_safe_write_read_list(tmp_path):
    """Test standard write, read, and list operations within SandboxVFS."""
    vfs = SandboxVFS(sandbox_root=str(tmp_path))
    
    # Write file
    safe_path = vfs.write_file("sub/hello.txt", "Hello VFS!")
    assert os.path.exists(safe_path)
    
    # Read file
    content = vfs.read_file("sub/hello.txt")
    assert content == "Hello VFS!"
    
    # List files
    files = vfs.list_files()
    assert "sub/hello.txt" in files


def test_sandbox_vfs_blocks_traversal_attempts(tmp_path):
    """Test that SandboxVFS raises SandboxVFSError on any path traversal attempt."""
    vfs = SandboxVFS(sandbox_root=str(tmp_path))
    
    with pytest.raises(SandboxVFSError, match="GUARDRAIL BLOCKED"):
        vfs.resolve_safe_path("../../etc/passwd")
        
    with pytest.raises(SandboxVFSError, match="GUARDRAIL BLOCKED"):
        vfs.write_file("../secret.txt", "hacked")

    with pytest.raises(SandboxVFSError, match="GUARDRAIL BLOCKED"):
        vfs.read_file("sub/../../boot.ini")


def test_sandbox_vfs_read_nonexistent_file(tmp_path):
    """Test reading a nonexistent file inside sandbox raises FileNotFoundError."""
    vfs = SandboxVFS(sandbox_root=str(tmp_path))
    with pytest.raises(FileNotFoundError):
        vfs.read_file("nonexistent.txt")
