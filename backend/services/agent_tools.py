import subprocess
import os

class AgentTool:
    name: str = ""
    description: str = ""

    def execute(self, params: dict) -> str:
        raise NotImplementedError()

class BashTool(AgentTool):
    name = "execute_bash"
    description = "Execute a local terminal command."

    def execute(self, params: dict) -> str:
        command = params.get("command", "")
        if not command:
            return "[Error] No command provided."
            
        # Physical Guardrails to enforce tool usage
        cmd_lower = command.strip().lower()
        if "type " in cmd_lower or "cat " in cmd_lower or cmd_lower.startswith("type") or cmd_lower.startswith("cat"):
            return "[Error] GUARDRAIL BLOCKED: You are strictly forbidden from using 'type' or 'cat' to read files in bash. You MUST use the <call_tool name=\"read_file\"> tool instead."
        if "findstr" in cmd_lower or "grep" in cmd_lower:
            return "[Error] GUARDRAIL BLOCKED: You are strictly forbidden from using 'findstr' or 'grep' in bash. You MUST use the <call_tool name=\"grep_search\"> tool instead."
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, timeout=10)
            try:
                stdout_str = result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                stdout_str = result.stdout.decode('gbk', errors='replace')
                
            try:
                stderr_str = result.stderr.decode('utf-8')
            except UnicodeDecodeError:
                stderr_str = result.stderr.decode('gbk', errors='replace')
                
            output = stdout_str + stderr_str
            if not output.strip():
                output = "[Command executed successfully with no output]"
            return output
        except subprocess.TimeoutExpired:
            return "[Error] Command timed out after 10 seconds."
        except Exception as e:
            return f"[Error] {str(e)}"

class ReadFileTool(AgentTool):
    name = "read_file"
    description = "Read the contents of a local file, optionally specifying start_line and end_line."

    def execute(self, params: dict) -> str:
        path = params.get("path", "")
        if not path:
            return "[Error] No path provided."
        
        if not os.path.exists(path):
            return f"[Error] File not found: {path}"
        
        if not os.path.isfile(path):
            return f"[Error] Path is not a file: {path}"
            
        start_line = params.get("start_line")
        end_line = params.get("end_line")
        
        try:
            if start_line is not None:
                start_line = int(start_line)
            if end_line is not None:
                end_line = int(end_line)
        except ValueError:
            return "[Error] start_line and end_line must be integers."

        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                return self._process_lines(lines, start_line, end_line, path)
        except UnicodeDecodeError:
            try:
                with open(path, 'r', encoding='gbk') as f:
                    lines = f.readlines()
                    return self._process_lines(lines, start_line, end_line, path)
            except:
                return f"[Error] Cannot read file as text: {path}"
        except Exception as e:
            return f"[Error] {str(e)}"
            
    def _process_lines(self, lines: list, start_line: int, end_line: int, path: str) -> str:
        total_lines = len(lines)
        
        s = 1 if start_line is None else max(1, start_line)
        e = total_lines if end_line is None else min(total_lines, end_line)
        
        if s > total_lines:
            return f"[Error] start_line ({s}) is beyond the end of file ({total_lines} lines)."
            
        if e < s:
            return f"[Error] end_line ({e}) cannot be before start_line ({s})."
            
        # 截取行，注意 0-indexed vs 1-indexed
        sliced_lines = lines[s-1:e]
        
        if len(sliced_lines) > 800:
            content = "".join(sliced_lines[:800])
            return content + f"\n\n[Warning: Output truncated at 800 lines to prevent context overflow. File has {total_lines} lines total.]"
            
        content = "".join(sliced_lines)
        return content

class GrepSearchTool(AgentTool):
    name = "grep_search"
    description = "Search for a query string in all text files within a directory."

    def execute(self, params: dict) -> str:
        dir_path = params.get("dir_path", "")
        query = params.get("query", "")
        if not dir_path or not query:
            return "[Error] dir_path and query are required."
        
        if not os.path.isdir(dir_path):
            return f"[Error] Directory not found: {dir_path}"
            
        results = []
        max_results = 50
        valid_exts = {'.txt', '.md', '.json', '.py', '.js', '.jsx', '.ts', '.tsx', '.html', '.css', '.csv', '.env'}
        
        for root, _, files in os.walk(dir_path):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in valid_exts:
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                results.append(f"{file_path}:{i}:{line.strip()}")
                                if len(results) >= max_results:
                                    results.append(f"\n[Warning: Output truncated at {max_results} results]")
                                    return "\n".join(results)
                except Exception:
                    pass
                    
        if not results:
            return f"No results found for '{query}' in {dir_path}."
            
        return "\n".join(results)

# Register tools
TOOL_REGISTRY = {
    BashTool.name: BashTool(),
    ReadFileTool.name: ReadFileTool(),
    GrepSearchTool.name: GrepSearchTool()
}
