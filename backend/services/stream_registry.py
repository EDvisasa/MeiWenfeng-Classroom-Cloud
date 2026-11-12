import threading
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class StreamController:
    """单个会话的流生命周期控制器"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.cancel_event = threading.Event()
        self._active_stream = None
        self._lock = threading.Lock()

    def set_stream(self, stream: Any):
        """登记底层的 OpenAI / httpx 流对象"""
        with self._lock:
            self._active_stream = stream
            # 如果在流建立之前就已经收到了中断信号，则立即就地关闭
            if self.cancel_event.is_set():
                self._close_stream()

    def _close_stream(self):
        """物理切断底层 TCP 套接字"""
        if self._active_stream is not None:
            try:
                if hasattr(self._active_stream, "close"):
                    self._active_stream.close()
                elif hasattr(self._active_stream, "response") and hasattr(self._active_stream.response, "close"):
                    self._active_stream.response.close()
            except Exception as e:
                logger.warning(f"Error closing stream for session {self.session_id}: {e}")
            finally:
                self._active_stream = None

    def abort(self) -> bool:
        """触发中断：设置标志并物理关闭流"""
        with self._lock:
            self.cancel_event.set()
            had_stream = self._active_stream is not None
            self._close_stream()
            return had_stream

    @property
    def is_aborted(self) -> bool:
        return self.cancel_event.is_set()


class StreamRegistry:
    """全局线程安全的活动流生命周期注册中枢"""
    def __init__(self):
        self._controllers: Dict[str, StreamController] = {}
        self._lock = threading.Lock()

    def acquire(self, session_id: str) -> StreamController:
        """为会话创建或重置流控制器"""
        with self._lock:
            # 如果此前该 session 存在未完结的流，先主动中止它
            if session_id in self._controllers:
                try:
                    self._controllers[session_id].abort()
                except Exception as e:
                    logger.warning(f"Error aborting prior stream for session {session_id}: {e}")
            controller = StreamController(session_id)
            self._controllers[session_id] = controller
            return controller

    def get(self, session_id: str) -> Optional[StreamController]:
        with self._lock:
            return self._controllers.get(session_id)

    def release(self, session_id: str, controller: StreamController):
        """流正常结束或异常退出时注销控制器"""
        with self._lock:
            if self._controllers.get(session_id) is controller:
                del self._controllers[session_id]

    def abort(self, session_id: str) -> bool:
        """主动中断指定 session 的模型推理"""
        with self._lock:
            controller = self._controllers.get(session_id)
        if controller:
            was_aborted = controller.abort()
            with self._lock:
                if self._controllers.get(session_id) is controller:
                    del self._controllers[session_id]
            logger.info(f"StreamRegistry: successfully aborted active stream for session {session_id}")
            return True
        return False


# 全局单例
stream_registry = StreamRegistry()
