import httpx
from fastapi import APIRouter, HTTPException, Body, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
from backend.database import get_db_connection

router = APIRouter(prefix="/api/chat", tags=["models"])

def resolve_max_tokens(model_name: str, target_model: str, base_url: str, api_val: Optional[int]) -> int:
    """根据模型名称、上游模型名、基础URL和 API 返回的值综合判定最终的 max_tokens"""
    # 1. 默认设置（根据模型名字硬编码）
    max_tokens = 8192
    name_lower = (model_name + " " + target_model).lower()
    is_local = "localhost" in base_url or "127.0.0.1" in base_url
    
    if "gemini" in name_lower:
        max_tokens = 1000000
    elif "claude" in name_lower:
        max_tokens = 1000000
    elif "gpt-5" in name_lower or "gpt-4o" in name_lower:
        max_tokens = 1000000
    elif "deepseek" in name_lower:
        max_tokens = 1000000
    elif "qwen" in name_lower and not is_local:
        max_tokens = 1000000
    elif "qwen" in name_lower:
        max_tokens = 262144

    # 2. 结合 API 探测结果
    # 许多代理(如 LiteLLM) 在无法获知 upstream max_tokens 时默认返回 8192 或 4096。
    # 如果 API 返回的值存在，只有当它真的大于我们硬编码的高配值，或者我们硬编码只有 8192 时，我们才采用。
    if api_val:
        max_tokens = max(max_tokens, api_val)
        
    return max_tokens

def detect_and_update_max_tokens(model_id: int):
    """通过本地网关 /v1/models 探测并更新 max_context_tokens，如果已被人工锁定则跳过"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 0. 检查是否已被人工锁定
        cursor.execute("SELECT is_custom_tokens FROM model_config WHERE id = ?", (model_id,))
        check_row = cursor.fetchone()
        if not check_row or check_row["is_custom_tokens"] == 1:
            conn.close()
            return

        cursor.execute("SELECT name, base_url, selected_model_id FROM model_config WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return
            
        model_name = row["name"]
        base_url = row["base_url"]
        target_model = row["selected_model_id"] or row["name"]
        
        api_val = None
        # 2. 通过请求 base_url/models 探测 (优先)
        try:
            safe_base_url = base_url.replace("://localhost:", "://127.0.0.1:")
            url = f"{safe_base_url.rstrip('/')}/models"
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for m in data:
                        if m.get("id") == target_model:
                            info = m.get("model_info", {})
                            val = m.get("max_input_tokens") or info.get("max_input_tokens") or m.get("max_tokens") or m.get("context_window")
                            if val:
                                api_val = int(val)
                            break
        except Exception as e:
            print(f"Auto-detect max_tokens failed for {target_model}: {e}")
            
        final_max_tokens = resolve_max_tokens(model_name, target_model, base_url, api_val)
        
        cursor.execute("UPDATE model_config SET max_context_tokens = ? WHERE id = ?", (final_max_tokens, model_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating max_tokens: {e}")

class ModelUpdateRequest(BaseModel):
    id: int
    name: str = ""
    base_url: str
    api_key: str = ""
    protocol: str = "openai"
    selected_model_id: str = ""
    max_context_tokens: Optional[int] = None

class ModelCreateRequest(BaseModel):
    name: str
    protocol: str = "openai"
    base_url: str = ""
    api_key: str = ""
    max_context_tokens: Optional[int] = None

@router.get("/models")
def list_models():
    """获取所有模型配置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, protocol, base_url, api_key, is_active, selected_model_id, max_context_tokens, is_custom_tokens FROM model_config")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/update")
def update_model_config(payload: ModelUpdateRequest, background_tasks: BackgroundTasks):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if updating name, ensure uniqueness
        if payload.name:
            cursor.execute("SELECT id FROM model_config WHERE name = ? AND id != ?", (payload.name, payload.id))
            if cursor.fetchone():
                conn.close()
                raise HTTPException(status_code=400, detail="配置名称已存在，请使用其他名称")

        is_custom = 1 if payload.max_context_tokens else 0
        
        if is_custom:
            cursor.execute(
                """UPDATE model_config 
                   SET name = ?, base_url = ?, api_key = ?, protocol = ?, selected_model_id = ?, max_context_tokens = ?, is_custom_tokens = ? 
                   WHERE id = ?""",
                (payload.name, payload.base_url, payload.api_key, payload.protocol, payload.selected_model_id, payload.max_context_tokens, is_custom, payload.id)
            )
        else:
            cursor.execute(
                """UPDATE model_config 
                   SET name = ?, base_url = ?, api_key = ?, protocol = ?, selected_model_id = ?, is_custom_tokens = 0 
                   WHERE id = ?""",
                (payload.name, payload.base_url, payload.api_key, payload.protocol, payload.selected_model_id, payload.id)
            )
        conn.commit()
        conn.close()
        if not is_custom:
            background_tasks.add_task(detect_and_update_max_tokens, payload.id)
        return {"status": "success"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/models/create")
def create_model_config(payload: ModelCreateRequest, background_tasks: BackgroundTasks):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify unique name
        cursor.execute("SELECT id FROM model_config WHERE name = ?", (payload.name,))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="配置名称已存在，请使用其他名称")
            
        is_custom = 1 if payload.max_context_tokens else 0
        max_tokens = payload.max_context_tokens if payload.max_context_tokens else 8192
        
        cursor.execute(
            """INSERT INTO model_config (name, base_url, api_key, protocol, max_context_tokens, is_custom_tokens) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (payload.name, payload.base_url, payload.api_key, payload.protocol, max_tokens, is_custom)
        )
        model_id = cursor.lastrowid
        conn.commit()
        conn.close()
        if not is_custom:
            background_tasks.add_task(detect_and_update_max_tokens, model_id)
        return {"status": "success", "id": model_id}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/models/{id}")
def delete_model_config(id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT is_active, name FROM model_config WHERE id = ?", (id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="未找到该配置")
            
        if row["is_active"] == 1:
            conn.close()
            raise HTTPException(status_code=400, detail="不能删除当前激活的配置")
            
        cursor.execute("SELECT COUNT(*) as count FROM model_config")
        count_row = cursor.fetchone()
        if count_row["count"] <= 1:
            conn.close()
            raise HTTPException(status_code=400, detail="不能删除最后一个配置")
            
        cursor.execute("DELETE FROM model_config WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except HTTPException as he:
        raise he
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
        # 同步探测并更新 max_tokens，保证前端接下来的 fetchModels 拿到最新数据
        detect_and_update_max_tokens(model_id)
        
        return {"status": "success", "active_model": row["name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
