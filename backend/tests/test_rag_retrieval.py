import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.routers.chat import send_message, ChatRequest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from backend.routers.chat import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_long_file_rag_retrieval_uses_original_message(tmp_path):
    """
    Test that when @current_file expands a long file, the RAG retrieval
    still uses the short, original message, preventing ChromaDB crash or poor search results.
    """
    # Create a fake file
    fake_file = tmp_path / "fake_file.txt"
    fake_file.write_text("This is a very long file content. " * 500, encoding="utf-8")
    
    # Payload simulating user sending "@current_file"
    original_msg = "宝贝，6-2干了啥？ @current_file"
    payload = {
        "messages": [{"role": "user", "content": original_msg}],
        "persona_type": "simplified",
        "current_file_path": str(fake_file),
        "cursor_line": 1
    }

    # Mock the RAG client
    with patch("backend.services.rag_factory.get_rag_client") as mock_get_rag:
        
        mock_rag_instance = MagicMock()
        mock_get_rag.return_value = mock_rag_instance
        
        # We don't care about the actual streaming output, just the arguments passed to retrieve
        try:
            list(send_message(ChatRequest(**payload)))
        except Exception:
            pass # Ignore streaming or DB errors
            
        # The rag client retrieve should be called with the original message, NOT the expanded one!
        # Because we only want to search the vector db with "宝贝，6-2干了啥？ @current_file", not 5000 characters of text!
        assert mock_rag_instance.retrieve.call_count >= 2
        args, kwargs = mock_rag_instance.retrieve.call_args_list[0]
        
        # This will currently FAIL because chat.py passes last_user_msg (which includes <file_content>...)
        assert "<file_content" not in args[0], "RAG retrieval query contains expanded file content!"
        assert args[0] == original_msg, f"Expected '{original_msg}', got '{args[0][:100]}...'"


def test_rag_retrieval_filters_out_irrelevant_casual_chat_bug_10():
    """
    TDD [Bug #10] RED step:
    当用户输入纯闲聊或简单问候（如 "你好呀"、"吃了没"、"呃呃呃"）时，
    ChromaDB 语义检索必须通过距离阈值（distance threshold，如 distance > 1.2 或 similarity < 0.3）
    拦截不相关资料的机械召回，返回空列表，防止闲聊时检索出无关代码或专业讲义污染上下文。
    """
    from backend.services.chroma_client import chroma_rag_client
    
    with patch.object(chroma_rag_client, "_get_collection") as mock_get_coll:
        mock_coll = MagicMock()
        mock_get_coll.return_value = mock_coll
        mock_coll.count.return_value = 5
        # 模拟 ChromaDB query 返回很大的距离值（例如 1.5 表示极度不相关）
        mock_coll.query.return_value = {
            "documents": [["《嵌入式GPIO寄存器配置规范》", "万欲魔宗宗规第三条"]],
            "distances": [[1.5, 1.6]]
        }
        
        # 检索闲聊语
        results = chroma_rag_client.retrieve("你好呀，吃了没")
        
        # 距离 1.5 > 设定的阈值（例如 1.2 或 1.0），必须被拦截过滤，返回空列表！
        assert len(results) == 0, f"Expected 0 results for casual chat with high distance, got {results}"


def test_chunk_text_uses_natural_boundaries_without_character_truncation_bug_11():
    """
    TDD [Bug #11] RED step:
    验证 _chunk_text 在切块重叠时，不会使用简单的字符串硬截断 [-overlap:]，
    导致单词或句首被生硬切断（出现半个词或乱码字符）。
    重叠内容必须保留完整的自然句子或段落边界。
    """
    from backend.services.chroma_client import _chunk_text
    
    # 构造一段由多个长句组成的文章
    sent1 = "第一句这是一个非常非常长但是结构完整的中文句子用以测试文本分块逻辑。" * 5  # 175字
    sent2 = "第二句这是紧接着的另一个完整句子用于验证句界分隔是否会发生乱码或生硬截断。" * 5 # 190字
    sent3 = "第三句我们希望分块结果在发生重叠时能保持整句完整而不是从句子中间割裂。" * 5  # 185字
    text = f"{sent1}。{sent2}。{sent3}。"
    
    chunks = _chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) >= 2
    
    # 验证每一个 chunk 中，绝对不会存在从单句中间字符硬切断产生的残缺片段
    for i, c in enumerate(chunks):
        if i > 0:
            idx = text.find(c[:20])
            assert idx != -1
            if idx > 0:
                prev_char = text[idx - 1]
                assert prev_char in ["。", "！", "？", "\n"], f"Chunk {i} started at middle of sentence! prev_char='{prev_char}', chunk start='{c[:20]}'"

