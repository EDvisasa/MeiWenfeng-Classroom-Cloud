import threading
import time
import json
from backend.services.memory_decay import process_memory_decay

def run_decay_with_progress():
    result_container = {}
    
    def target():
        try:
            stats = process_memory_decay()
            result_container["stats"] = stats
        except Exception as e:
            result_container["error"] = str(e)
            
    t = threading.Thread(target=target)
    t.start()
    
    while t.is_alive():
        time.sleep(1)
        yield {"type": "summarize_progress", "state": "loading"}
        
    t.join()
    if "error" in result_container:
        yield {"type": "summarize_progress", "state": "error", "error": result_container["error"]}
    else:
        yield {"type": "summarize_progress", "state": "done", "stats": result_container.get("stats", {})}
