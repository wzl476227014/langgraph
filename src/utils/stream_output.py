"""
流式输出管理模块
提供打字机效果的流式输出功能，用于模型调用输出
"""

import sys
import time
import threading
from typing import Iterator, Optional, Callable
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StreamOutputManager:
    """流式输出管理器"""
    
    def __init__(self, speed: float = 0.01, enable_typewriter: bool = True):
        """
        初始化流式输出管理器
        
        Args:
            speed: 字符输出速度（秒）
            enable_typewriter: 是否启用打字机效果
        """
        self.speed = speed
        self.enable_typewriter = enable_typewriter
        self._buffer = []
        self._interrupted = False
        
    def stream_print(self, text_iterator: Iterator[str], prefix: str = "", 
                    color: str = "", callback: Optional[Callable] = None) -> str:
        """
        流式打印文本
        
        Args:
            text_iterator: 文本迭代器
            prefix: 输出前缀
            color: ANSI颜色代码
            callback: 每个chunk的回调函数
            
        Returns:
            完整的输出文本
        """
        self._interrupted = False
        full_text = ""
        
        # ANSI颜色代码
        colors = {
            "blue": "\033[94m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "purple": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "reset": "\033[0m"
        }
        
        # 输出前缀
        if prefix:
            sys.stdout.write(prefix)
            sys.stdout.flush()
        
        # 设置颜色
        if color in colors:
            sys.stdout.write(colors[color])
        
        try:
            for chunk in text_iterator:
                if self._interrupted:
                    # 如果被中断，快速输出剩余内容
                    remaining_chunks = [chunk]
                    for remaining in text_iterator:
                        remaining_chunks.append(remaining)
                    full_remaining = ''.join(remaining_chunks)
                    sys.stdout.write(full_remaining)
                    full_text += full_remaining
                    break
                
                # 打字机效果输出
                if self.enable_typewriter:
                    for char in chunk:
                        try:
                            sys.stdout.write(char)
                            sys.stdout.flush()
                            time.sleep(self.speed)
                        except UnicodeEncodeError:
                            # 处理编码问题
                            try:
                                sys.stdout.buffer.write(char.encode('utf-8', errors='ignore'))
                                sys.stdout.buffer.flush()
                            except:
                                continue
                else:
                    # 直接输出chunk
                    try:
                        sys.stdout.write(chunk)
                        sys.stdout.flush()
                    except UnicodeEncodeError:
                        sys.stdout.buffer.write(chunk.encode('utf-8', errors='ignore'))
                        sys.stdout.buffer.flush()
                
                full_text += chunk
                
                # 执行回调
                if callback:
                    callback(chunk)
            
        finally:
            # 重置颜色
            if color in colors:
                sys.stdout.write(colors["reset"])
            
            sys.stdout.write("\n")
            sys.stdout.flush()
        
        return full_text
    
    def interrupt(self):
        """中断输出"""
        self._interrupted = True


class AgentStreamOutput:
    """Agent专用流式输出"""
    
    def __init__(self, agent_name: str, enable_stream: bool = True):
        """
        初始化Agent流式输出
        
        Args:
            agent_name: Agent名称
            enable_stream: 是否启用流式输出
        """
        self.agent_name = agent_name
        self.enable_stream = enable_stream
        self.output_manager = StreamOutputManager(speed=0.005, enable_typewriter=enable_stream)
        
    def print_thinking(self, message: str = ""):
        """打印思考状态"""
        if not message:
            messages = [
                "正在分析...",
                "正在思考...",
                "正在处理...",
                "正在规划...",
                "正在生成..."
            ]
            import random
            message = random.choice(messages)
        
        prefix = f"\033[95m[{self.agent_name}]\033[0m: "
        sys.stdout.write(f"{prefix}{message}")
        sys.stdout.flush()
        
        # 模拟思考动画
        for _ in range(3):
            time.sleep(0.3)
            sys.stdout.write(".")
            sys.stdout.flush()
        
        # 清除当前行
        sys.stdout.write("\r" + " " * (len(prefix) + len(message) + 3) + "\r")
        sys.stdout.flush()
    
    def stream_output(self, text_iterator: Iterator[str], task_type: str = "执行") -> str:
        """
        流式输出Agent响应
        
        Args:
            text_iterator: 文本迭代器
            task_type: 任务类型
            
        Returns:
            完整的输出文本
        """
        # 打印任务开始
        prefix = f"\033[95m[{self.agent_name}]\033[0m {task_type}: "
        
        if self.enable_stream:
            # 流式输出
            return self.output_manager.stream_print(
                text_iterator, 
                prefix=prefix,
                color="white"
            )
        else:
            # 非流式输出（收集所有内容后一次性输出）
            full_text = ""
            sys.stdout.write(prefix)
            for chunk in text_iterator:
                full_text += chunk
            sys.stdout.write(full_text + "\n")
            sys.stdout.flush()
            return full_text
    
    def print_progress(self, current: int, total: int, description: str = ""):
        """
        打印进度条
        
        Args:
            current: 当前进度
            total: 总进度
            description: 描述信息
        """
        if total <= 0:
            return
        
        percentage = (current / total) * 100
        bar_length = 30
        filled_length = int(bar_length * current / total)
        
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # 构建进度信息
        progress_str = f"\r\033[95m[{self.agent_name}]\033[0m [{bar}] {percentage:.1f}% {description}"
        
        sys.stdout.write(progress_str)
        sys.stdout.flush()
        
        if current >= total:
            sys.stdout.write("\n")
            sys.stdout.flush()


# 全局流式输出管理器
global_stream_manager = StreamOutputManager()


def enable_stream_output(enable: bool = True):
    """启用或禁用全局流式输出"""
    global_stream_manager.enable_typewriter = enable


def set_stream_speed(speed: float):
    """设置流式输出速度"""
    global_stream_manager.speed = speed


def stream_print(text_iterator: Iterator[str], prefix: str = "", color: str = "") -> str:
    """全局流式打印函数"""
    return global_stream_manager.stream_print(text_iterator, prefix, color)