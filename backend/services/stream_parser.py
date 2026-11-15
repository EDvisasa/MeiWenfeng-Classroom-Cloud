import json
import uuid
import re
from typing import Dict, Any, List, Optional


class StreamParser:
    """Parses LLM stream chunks, yielding standard text and accumulating tool calls."""
    KNOWN_TOOL_NAMES = {
        "read_file", "grep_search", "execute_bash", "replace_file_content",
        "create_file", "web_search", "read_url_content", "call_openclaw_agent",
        "search_memory", "get_memory_timeline", "get_memory_calendar", "expand_memory",
    }
    _DIRECT_TOOL_REGEX = (
        r"<(call_openclaw_agent|read_file|grep_search|execute_bash|"
        r"replace_file_content|create_file|web_search|read_url_content|"
        r"search_memory|get_memory_timeline|get_memory_calendar|expand_memory)>([\s\S]*?)</\1>"
    )

    def __init__(self):
        self.tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}
        self.full_content: str = ""

    def process_chunk(self, chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a single stream chunk and return it if it should be yielded immediately"""
        chunk_type = chunk.get("type", "text")
        
        if chunk_type == "tool_calls_chunk":
            for tc in chunk.get("tool_calls", []):
                idx = tc.get("index", 0)
                if idx not in self.tool_calls_accumulator:
                    self.tool_calls_accumulator[idx] = {
                        "id": tc.get("id", ""), 
                        "type": "function", 
                        "function": {"name": "", "arguments": ""}
                    }
                
                func = tc.get("function", {})
                if func.get("name"):
                    self.tool_calls_accumulator[idx]["function"]["name"] += func["name"]
                if func.get("arguments"):
                    self.tool_calls_accumulator[idx]["function"]["arguments"] += func["arguments"]
            return None # Do not yield tool calls chunks directly
            
        if chunk_type in ["text", "thinking"]:
            self.full_content += chunk.get("text", "")
            return chunk
            
        # Yield retry status or other internal chunks unmodified
        return chunk
        
    def get_full_content(self) -> str:
        return self.full_content

    def _get_xml_tool_calls(self) -> List[Dict[str, Any]]:
        results = []
        if not self.full_content:
            return results

        for match in re.finditer(self._DIRECT_TOOL_REGEX, self.full_content):
            tool_name = match.group(1)
            payload_str = match.group(2).strip()
            results.append(self._build_xml_tool_item(tool_name, payload_str))

        pattern_call_tool = r'<call_tool\s+name="([^"]+)">([\s\S]*?)</call_tool>'
        for match in re.finditer(pattern_call_tool, self.full_content):
            tool_name = match.group(1).strip()
            payload_str = match.group(2).strip()
            if tool_name in self.KNOWN_TOOL_NAMES:
                results.append(self._build_xml_tool_item(tool_name, payload_str))

        return results

    def _build_xml_tool_item(self, tool_name: str, payload_str: str) -> Dict[str, Any]:
        try:
            t_param = json.loads(payload_str) if payload_str else {}
        except json.JSONDecodeError:
            param_map = {
                "call_openclaw_agent": "task_message",
                "read_file": "file_path",
                "execute_bash": "command",
                "web_search": "query",
                "search_memory": "query",
                "get_memory_timeline": "date_range",
                "get_memory_calendar": "date_range",
                "read_url_content": "url",
            }
            key = param_map.get(tool_name, "content")
            t_param = {key: payload_str}

        call_id = "call_xml_" + uuid.uuid4().hex[:12]
        return {
            "id": call_id,
            "name": tool_name,
            "param": t_param,
            "raw_payload": {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(t_param, ensure_ascii=False)
                }
            }
        }

    def has_tool_calls(self) -> bool:
        return len(self.tool_calls_accumulator) > 0 or len(self._get_xml_tool_calls()) > 0
        
    def get_parsed_tool_calls(self) -> List[Dict[str, Any]]:
        """Extracts and parses the accumulated tool calls."""
        parsed_tools = []
        
        for idx, tc in sorted(self.tool_calls_accumulator.items()):
            if not tc["id"]:
                tc["id"] = "call_" + uuid.uuid4().hex[:16]
                
            func_name = tc["function"]["name"]
            args_str = tc["function"]["arguments"]
            
            try:
                t_param = json.loads(args_str) if args_str else {}
            except json.JSONDecodeError:
                t_param = {}
                
            parsed_tools.append({
                "id": tc["id"],
                "name": func_name,
                "param": t_param,
                "raw_payload": tc
            })

        parsed_tools.extend(self._get_xml_tool_calls())
        return parsed_tools

    def get_clean_content(self) -> str:
        """Return content with XML tool tags stripped out."""
        content = self.full_content
        content = re.sub(self._DIRECT_TOOL_REGEX, '', content)
        pattern_call_tool = r'<call_tool\s+name="[^"]+">[\s\S]*?</call_tool>'
        content = re.sub(pattern_call_tool, '', content)
        return content.strip()

