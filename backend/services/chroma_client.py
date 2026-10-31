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
LOCAL_MODELS_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rag_index", "models"))

# 优先锁定工程本地模型目录，防止模型缓存落入系统 C 盘 (C:\Users\<user>\.cache\huggingface)
if not os.environ.get("HF_HOME"):
    os.environ["HF_HOME"] = LOCAL_MODELS_DIR

# 禁用 Transformers 异步多线程权重加载，规避 Windows Python 3.13 下 torch.storage 多线程并发 access violation
os.environ["HF_DEACTIVATE_ASYNC_LOAD"] = "1" 

def _get_chroma_client():
    try:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        return client
    except ImportError:
        raise RuntimeError("chromadb 未安装，请运行: pip install chromadb sentence-transformers")

def _check_hf_reachable(timeout: float = 2.0) -> bool:
    """快速探测 Hugging Face 是否可达（超时默认 2 秒，避免阻塞启动）"""
    import socket
    try:
        s = socket.create_connection(("huggingface.co", 443), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def _get_embedding_fn():
    """优先用本地已缓存的 sentence-transformers 模型（纯离线秒级启动），未缓存时探测网络与自动降级"""
    try:
        if not os.environ.get("HF_HOME"):
            os.environ["HF_HOME"] = LOCAL_MODELS_DIR

        # 0. 快速探测本地模型权重目录是否存在（毫秒级判断）
        cached_model_path = os.path.join(
            LOCAL_MODELS_DIR, 
            "hub", 
            "models--sentence-transformers--paraphrase-multilingual-MiniLM-L12-v2"
        )
        has_local_weights = os.path.exists(cached_model_path) and any(
            fname.endswith((".safetensors", ".bin")) for _, _, files in os.walk(cached_model_path) for fname in files
        )

        if has_local_weights:
            # 本地模型完备：直接锁死离线模式，禁止任何外部联网行为
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"
            try:
                from chromadb.utils import embedding_functions
                ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name="paraphrase-multilingual-MiniLM-L12-v2",
                    local_files_only=True
                )
                return ef
            except Exception as e:
                print(f"[Embedding Warning] 本地模型加载失败 ({e})，直接回退至内置轻量嵌入...")
                return None

        from chromadb.utils import embedding_functions

        # 1. 尝试直接读取本地磁盘模型缓存（免除向 HuggingFace Hub 联网校验导致的卡顿与未授权警告）
        try:
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2",
                local_files_only=True
            )
            return ef
        except Exception:
            pass  # 本地尚无完整缓存

        # 2. 本地无模型缓存时，先快速探测 Hugging Face 连通性（2 秒超时）
        print("[Embedding] 本地未检测到模型缓存，正在探测 Hugging Face 网络连通性...")
        if _check_hf_reachable(timeout=2.0):
            print("[Embedding] Hugging Face 连通正常，开始拉取模型权重...")
            ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
            return ef
        else:
            print("[Embedding Warning] Hugging Face 连接超时或无法访问，跳过联网，回退至内置默认嵌入。")
            return None
    except Exception as e:
        print(f"[Embedding Warning] 初始化嵌入模型异常 ({e})，回退至内置默认嵌入。")
        return None  # 让 chromadb 用内置默认嵌入（all-MiniLM-L6-v2）

def _get_overlap_text(text: str, max_overlap: int) -> str:
    """获取不超过 max_overlap 且保持完整句子或段落边界的末尾文本"""
    if not text or len(text) <= max_overlap:
        return text
    tail = text[-max_overlap:]
    match = re.search(r'[。！？\.\!\?\n]\s*', tail)
    if match and match.end() < len(tail):
        return tail[match.end():]
    match_all = list(re.finditer(r'[。！？\.\!\?\n]\s*', text))
    if match_all:
        for m in reversed(match_all):
            if m.end() < len(text) and len(text) - m.end() <= max_overlap * 2:
                return text[m.end():]
    return ""


