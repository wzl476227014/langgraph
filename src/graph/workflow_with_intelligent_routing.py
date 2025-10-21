"""
集成智能路由的工作流管理器
"""

import uuid
import logging
from typing import Dict, Any, List, Optional
from ..utils.logger import get_logger
from .workflow import MultiAgentWorkflow
from .state import create_workflow_state

logger = get_logger(__name__)


class IntelligentMultiAgentWorkflow(MultiAgentWorkflow):
    """集成智能路由的多智能体工作流"""
    
    def __init__(self):
        super().__init__()
        # 延迟导入以避免循环依赖
        self._intent_analyzer = None
    
    def _get_intent_analyzer(self):
        """获取意图分析器实例"""
        if self._intent_analyzer is None:
            try:
                from ..enhanced_intent_analyzer import TaskIntentAnalyzer
                self._intent_analyzer = TaskIntentAnalyzer()
                logger.info("意图分析器加载成功", agent_name="IntelligentWorkflow")
            except ImportError:
                logger.warning("无法导入意图分析器，使用默认路由", agent_name="IntelligentWorkflow")
                self._intent_analyzer = None
        return self._intent_analyzer
    
    def execute(self, user_request: str, user_constraints: List[str] = None, 
                file_processing_results: List[Dict[str, Any]] = None, 
                extract_only: bool = False, use_premium_template: bool = False):
        """
        智能执行工作流
        
        Args:
            user_request: 用户请求
            user_constraints: 用户约束
            file_processing_results: 文件处理结果列表
            extract_only: 是否只提取HTML页面，不整合
            use_premium_template: 是否使用Premium高端模板直接生成
            
        Returns:
            最终的工作流状态
        """
        try:
            # 构建上下文
            context = {
                "has_files": bool(file_processing_results),
                "extract_only": extract_only,
                "use_premium_template": use_premium_template,
                "has_existing_report": self._check_existing_report()
            }
            
            # 进行智能意图分析
            logger.info(f"开始意图分析: {user_request}", agent_name="IntelligentWorkflow")
            intent_result = self._analyze_intent(user_request, context)
            
            if intent_result:
                logger.info(f"智能路由: {intent_result.get('intent', 'unknown')} (置信度: {intent_result.get('confidence', 0)})", 
                           agent_name="IntelligentWorkflow")
                logger.info(f"目标页面: {intent_result.get('target_pages', [])}", agent_name="IntelligentWorkflow")
                
                # 检查是否是页面级优化任务
                if self._is_page_optimization_task(intent_result):
                    return self._execute_page_optimization(user_request, intent_result, context, file_processing_results)
                
                # 检查是否是其他快速任务
                elif self._is_quick_task(intent_result):
                    return self._execute_quick_task(user_request, intent_result, context, file_processing_results)
            
            # 如果不是特殊任务或分析失败，使用默认完整流程
            logger.info("使用完整工作流程", agent_name="IntelligentWorkflow")
            return super().execute(user_request, user_constraints, file_processing_results, extract_only, use_premium_template)
            
        except Exception as e:
            logger.error(f"智能工作流执行失败: {str(e)}", agent_name="IntelligentWorkflow")
            # 回退到默认流程
            return super().execute(user_request, user_constraints, file_processing_results, extract_only, use_premium_template)
    
    def _analyze_intent(self, user_request: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """分析用户意图"""
        try:
            analyzer = self._get_intent_analyzer()
            if analyzer is None:
                return None
            
            result = analyzer.analyze_intent(user_request, context)
            return {
                "intent": result.intent.value,
                "confidence": result.confidence,
                "target_pages": result.target_pages,
                "specific_requirements": result.specific_requirements,
                "reasoning": result.reasoning
            }
        except Exception as e:
            logger.error(f"意图分析失败: {str(e)}", agent_name="IntelligentWorkflow")
            return None
    
    def _is_page_optimization_task(self, intent_result: Dict[str, Any]) -> bool:
        """判断是否是页面优化任务"""
        intent = intent_result.get("intent", "")
        return intent in ["optimize_single_page", "regenerate_single_page"]
    
    def _is_quick_task(self, intent_result: Dict[str, Any]) -> bool:
        """判断是否是快速任务"""
        intent = intent_result.get("intent", "")
        return intent in ["check_status", "query_information"]
    
    def _execute_page_optimization(self, user_request: str, intent_result: Dict[str, Any], 
                                  context: Dict[str, Any], file_processing_results: List[Dict[str, Any]]):
        """执行页面优化任务"""
        logger.info("执行页面优化快速流程", agent_name="IntelligentWorkflow")
        
        try:
            # 创建简化的工作流状态
            workflow_id = str(uuid.uuid4())
            state = create_workflow_state(workflow_id, user_request)
            
            # 添加文件处理结果
            if file_processing_results:
                for i, result in enumerate(file_processing_results):
                    file_id = result.get("result", {}).get("file_id", f"file_{i}")
                    state.add_file_processing_result(file_id, result)
            
            # 获取目标页面
            target_pages = intent_result.get("target_pages", [1])
            target_page = target_pages[0] if target_pages else 1
            
            # 直接使用React Agent进行页面优化
            from ..agents.react_agent import ReactAgent
            from ..agents.react_agent_optimizer import extend_react_agent_with_optimization
            
            react_agent = ReactAgent()
            extend_react_agent_with_optimization(react_agent)
            
            # 执行优化
            is_regenerate = intent_result.get("intent") == "regenerate_single_page"
            result = react_agent.optimize_single_page(
                state, 
                target_page, 
                user_request, 
                regenerate=is_regenerate
            )
            
            # 更新状态
            state.add_execution_result("page_optimization", result)
            
            # 设置完成状态
            from ..graph.state import WorkflowStatus
            state.workflow_status = WorkflowStatus.COMPLETED
            
            logger.info(f"页面{target_page}优化完成", agent_name="IntelligentWorkflow")
            
            return state
            
        except Exception as e:
            logger.error(f"页面优化执行失败: {str(e)}", agent_name="IntelligentWorkflow")
            # 回退到默认流程
            return super().execute(user_request, [], file_processing_results, False, False)
    
    def _execute_quick_task(self, user_request: str, intent_result: Dict[str, Any], 
                           context: Dict[str, Any], file_processing_results: List[Dict[str, Any]]):
        """执行快速任务"""
        logger.info("执行快速任务流程", agent_name="IntelligentWorkflow")
        
        try:
            # 创建简化的工作流状态
            workflow_id = str(uuid.uuid4())
            state = create_workflow_state(workflow_id, user_request)
            
            intent = intent_result.get("intent", "")
            
            if intent == "check_status":
                # 状态检查
                result = {"status": "running", "message": "系统运行正常"}
                state.add_execution_result("status_check", result)
                
            elif intent == "query_information":
                # 信息查询 - 使用React Agent
                from ..agents.react_agent import ReactAgent
                react_agent = ReactAgent()
                result = react_agent.execute(state)
                state.add_execution_result("information_query", result)
            
            # 设置完成状态
            from ..graph.state import WorkflowStatus
            state.workflow_status = WorkflowStatus.COMPLETED
            
            return state
            
        except Exception as e:
            logger.error(f"快速任务执行失败: {str(e)}", agent_name="IntelligentWorkflow")
            # 回退到默认流程
            return super().execute(user_request, [], file_processing_results, False, False)
    
    def _check_existing_report(self) -> bool:
        """检查是否有已存在的报告"""
        # TODO: 实现检查逻辑
        return False


# 创建智能工作流实例
intelligent_workflow = IntelligentMultiAgentWorkflow()


def get_intelligent_workflow() -> IntelligentMultiAgentWorkflow:
    """获取智能工作流实例"""
    return intelligent_workflow