"""
外部 RAG API 客户端 —— 对接任意支持 OpenAI 兼容检索接口或自定义格式的外部知识库服务。
（如 Dify、FastGPT、AnythingLLM 等）

接口约定（外部服务需实现以下两个端点）：
  POST {base_url}/retrieve   body: {"query": "...", "top_k": 3}
                              resp: {"chunks": ["...", "..."]}

  POST {base_url}/upload     multipart form: file=<filename, content>
                              resp: {"status": "ok"}  (可选，同步失败时降级)
"""
import httpx
from typing import Dict, Any, List, Optional
from backend.services.rag_factory import RAGClient


class ExternalRAGClient(RAGClient):
    def __init__(self, base_url: str = "", api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    @property
    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def retrieve(self, query: str, dataset_names: Optional[List[str]] = None, n_results: int = 4) -> List[str]:
        """向外部 RAG 服务发送检索请求"""
        if not self.base_url:
            return []
        try:
            safe_url = self.base_url.replace("://localhost:", "://127.0.0.1:")
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(
                    f"{safe_url}/retrieve",
                    json={"query": query, "top_k": n_results},
                    headers=self._headers
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # 兼容不同响应格式
                    chunks = data.get("chunks") or data.get("data", {}).get("chunks", [])
                    if isinstance(chunks, list):
                        return [c if isinstance(c, str) else c.get("content", "") for c in chunks]
        except Exception as e:
            print(f"ExternalRAG retrieve error: {e}")
        return []

    def sync_knowledge(self, files_content: Dict[str, str], dataset_name: str = "Classroom_Knowledge") -> Dict[str, Any]:
        """向外部 RAG 服务上传文件（如果支持的话）"""
        if not self.base_url:
            return {"status": "error", "message": "未配置外部 RAG 接口地址"}
        try:
            safe_url = self.base_url.replace("://localhost:", "://127.0.0.1:")
            with httpx.Client(timeout=30.0) as client:
                for filename, content in files_content.items():
                    short_name = filename.split("/")[-1].split("\\")[-1]
                    files = {"file": (short_name, content.encode("utf-8"), "text/markdown")}
                    auth_h = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
                    try:
                        client.post(f"{safe_url}/upload", files=files, headers=auth_h)
                    except Exception:
                        pass
            return {"status": "success", "message": f"已尝试上传 {len(files_content)} 份文件到外部 RAG 服务。"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_sync_status(self, dataset_name: str = "Classroom_Knowledge") -> Dict[str, Any]:
        """外部服务状态查询（仅做 ping 检测）"""
        if not self.base_url:
            return {"status": "error", "message": "未配置外部 RAG 接口地址"}
        try:
            safe_url = self.base_url.replace("://localhost:", "://127.0.0.1:")
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{safe_url}/status", headers=self._headers)
                if resp.status_code == 200:
                    return {"status": "success", "documents": {}, "message": "外部 RAG 服务连接正常"}
        except Exception as e:
            return {"status": "error", "message": f"无法连接外部 RAG 服务: {e}"}
        return {"status": "error", "message": "外部 RAG 服务响应异常"}

    def save_memory(self, user_msg: str, assistant_msg: str, level: int = 0) -> bool:
        """外部服务目前不支持高频记忆写入，降级处理"""
        return False

    def retrieve_memory(self, query: str, n_results: int = 3) -> List[str]:
        """外部服务目前不支持记忆检索，返回空"""
        return []
