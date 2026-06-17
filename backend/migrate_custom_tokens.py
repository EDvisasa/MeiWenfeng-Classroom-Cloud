import sqlite3
import os
import sys

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.routers.models import resolve_max_tokens

DB_PATH = os.path.join(os.path.dirname(__file__), 'classroom.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Check if is_custom_tokens exists
    cursor.execute("PRAGMA table_info(model_config)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if "is_custom_tokens" not in columns:
        print("Adding is_custom_tokens column...")
        cursor.execute("ALTER TABLE model_config ADD COLUMN is_custom_tokens INTEGER DEFAULT 0")
        conn.commit()
    else:
        print("Column is_custom_tokens already exists.")
        
    # 2. Reset historical dirty data and strictly use heuristics
    print("Cleaning historical data...")
    cursor.execute("SELECT id, name, selected_model_id, base_url FROM model_config")
    rows = cursor.fetchall()
    
    for row in rows:
        model_id, name, selected_model_id, base_url = row
        # Since we are resetting, we assume no api_val is available right now
        # The user will manually set custom ones in the UI later
        new_max = resolve_max_tokens(name, selected_model_id or "", base_url or "", None)
        cursor.execute(
            "UPDATE model_config SET max_context_tokens = ?, is_custom_tokens = 0 WHERE id = ?",
            (new_max, model_id)
        )
        
    conn.commit()
    conn.close()
    print("Migration complete. All models reset to heuristic bounds and custom locks released.")

if __name__ == "__main__":
    migrate()
