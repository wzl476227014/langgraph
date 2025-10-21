"""
日志管理模块
负责应用日志的记录和管理
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union
from datetime import datetime
from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from rich.panel import Panel


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    COLORS = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold red'
    }
    
    def format(self, record):
        # 确保消息是字符串
        message = record.getMessage()
        if not isinstance(message, str):
            message = str(message)
        
        # 创建日志内容
        log_content = {
            'time': datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S'),
            'level': record.levelname,
            'message': message,
            'filename': record.filename,
            'lineno': record.lineno,
            'funcName': record.funcName
        }
        
        if hasattr(record, 'agent_name'):
            log_content['agent'] = getattr(record, 'agent_name')
            return f"[{log_content['time']}] [{log_content['level']}] [{log_content['agent']}] {log_content['filename']}:{log_content['lineno']} - {log_content['funcName']} - {log_content['message']}"
        else:
            return f"[{log_content['time']}] [{log_content['level']}] {log_content['filename']}:{log_content['lineno']} - {log_content['funcName']} - {log_content['message']}"


class CustomLogger(logging.Logger):
    """自定义Logger类，用于显示真实调用者信息"""
    
    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, stacklevel=1):
        """
        重写_log方法，增加stacklevel来跳过Logger类的包装层
        """
        # 增加stacklevel来跳过Logger类的包装层
        # 需要跳过：Logger.info/warning/error/debug -> Logger._log -> logging.Logger._log
        # 所以增加2层，因为logging.Logger._log会再调用findCaller(stacklevel=1)
        stacklevel += 2
        super()._log(level, msg, args, exc_info, extra, stack_info, stacklevel)


class Logger:
    """日志管理器"""
    
    def __init__(self, name: str = "margs", level: str = "INFO"):
        """
        初始化日志管理器
        
        Args:
            name: 日志器名称
            level: 日志级别
        """
        self.name = name
        # 设置自定义的Logger类
        logging.setLoggerClass(CustomLogger)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """设置日志处理器"""
        # 控制台处理器（使用Rich）
        console = Console()
        console_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,  # 允许使用rich的markup语法
            show_level=True,
            show_time=True,
            show_path=False
        )
        console_handler.setLevel(logging.INFO)
        
        # 文件处理器
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        log_file = log_dir / f"{self.name}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        # 设置格式化器，包含调用者信息
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(agent_name)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        )
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(agent_name)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s'
        )
        
        console_handler.setFormatter(console_formatter)
        file_handler.setFormatter(file_formatter)
        
        # 添加处理器
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
    
    def _ensure_str(self, message: Union[str, Text]) -> str:
        """确保消息是字符串格式"""
        if isinstance(message, Text):
            return message.plain
        return str(message)
    
    def debug(self, message: str, agent_name: str = None, **kwargs):
        """记录调试信息"""
        extra = {'agent_name': agent_name or 'System'}
        self.logger.debug(self._ensure_str(message), extra=extra, **kwargs)
    
    def info(self, message: str, agent_name: str = None, **kwargs):
        """记录信息"""
        extra = {'agent_name': agent_name or 'System'}
        self.logger.info(self._ensure_str(message), extra=extra, **kwargs)
    
    def warning(self, message: str, agent_name: str = None, **kwargs):
        """记录警告"""
        extra = {'agent_name': agent_name or 'System'}
        self.logger.warning(self._ensure_str(message), extra=extra, **kwargs)
    
    def error(self, message: str, agent_name: str = None, **kwargs):
        """记录错误"""
        extra = {'agent_name': agent_name or 'System'}
        self.logger.error(self._ensure_str(message), extra=extra, **kwargs)
    
    def critical(self, message: str, agent_name: str = None, **kwargs):
        """记录严重错误"""
        extra = {'agent_name': agent_name or 'System'}
        self.logger.critical(self._ensure_str(message), extra=extra, **kwargs)
    
    def _get_external_caller_info(self):
        """获取外部调用者信息，跳过Logger类的所有方法"""
        import inspect
        stack = inspect.stack()
        # 跳过前几层：_get_external_caller_info, log_xxx方法, Logger方法
        for i in range(3, len(stack)):
            frame_info = stack[i]
            # 检查是否在logger.py中
            if 'logger.py' not in frame_info.filename:
                return frame_info.filename, frame_info.lineno, frame_info.function
        # 如果没找到，返回第3层的信息
        frame_info = stack[3] if len(stack) > 3 else stack[-1]
        return frame_info.filename, frame_info.lineno, frame_info.function

    def log_agent_start(self, agent_name: str, task: str):
        """记录Agent开始任务"""
        panel = Panel(
            f"[bold green]Agent {agent_name} 开始任务[/bold green]\n[dim]{task}[/dim]",
            title="AGENT",
            border_style="green"
        )
        console = Console()
        console.print(panel)
        
        # 获取真实调用者信息并直接创建日志记录
        filename, lineno, funcName = self._get_external_caller_info()
        extra = {'agent_name': agent_name}
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, filename, lineno,
            f"开始任务: {task}", (), None, funcName, extra
        )
        self.logger.handle(record)
    
    def log_agent_complete(self, agent_name: str, task: str, result_summary: str = None):
        """记录Agent完成任务"""
        content = f"[bold blue]Agent {agent_name} 完成任务[/bold blue]\n[dim]{task}[/dim]"
        if result_summary:
            content += f"\n\n[yellow]结果摘要:[/yellow]\n{result_summary}"
        
        panel = Panel(
            content,
            title="COMPLETE",
            border_style="blue"
        )
        console = Console()
        console.print(panel)
        
        # 获取真实调用者信息并直接创建日志记录
        filename, lineno, funcName = self._get_external_caller_info()
        extra = {'agent_name': agent_name}
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, filename, lineno,
            f"完成任务: {task}", (), None, funcName, extra
        )
        self.logger.handle(record)
        
        if result_summary:
            record = self.logger.makeRecord(
                self.logger.name, logging.INFO, filename, lineno,
                f"结果摘要: {result_summary}", (), None, funcName, extra
            )
            self.logger.handle(record)
    
    def log_workflow_step(self, step_name: str, status: str = "running"):
        """记录工作流步骤"""
        status_colors = {
            'running': 'yellow',
            'completed': 'green',
            'failed': 'red',
            'skipped': 'gray'
        }
        
        color = status_colors.get(status, 'white')
        panel = Panel(
            f"[{color}]工作流步骤: {step_name} - {status.upper()}[/{color}]",
            title="WORKFLOW",
            border_style=color
        )
        console = Console()
        console.print(panel)
        
        # 获取真实调用者信息并直接创建日志记录
        filename, lineno, funcName = self._get_external_caller_info()
        extra = {'agent_name': 'System'}
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, filename, lineno,
            f"工作流步骤: {step_name} - {status}", (), None, funcName, extra
        )
        self.logger.handle(record)
    
    def log_user_interaction(self, interaction_type: str, message: str):
        """记录用户交互"""
        panel = Panel(
            f"[bold magenta]用户交互 - {interaction_type}[/bold magenta]\n{message}",
            title="USER INPUT",
            border_style="magenta"
        )
        console = Console()
        console.print(panel)
        
        # 获取真实调用者信息并直接创建日志记录
        filename, lineno, funcName = self._get_external_caller_info()
        extra = {'agent_name': 'System'}
        record = self.logger.makeRecord(
            self.logger.name, logging.INFO, filename, lineno,
            f"用户交互({interaction_type}): {message}", (), None, funcName, extra
        )
        self.logger.handle(record)


# 全局日志器实例
logger = Logger()


def get_logger(name: str = None) -> Logger:
    """获取日志器实例"""
    if name:
        return Logger(name)
    return logger


def log_agent_start(agent_name: str, task: str):
    """记录Agent开始任务的便捷函数"""
    logger.log_agent_start(agent_name, task)


def log_agent_complete(agent_name: str, task: str, result_summary: str = None):
    """记录Agent完成任务的便捷函数"""
    logger.log_agent_complete(agent_name, task, result_summary)


def log_workflow_step(step_name: str, status: str = "running"):
    """记录工作流步骤的便捷函数"""
    logger.log_workflow_step(step_name, status)


def log_user_interaction(interaction_type: str, message: str):
    """记录用户交互的便捷函数"""
    logger.log_user_interaction(interaction_type, message)


def setup_logging(level: str = "INFO"):
    """
    初始化全局日志配置
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # 获取根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    
    # 移除所有现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 添加控制台处理器
    console_handler = RichHandler(
        level=level.upper(),
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=True  # 显示文件路径和行号
    )
    root_logger.addHandler(console_handler)
    
    # 设置全局日志器
    global logger
    logger = Logger(level=level)
