"""
幻灯片队列管理
用于在ReactAgent和流式响应之间传递新生成的幻灯片
"""

import queue
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class SlideEvent:
    slide_index: str
    slide_content: str
    slide_title: str
    total_slides: int
    workflow_id: str

class SlideQueue:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SlideQueue, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not getattr(self, '_initialized', False):
            self._queues: Dict[str, queue.Queue] = {}
            self._queue_lock = threading.Lock()
            self._initialized = True
    
    def create_queue(self, workflow_id: str) -> None:
        """为特定工作流创建队列"""
        with self._queue_lock:
            if workflow_id not in self._queues:
                self._queues[workflow_id] = queue.Queue()
                print(f"DEBUG - SlideQueue: Created queue for workflow {workflow_id}")
    
    def add_slide(self, workflow_id: str, slide_event: SlideEvent) -> None:
        """添加新的幻灯片事件"""
        with self._queue_lock:
            if workflow_id not in self._queues:
                self.create_queue(workflow_id)
            
            self._queues[workflow_id].put(slide_event)
            print(f"DEBUG - SlideQueue: Added slide {slide_event.slide_index} to queue for workflow {workflow_id}")
    
    def get_slide(self, workflow_id: str, timeout: float = 0.1) -> Optional[SlideEvent]:
        """获取新的幻灯片事件（非阻塞）"""
        with self._queue_lock:
            if workflow_id not in self._queues:
                return None
        
        try:
            return self._queues[workflow_id].get(timeout=timeout)
        except queue.Empty:
            return None
    
    def cleanup_queue(self, workflow_id: str) -> None:
        """清理特定工作流的队列"""
        with self._queue_lock:
            if workflow_id in self._queues:
                del self._queues[workflow_id]
                print(f"DEBUG - SlideQueue: Cleaned up queue for workflow {workflow_id}")

# 全局实例
slide_queue = SlideQueue()