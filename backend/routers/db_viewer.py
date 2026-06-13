from fastapi import APIRouter, HTTPException
from backend.database import get_db_connection
import sqlite3

router = APIRouter(prefix="/api/chat/db", tags=["database"])

@router.get("/tables")
def list_tables():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row["name"] for row in cursor.fetchall()]
        conn.close()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tables/{table_name}")
def get_table_data(table_name: str, limit: int = 200, offset: int = 0):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Validate table name to prevent SQL injection
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Table not found")
            
        # For chat_messages and memory_logs, order by id descending to show newest first
        if table_name in ["chat_messages", "memory_logs"]:
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
        else:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
            
        rows = cursor.fetchall()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col["name"] for col in cursor.fetchall()]
        
        conn.close()
        
        return {
            "table": table_name,
            "columns": columns,
            "data": [dict(row) for row in rows]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
