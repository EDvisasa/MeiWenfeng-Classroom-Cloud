"""
ChromaDB 本地向量知识库客户端
- 提供与 ragflow_client.py 完全相同的接口：retrieve / sync_knowledge / get_sync_status
- 使用两个 Collection 分离：
    * "classroom_knowledge" — 讲义、人设卡等结构化知识（手动同步）
    * "conversation_memory"  — 对话记忆（每次对话后自动写入）
- 嵌入模型：优先使用本地 sentence-transformers paraphrase-multilingual-MiniLM-L12-v2（中英文双语，小而快）
  fallback: chromadb 内置默认嵌入（all-MiniLM-L6-v2）
"""
import os
import hashlib
import re
from typing import Dict, List, Any, Optional

CHROMA_PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rag_index", "chroma")

def _get_chroma_client():
    try:
        import chromadb
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        return client
    except ImportError:
        raise RuntimeError("chromadb 未安装，请运行: pip install chromadb sentence-transformers")

def _get_embedding_fn():
    """优先用 sentence-transformers 多语言小模型，失败则 fallback 至 chromadb 默认"""
    try:
        from chromadb.utils import embedding_functions
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="paraphrase-multilingual-MiniLM-L12-v2"
        )
        return ef
    except Exception:
        return None  # 让 chromadb 用内置默认嵌入（all-MiniLM-L6-v2）

def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 60) -> List[str]:
    """按句子边界切块，保持一定重叠"""
    # 先按段落切（两个换行为段落分隔）
    paragraphs = re.split(r'\n{2,}', text.strip())
    chunks = []
    current = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # 如果单个段落超过 chunk_size，继续按句子切
        if len(para) > chunk_size:
            sentences = re.split(r'(?<=[。！？\.\!\?])\s*', para)
            for sent in sentences:
                if len(current) + len(sent) <= chunk_size:
                    current += sent
                else:
                    if current:
                        chunks.append(current.strip())
                    current = current[-overlap:] + sent if len(current) > overlap else sent
        else:
            if len(current) + len(para) <= chunk_size:
                current += "\n" + para
            else:
                if current:
                    chunks.append(current.strip())
                current = current[-overlap:] + "\n" + para if len(current) > overlap else para

    if current.strip():
        chunks.append(current.strip())
    
    return [c for c in chunks if c.strip()]


import threading
from backend.services.rag_factory import RAGClient

class ChromaRAGClient(RAGClient):
    def __init__(self):
        self._client = None
        self._ef = None
        self._lock = threading.Lock()

    def _ensure_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
                    # 先初始化变量，最后再赋值给 self._client，避免其他线程过早看到 _client 不为空
                    client = _get_chroma_client()
                    ef = _get_embedding_fn()
                    self._ef = ef
                    self._client = client

    def _get_collection(self, name: str):
        self._ensure_client()
        kwargs = {"name": name}
        if self._ef:
            kwargs["embedding_function"] = self._ef
        return self._client.get_or_create_collection(**kwargs)

    # ── 知识库文件同步 ────────────────────────────────────────────
    def sync_knowledge(self, files_content: Dict[str, str], dataset_name: str = "Classroom_Knowledge") -> Dict[str, Any]:
        """把 Markdown 文件分块后存入 ChromaDB，支持幂等更新（按文件名删旧存新）"""
        try:
            self._ensure_client()
            collection_name = dataset_name.lower().replace(" ", "_").replace("-", "_")
            collection = self._get_collection(collection_name)
            
            total_chunks = 0
            for filename, content in files_content.items():
                short_name = filename.split("/")[-1].split("\\")[-1]
                
                # 1. 删除该文件的所有旧块
                try:
                    existing = collection.get(where={"source_file": short_name})
                    if existing and existing.get("ids"):
                        collection.delete(ids=existing["ids"])
                except Exception:
                    pass
                
                # 2. 切块并写入
                chunks = _chunk_text(content)
                if not chunks:
                    continue

                ids = [hashlib.md5(f"{short_name}::chunk::{i}".encode()).hexdigest() for i in range(len(chunks))]
                metadatas = [{"source_file": short_name, "chunk_index": i} for i in range(len(chunks))]
                
                collection.upsert(documents=chunks, ids=ids, metadatas=metadatas)
                total_chunks += len(chunks)
            
            return {"status": "success", "message": f"成功同步 {len(files_content)} 份文件（共 {total_chunks} 块）到本地 ChromaDB 知识库 [{collection_name}]。"}
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"status": "error", "message": f"ChromaDB 同步失败: {str(e)}"}

    def get_sync_status(self, dataset_name: str = "Classroom_Knowledge") -> Dict[str, Any]:
        """返回已索引文件列表及块数"""
        try:
            self._ensure_client()
            collection_name = dataset_name.lower().replace(" ", "_").replace("-", "_")
            collection = self._get_collection(collection_name)
            
            all_meta = collection.get(include=["metadatas"])
            file_chunks: Dict[str, int] = {}
            for meta in (all_meta.get("metadatas") or []):
                fname = meta.get("source_file", "unknown")
                file_chunks[fname] = file_chunks.get(fname, 0) + 1
            
            documents = {fname: {"status": "done", "chunk_count": cnt} for fname, cnt in file_chunks.items()}
            return {"status": "success", "documents": documents}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def retrieve(self, query: str, dataset_names: Optional[List[str]] = None, n_results: int = 4) -> List[str]:
        """语义检索：从知识库 + 对话记忆中分别召回，返回 chunk 列表"""
        if dataset_names is None:
            dataset_names = ["Classroom_Knowledge"]
        try:
            self._ensure_client()
            all_chunks = []
            
            for name in dataset_names:
                collection_name = name.lower().replace(" ", "_").replace("-", "_")
                try:
                    collection = self._get_collection(collection_name)
                    count = collection.count()
                    if count == 0:
                        continue
                    results = collection.query(query_texts=[query], n_results=min(n_results, count))
                    docs = results.get("documents", [[]])[0]
                    all_chunks.extend(docs)
                except Exception:
                    continue
            
            return all_chunks
        except Exception as e:
            print(f"ChromaDB retrieval error: {e}")
            return []

    # ── 对话记忆专用接口 ──────────────────────────────────────────
    def save_memory(self, user_msg: str, assistant_msg: str, level: int = 0) -> bool:
        """把一轮对话存入 conversation_memory collection，用于后续语义召回"""
        try:
            self._ensure_client()
            collection = self._get_collection("conversation_memory")
            
            combined = f"用户：{user_msg}\n媚吻锋：{assistant_msg}"
            doc_id = hashlib.md5(combined[:200].encode("utf-8")).hexdigest()
            
            from datetime import datetime
            collection.upsert(
                documents=[combined],
                ids=[doc_id],
                metadatas=[{
                    "level": level,
                    "timestamp": datetime.now().isoformat(),
                    "user_snippet": user_msg[:100]
                }]
            )
            return True
        except Exception as e:
            print(f"ChromaDB save_memory error: {e}")
            return False

    def retrieve_memory(self, query: str, n_results: int = 3) -> List[str]:
        """单独从对话记忆 collection 检索（供外部直接调用）"""
        try:
            self._ensure_client()
            collection = self._get_collection("conversation_memory")
            count = collection.count()
            if count == 0:
                return []
            results = collection.query(query_texts=[query], n_results=min(n_results, count))
            return results.get("documents", [[]])[0]
        except Exception as e:
            print(f"ChromaDB retrieve_memory error: {e}")
            return []


chroma_rag_client = ChromaRAGClient()
