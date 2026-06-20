import subprocess
import os
import shlex

import re
import xml.etree.ElementTree as ET
from typing import Generator, List, Dict, Any, Protocol
from openai import OpenAI

class AgentTool:
    name: str = ""
    description: str = ""

    def execute(self, params: dict) -> str:
        raise NotImplementedError()

import time
import uuid

# Global dictionary for BashTool HITL approvals
PENDING_APPROVALS = {}

class BashTool(AgentTool):
    name = "execute_bash"
    description = "Execute a local terminal command."

    def execute(self, params: dict) -> str:
        command = params.get("command", "")
        approval_id = params.get("approval_id", "")
        
        if not command:
            return "[Error] No command provided."

        if approval_id:
            PENDING_APPROVALS[approval_id] = "pending"
            start_time = time.time()
            timeout = 60
            
            while True:
                status = PENDING_APPROVALS.get(approval_id)
                if status == "approve":
                    del PENDING_APPROVALS[approval_id]
                    break
                elif status == "reject":
                    del PENDING_APPROVALS[approval_id]
                    return "[Error] User rejected the execution of this command."
                    
                if time.time() - start_time > timeout:
                    if approval_id in PENDING_APPROVALS:
                        del PENDING_APPROVALS[approval_id]
                    return "[Error] Command approval timed out after 60 seconds."
                    
                time.sleep(0.5)

        # Physical Guardrails to enforce tool usage using shlex for safer parsing
        try:
            # We split the command to safely inspect the base binary being called,
            # handling shell escapes and quotes properly.
            parsed_cmd = shlex.split(command, posix=True)
            if parsed_cmd:
                base_binary = os.path.basename(parsed_cmd[0]).lower()

                # Check for direct calls to forbidden binaries
                if base_binary in ["cat", "type"]:
                    return "[Error] GUARDRAIL BLOCKED: You are strictly forbidden from using 'type' or 'cat' to read files in bash. You MUST use the <call_tool name=\"read_file\"> tool instead."
                if base_binary in ["grep", "findstr"]:
                    return "[Error] GUARDRAIL BLOCKED: You are strictly forbidden from using 'findstr' or 'grep' in bash. You MUST use the <call_tool name=\"grep_search\"> tool instead."

                # Also block common bypasses like tail or head used for full file reading
                if base_binary in ["tail", "head", "more", "less"]:
                     return "[Error] GUARDRAIL BLOCKED: You are strictly forbidden from using shell utilities to read files. You MUST use the <call_tool name=\"read_file\"> tool instead."
        except ValueError:
            # If shlex fails to parse (e.g. unclosed quotes), we fall back to a strict string check
            pass

        # Fallback string matching for piped commands or complex shell strings
        cmd_lower = command.strip().lower()
        if "cat " in cmd_lower or "type " in cmd_lower or "| cat" in cmd_lower or "| type" in cmd_lower:
            return "[Error] GUARDRAIL BLOCKED: You are strictly forbidden from using 'type' or 'cat' to read files in bash. You MUST use the <call_tool name=\"read_file\"> tool instead."
        if "grep" in cmd_lower or "findstr" in cmd_lower:
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

