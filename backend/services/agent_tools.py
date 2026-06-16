import subprocess
import os

import re
import xml.etree.ElementTree as ET
from typing import Generator, List, Dict, Any, Protocol

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


# --- 新增：底层 LLM 协议接口 ---
class LLMClientProtocol(Protocol):
    def stream_completion(self, messages: List[Dict[str, str]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        ...

class OpenAILLMClient:
    """纯粹的 OpenAI 协议流式客户端，不包含任何业务逻辑和工具解析"""
    def __init__(self, api_key: str, base_url: str, model_id: str):
        self.client = OpenAI(api_key=api_key or "no-key-required", base_url=base_url)
        self.model_id = model_id

    def stream_completion(self, messages: List[Dict[str, str]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        call_kwargs = {
            "model": self.model_id,
            "messages": messages,
            "stream": True,
            "temperature": 1.0,
            "stop": ["[System"]
        }
        if "max_tokens" in kwargs and kwargs["max_tokens"] > 0:
            call_kwargs["max_tokens"] = kwargs["max_tokens"]

        response = self.client.chat.completions.create(**call_kwargs)
        for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    yield {"type": "thinking", "text": delta.reasoning_content}
                if delta.content:
                    yield {"type": "text", "text": delta.content}

# --- 新增：AgentExecutor 应用层 ---
class AgentExecutor:
    """
    负责多轮对话循环、实时流式标签拦截、工具解析与执行的高层模块。
    它包裹了底层的 LLMClientProtocol，实现了协议解耦。
    """
    def __init__(self, llm_client: LLMClientProtocol, max_iterations: int = 5):
        self.llm_client = llm_client
        self.max_iterations = max_iterations

    def run(self, messages: List[Dict[str, str]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        iteration = 0
        current_messages = messages.copy()

        while iteration < self.max_iterations:
            iteration += 1
            full_content = ""

            # 使用状态机实时拦截 <call_tool> 或 <execute_bash>
            buffer = ""
            in_tag = False

            for chunk in self.llm_client.stream_completion(current_messages, **kwargs):
                if chunk.get("type") == "thinking":
                    yield chunk
                    continue

                text = chunk.get("text", "")

                # 边收边解析，判断是否进入了工具标签
                for char in text:
                    if not in_tag and not buffer and char == '<':
                        buffer += char
                        continue

                    if buffer or in_tag:
                        buffer += char
                        if buffer.startswith("<call_tool") or buffer.startswith("<execute_bash"):
                            in_tag = True
                            # 缓冲中，不向前端 yield
                        elif buffer.startswith("<"):
                            # 如果发现不是目标标签，释放缓冲
                            if ">" in buffer or len(buffer) > 20:
                                if not buffer.startswith("<call_tool") and not buffer.startswith("<execute_bash"):
                                    yield {"type": "text", "text": buffer}
                                    full_content += buffer
                                    buffer = ""
                                    in_tag = False
                        else:
                            # 意外情况，释放缓冲
                            yield {"type": "text", "text": buffer}
                            full_content += buffer
                            buffer = ""
                    else:
                        yield {"type": "text", "text": char}
                        full_content += char

            # 流结束后，如果有遗留缓冲（完整的工具标签）
            if buffer:
                full_content += buffer

            # 解析并执行工具
            tools_to_run = self._parse_tools(full_content)

            if not tools_to_run:
                break # 没有工具调用，结束循环

            current_messages.append({"role": "assistant", "content": full_content})

            system_result_text = ""
            for idx, t in enumerate(tools_to_run):
                yield {"type": "tool_start", "tool_name": t["name"], "command": t["command_str"]}

                if t["name"] in TOOL_REGISTRY:
                    output = TOOL_REGISTRY[t["name"]].execute(t["param"])
                else:
                    output = f"[Error] Unknown tool: {t['name']}"

                yield {"type": "tool_output", "text": output}
                yield {"type": "tool_end"}

                system_result_text += f"[System Tool Result {idx+1}]:\n{output}\n\n"

            # 将执行结果喂给模型，进入下一轮
            current_messages.append({
                "role": "user",
                "content": f"{system_result_text}请根据上述结果继续分析，或者如果信息足够，请立刻使用你当前的人设进行最终回复（最终回复绝不能包含任何XML标签）。"
            })

    def _parse_tools(self, full_content: str) -> List[Dict[str, Any]]:
        tools_to_run = []
        matches = re.finditer(r'<call_tool[^>]*>.*?(?:</call_tool>|$)', full_content, re.DOTALL)
        for match in matches:
            tool_xml = match.group(0)
            if not tool_xml.endswith("</call_tool>"):
                tool_xml += "</call_tool>"
            try:
                root = ET.fromstring(tool_xml)
                t_name = root.attrib.get("name")
                t_param = {}
                for child in root:
                    t_param[child.tag] = child.text if child.text else ""

                c_str = self._format_command_str(t_name, t_param)
                if t_name:
                    tools_to_run.append({"name": t_name, "param": t_param, "command_str": c_str})
            except Exception:
                pass

        # 兼容旧版 <execute_bash> 标签
        if not tools_to_run:
            match_old = re.search(r'<execute_bash>(.*?)(?:</execute_bash>|$)', full_content, re.DOTALL)
            if match_old:
                c_str = match_old.group(1).strip()
                tools_to_run.append({"name": "execute_bash", "param": {"command": c_str}, "command_str": c_str})

        return tools_to_run

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
        else:
            return t_param.get("command", str(t_param))
