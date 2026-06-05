import os
import httpx
from typing import Dict, Any

RAGFLOW_API_KEY = os.environ.get("RAGFLOW_API_KEY", "")
RAGFLOW_BASE_URL = os.environ.get("RAGFLOW_BASE_URL", "http://localhost/api/v1").rstrip("/")

class RAGFlowClient:
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

    async def _get_or_create_dataset(self) -> str:
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.base_url}/datasets", headers=self.headers)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for ds in data:
                        if ds.get("name") == self.dataset_name:
                            return ds.get("id")
            except Exception as e:
                print(f"Failed to fetch datasets: {e}")

            # Create if not exists
            resp = await client.post(
                f"{self.base_url}/datasets", 
                json={"name": self.dataset_name}, 
                headers=self.headers
            )
            resp.raise_for_status()
            return resp.json()["data"]["id"]

    async def sync_knowledge(self, files_content: Dict[str, str]) -> Dict[str, Any]:
        """Uploads a dictionary of filename -> markdown content to RAGFlow."""
        if not self.api_key or self.api_key == "your_ragflow_api_key_here":
            return {"status": "error", "message": "RAGFLOW_API_KEY 未配置，请前往 RAGFlow 的 API 页面生成并在 .env 中配置。"}
            
        try:
            dataset_id = await self._get_or_create_dataset()
            
            async with httpx.AsyncClient() as client:
                for filename, content in files_content.items():
                    # Format as multipart/form-data
                    # Only pass Authorization header, httpx will auto-generate Content-Type boundary
                    auth_header = {"Authorization": f"Bearer {self.api_key}"}
                    
                    files = {
                        "file": (filename.split('/')[-1], content.encode('utf-8'), "text/markdown")
                    }
                    
                    resp = await client.post(
                        f"{self.base_url}/datasets/{dataset_id}/documents",
                        headers=auth_header,
                        files=files
                    )
                    
                    if resp.status_code != 200:
                        print(f"Failed to upload {filename}: {resp.text}")
                        continue
                        
                    # Try to parse (ignore if endpoint varies in specific RAGFlow version)
                    try:
                        doc_data = resp.json().get("data", [])
                        if doc_data:
                            # doc_data might be a list or a dict depending on RAGFlow version
                            doc_id = doc_data[0].get("id") if isinstance(doc_data, list) else doc_data.get("id")
                            if doc_id:
                                await client.post(
                                    f"{self.base_url}/datasets/{dataset_id}/documents/{doc_id}/parse",
                                    headers=self.headers
                                )
                    except Exception as e:
                        print(f"Parsing trigger failed (safe to ignore if auto-parsing is on): {e}")

            return {"status": "success", "message": f"成功同步并开始解析 {len(files_content)} 份讲义到 RAGFlow 知识库。"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"status": "error", "message": f"同步到 RAGFlow 失败: {str(e)}"}

    async def retrieve(self, query: str) -> str:
        """Retrieve relevant context for a query."""
        if not self.api_key or self.api_key == "your_ragflow_api_key_here":
            return ""
            
        try:
            dataset_id = await self._get_or_create_dataset()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/retrieval",
                    json={"dataset_ids": [dataset_id], "question": query, "top_k": 3},
                    headers=self.headers
                )
                if resp.status_code == 200:
                    chunks = resp.json().get("data", {}).get("chunks", [])
                    context = "\n\n".join([c.get("content", "") for c in chunks])
                    return context
        except Exception as e:
            print(f"RAGFlow retrieval error: {e}")
            return ""
        return ""

ragflow_client = RAGFlowClient()
