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
    parameters_schema: dict = {}

    def execute(self, params: dict) -> str:
        raise NotImplementedError()

import time
import uuid

# Global dictionary for BashTool HITL approvals
PENDING_APPROVALS = {}

class BashTool(AgentTool):
    name = "execute_bash"
    description = "Execute a local terminal command. Use this for running tests, managing files, and checking system state."
    parameters_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash/cmd command to execute."
            },
            "approval_id": {
                "type": "string",
                "description": "Optional unique ID for HITL approval."
            }
        },
        "required": ["command"]
    }

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
    description = "Read lines from a file. You can specify a range using start_line and end_line."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative path to the file."
            },
            "start_line": {
                "type": "string",
                "description": "Optional start line number."
            },
            "end_line": {
                "type": "string",
                "description": "Optional end line number."
            }
        },
        "required": ["path"]
    }

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
            return content + f"\n\n[Warning: Output truncated at 800 lines to prevent context overflow. File has {total_lines} lines total. 👉 To read more, call this tool again with <start_line>{s + 800}</start_line>]"
            
        content = "".join(sliced_lines)
        return content

class GrepSearchTool(AgentTool):
    name = "grep_search"
    description = "Search for a query string in all text files within a directory."
    parameters_schema = {
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "The directory path to search in."
            },
            "query": {
                "type": "string",
                "description": "The string to search for."
            }
        },
        "required": ["dir_path", "query"]
    }

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
    description = "Surgically replace a block of text in a specific file. Restricted to the data/materials/Sandbox directory."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path to the file in the Sandbox."
            },
            "old_content": {
                "type": "string",
                "description": "The exact existing content to replace."
            },
            "new_content": {
                "type": "string",
                "description": "The new content to insert."
            }
        },
        "required": ["path", "old_content", "new_content"]
    }

    def execute(self, params: dict) -> str:
        path = params.get("path", "")
        old_content = params.get("old_content", "")
        new_content = params.get("new_content", "")
        
        if not path or not old_content or new_content is None:
            return "[Error] path, old_content, and new_content are required."
            
        # Security Guardrail: Sandbox Restriction
        # Use realpath to resolve symbolic links (symlink bypass prevention)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sandbox_dir = os.path.realpath(os.path.join(project_root, "data", "materials", "Sandbox"))
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
    description = "Create a completely new file with content. Restricted to the data/materials/Sandbox directory."
    parameters_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The path of the new file to create in the Sandbox."
            },
            "content": {
                "type": "string",
                "description": "The complete content of the new file."
            }
        },
        "required": ["path", "content"]
    }

    def execute(self, params: dict) -> str:
        path = params.get("path", "")
        content = params.get("content", "")
        
        if not path or content is None:
            return "[Error] path and content are required."
            
        # Security Guardrail: Sandbox Restriction
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        sandbox_dir = os.path.realpath(os.path.join(project_root, "data", "materials", "Sandbox"))
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

class WebSearchTool(AgentTool):
    name = "web_search"
    description = "Search the internet using DuckDuckGo to find information."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query."
            }
        },
        "required": ["query"]
    }

    def execute(self, params: dict) -> str:
        query = params.get("query", "")
        if not query:
            return "[Error] query is required."
            
        try:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                from ddgs import DDGS
                
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                
            if not results:
                return f"[Result] No web results found for query: {query}"
                
            formatted_results = []
            for idx, res in enumerate(results, 1):
                title = res.get("title", "No Title")
                href = res.get("href", "No URL")
                body = res.get("body", "No Body")
                formatted_results.append(f"Result {idx}:\nTitle: {title}\nURL: {href}\nSnippet: {body}\n")
                
            final_output = "\n".join(formatted_results)
            # Ensure it doesn't get too long and crash context
            if len(final_output) > 2000:
                final_output = final_output[:2000] + "\n...[Truncated]"
                
            return final_output
            
        except ImportError:
            return "[Error] ddgs package is not installed. Please run pip install ddgs."
        except Exception as e:
            # Duckduckgo-search is prone to rate-limits and network timeouts
            return f"[Error] Web search failed: {str(e)}. (Consider trying a different query or waiting a bit)."

