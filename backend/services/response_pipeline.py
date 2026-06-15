import json
import logging
import re
from typing import AsyncGenerator, Callable, Dict, Any, List, Optional, Awaitable, Union, Generator

from backend.database import get_db_connection
from backend.services.rag_factory import save_memory_to_rag

logger = logging.getLogger(__name__)

def json_escape(text: str) -> str:
    """包装为 JSON 字符串，便于前端原样解析"""
    return json.dumps({"text": text}, ensure_ascii=False)

class TagStreamInterceptor:
    """
    流式拦截器：处理大模型输出流，缓冲并拦截特定的 XML 标签和 [SYSTEM_PASS]。
    向外只 yield 纯净的（去除了标签的）文本或字典对象。
    """
    def __init__(self):
        self.buffer = ""
        self.in_tag = False
        self.current_tag_name = ""
        self.intercepted_data = {}  # 存储拦截到的标签数据，例如 {"glossary": [...], "explainer": [...], "system_pass": True}
        self.clean_text_accumulated = "" # 积累最终的纯净文本用于记忆保存

        # 定义需要拦截的标签列表
        self.target_tags = ["glossary", "explainer", "new_course"]

    def _flush_buffer_safe(self) -> str:
        """安全地清空缓冲区并返回纯净文本"""
        res = self.buffer
        self.buffer = ""
        self.clean_text_accumulated += res
        return res

    def process_chunk(self, chunk: Union[str, Dict[str, Any]]) -> Generator[Union[str, Dict[str, Any]], None, None]:
        """处理每一个流入的 chunk"""
        is_dict = isinstance(chunk, dict)
        if is_dict:
            if chunk.get("type") != "text":
                # 如果是非文本字典（如 thinking, tool_start），直接放行
                if not self.in_tag and self.buffer:
                    if not self.buffer.startswith("<") and not self.buffer.startswith("["):
                         safe_text = self._flush_buffer_safe()
                         if safe_text: yield safe_text
                yield chunk
                return
            else:
                text = chunk.get("text", "")
        else:
            text = chunk

        # 2. 进行状态机缓冲处理
        for char in text:
            if not self.in_tag and not self.buffer and (char == '<' or char == '['):
                self.buffer += char
                continue

            if self.buffer or self.in_tag:
                self.buffer += char

                # 检查是否匹配到了 [SYSTEM_PASS]
                if self.buffer.startswith("["):
                    if self.buffer == "[SYSTEM_PASS]":
                        self.intercepted_data["system_pass"] = True
                        self.buffer = "" # 拦截成功，清空缓冲
                    elif not "[SYSTEM_PASS]".startswith(self.buffer):
                        # 不是目标标签，释放缓冲
                        safe_text = self._flush_buffer_safe()
                        if safe_text:
                            yield {"type": "text", "text": safe_text} if is_dict else safe_text

                # 检查是否匹配到了 XML 标签
                elif self.buffer.startswith("<"):
                    # 尝试解析当前缓冲是否是一个完整的标签
                    if ">" in self.buffer:
                        # 检查是否是单闭合标签 <... />
                        if self.buffer.endswith("/>"):
                            tag_match = re.match(r'<([a-zA-Z_]+)([^>]*)/>', self.buffer)
                            if tag_match and tag_match.group(1) in self.target_tags:
                                self._store_tag(tag_match.group(1), tag_match.group(2), "")
                                self.buffer = "" # 拦截成功
                            else:
                                # 未知标签，直接放行
                                safe_text = self._flush_buffer_safe()
                                if safe_text:
                                    yield {"type": "text", "text": safe_text} if is_dict else safe_text

                        # 检查是否是闭合标签结束 </tag>
                        elif re.search(r'</([a-zA-Z_]+)>$', self.buffer):
                            tag_match = re.search(r'<([a-zA-Z_]+)([^>]*)>([\s\S]*?)</\1>$', self.buffer)
                            if tag_match and tag_match.group(1) in self.target_tags:
                                self._store_tag(tag_match.group(1), tag_match.group(2), tag_match.group(3))
                                self.buffer = "" # 拦截成功
                                self.in_tag = False
                            else:
                                # 未知标签，直接放行
                                safe_text = self._flush_buffer_safe()
                                if safe_text:
                                    yield {"type": "text", "text": safe_text} if is_dict else safe_text
                                self.in_tag = False

                        # 检查是否是起始标签结束 <tag>
                        else:
                            start_match = re.match(r'<([a-zA-Z_]+)([^>]*)>$', self.buffer)
                            if start_match:
                                if start_match.group(1) in self.target_tags:
                                    self.in_tag = True # 进入标签内部，继续缓冲
                                else:
                                    # 不是我们要拦截的标签，放行
                                    safe_text = self._flush_buffer_safe()
                                    if safe_text:
                                        yield {"type": "text", "text": safe_text} if is_dict else safe_text
            else:
                self.clean_text_accumulated += char
                if is_dict:
                    # 复制原有的字典结构并替换文本，防止丢失原本的附加信息（如 id 等）
                    out_dict = dict(chunk)
                    out_dict["text"] = char
                    yield out_dict
                else:
                    yield char

    def _store_tag(self, tag_name: str, attrs_str: str, content: str):
        """解析并存储拦截到的标签数据"""
        attrs = {}
        for match in re.finditer(r'([a-zA-Z_]+)="([^"]*)"', attrs_str):
            attrs[match.group(1)] = match.group(2)

        if tag_name not in self.intercepted_data:
            self.intercepted_data[tag_name] = []

        self.intercepted_data[tag_name].append({
            "attrs": attrs,
            "content": content
        })

    def finish(self) -> Generator[Union[str, Dict[str, Any]], None, None]:
        """流结束时调用，清空剩余缓冲"""
        if self.buffer:
            # 如果流结束了还有缓冲，说明是未闭合的标签或普通文本，直接放行
            safe_text = self._flush_buffer_safe()
            if safe_text: yield {"type": "text", "text": safe_text}


