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
        yield "[系统记忆压缩] 正在压缩中...\n\n"
        
    t.join()
    if "error" in result_container:
        yield f"[系统记忆压缩] 压缩失败: {result_container['error']}\n\n"
    else:
        yield f"[系统记忆压缩] 压缩完成！新记忆已归档入库。处理统计: {json.dumps(result_container.get('stats', {}), ensure_ascii=False)}\n\n"
