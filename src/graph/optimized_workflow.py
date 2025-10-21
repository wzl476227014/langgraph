"""
优化的工作流处理
专门处理页面级优化等轻量级任务
"""

import logging
from typing import Dict, Any, Optional
from ..task_router import TaskRouter, TaskType
from ..utils.logger import get_logger

logger = get_logger(__name__)


class OptimizedWorkflowHandler:
    """优化工作流处理器"""
    
    def __init__(self):
        self.task_router = TaskRouter()
    
    def should_use_optimized_flow(self, task: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """判断是否应使用优化流程
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            是否使用优化流程
        """
        task_type = self.task_router.identify_task_type(task, context)
        
        # 以下任务类型使用优化流程
        optimized_types = [
            TaskType.REPORT_OPTIMIZATION,
            TaskType.FILE_EXTRACTION,
            TaskType.INFO_QUERY,
            TaskType.STATUS_CHECK
        ]
        
        return task_type in optimized_types
    
    def get_optimized_config(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """获取优化配置
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            优化配置
        """
        task_type, workflow_config = self.task_router.route_task(task, context)
        
        # 特殊处理页面优化
        if "第" in task and "页" in task and ("优化" in task or "修改" in task):
            # 提取页码
            import re
            page_match = re.search(r"第(\d+)页", task)
            if page_match:
                page_num = int(page_match.group(1))
                workflow_config["target_page"] = page_num
                workflow_config["optimization_type"] = "page_specific"
                logger.info(f"页面级优化: 目标页码={page_num}", agent_name="OptimizedWorkflow")
        
        return workflow_config
    
    def execute_optimized_flow(self, state: Any, config: Dict[str, Any]) -> Any:
        """执行优化流程
        
        Args:
            state: 工作流状态
            config: 优化配置
            
        Returns:
            更新后的状态
        """
        logger.info(f"执行优化流程: {config.get('workflow', 'unknown')}", agent_name="OptimizedWorkflow")
        
        # 如果是页面特定优化
        if config.get("optimization_type") == "page_specific":
            target_page = config.get("target_page")
            logger.info(f"执行页面 {target_page} 的优化", agent_name="OptimizedWorkflow")
            
            # 直接调用报告Agent进行页面优化
            from ..agents.report_agent import ReportAgent
            report_agent = ReportAgent()
            
            # 设置优化模式
            state.optimization_mode = True
            state.target_page = target_page
            state.skip_steps = config.get("skip_steps", [])
            
            # 执行优化
            result = report_agent.optimize_page(state, target_page)
            state.add_execution_result("page_optimization", result)
            
            logger.info(f"页面 {target_page} 优化完成", agent_name="OptimizedWorkflow")
            
        elif config.get("direct_to_report"):
            # 直接进入报告生成
            logger.info("直接进入报告生成阶段", agent_name="OptimizedWorkflow")
            
            from ..agents.report_agent import ReportAgent
            report_agent = ReportAgent()
            
            state.optimization_mode = True
            state.skip_steps = config.get("skip_steps", [])
            
            result = report_agent.execute(state)
            state.add_execution_result("report_optimization", result)
            
        else:
            # 执行指定的agents
            agents = config.get("agents", [])
            for agent_name in agents:
                if agent_name in config.get("skip_steps", []):
                    logger.info(f"跳过 {agent_name} agent", agent_name="OptimizedWorkflow")
                    continue
                
                logger.info(f"执行 {agent_name} agent", agent_name="OptimizedWorkflow")
                
                if agent_name == "react":
                    from ..agents.react_agent import ReactAgent
                    agent = ReactAgent()
                elif agent_name == "report":
                    from ..agents.report_agent import ReportAgent
                    agent = ReportAgent()
                elif agent_name == "memory":
                    from ..agents.memory_agent import MemoryAgent
                    agent = MemoryAgent()
                else:
                    logger.warning(f"未知的agent: {agent_name}", agent_name="OptimizedWorkflow")
                    continue
                
                result = agent.execute(state)
                state.add_execution_result(f"{agent_name}_result", result)
        
        return state


def check_and_apply_optimization(state: Any, task: str) -> bool:
    """检查并应用优化
    
    Args:
        state: 工作流状态
        task: 任务描述
        
    Returns:
        是否应用了优化
    """
    handler = OptimizedWorkflowHandler()
    
    context = {
        "has_files": bool(getattr(state, 'file_processing_results', None)),
        "has_previous_report": bool(getattr(state, 'previous_report', None))
    }
    
    if handler.should_use_optimized_flow(task, context):
        config = handler.get_optimized_config(task, context)
        
        # 更新状态
        state.workflow_config = config
        state.optimization_applied = True
        
        logger.info(f"应用优化配置: {config}", agent_name="OptimizationChecker")
        
        return True
    
    return False