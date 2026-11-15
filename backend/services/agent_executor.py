import time
import json
from typing import List, Dict, Any, Generator, Optional, Protocol
from openai import OpenAI
import openai
import httpx
import copy

from backend.services.agent_tools import TOOL_REGISTRY
from backend.services.stream_parser import StreamParser
from backend.services.tool_engine import ToolExecutionEngine

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

        controller = kwargs.get("stream_controller")

        max_retries = 10
        base_wait = 2

        for attempt in range(1, max_retries + 1):
            if controller and controller.is_aborted:
                return

            response = None
            try:
                response = self.client.chat.completions.create(**call_kwargs)
                if controller:
                    controller.set_stream(response)
                    if controller.is_aborted:
                        return
                
                if attempt > 1:
                    yield {"type": "retry_status", "text": json.dumps({"success": True})}

                for chunk in response:
                    if controller and controller.is_aborted:
                        return
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                            yield {"type": "thinking", "text": delta.reasoning_content}
                        if delta.content:
                            yield {"type": "text", "text": delta.content}
                        if hasattr(delta, "tool_calls") and delta.tool_calls:
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
                # If controller was aborted, exit immediately without retrying
                if controller and controller.is_aborted:
                    return

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
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass


class AgentExecutor:
    def __init__(self, llm_client: LLMClientProtocol, max_iterations: Optional[int] = None):
        self.llm_client = llm_client
        self.max_iterations = max_iterations

    def run(self, messages: List[Dict[str, Any]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        current_messages = messages.copy()

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
        controller = kwargs.get("stream_controller")

        while self.max_iterations is None or self.max_iterations <= 0 or iteration < self.max_iterations:
            if controller and controller.is_aborted:
                return

            iteration += 1
            parser = StreamParser()

            # 1. Pipeline Stage 1: Stream chunks through the Parser
            for chunk in self.llm_client.stream_completion(current_messages, **kwargs):
                if controller and controller.is_aborted:
                    return
                event = parser.process_chunk(chunk)
                if event:
                    yield event

            # If no tools were called, we are done
            if not parser.has_tool_calls():
                break

            parsed_tools = parser.get_parsed_tool_calls()
            full_content = parser.get_clean_content()

            # Prepare assistant message with native OpenAI tool calls (function.arguments must be a JSON string)
            assistant_msg = {"role": "assistant"}
            assistant_msg["content"] = full_content if full_content.strip() else ""
            
            cleaned_tool_calls = []
            for tc in parsed_tools:
                payload = copy.deepcopy(tc.get("raw_payload", {}))
                payload.pop("arguments", None)
                func = payload.get("function")
                if not isinstance(func, dict):
                    func = {"name": tc.get("name", ""), "arguments": "{}"}
                    payload["function"] = func

                raw_args = func.get("arguments")
                if isinstance(raw_args, str):
                    func["arguments"] = raw_args if raw_args.strip() else "{}"
                elif raw_args is None:
                    func["arguments"] = "{}"
                else:
                    func["arguments"] = json.dumps(raw_args, ensure_ascii=False)
                cleaned_tool_calls.append(payload)

            assistant_msg["tool_calls"] = cleaned_tool_calls
            current_messages.append(assistant_msg)

            # 3. Pipeline Stage 3: Execute tools
            engine = ToolExecutionEngine()
            for event in engine.execute_tools(parsed_tools):
                if event["type"] == "tool_results":
                    for res in event["results"]:
                        current_messages.append(res)
                else:
                    yield event