class ReadUrlContentTool(AgentTool):
    name = "read_url_content"
    description = "Read and extract clean markdown content from a specific URL. Useful for reading documentation or articles."
    parameters_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL of the webpage to read."
            },
            "start_line": {
                "type": "string",
                "description": "Optional start line number for pagination."
            },
            "end_line": {
                "type": "string",
                "description": "Optional end line number for pagination."
            }
        },
        "required": ["url"]
    }

    def execute(self, params: dict) -> str:
        url = params.get("url", "")
        if not url:
            return "[Error] url is required."
            
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
            import httpx
            try:
                from bs4 import BeautifulSoup
            except ImportError:
                return "[Error] beautifulsoup4 package is not installed. Please run pip install beautifulsoup4."
            try:
                import markdownify
            except ImportError:
                return "[Error] markdownify package is not installed. Please run pip install markdownify."
                
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            
            # Use a slightly longer timeout for heavy pages
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                html_content = response.text
                
            # Clean noise using BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()
                
            clean_html = str(soup)
            
            # Convert to Markdown
            md_content = markdownify.markdownify(clean_html, heading_style="ATX").strip()
            
            # Split into lines
            lines = md_content.split('\n')
            total_lines = len(lines)
            
            if total_lines == 0:
                return f"[Result] URL fetched but no readable content was extracted: {url}"
                
            s = 1 if start_line is None else max(1, start_line)
            e = total_lines if end_line is None else min(total_lines, end_line)
            
            if s > total_lines:
                return f"[Error] start_line ({s}) is beyond the end of content ({total_lines} lines)."
                
            if e < s:
                return f"[Error] end_line ({e}) cannot be before start_line ({s})."
                
            sliced_lines = lines[s-1:e]
            
            if len(sliced_lines) > 800:
                content = "\n".join(sliced_lines[:800])
                return content + f"\n\n[Warning: Webpage content truncated at 800 lines. Total length is {total_lines} lines. 👉 To read more, call this tool again with <start_line>{s + 800}</start_line>]"
                
            return "\n".join(sliced_lines)
            
        except httpx.HTTPStatusError as e:
            return f"[Error] HTTP error occurred: {e.response.status_code} - {e.response.reason_phrase}"
        except httpx.RequestError as e:
            return f"[Error] Request error occurred: {str(e)}"
        except Exception as e:
            return f"[Error] Failed to read URL: {str(e)}"