class ReplaceFileContentTool(AgentTool):
    name = "replace_file_content"
    description = "Surgically replace a block of text in a specific file. Restricted to the docs/sandbox directory."

    def execute(self, params: dict) -> str:
        path = params.get("path", "")
        old_content = params.get("old_content", "")
        new_content = params.get("new_content", "")
        
        if not path or not old_content or new_content is None:
            return "[Error] path, old_content, and new_content are required."
            
        # Security Guardrail: Sandbox Restriction
        # Use realpath to resolve symbolic links (symlink bypass prevention)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sandbox_dir = os.path.realpath(os.path.join(project_root, "docs", "sandbox"))
        target_path = os.path.realpath(path)
        
        # Use commonpath for mathematically safe boundary checking (handles all OS path quirks)
        try:
            if os.path.commonpath([sandbox_dir, target_path]) != sandbox_dir:
                return f"[Error] GUARDRAIL BLOCKED: Sandbox boundary violation. You are only allowed to modify files within {sandbox_dir}."
            # Additionally, prevent modifying the sandbox directory itself
            if target_path == sandbox_dir:
                return f"[Error] GUARDRAIL BLOCKED: Cannot modify the sandbox directory itself."
        except ValueError:
            # commonpath raises ValueError if paths are on different drives in Windows
            return f"[Error] GUARDRAIL BLOCKED: Sandbox boundary violation (different drive)."
            
        if not os.path.exists(target_path):
            return f"[Error] File not found: {target_path}"
            
        if not os.path.isfile(target_path):
            return f"[Error] Path is not a file: {target_path}"
            
        try:
            with open(target_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            occurrences = content.count(old_content)
            if occurrences == 0:
                return "[Error] old_content not found in the file. Please make sure the old_content exactly matches the existing text, including whitespace and line endings."
            elif occurrences > 1:
                return f"[Error] old_content found {occurrences} times in the file. The replacement must be unique to avoid unintended changes."
                
            new_file_content = content.replace(old_content, new_content)
            
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(new_file_content)
                
            return f"[Success] Replaced content in {target_path}"
        except Exception as e:
            return f"[Error] Failed to replace content: {str(e)}"

class CreateFileTool(AgentTool):
    name = "create_file"
    description = "Create a brand new file with the specified content. Restricted to the docs/sandbox directory."

    def execute(self, params: dict) -> str:
        path = params.get("path", "")
        content = params.get("content", "")
        
        if not path or content is None:
            return "[Error] path and content are required."
            
        # Security Guardrail: Sandbox Restriction
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sandbox_dir = os.path.realpath(os.path.join(project_root, "docs", "sandbox"))
        target_path = os.path.realpath(path)
        
        try:
            if os.path.commonpath([sandbox_dir, target_path]) != sandbox_dir:
                return f"[Error] GUARDRAIL BLOCKED: Sandbox boundary violation. You are only allowed to modify files within {sandbox_dir}."
            if target_path == sandbox_dir:
                return f"[Error] GUARDRAIL BLOCKED: Cannot modify the sandbox directory itself."
        except ValueError:
            return f"[Error] GUARDRAIL BLOCKED: Sandbox boundary violation (different drive)."
            
        if os.path.exists(target_path):
            return f"[Error] File already exists at {target_path}. Please use replace_file_content to edit it."
            
        try:
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"[Success] Created new file at {target_path}"
        except Exception as e:
            return f"[Error] Failed to create file: {str(e)}"

# Register tools
TOOL_REGISTRY = {
    "read_file": ReadFileTool(),
    "grep_search": GrepSearchTool(),
    "execute_bash": BashTool(),
    "replace_file_content": ReplaceFileContentTool(),
    "create_file": CreateFileTool(),
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

        import time
        import httpx
        import openai

        max_retries = 10
        base_wait = 2

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(**call_kwargs)
                
                if attempt > 1:
                    import json
                    yield {"type": "retry_status", "text": json.dumps({"success": True})}

                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            yield {"type": "thinking", "text": delta.reasoning_content}
                        if delta.content:
                            yield {"type": "text", "text": delta.content}
                
                return

            except (
                openai.APIConnectionError, 
                openai.RateLimitError, 
                openai.APITimeoutError, 
                openai.InternalServerError,
                httpx.NetworkError, 
                httpx.TimeoutException,
                ConnectionError
            ) as e:
                if attempt == max_retries:
                    import json
                    yield {"type": "retry_status", "text": json.dumps({"error": str(e).split('\n')[0][:80], "failed": True})}
                    raise e
                
                wait_time = min(base_wait * (2 ** (attempt - 1)), 30)
                error_msg = str(e).split('\n')[0][:80]
                
                # 在后端终端打印详细报错，方便开发者排查问题（UI 会在重试成功后自动清理气泡）
                print(f"[API Retry Warning] Attempt {attempt}/{max_retries} failed. Retrying in {wait_time}s. Error: {str(e)}")
                
                import json
                payload = json.dumps({
                    "error": error_msg,
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "wait_time": wait_time
                })
                yield {"type": "retry_status", "text": payload}
                time.sleep(wait_time)


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
        import platform
        current_os = platform.system()
        os_instruction = f"Operating System: {current_os}."
        if current_os == "Windows":
            os_instruction += " You are using Windows cmd.exe. CRITICAL: Multiline strings do NOT work well in `python -c` or standard terminal commands here. If you need to run a python script, write it entirely on ONE line using semicolons (e.g. `python -c \"import os; print('hi')\"`), or write it to a temporary .py file and execute that file. Use Windows commands (e.g., `dir` instead of `ls`)."
        else:
            os_instruction += " You are using a standard Unix bash shell."

        system_injection = f"""
<tool_use_guidelines>
You have access to a local command-line terminal and file system tools.
{os_instruction}

CRITICAL RULES:
1. THINK BEFORE YOU ACT: You MUST ALWAYS start your response with a <thought> block to explain your plan and reasoning.
2. STRICT TAG SEQUENCE: You MUST explicitly close your `</thought>` block BEFORE outputting any tool calls. NEVER nest tools inside `<thought>`.
3. BATCH EXECUTION: To execute operations concurrently, you MUST wrap all your `<call_tool>` blocks inside a SINGLE `<tool_batch>...</tool_batch>` container. 
4. STOP AT BATCH CLOSURE: After you output `</tool_batch>`, you MUST STOP generating immediately. DO NOT hallucinate the system's response. The system will execute all tools within the batch concurrently and return "[System Tool Result]"s.
5. ERROR RECOVERY: If the system execution result contains an error, analyze it in your next <thought> block and try a different command. Do NOT bother the user with technical errors.
6. USE SPECIFIC TOOLS: You MUST use `read_file` to read files. NEVER use `cat` or `type` via `execute_bash`.
7. ENFORCE SEARCH TOOL: To search for a specific string or keywords across files in a directory, you MUST use the `grep_search` tool. You are ABSOLUTELY FORBIDDEN from using `execute_bash` (like findstr, grep, or custom python scripts) to search files.
8. TIME PERCEPTION: You already have the exact, up-to-date real-world time in the `<current_time>` block of your system prompt. Do NOT use `execute_bash` or any code to check the current time or date. Rely entirely on the injected time.
9. MAINTAIN PERSONA: When you have gathered all necessary information and are ready to reply to the user, you MUST completely drop the XML tags and resume your designated roleplay persona to give the final answer. NEVER expose XML tags or tool outputs to the user in your final reply.

TOOL EXECUTION FORMAT:
<thought>
I need to check the current directory contents and read config.json.
</thought>
<tool_batch>
<call_tool name="execute_bash">
<command>{"dir" if current_os == "Windows" else "ls -la"}</command>
</call_tool>
<call_tool name="read_file">
<path>config.json</path>
<start_line>10</start_line>
<end_line>50</end_line>
</call_tool>
</tool_batch>

OR to search for a query across files in a directory:
<thought>
I need to find where 'login' is mentioned in the src folder.
</thought>
<tool_batch>
<call_tool name="grep_search">
<dir_path>C:/path/to/src</dir_path>
<query>login</query>
</call_tool>
</tool_batch>

OR to surgically replace code in a sandbox file:
<thought>
I need to update the sandbox test file to increase difficulty.
</thought>
<tool_batch>
<call_tool name="replace_file_content">
  <path>docs/sandbox/target_file.py</path>
  <old_content>exact text to be replaced (must be unique)</old_content>
  <new_content>new text</new_content>
</call_tool>

If you need to create an entirely new file from scratch in the sandbox, use:
<call_tool name="create_file">
  <path>docs/sandbox/new_file.py</path>
  <content>entire content of the new file</content>
</call_tool>
</tool_batch>
</tool_use_guidelines>
"""
        current_messages = messages.copy()
        if len(current_messages) > 0 and current_messages[0]["role"] == "system":
            current_messages[0]["content"] = str(current_messages[0]["content"]) + "\n\n" + system_injection
        else:
            current_messages.insert(0, {"role": "system", "content": system_injection})

        iteration = 0


        while iteration < self.max_iterations:
            iteration += 1
            full_content = ""

            # 使用状态机实时拦截 <call_tool> 或 <execute_bash>
            buffer = ""
            in_tag = False

            for chunk in self.llm_client.stream_completion(current_messages, **kwargs):
                chunk_type = chunk.get("type", "text")  # "thinking" 或 "text"
                
                if chunk_type not in ["text", "thinking"]:
                    yield chunk
                    continue
                    
                text = chunk.get("text", "")

                # 对 thinking 和 text 通道应用完全相同的拦截器状态机
                # 防止 DeepSeek 把 <tool_batch> 或故事正文写入 reasoning_content 时直接泄漏
                for char in text:
                    if not in_tag and not buffer and char == '<':
                        buffer += char
                        continue

                    if buffer or in_tag:
                        buffer += char
                        if buffer.startswith("<tool_batch"):
                            in_tag = True
                            # 关键修复：检测 </tool_batch> 闭合，一旦发现就刷新并退出 in_tag 状态
                            if "</tool_batch>" in buffer:
                                full_content += buffer
                                buffer = ""
                                in_tag = False
                                # 不 yield 任何内容（tool_batch 本体对前端不可见）
                        elif buffer.startswith("<"):
                            # 如果发现不是目标标签，释放缓冲
                            if ">" in buffer or len(buffer) > 20:
                                if not buffer.startswith("<tool_batch"):
                                    yield {"type": chunk_type, "text": buffer}
                                    full_content += buffer
                                    buffer = ""
                                    in_tag = False
                        else:
                            # 意外情况，释放缓冲
                            yield {"type": chunk_type, "text": buffer}
                            full_content += buffer
                            buffer = ""
                    else:
                        yield {"type": chunk_type, "text": char}
                        full_content += char


            # 流结束后，如果有遗留缓冲（完整的工具标签）
            if buffer:
                full_content += buffer

            # 解析并执行工具
            tools_to_run = self._parse_tools(full_content)

            if not tools_to_run:
                break # 没有工具调用，结束循环

            current_messages.append({"role": "assistant", "content": full_content})

            import concurrent.futures
            
            system_result_text = ""
            
            # 去重逻辑
            unique_tools = []
            seen = set()
            for t in tools_to_run:
                # 序列化 param 字典以便哈希去重
                param_repr = repr(sorted(t["param"].items()) if isinstance(t.get("param"), dict) else t.get("param"))
                key = (t["name"], param_repr)
                if key not in seen:
                    seen.add(key)
                    unique_tools.append(t)
            
            tools_to_run = unique_tools

            def run_tool(t):
                if t["name"] in TOOL_REGISTRY:
                    return TOOL_REGISTRY[t["name"]].execute(t["param"])
                else:
                    return f"[Error] Unknown tool: {t['name']}"

            # 区分安全工具与危险工具
            safe_tools = [t for t in tools_to_run if t["name"] != "execute_bash"]
            unsafe_tools = [t for t in tools_to_run if t["name"] == "execute_bash"]

            # 1. 并发执行 Safe Tools
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
                    system_result_text += f"[System Tool Result {t['name']}]:\n{output}\n\n"

            # 2. 串行执行 Unsafe Tools 提前 yield 发送前端拦截卡片
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
                    system_result_text += f"[System Tool Result {t['name']}]:\n{output}\n\n"

            # 将执行结果喂给模型，进入下一轮
            current_messages.append({
                "role": "user",
                "content": f"{system_result_text}请根据上述结果继续分析，或者如果信息足够，请立刻使用你当前的人设进行最终回复（最终回复绝不能包含任何XML标签）。"
            })

    def _parse_tools(self, full_content: str) -> List[Dict[str, Any]]:
        tools_to_run = []
        
        # 1. 尝试解析标准的 <call_tool>
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

        # 2. 如果没有找到标准的 <call_tool>，则尝试兼容大模型的直接标签幻觉（如 <grep_search>...</grep_search>）
        if not tools_to_run:
            for tool_name in TOOL_REGISTRY.keys():
                pattern = f'<{tool_name}>(.*?)(?:</{tool_name}>|$)'
                for match in re.finditer(pattern, full_content, re.DOTALL):
                    inner_xml = match.group(1).strip()
                    # 将其组装成可以被 ET 解析的格式
                    dummy_xml = f"<{tool_name}>{inner_xml}</{tool_name}>"
                    try:
                        root = ET.fromstring(dummy_xml)
                        t_param = {}
                        for child in root:
                            t_param[child.tag] = child.text if child.text else ""
                            
                        # 特殊处理 execute_bash
                        if tool_name == "execute_bash" and not t_param:
                            # 兼容 <execute_bash>ls -la</execute_bash> 的旧格式
                            c_str = inner_xml.strip()
                            t_param = {"command": c_str}
                        else:
                            c_str = self._format_command_str(tool_name, t_param)
                            
                        tools_to_run.append({"name": tool_name, "param": t_param, "command_str": c_str})
                    except Exception:
                        pass

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
