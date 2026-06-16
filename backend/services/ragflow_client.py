import os
import httpx
from typing import Dict, Any
from backend.services.rag_factory import RAGClient

RAGFLOW_API_KEY = os.environ.get("RAGFLOW_API_KEY", "")
RAGFLOW_BASE_URL = os.environ.get("RAGFLOW_BASE_URL", "http://localhost/api/v1").rstrip("/")

class RAGFlowClient(RAGClient):
    def __init__(self):
        self.dataset_name = "Classroom_Knowledge"

    @property
    def api_key(self):
        return os.environ.get("RAGFLOW_API_KEY", "")

    @property
    def base_url(self):
        return os.environ.get("RAGFLOW_BASE_URL", "http://localhost/api/v1").rstrip("/")

    @property
    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def _get_or_create_dataset(self, dataset_name: str) -> str:
        with httpx.Client() as client:
            try:
                resp = client.get(f"{self.base_url}/datasets", headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for ds in data:
                        if ds.get("name") == dataset_name:
                            return ds.get("id")
            except Exception as e:
                print(f"Failed to fetch datasets: {e}")

            # Create if not exists
            resp = client.post(
                f"{self.base_url}/datasets", 
                json={"name": dataset_name}, 
                headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()["data"]["id"]

    def sync_knowledge(self, files_content: Dict[str, str], dataset_name: str = "Classroom_Knowledge") -> Dict[str, Any]:
        """Uploads a dictionary of filename -> markdown content to RAGFlow."""
        if not self.api_key or self.api_key == "your_ragflow_api_key_here":
            return {"status": "error", "message": "RAGFLOW_API_KEY 未配置，请前往 RAGFlow 的 API 页面生成并在 .env 中配置。"}
            
        try:
            dataset_id = self._get_or_create_dataset(dataset_name)
            
            with httpx.Client() as client:
                for filename, content in files_content.items():
                    auth_header = {"Authorization": f"Bearer {self.api_key}"}
                    
                    # 1. 强迫症清理：检查是否有同名文件，如果有则删除
                    try:
                        list_resp = client.get(
                            f"{self.base_url}/datasets/{dataset_id}/documents",
                            headers=self.headers
                        )
                        if list_resp.status_code == 200:
                            # 兼容不同 RAGFlow 版本的响应结构
                            docs_data = list_resp.json().get("data", {})
                            docs = docs_data.get("docs", []) if isinstance(docs_data, dict) else (docs_data if isinstance(docs_data, list) else [])
                            
                            to_delete_ids = [d.get("id") for d in docs if d.get("name") == filename.split('/')[-1] and d.get("id")]
                            if to_delete_ids:
                                client.request(
                                    "DELETE",
                                    f"{self.base_url}/datasets/{dataset_id}/documents",
                                    json={"ids": to_delete_ids},
                                    headers=self.headers
                                )
                    except Exception as e:
                        print(f"Cleanup check failed (ignored): {e}")
                    
                    # 2. 上传新文件
                    files = {
                        "file": (filename.split('/')[-1], content.encode('utf-8'), "text/markdown")
                    }
                    
                    resp = client.post(
                        f"{self.base_url}/datasets/{dataset_id}/documents",
                        headers=auth_header,
                        files=files
                    )
                    
                    if resp.status_code != 200:
                        print(f"Failed to upload {filename}: {resp.text}")
                        continue
                        
                    try:
                        doc_data = resp.json().get("data", [])
                        if doc_data:
                            doc_id = doc_data[0].get("id") if isinstance(doc_data, list) else doc_data.get("id")
                            if doc_id:
                                # Trigger parsing
                                client.post(
                                    f"{self.base_url}/datasets/{dataset_id}/chunks",
                                    json={"document_ids": [doc_id]},
                                    headers=self.headers
                                )
                    except Exception as e:
                        print(f"Parsing trigger failed (safe to ignore if auto-parsing is on): {e}")

            return {"status": "success", "message": f"成功同步并开始解析 {len(files_content)} 份文件到 RAGFlow 知识库 {dataset_name}。"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"同步到 RAGFlow 失败: {str(e)}"}

    def get_sync_status(self, dataset_name: str = "Classroom_Knowledge") -> Dict[str, Any]:
        """获取已同步文件的同步状态列表"""
        if not self.api_key or self.api_key == "your_ragflow_api_key_here":
            return {"status": "error", "message": "RAGFLOW_API_KEY 未配置"}
        try:
            dataset_id = self._get_or_create_dataset(dataset_name)
            with httpx.Client() as client:
                resp = client.get(
                    f"{self.base_url}/datasets/{dataset_id}/documents",
                    headers=self.headers
                )
                if resp.status_code == 200:
                    docs_data = resp.json().get("data", {})
                    docs = docs_data.get("docs", []) if isinstance(docs_data, dict) else (docs_data if isinstance(docs_data, list) else [])
                    
                    status_map = {}
                    for d in docs:
                        name = d.get("name")
                        if name:
                            status_map[name] = {
                                "id": d.get("id"),
                                "run": d.get("run"),
                                "status": d.get("status")
                            }
                    return {"status": "success", "documents": status_map}
                else:
                    return {"status": "error", "message": f"RAGFlow API returned status {resp.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def retrieve(self, query: str, dataset_names: list = None, n_results: int = 4) -> list[str]:
        """Retrieve relevant context for a query."""
        if dataset_names is None:
            dataset_names = ["Classroom_Knowledge"]

        if not self.api_key or self.api_key == "your_ragflow_api_key_here":
            return []

        try:
            dataset_ids = [self._get_or_create_dataset(name) for name in dataset_names]

            with httpx.Client() as client:
                resp = client.post(
                    f"{self.base_url}/retrieval",
                    json={"dataset_ids": dataset_ids, "question": query, "top_k": n_results},
                    headers=self.headers
                )
                if resp.status_code == 200:
                    chunks = resp.json().get("data", {}).get("chunks", [])
                    return [c.get("content", "") for c in chunks]
        except Exception as e:
            print(f"RAGFlow retrieval error: {e}")
            return []
        return []

    def save_memory(self, user_msg: str, assistant_msg: str, level: int = 0) -> bool:
        """RAGFlow does not support high-frequency memory writes well, fallback to no-op"""
        return False

    def retrieve_memory(self, query: str, n_results: int = 3) -> list[str]:
        """RAGFlow memory retrieval not implemented"""
        return []

ragflow_client = RAGFlowClient()