def _extract_document_header(text: str) -> str:
    """提取文档的顶层标题或时间戳元数据头，供后续切片继承 (ADR-012)"""
    if not text:
        return ""
    # 1. 匹配 【记录时间：...】 格式
    time_match = re.match(r'^(【记录时间：[^】]+】)', text.strip())
    if time_match:
        return time_match.group(1).strip()
    # 2. 匹配 Markdown 一级标题 # Title
    h1_match = re.search(r'^#\s+([^\n]+)', text, re.MULTILINE)
    if h1_match:
        title = h1_match.group(1).strip()
        return f"【文档：{title}】"
    return ""


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 60, inherit_header: bool = True) -> List[str]:
    """按句子边界切块，保持一定重叠，并支持多切片元数据头继承 (ADR-012)"""
    text_clean = text.strip()
    if not text_clean:
        return []

    header_prefix = _extract_document_header(text_clean) if inherit_header else ""

    # 先按段落切（两个换行为段落分隔）
    paragraphs = re.split(r'\n{2,}', text_clean)
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
                    current = _get_overlap_text(current, overlap) + sent
        else:
            if len(current) + len(para) <= chunk_size:
                current += "\n" + para
            else:
                if current:
                    chunks.append(current.strip())
                current = _get_overlap_text(current, overlap) + "\n" + para

    if current.strip():
        chunks.append(current.strip())
    
    cleaned_chunks = [c for c in chunks if c.strip()]

    # 若存在多个切片且提取到了头部标识，为后续切片继承头部信息 (ADR-012)
    if len(cleaned_chunks) > 1 and header_prefix:
        for i in range(1, len(cleaned_chunks)):
            if not cleaned_chunks[i].startswith(header_prefix):
                cleaned_chunks[i] = f"{header_prefix}（接上文）\n{cleaned_chunks[i]}"

    return cleaned_chunks


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
                if collection_name == "memory_knowledge":
                    # ADR-012: 压缩日记属于高密度原子事件胶囊，整篇完整入库，绝不切碎
                    # 避免 400 字符机械切割导致时间戳脱落与文字断句。若偶遇极端超长文档（> 2000字）才进行保护性切分。
                    if len(content.strip()) <= 2000:
                        chunks = [content.strip()]
                    else:
                        chunks = _chunk_text(content, chunk_size=800, overlap=80, inherit_header=True)
                else:
                    # 教材技术文档（Classroom_Knowledge 等）：按句号自然分块并继承文档标题 (ADR-012)
                    chunks = _chunk_text(content, chunk_size=400, overlap=60, inherit_header=True)
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
                    results = collection.query(query_texts=[query], n_results=min(n_results, count), include=["documents", "distances"])
                    docs = results.get("documents", [[]])[0]
                    distances = results.get("distances", [[]])[0]
                    if distances and len(distances) == len(docs):
                        # 物理区间校准阈值 (Bug #10): 实测技术课件召回范围 [0.15~0.66]，闲聊短句 >0.78，收敛阈值设定为 0.75
                        docs = [doc for doc, dist in zip(docs, distances) if dist <= 0.75]
                    all_chunks.extend(docs)
                except Exception:
                    continue
            
            return all_chunks
        except Exception as e:
            print(f"ChromaDB retrieval error: {e}")
            return []

    # ── 对话记忆专用接口 ──────────────────────────────────────────
    def save_memory(self, user_msg: str, assistant_msg: str, level: int = 0, session_id: Optional[str] = None) -> Optional[str]:
        """把一轮对话存入 conversation_memory collection，用于后续语义召回，返回 doc_id"""
        try:
            self._ensure_client()
            collection = self._get_collection("conversation_memory")
            
            from datetime import datetime
            time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            combined = f"【对话记录 ({time_str})】\n用户：{user_msg}\n媚吻锋：{assistant_msg}"
            doc_id = hashlib.md5(combined[:200].encode("utf-8")).hexdigest()
            
            collection.upsert(
                documents=[combined],
                ids=[doc_id],
                metadatas=[{
                    "level": level,
                    "timestamp": datetime.now().isoformat(),
                    "user_snippet": user_msg[:100],
                    "session_id": session_id or ""
                }]
            )
            return doc_id
        except Exception as e:
            print(f"ChromaDB save_memory error: {e}")
            return None

    def delete_memory(self, doc_id: str) -> bool:
        """从 conversation_memory collection 中精准物理移除指定的记忆切片"""
        if not doc_id:
            return False
        try:
            self._ensure_client()
            collection = self._get_collection("conversation_memory")
            collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            print(f"ChromaDB delete_memory error: {e}")
            return False

    def retrieve_memory(self, query: str, n_results: int = 3) -> List[str]:
        """单独从对话记忆 collection 检索（供外部直接调用）"""
        try:
            self._ensure_client()
            collection = self._get_collection("conversation_memory")
            count = collection.count()
            if count == 0:
                return []
            results = collection.query(query_texts=[query], n_results=min(n_results, count), include=["documents", "distances"])
            docs = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            if distances and len(distances) == len(docs):
                # 物理区间校准阈值 (Bug #10): 收敛阈值设定为 0.75
                docs = [doc for doc, dist in zip(docs, distances) if dist <= 0.75]
            return docs
        except Exception as e:
            print(f"ChromaDB retrieve_memory error: {e}")
            return []


    def heal_memory_knowledge_from_db(self, db_path: Optional[str] = None, prune_orphans: bool = True) -> Dict[str, Any]:
        """
        根据 ADR-012 将 SQLite 中的 Level 1~4 日记重新同步为整篇原子切片，
        消除 ChromaDB 中历史遗留的碎片化 Chunk。
        若 prune_orphans 为 True，同时清理已在 SQLite 中被删除的幽灵孤儿日记 (Orphans)。
        纯只读连接 SQLite classroom.db，对原数据库无任何写操作。
        """
        import sqlite3
        if not db_path:
            db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "classroom.db"))
        
        if not os.path.exists(db_path):
            return {"status": "error", "message": f"Database file not found: {db_path}"}
            
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT id, level, timestamp, summary FROM memory_logs WHERE level > 0 ORDER BY id ASC")
            rows = cursor.fetchall()
            conn.close()

            files_content = {}
            for r in rows:
                summary = r["summary"] or ""
                if not summary.strip():
                    continue
                filename = f"Memory_Level_{r['level']}_{r['id']}.md"
                time_str = r["timestamp"] or ""
                if summary.strip().startswith("【记录时间") or summary.strip().startswith("【时间跨度"):
                    sync_text = summary.strip()
                else:
                    sync_text = f"【记录时间：{time_str}】\n{summary.strip()}"
                files_content[filename] = sync_text

            if not files_content:
                return {"status": "success", "message": "没有找到需要同步的日记条目。"}

            res = self.sync_knowledge(files_content, dataset_name="Memory_Knowledge")

            if prune_orphans:
                try:
                    coll = self._get_collection("memory_knowledge")
                    all_meta = coll.get(include=["metadatas"])
                    orphan_ids = []
                    for meta, doc_id in zip(all_meta.get("metadatas", []), all_meta.get("ids", [])):
                        src = meta.get("source_file")
                        if src and src not in files_content:
                            orphan_ids.append(doc_id)
                    if orphan_ids:
                        coll.delete(ids=orphan_ids)
                except Exception:
                    pass

            return res
        except Exception as e:
            return {"status": "error", "message": str(e)}


chroma_rag_client = ChromaRAGClient()
