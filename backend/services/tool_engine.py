import uuid
import concurrent.futures
from typing import Dict, Any, List, Generator

# Import the registry directly
from backend.services.agent_tools import TOOL_REGISTRY

class ToolExecutionEngine:
    """Executes agent tools safely and concurrently, yielding events for the frontend."""
    
    def _format_command_str(self, t_name: str, t_param: dict) -> str:
        if t_name == "read_file":
            path = t_param.get("path", "")
            start_line = t_param.get("start_line", "")
            end_line = t_param.get("end_line", "")
            if start_line and end_line:
                return f"{path} (Lines {start_line}-{end_line})"
            elif start_line:
                return f"{path} (From line {start_line})"
            else:
                return path
        elif t_name == "grep_search":
            return f"Search '{t_param.get('query', '')}' in {t_param.get('dir_path', '')}"
        elif t_name == "web_search":
            return f"Web Search: '{t_param.get('query', '')}'"
        elif t_name == "read_url_content":
            url = t_param.get("url", "")
            start_line = t_param.get("start_line", "")
            if start_line:
                return f"Browser: {url} (Line {start_line}+)"
            return f"Browser: {url}"
        elif t_name == "execute_bash":
            return t_param.get("command", "")
        else:
            args = []
            for k, v in t_param.items():
                if k != "approval_id":
                    args.append(f"{k}={v}")
            return f"{t_name}({', '.join(args)})"
            
    def execute_tools(self, tools_to_run: List[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """
        Executes a batch of tools.
        Yields UI events (tool_start, tool_output, tool_end).
        The final yielded item is always {"type": "tool_results", "results": [...]}
        """
        safe_tools = []
        unsafe_tools = []
        
        # Enforce Tool_Registry matching and format command_str
        for t in tools_to_run:
            name = t["name"]
            tool_obj = TOOL_REGISTRY.get(name)
            t["command_str"] = self._format_command_str(name, t["param"])
            
            # Check the new is_safe flag on the class instance
            if tool_obj and getattr(tool_obj, 'is_safe', True):
                safe_tools.append(t)
            else:
                unsafe_tools.append(t)
                
        final_results = []
        
        def run_tool(t):
            if t["name"] in TOOL_REGISTRY:
                return TOOL_REGISTRY[t["name"]].execute(t["param"])
            return f"[Error] Unknown tool: {t['name']}"

        # 1. Execute Safe Tools concurrently
        if safe_tools:
            results = [None] * len(safe_tools)
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(safe_tools))) as executor:
                future_to_tool = {executor.submit(run_tool, t): idx for idx, t in enumerate(safe_tools)}
                for future in concurrent.futures.as_completed(future_to_tool):
                    idx = future_to_tool[future]
                    try:
                        results[idx] = future.result()
                    except Exception as exc:
                        results[idx] = f"[Error] Exception executing tool: {exc}"

            for idx, (t, output) in enumerate(zip(safe_tools, results)):
                yield {"type": "tool_start", "tool_name": t["name"], "command": t["command_str"]}
                yield {"type": "tool_output", "text": str(output)}
                yield {"type": "tool_end"}
                
                final_results.append({
                    "role": "tool",
                    "tool_call_id": t["id"],
                    "name": t["name"],
                    "content": str(output)
                })

        # 2. Execute Unsafe Tools sequentially
        if unsafe_tools:
            for t in unsafe_tools:
                approval_id = uuid.uuid4().hex
                if "param" not in t or not isinstance(t["param"], dict):
                    t["param"] = {}
                t["param"]["approval_id"] = approval_id
                
                yield {"type": "tool_start", "tool_name": t["name"], "command": t["command_str"], "approval_id": approval_id}
                
                try:
                    output = run_tool(t)
                except Exception as exc:
                    output = f"[Error] Exception executing unsafe tool: {exc}"
                    
                yield {"type": "tool_output", "text": str(output)}
                yield {"type": "tool_end"}
                
                final_results.append({
                    "role": "tool",
                    "tool_call_id": t["id"],
                    "name": t["name"],
                    "content": str(output)
                })
                
        yield {"type": "tool_results", "results": final_results}
