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
    is_safe: bool = True

    def execute(self, params: dict) -> str:
        raise NotImplementedError()

import time
import uuid

# Global dictionary for BashTool HITL approvals
PENDING_APPROVALS = {}

class BashTool(AgentTool):
    name = "execute_bash"
    description = "Execute a local terminal command. Use this for running tests, managing files, and checking system state."
    is_safe = False
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
            timeout = getattr(self, 'approval_timeout', 60)
            
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
                    
                time.sleep(0.05)

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

        ext = path.lower().split('.')[-1] if '.' in path else ''
        binary_exts = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'ico', 'pdf', 'zip', 'rar', 'tar', 'gz', '7z', 'mp3', 'mp4', 'wav', 'avi', 'mkv', 'exe', 'dll', 'so', 'dylib'}
        if ext in binary_exts:
            return f"[Error] Cannot read binary file '{path}' as text. If this is an image, please use vision tools."

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

class OpenClawAgentTool(AgentTool):
    name = "call_openclaw_agent"
    description = "Delegate a task or instruction to the external WSL OpenClaw Gateway agent (BaiTizi). Automatically verifies online status before sending."
    is_safe = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "task_message": {
                "type": "string",
                "description": "The task instruction or prompt to delegate to the OpenClaw agent."
            },
            "agent_id": {
                "type": "string",
                "description": "Optional target agent ID inside OpenClaw (default: 'main')."
            }
        },
        "required": ["task_message"]
    }

    def execute(self, params: dict) -> str:
        task_message = params.get("task_message", "").strip()
        agent_id = params.get("agent_id", "main")
        if not task_message:
            return "[Error] No task_message provided for OpenClaw agent."

        from backend.services.openclaw_client import check_openclaw_status, send_to_openclaw
        status = check_openclaw_status(timeout=3, ttl=5)
        if not status.get("online", False):
            reason = status.get("reason", "WSL Gateway Offline")
            return f"[Status: Offline] 白提子（OpenClaw 网关节点）当前离线或未运行（原因: {reason}）。请向用户说明节点未启动，建议先在终端启动网关后再尝试调用。"

        res = send_to_openclaw(task_message, agent=agent_id, json_output=True)
        return str(res)

# Register tools
TOOL_REGISTRY = {
    "read_file": ReadFileTool(),
    "grep_search": GrepSearchTool(),
    "execute_bash": BashTool(),
    "replace_file_content": ReplaceFileContentTool(),
    "create_file": CreateFileTool(),
    "web_search": WebSearchTool(),
    "read_url_content": ReadUrlContentTool(),
    "call_openclaw_agent": OpenClawAgentTool(),
}