# Register tools
TOOL_REGISTRY = {
    "read_file": ReadFileTool(),
    "grep_search": GrepSearchTool(),
    "execute_bash": BashTool(),
    "replace_file_content": ReplaceFileContentTool(),
    "create_file": CreateFileTool(),
    "web_search": WebSearchTool(),
    "read_url_content": ReadUrlContentTool(),
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
        if "tools" in kwargs and kwargs["tools"]:
            call_kwargs["tools"] = kwargs["tools"]

        import time
        import httpx
        import openai
        import json

        max_retries = 10
        base_wait = 2

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat.completions.create(**call_kwargs)
                
                if attempt > 1:
                    yield {"type": "retry_status", "text": json.dumps({"success": True})}

                for chunk in response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            yield {"type": "thinking", "text": delta.reasoning_content}
                        if delta.content:
                            yield {"type": "text", "text": delta.content}
                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            # 提取原生 JSON tool calls 并原样返回给 Executor 聚合
                            # 注意: OpenAI v1 API 中的 delta.tool_calls 是对象列表
                            calls_list = []
                            for tc in delta.tool_calls:
                                c_dict = {"index": tc.index}
                                if tc.id is not None:
                                    c_dict["id"] = tc.id
                                if tc.function is not None:
                                    c_dict["function"] = {}
                                    if tc.function.name is not None:
                                        c_dict["function"]["name"] = tc.function.name
                                    if tc.function.arguments is not None:
                                        c_dict["function"]["arguments"] = tc.function.arguments
                                calls_list.append(c_dict)
                            if calls_list:
                                yield {"type": "tool_calls_chunk", "tool_calls": calls_list}
                
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
                    yield {"type": "retry_status", "text": json.dumps({"error": str(e).split('\n')[0][:80], "failed": True})}
                    raise e
                
                wait_time = min(base_wait * (2 ** (attempt - 1)), 30)
                error_msg = str(e).split('\n')[0][:80]
                
                yield {"type": "retry_status", "text": json.dumps({
                    "attempt": attempt,
                    "max_retries": max_retries,
                    "wait_time": wait_time,
                    "error": error_msg
                })}
                time.sleep(wait_time)


def get_agent_execution_protocol() -> str:
    import platform
    current_os = platform.system()
    os_instruction = ""
    if current_os == "Windows":
        os_instruction += " You are using Windows cmd.exe. CRITICAL: Multiline strings do NOT work well in `python -c` or standard terminal commands here. If you need to run a python script, write it entirely on ONE line using semicolons (e.g. `python -c \"import os; print('hi')\"`), or write it to a temporary .py file and execute that file. Use Windows commands (e.g., `dir` instead of `ls`)."
    else:
        os_instruction += " You are using a standard Unix bash shell."

    return f"""
<agent_execution_protocol>
<environment_constraints>
1. You have native function calling tools via the API. Do NOT hallucinate tool results.
2. {os_instruction}
3. ERROR RECOVERY: If a tool execution fails, analyze it in your next <think> block and try a different command.
4. SPECIFIC TOOLS: You MUST use `read_file` to read files and `grep_search` to search directories.
5. TIME PERCEPTION: You already have the exact real-world time in the `<current_time>` block of your system prompt.
6. WEB SEARCH: You have access to a `web_search` tool. Use it to look up recent facts or news.
</environment_constraints>

<execution_framework>
To ensure perfect immersion and strict format compliance, your response MUST strictly follow this exact sequence:

[PHASE 1: INTERNAL REASONING]
You MUST start with a `<think>` block that strictly follows these 6 steps:
1. User Intent: Analyze the user's explicit request and hidden emotional needs.
2. Tool Selection: Determine if you need to use `web_search`, read files, or run commands. (If YES, plan to call the tool and STOP your turn immediately).
3. Attribute Analysis: Analyze your current Affection Score, Social Status, and Refractory state to determine your precise tone.
4. Response Plan: Design your non-verbal actions (wrapped in `*`) and dialogue strategy.
5. Property Calculation: Calculate the exact delta for Affection, Social Status, Social Skills, and Refractory Period.
6. Post-Response Checklist: Remind yourself to output the `<monologue>` block followed by the `<property_update>` tag at the very end.

[PHASE 2: DIALOGUE & ACTIONS]
Respond directly in character (wrapped in `*` for actions). Do not output XML tags or tool calls here.

[PHASE 3: HIDDEN STATE]
Append your `<monologue>...</monologue>` block.
Finally, append the `<property_update>` tag.
CRITICAL: The `<property_update>` tag MUST be the very last thing in your response.
</execution_framework>
</agent_execution_protocol>
"""

class AgentExecutor:
    def __init__(self, llm_client: LLMClientProtocol, max_iterations: int = 5):
        self.llm_client = llm_client
        self.max_iterations = max_iterations

    def run(self, messages: List[Dict[str, Any]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        system_injection = get_agent_execution_protocol()
        current_messages = messages.copy()
        if len(current_messages) > 0 and current_messages[0]["role"] == "system":
            current_messages[0]["content"] = str(current_messages[0]["content"]) + "\n\n" + system_injection
        else:
            current_messages.insert(0, {"role": "system", "content": system_injection})

        # Inject Tool Schemas natively
        tools_list = []
        for name, tool_obj in TOOL_REGISTRY.items():
            schema = getattr(tool_obj, 'parameters_schema', {})
            tools_list.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool_obj.description,
                    "parameters": schema if schema else {"type": "object", "properties": {}}
                }
            })
        kwargs["tools"] = tools_list

        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1
            full_content = ""
            tool_calls_accumulator = {}

            for chunk in self.llm_client.stream_completion(current_messages, **kwargs):
                chunk_type = chunk.get("type", "text")
                
                if chunk_type == "tool_calls_chunk":
                    for tc in chunk.get("tool_calls", []):
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_accumulator:
                            tool_calls_accumulator[idx] = {
                                "id": tc.get("id", ""), 
                                "type": "function", 
                                "function": {"name": "", "arguments": ""}
                            }
                        
                        func = tc.get("function", {})
                        if func.get("name"):
                            tool_calls_accumulator[idx]["function"]["name"] += func["name"]
                        if func.get("arguments"):
                            tool_calls_accumulator[idx]["function"]["arguments"] += func["arguments"]
                    continue
                
                if chunk_type not in ["text", "thinking"]:
                    yield chunk
                    continue
                    
                text = chunk.get("text", "")
                full_content += text
                yield chunk

            import json
            import uuid
            import concurrent.futures
            
            tools_to_run = []
            final_tool_calls_payload = []
            
            # If we accumulated tool calls, parse them
            if tool_calls_accumulator:
                # 伪造 <tool_batch> 骗前端解析器，让前端不用改代码也能渲染华丽UI
                yield {"type": "text", "text": "\n<tool_batch>\n"}
                
                for idx, tc in sorted(tool_calls_accumulator.items()):
                    # OpenAI requires tool_call_id to be populated. If empty, generate one (for some open source models).
                    if not tc["id"]:
                        tc["id"] = "call_" + uuid.uuid4().hex[:16]
                        
                    final_tool_calls_payload.append(tc)
                    func_name = tc["function"]["name"]
                    args_str = tc["function"]["arguments"]
                    try:
                        t_param = json.loads(args_str) if args_str else {}
                    except json.JSONDecodeError:
                        t_param = {}
                        
                    c_str = self._format_command_str(func_name, t_param)
                    tools_to_run.append({"id": tc["id"], "name": func_name, "param": t_param, "command_str": c_str})
                    
                    # 伪造具体的 <call_tool>
                    fake_xml = f'<call_tool name="{func_name}">\n'
                    for k, v in t_param.items():
                        fake_xml += f'<{k}>{v}</{k}>\n'
                    fake_xml += "</call_tool>\n"
                    
                    yield {"type": "text", "text": fake_xml}
                    
                yield {"type": "text", "text": "</tool_batch>\n"}

            if not tools_to_run:
                break # No tool calls, exit loop

            # Prepare assistant message
            assistant_msg = {"role": "assistant"}
            if full_content.strip():
                assistant_msg["content"] = full_content
            else:
                assistant_msg["content"] = ""
            assistant_msg["tool_calls"] = final_tool_calls_payload
            
            # Note: We do NOT append the fake <tool_batch> string into current_messages!
            # The model only sees its standard native tool_calls structure.
            current_messages.append(assistant_msg)

            # Execute tools
            def run_tool(t):
                if t["name"] in TOOL_REGISTRY:
                    return TOOL_REGISTRY[t["name"]].execute(t["param"])
                return f"[Error] Unknown tool: {t['name']}"

            safe_tools = [t for t in tools_to_run if t["name"] != "execute_bash"]
            unsafe_tools = [t for t in tools_to_run if t["name"] == "execute_bash"]

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
                    
                    # Append strictly as a standard tool message
                    current_messages.append({
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
                    
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": t["id"],
                        "name": t["name"],
                        "content": str(output)
                    })

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
        else:
            return t_param.get("command", str(t_param))
