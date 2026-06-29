import json
import uuid
from typing import Dict, Any, List, Optional

class ToolFormatter:
    """Formats raw tool calls into pseudo-XML for the frontend rendering"""
    @staticmethod
    def generate_fake_xml(tools_to_run: List[Dict[str, Any]]) -> str:
        if not tools_to_run:
            return ""
            
        # We wrap it in <tool_batch> to trigger the frontend parser
        xml_blocks = ["\n<tool_batch>\n"]
        for tc in tools_to_run:
            func_name = tc.get("name", "")
            params = tc.get("param", {})
            fake_xml = f'<call_tool name="{func_name}">\n'
            for k, v in params.items():
                fake_xml += f'<{k}>{v}</{k}>\n'
            fake_xml += "</call_tool>\n"
            xml_blocks.append(fake_xml)
        xml_blocks.append("</tool_batch>\n")
        
        return "".join(xml_blocks)

class StreamParser:
    """Parses LLM stream chunks, yielding standard text and accumulating tool calls."""
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
        
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls_accumulator) > 0
        
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
                "raw_payload": tc # The exact OpenAI structure needed for messages later
            })
            
        return parsed_tools