class ResponsePipeline:
    """
    聊天响应管道：负责流缓冲、SSE 格式化、副作用派发和最终的记忆保存。
    """
    def __init__(self, original_user_msg: str):
        self.original_user_msg = original_user_msg
        self.interceptor = TagStreamInterceptor()
        self.handlers: Dict[str, Callable] = {}

    def register_handler(self, tag_name: str, handler: Callable):
        """注册副作用处理器"""
        self.handlers[tag_name] = handler

    def process_stream(self, raw_stream: Generator) -> Generator[str, None, None]:
        """处理原始大模型流，并转换为 SSE 格式发送"""
        was_aborted = False
        try:
            for chunk in raw_stream:
                # 如果底层传来的是已经包好的 dict，比如工具输出或者之前 chat.py 里的 dict，
                # stream_chat 中其实 yield 的是原始 chunk 还是 dict？
                # 由于底层的 stream_chat 可能会 yield dict 或 str，拦截器能处理。
                for processed_chunk in self.interceptor.process_chunk(chunk):
                    if isinstance(processed_chunk, dict):
                        yield f"data: {json.dumps(processed_chunk, ensure_ascii=False)}\n\n"
                    else:
                        yield f"data: {json_escape(processed_chunk)}\n\n"

            # 流结束
            for processed_chunk in self.interceptor.finish():
                if isinstance(processed_chunk, dict):
                    yield f"data: {json.dumps(processed_chunk, ensure_ascii=False)}\n\n"
                else:
                    yield f"data: {json_escape(processed_chunk)}\n\n"

        except GeneratorExit:
            was_aborted = True
            logger.info("Client disconnected/aborted. Skipping side-effects and database save.")
            raise
        except Exception as e:
            import traceback
            logger.error(f"ResponsePipeline stream error: {e}")
            traceback.print_exc()
            yield f"data: {json_escape('[后端报错] 聊天流异常: ' + str(e))}\n\n"
        finally:
            if not was_aborted:
                self._execute_side_effects()
                self._save_memory()

    def _execute_side_effects(self):
        """同步执行所有拦截到的标签副作用"""
        data = self.interceptor.intercepted_data

        # 处理 [SYSTEM_PASS]
        if data.get("system_pass") and "system_pass" in self.handlers:
            try:
                self.handlers["system_pass"]()
            except Exception as e:
                logger.error(f"Error handling system_pass: {e}")

        # 处理其他 XML 标签
        for tag_name, items in data.items():
            if tag_name == "system_pass": continue
            if tag_name in self.handlers:
                for item in items:
                    try:
                        self.handlers[tag_name](item["attrs"], item["content"])
                    except Exception as e:
                        logger.error(f"Error handling tag <{tag_name}>: {e}")

    def _save_memory(self):
        """保存干净的对话文本到记忆系统"""
        clean_text = self.interceptor.clean_text_accumulated.strip()
        if not self.original_user_msg or not clean_text:
            return

        try:
            memory_content = f"【对话记录】\n用户：{self.original_user_msg}\n媚吻锋：{clean_text}"
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memory_logs (content, level, status) VALUES (?, 0, 'active')",
                (memory_content,)
            )
            conn.commit()

            # 自动压缩检查
            cursor.execute("SELECT COUNT(*) FROM memory_logs WHERE level = 0 AND status = 'active'")
            active_level0_count = cursor.fetchone()[0]
            if active_level0_count >= 10:
                import threading
                from backend.services.memory_decay import process_memory_decay
                threading.Thread(target=process_memory_decay, daemon=True).start()

            conn.close()

            # 存入 RAG 向量库
            save_memory_to_rag(self.original_user_msg, clean_text, level=0)
        except Exception as e:
            logger.error(f"Failed to save memory in pipeline: {e}")
