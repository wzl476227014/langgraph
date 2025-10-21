"""任务路由系统
智能识别任务类型并选择对应的工作流
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TaskType(Enum):
    """任务类型枚举"""
    # 报告生成类
    REPORT_GENERATION = "report_generation"  # 生成完整报告
    REPORT_OPTIMIZATION = "report_optimization"  # 优化现有报告
    
    # 文件处理类
    FILE_EXTRACTION = "file_extraction"  # 文件内容提取
    FILE_CONVERSION = "file_conversion"  # 文件格式转换
    
    # 数据分析类
    DATA_ANALYSIS = "data_analysis"  # 数据分析
    DATA_VISUALIZATION = "data_visualization"  # 数据可视化
    
    # 查询类
    INFO_QUERY = "info_query"  # 信息查询
    STATUS_CHECK = "status_check"  # 状态检查
    
    # 其他
    GENERAL = "general"  # 通用任务
    UNKNOWN = "unknown"  # 未知任务


@dataclass
class TaskPattern:
    """任务模式定义"""
    type: TaskType
    patterns: List[str]  # 正则表达式模式
    keywords: List[str]  # 关键词
    priority: int = 0  # 优先级（越高越优先）


class TaskRouter:
    """任务路由器"""
    
    def __init__(self):
        self.task_patterns = self._initialize_patterns()
        self.workflow_mapping = self._initialize_workflow_mapping()
    
    def _initialize_patterns(self) -> List[TaskPattern]:
        """初始化任务模式"""
        return [
            # 报告生成
            TaskPattern(
                type=TaskType.REPORT_GENERATION,
                patterns=[
                    r"生成.*报告",
                    r"创建.*报告",
                    r"制作.*PPT",
                    r"写.*文档",
                    r"generate.*report",
                    r"create.*presentation"
                ],
                keywords=["报告", "文档", "PPT", "演示", "report", "document"],
                priority=10
            ),
            
            # 报告优化 - 增强识别能力
            TaskPattern(
                type=TaskType.REPORT_OPTIMIZATION,
                patterns=[
                    r"优化.*报告",
                    r"优化.*第.*页",  # 明确的页面优化
                    r"优化.*页.*内容",
                    r"修改.*第.*页",
                    r"改进.*第.*章",
                    r"调整.*第.*节",
                    r"更新.*页面",
                    r"改进.*文档",
                    r"修改.*PPT",
                    r"完善.*内容",
                    r"重写.*部分",
                    r"润色.*章节",
                    r"optimize.*page",
                    r"improve.*section",
                    r"revise.*chapter",
                    r"update.*slide"
                ],
                keywords=["优化", "改进", "修改", "完善", "调整", "更新", "重写", "润色", "第.*页", "optimize", "improve", "revise", "update"],
                priority=15  # 提高优先级，确保优先匹配
            ),
            
            # 文件提取
            TaskPattern(
                type=TaskType.FILE_EXTRACTION,
                patterns=[
                    r"提取.*内容",
                    r"解析.*文件",
                    r"读取.*数据",
                    r"extract.*from",
                    r"parse.*file"
                ],
                keywords=["提取", "解析", "读取", "extract", "parse"],
                priority=8
            ),
            
            # 文件转换
            TaskPattern(
                type=TaskType.FILE_CONVERSION,
                patterns=[
                    r"转换.*格式",
                    r".*转.*PDF",
                    r".*转.*HTML",
                    r"convert.*to",
                    r"transform.*format"
                ],
                keywords=["转换", "转化", "convert", "transform"],
                priority=7
            ),
            
            # 数据分析
            TaskPattern(
                type=TaskType.DATA_ANALYSIS,
                patterns=[
                    r"分析.*数据",
                    r"统计.*信息",
                    r"计算.*指标",
                    r"analyze.*data",
                    r"calculate.*metrics"
                ],
                keywords=["分析", "统计", "计算", "analyze", "calculate"],
                priority=6
            ),
            
            # 信息查询
            TaskPattern(
                type=TaskType.INFO_QUERY,
                patterns=[
                    r"查询.*信息",
                    r"搜索.*内容",
                    r"查找.*资料",
                    r"search.*for",
                    r"find.*information"
                ],
                keywords=["查询", "搜索", "查找", "search", "find"],
                priority=5
            ),
            
            # 状态检查
            TaskPattern(
                type=TaskType.STATUS_CHECK,
                patterns=[
                    r"检查.*状态",
                    r"查看.*进度",
                    r"显示.*信息",
                    r"check.*status",
                    r"show.*progress"
                ],
                keywords=["检查", "查看", "显示", "状态", "check", "status"],
                priority=4
            )
        ]
    
    def _initialize_workflow_mapping(self) -> Dict[TaskType, Dict[str, Any]]:
        """初始化工作流映射"""
        return {
            TaskType.REPORT_GENERATION: {
                "workflow": "full_workflow",
                "agents": ["plan", "react", "reflect", "report"],
                "skip_steps": [],
                "config": {"enable_memory": True, "enable_reflection": True}
            },
            TaskType.REPORT_OPTIMIZATION: {
                "workflow": "optimization_workflow",
                "agents": ["report"],  # 仅使用report agent进行优化
                "skip_steps": ["plan", "plan_confirmation", "react", "content_confirmation", "reflect", "memory", "final_confirmation"],
                "direct_to_report": True,  # 直接进入报告生成
                "config": {
                    "enable_memory": False, 
                    "enable_reflection": False,
                    "enable_user_interaction": False,
                    "optimization_mode": True
                }
            },
            TaskType.FILE_EXTRACTION: {
                "workflow": "extraction_workflow",
                "agents": ["file_processor"],
                "skip_steps": ["plan", "react", "reflect", "report"],
                "config": {"extract_only": True}
            },
            TaskType.FILE_CONVERSION: {
                "workflow": "conversion_workflow",
                "agents": ["file_processor", "report"],
                "skip_steps": ["plan", "react", "reflect"],
                "config": {"convert_format": True}
            },
            TaskType.DATA_ANALYSIS: {
                "workflow": "analysis_workflow",
                "agents": ["react", "report"],
                "skip_steps": ["plan", "reflect"],
                "config": {"focus_on_data": True}
            },
            TaskType.INFO_QUERY: {
                "workflow": "query_workflow",
                "agents": ["react"],
                "skip_steps": ["plan", "reflect", "report"],
                "config": {"quick_response": True}
            },
            TaskType.STATUS_CHECK: {
                "workflow": "status_workflow",
                "agents": ["memory"],
                "skip_steps": ["plan", "react", "reflect", "report"],
                "config": {"status_only": True}
            },
            TaskType.GENERAL: {
                "workflow": "full_workflow",
                "agents": ["plan", "react", "reflect", "report"],
                "skip_steps": [],
                "config": {"enable_memory": True, "enable_reflection": True}
            },
            TaskType.UNKNOWN: {
                "workflow": "full_workflow",
                "agents": ["plan", "react", "reflect", "report"],
                "skip_steps": [],
                "config": {"enable_memory": True, "enable_reflection": True}
            }
        }
    
    def identify_task_type(self, task: str, context: Optional[Dict[str, Any]] = None) -> TaskType:
        """识别任务类型
        
        Args:
            task: 任务描述
            context: 上下文信息（如文件、历史记录等）
        
        Returns:
            识别出的任务类型
        """
        task_lower = task.lower()
        matches = []
        
        # 特殊处理：页面级优化（最高优先级）
        page_optimization_patterns = [
            r"优化.*第.{1,3}页",
            r"修改.*第.{1,3}页",
            r"改进.*第.{1,3}页",
            r"调整.*第.{1,3}页",
            r"优化第.{1,3}页",
            r"第.{1,3}页.*优化",
            r"第.{1,3}页.*修改"
        ]
        
        for pattern in page_optimization_patterns:
            if re.search(pattern, task):
                logger.info(f"检测到页面级优化任务: {task}")
                return TaskType.REPORT_OPTIMIZATION
        
        # 基于模式和关键词匹配
        for pattern_def in self.task_patterns:
            score = 0
            
            # 检查正则模式
            for pattern in pattern_def.patterns:
                if re.search(pattern, task_lower):
                    score += 2
                    break
            
            # 检查关键词
            for keyword in pattern_def.keywords:
                # 处理带正则的关键词
                if ".*" in keyword:
                    if re.search(keyword, task_lower):
                        score += 2
                elif keyword in task_lower:
                    score += 1
            
            if score > 0:
                matches.append((pattern_def.type, score + pattern_def.priority))
        
        # 考虑上下文信息
        if context:
            # 如果有文件上传，倾向于文件处理任务
            if context.get("has_files"):
                if "提取" in task or "extract" in task_lower:
                    return TaskType.FILE_EXTRACTION
                elif "转换" in task or "convert" in task_lower:
                    return TaskType.FILE_CONVERSION
            
            # 如果有数据，倾向于数据分析
            if context.get("has_data"):
                return TaskType.DATA_ANALYSIS
        
        # 选择得分最高的任务类型
        if matches:
            matches.sort(key=lambda x: x[1], reverse=True)
            return matches[0][0]
        
        # 默认返回通用任务
        return TaskType.GENERAL
    
    def get_workflow_config(self, task_type: TaskType) -> Dict[str, Any]:
        """获取工作流配置
        
        Args:
            task_type: 任务类型
        
        Returns:
            工作流配置
        """
        return self.workflow_mapping.get(task_type, self.workflow_mapping[TaskType.GENERAL])
    
    def route_task(self, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[TaskType, Dict[str, Any]]:
        """路由任务到合适的工作流
        
        Args:
            task: 任务描述
            context: 上下文信息
        
        Returns:
            (任务类型, 工作流配置)
        """
        task_type = self.identify_task_type(task, context)
        workflow_config = self.get_workflow_config(task_type)
        
        logger.info(f"任务路由: {task[:50]}... -> {task_type.value}")
        logger.debug(f"工作流配置: {workflow_config}")
        
        return task_type, workflow_config
    
    def get_required_agents(self, task_type: TaskType) -> List[str]:
        """获取任务所需的Agent列表
        
        Args:
            task_type: 任务类型
        
        Returns:
            Agent列表
        """
        config = self.get_workflow_config(task_type)
        return config.get("agents", [])
    
    def should_skip_step(self, task_type: TaskType, step: str) -> bool:
        """判断是否应跳过某个步骤
        
        Args:
            task_type: 任务类型
            step: 步骤名称
        
        Returns:
            是否跳过
        """
        config = self.get_workflow_config(task_type)
        return step in config.get("skip_steps", [])


# 全局路由器实例
_router = None

def get_router() -> TaskRouter:
    """获取全局路由器实例"""
    global _router
    if _router is None:
        _router = TaskRouter()
    return _router

def route_task(task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[TaskType, Dict[str, Any]]:
    """便捷函数：路由任务"""
    return get_router().route_task(task, context)