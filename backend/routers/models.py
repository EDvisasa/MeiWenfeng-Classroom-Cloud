import httpx
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, Any
from backend.database import get_db_connection

router = APIRouter(prefix="/api/chat", tags=["models"])

class ModelUpdateRequest(BaseModel):
    id: int
    base_url: str
    api_key: str = ""
    protocol: str = "openai"
    selected_model_id: str = ""

@router.get("/models")
def list_models():
    """获取所有模型配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, protocol, base_url, api_key, is_active, selected_model_id FROM model_config")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/update")
def update_model_config(payload: ModelUpdateRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE model_config 
               SET base_url = ?, api_key = ?, protocol = ?, selected_model_id = ? 
               WHERE id = ?""",
            (payload.base_url, payload.api_key, payload.protocol, payload.selected_model_id, payload.id)
        )
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models/available")
def get_available_models(base_url: str, api_key: str = None, protocol: str = "openai"):
    if protocol != "openai":
        return {"status": "success", "models": []}
    
    headers = {}
    if api_key and api_key != "none" and api_key.strip() != "":
        headers["Authorization"] = f"Bearer {api_key}"
        
    try:
        # Avoid IPv6 connection issues on Windows with httpx by mapping localhost to 127.0.0.1
        safe_base_url = base_url.replace("://localhost:", "://127.0.0.1:")
        url = f"{safe_base_url.rstrip('/')}/models"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                models_list = data.get("data", [])
                model_ids = [m.get("id") for m in models_list if m.get("id")]
                return {"status": "success", "models": model_ids}
            else:
                return {"status": "error", "message": f"API returned status {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/switch_model")
def switch_model(payload: Dict[str, Any] = Body(...)):
    """切换当前激活的模型"""
    model_id = payload.get("id")
    if model_id is None:
        raise HTTPException(status_code=400, detail="Missing model 'id' in request body")
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # 先将所有模型设为不激活
        cursor.execute("UPDATE model_config SET is_active = 0")
        # 将选中的模型设为激活
        cursor.execute("UPDATE model_config SET is_active = 1 WHERE id = ?", (model_id,))
        conn.commit()
        
        # 获取最新的激活模型
        cursor.execute("SELECT name FROM model_config WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="Model not found")
            
        return {"status": "success", "active_model": row["name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
