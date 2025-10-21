"""
智能工作流路由器
基于LLM意图分析的智能任务路由系统
"""

import logging
from typing import Dict, Any, Optional, List
from .task_intent_analyzer import TaskIntentAnalyzer, TaskIntent, IntentAnalysisResult
from .agents.react_agent_optimizer import extend_react_agent_with_optimization
from .utils.logger import get_logger

logger = get_logger(__name__)


class IntelligentWorkflowRouter:
    """智能工作流路由器"""
    
    def __init__(self):
        self.intent_analyzer = TaskIntentAnalyzer()
        self.optimization_history = []
    
    def route_task_intelligently(self, task: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        智能路由任务
        
        Args:
            task: 任务描述
            context: 上下文信息
            
        Returns:
            路由决策和执行配置
        """
        # 分析任务意图
        intent_result = self.intent_analyzer.analyze_intent(task, context)
        
        logger.info(f"任务意图分析: {intent_result.intent.value} (置信度: {intent_result.confidence})")
        
        # 根据意图生成执行计划
        execution_plan = self._generate_execution_plan(intent_result, task, context)
        
        return {
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "target_pages": intent_result.target_pages,
            "execution_plan": execution_plan,
            "reasoning": intent_result.reasoning
        }
    
    def _generate_execution_plan(self, 
                                intent_result: IntentAnalysisResult, 
                                task: str, 
                                context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """生成执行计划"""
        
        intent = intent_result.intent
        
        if intent == TaskIntent.OPTIMIZE_SINGLE_PAGE:
            return self._plan_single_page_optimization(intent_result, task, context)
        
        elif intent == TaskIntent.REGENERATE_SINGLE_PAGE:
            return self._plan_single_page_regeneration(intent_result, task, context)
        
        elif intent == TaskIntent.OPTIMIZE_MULTIPLE_PAGES:
            return self._plan_multiple_page_optimization(intent_result, task, context)
        
        elif intent == TaskIntent.OPTIMIZE_ENTIRE_REPORT:
            return self._plan_entire_report_optimization(intent_result, task, context)
        
        elif intent == TaskIntent.GENERATE_NEW_REPORT:
            return self._plan_new_report_generation(intent_result, task, context)
        
        else:
            return self._plan_default_workflow(intent_result, task, context)
    
    def _plan_single_page_optimization(self, intent_result: IntentAnalysisResult, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """计划单页优化"""
        target_page = intent_result.target_pages[0] if intent_result.target_pages else 1
        
        return {
            "workflow_type": "single_page_optimization",
            "steps": [
                {
                    "type": "page_optimization",
                    "agent": "react",
                    "method": "optimize_single_page",
                    "params": {
                        "page_number": target_page,
                        "optimization_request": task,
                        "regenerate": False
                    }
                }
            ],
            "skip_steps": ["plan", "plan_confirmation", "reflect", "memory", "final_confirmation", "report_integration"],
            "tools": ["create_slide"],
            "estimated_time": "1-2 minutes",
            "description": f"直接优化第{target_page}页内容"
        }
    
    def _plan_single_page_regeneration(self, intent_result: IntentAnalysisResult, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """计划单页重新生成"""
        target_page = intent_result.target_pages[0] if intent_result.target_pages else 1
        
        return {
            "workflow_type": "single_page_regeneration", 
            "steps": [
                {
                    "type": "page_regeneration",
                    "agent": "react",
                    "method": "optimize_single_page",
                    "params": {
                        "page_number": target_page,
                        "optimization_request": task,
                        "regenerate": True
                    }
                }
            ],
            "skip_steps": ["plan", "plan_confirmation", "reflect", "memory", "final_confirmation", "report_integration"],
            "tools": ["create_slide"],
            "estimated_time": "2-3 minutes",
            "description": f"完全重新生成第{target_page}页内容"
        }
    
    def _plan_multiple_page_optimization(self, intent_result: IntentAnalysisResult, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """计划多页优化"""
        target_pages = intent_result.target_pages or [1]
        
        return {
            "workflow_type": "multiple_page_optimization",
            "steps": [
                {
                    "type": "batch_optimization",
                    "agent": "react",
                    "method": "optimize_multiple_pages",
                    "params": {
                        "page_numbers": target_pages,
                        "optimization_request": task
                    }
                }
            ],
            "skip_steps": ["plan", "plan_confirmation", "reflect", "memory", "final_confirmation"],
            "tools": ["create_slide"],
            "estimated_time": f"{len(target_pages)*2}-{len(target_pages)*3} minutes",
            "description": f"批量优化第{','.join(map(str, target_pages))}页"
        }
    
    def _plan_entire_report_optimization(self, intent_result: IntentAnalysisResult, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """计划整体报告优化"""
        return {
            "workflow_type": "entire_report_optimization",
            "steps": [
                {
                    "type": "reflection",
                    "agent": "reflect",
                    "method": "execute",
                    "params": {"optimization_focus": task}
                },
                {
                    "type": "report_integration",
                    "agent": "report",
                    "method": "execute",
                    "params": {"optimization_mode": True}
                }
            ],
            "skip_steps": ["plan", "plan_confirmation", "react", "content_confirmation", "memory", "final_confirmation"],
            "tools": ["content_generator", "report_generator"],
            "estimated_time": "10-15 minutes",
            "description": "整体优化报告结构和内容"
        }
    
    def _plan_new_report_generation(self, intent_result: IntentAnalysisResult, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """计划新报告生成"""
        return {
            "workflow_type": "full_report_generation",
            "steps": [
                {"type": "planning", "agent": "plan", "method": "execute"},
                {"type": "execution", "agent": "react", "method": "execute"},
                {"type": "reflection", "agent": "reflect", "method": "execute"},
                {"type": "integration", "agent": "report", "method": "execute"}
            ],
            "skip_steps": [],
            "tools": ["web_search", "content_generator", "create_slide", "report_generator"],
            "estimated_time": "20-30 minutes",
            "description": "生成完整的新报告"
        }
    
    def _plan_default_workflow(self, intent_result: IntentAnalysisResult, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """默认工作流计划"""
        return {
            "workflow_type": "default",
            "steps": [
                {"type": "planning", "agent": "plan", "method": "execute"},
                {"type": "execution", "agent": "react", "method": "execute"}
            ],
            "skip_steps": ["reflect", "memory", "final_confirmation"],
            "tools": [],
            "estimated_time": "5-10 minutes",
            "description": "执行通用任务流程"
        }
    
    def execute_intelligent_workflow(self, state, execution_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行智能工作流
        
        Args:
            state: 工作流状态
            execution_plan: 执行计划
            
        Returns:
            执行结果
        """
        workflow_type = execution_plan["workflow_type"]
        steps = execution_plan["steps"]
        
        logger.info(f"开始执行智能工作流: {workflow_type}")
        
        results = []
        
        try:
            for step in steps:
                step_result = self._execute_step(state, step)
                results.append(step_result)
                
                # 如果步骤失败，停止执行
                if not step_result.get("success", False):
                    break
            
            # 记录到优化历史
            self.optimization_history.append({
                "workflow_type": workflow_type,
                "timestamp": logger.get_timestamp() if hasattr(logger, 'get_timestamp') else None,
                "success": all(r.get("success", False) for r in results),
                "steps_count": len(steps)
            })
            
            return {
                "workflow_type": workflow_type,
                "success": all(r.get("success", False) for r in results),
                "results": results,
                "message": f"智能工作流 {workflow_type} 执行完成"
            }
            
        except Exception as e:
            logger.error(f"智能工作流执行失败: {str(e)}")
            return {
                "workflow_type": workflow_type,
                "success": False,
                "error": str(e),
                "results": results,
                "message": f"智能工作流 {workflow_type} 执行失败"
            }
    
    def _execute_step(self, state, step: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个步骤"""
        agent_name = step["agent"]
        method_name = step["method"]
        params = step.get("params", {})
        
        try:
            # 获取Agent实例
            agent = self._get_agent_instance(agent_name, state)
            
            # 如果是react agent，确保已扩展优化功能
            if agent_name == "react":
                extend_react_agent_with_optimization(agent)
            
            # 执行方法
            if hasattr(agent, method_name):
                method = getattr(agent, method_name)
                if params:
                    result = method(state, **params)
                else:
                    result = method(state)
                
                return {"success": True, "result": result, "step_type": step["type"]}
            else:
                raise AttributeError(f"Agent {agent_name} 没有方法 {method_name}")
                
        except Exception as e:
            logger.error(f"步骤执行失败 {step['type']}: {str(e)}")
            return {"success": False, "error": str(e), "step_type": step["type"]}
    
    def _get_agent_instance(self, agent_name: str, state):
        """获取Agent实例"""
        if agent_name == "react":
            from .agents.react_agent import ReactAgent
            return ReactAgent()
        elif agent_name == "plan":
            from .agents.plan_agent import PlanAgent
            return PlanAgent()
        elif agent_name == "reflect":
            from .agents.reflect_agent import ReflectAgent
            return ReflectAgent()
        elif agent_name == "report":
            from .agents.report_agent import ReportAgent
            return ReportAgent()
        else:
            raise ValueError(f"未知的Agent: {agent_name}")


# 全局路由器实例
_intelligent_router = None

def get_intelligent_router() -> IntelligentWorkflowRouter:
    """获取全局智能路由器实例"""
    global _intelligent_router
    if _intelligent_router is None:
        _intelligent_router = IntelligentWorkflowRouter()
    return _intelligent_router