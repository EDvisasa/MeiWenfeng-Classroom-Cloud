import os
from typing import List, Optional

class SandboxVFSError(PermissionError):
    """Raised when an operation violates sandbox path boundary guardrails."""
    pass


class SandboxVFS:
    """
    Deep module providing unified, boundary-enforced VFS operations inside the workspace Sandbox.
    Single Source of Truth (SSOT) for physical directory traversal prevention via os.path.commonpath.
    """
    def __init__(self, sandbox_root: Optional[str] = None):
        if sandbox_root is None:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            sandbox_root = os.path.join(project_root, "data", "materials", "Sandbox")
        self.sandbox_root = os.path.realpath(sandbox_root)
        os.makedirs(self.sandbox_root, exist_ok=True)

    def resolve_safe_path(self, relative_path: str) -> str:
        """
        Resolve relative_path securely against sandbox_root.
        Raises SandboxVFSError if the resolved path attempts to traverse outside sandbox_root.
        """
        if not relative_path or not relative_path.strip():
            raise SandboxVFSError("Invalid empty path provided to SandboxVFS.")

        # Strip leading slash/backslash to ensure os.path.join treats it as relative
        clean_rel = relative_path.lstrip("/\\")
        target_path = os.path.realpath(os.path.join(self.sandbox_root, clean_rel))

        # Core boundary guardrail SSOT
        common = os.path.commonpath([self.sandbox_root, target_path])
        if common != self.sandbox_root:
            raise SandboxVFSError(f"GUARDRAIL BLOCKED: Access violation outside sandbox root ({relative_path})")

        return target_path

    def read_file(self, relative_path: str, encoding: str = "utf-8") -> str:
        safe_path = self.resolve_safe_path(relative_path)
        if not os.path.exists(safe_path) or not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File not found in sandbox: {relative_path}")
        with open(safe_path, "r", encoding=encoding, errors="replace") as f:
            return f.read()

    def write_file(self, relative_path: str, content: str, encoding: str = "utf-8") -> str:
        safe_path = self.resolve_safe_path(relative_path)
        parent_dir = os.path.dirname(safe_path)
        os.makedirs(parent_dir, exist_ok=True)
        with open(safe_path, "w", encoding=encoding) as f:
            f.write(content)
        return safe_path

    def list_files(self) -> List[str]:
        result = []
        for root, _, files in os.walk(self.sandbox_root):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.sandbox_root)
                result.append(rel_path.replace("\\", "/"))
        return sorted(result)

# Global singleton instance for system-wide reuse
sandbox_vfs = SandboxVFS()
