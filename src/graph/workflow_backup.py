"""
LangGraph工作流模块
定义和管理multi-agent工作流
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from ..utils.logger import get_logger, log_workflow_step, log_user_interaction
from ..utils.config import get_config
from ..utils.llm_config import get_llm
from .state import (
    WorkflowState, WorkflowStatus, AgentStatus,
    create_workflow_state, create_execution_step, create_memory_entry
)

logger = get_logger(__name__)


class MultiAgentWorkflow:
    """Multi-Agent工作流管理器"""
    
    def __init__(self):
        """初始化工作流管理器"""
        self.config = get_config()
        self.workflow_config = self.config.get_workflow_config()
        self.llm = get_llm()
        
        # 创建工作流图
        self.graph = self._create_workflow_graph()
        
        # 工具执行器
        self.tool_executor = ToolNode([])
        
        logger.info("Multi-Agent工作流初始化完成", agent_name="WorkflowManager")
    
    def _create_workflow_graph(self) -> StateGraph:
        """创建工作流图"""
        # 创建状态图
        graph = StateGraph(WorkflowState)
        
        # 添加节点
        graph.add_node("plan", self._plan_node)
        graph.add_node("plan_confirmation", self._plan_confirmation_node)
        graph.add_node("react", self._react_node)
        graph.add_node("content_confirmation", self._content_confirmation_node)  # 新增：章节内容确认
        graph.add_node("reflect", self._reflect_node)
        graph.add_node("memory", self._memory_node)
        graph.add_node("final_confirmation", self._final_confirmation_node)
        graph.add_node("report_integration", self._report_integration_node)  # 新增：报告整合
        graph.add_node("report", self._report_node)
        graph.add_node("end", self._end_node)
        
        # 设置入口点
        graph.set_entry_point("plan")
        
        # 添加边
        graph.add_edge("plan", "plan_confirmation")
        graph.add_conditional_edges(
            "plan_confirmation",
            self._should_continue_after_plan,
            {
                "continue": "react",
                "retry": "plan",
                "cancel": "end"
            }
        )
        graph.add_conditional_edges(
            "react",
            self._should_continue_execution,
            {
                "continue": "react",
                "confirm": "content_confirmation",
                "reflect": "reflect",
                "end": "end"
            }
        )
        graph.add_conditional_edges(
            "content_confirmation",
            self._should_continue_after_content_confirmation,
            {
                "continue": "react",
                "revise": "react",
                "complete": "reflect"
            }
        )
        graph.add_edge("reflect", "memory")
        graph.add_edge("memory", "final_confirmation")
        graph.add_conditional_edges(
            "final_confirmation",
            self._should_generate_final_report,
            {
                "integrate": "report_integration",
                "revise": "react",
                "cancel": "end"
            }
        )
        # 优化：report_integration完成后直接结束，不需要再调用report节点
        graph.add_edge("report_integration", "end")
        # graph.add_edge("report", "end")  # 暂时保留report节点但不在主流程中使用
        
        # 添加内存checkpointer以支持状态管理
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        return graph.compile(checkpointer=checkpointer)
    
    def _plan_node(self, state: WorkflowState) -> WorkflowState:
        """Plan节点"""
        log_workflow_step("plan", "running")
        
        try:
            from ..agents.plan_agent import PlanAgent
            plan_agent = PlanAgent()
            
            result = plan_agent.execute(state)
            
            state.workflow_status = WorkflowStatus.PLANNING
            state.current_agent = "plan"
            state.plan = result.get("plan")
            state.execution_steps = result.get("execution_steps", [])
            
            logger.info("Plan节点执行完成", agent_name="WorkflowManager")
            log_workflow_step("plan", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"Plan节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.workflow_status = WorkflowStatus.FAILED
            state.set_last_error(str(e))
            log_workflow_step("plan", "failed")
            return state
    
    def _plan_confirmation_node(self, state: WorkflowState) -> WorkflowState:
        """计划确认节点"""
        log_workflow_step("plan_confirmation", "running")
        
        try:
            if self.workflow_config.get("enable_user_interaction", True):
                # 显示计划给用户确认
                plan_summary = self._generate_plan_summary(state)
                print("\n" + "="*50)
                print("PLAN 执行计划")
                print("="*50)
                print(plan_summary)
                print("="*50)
                
                # 获取用户输入
                user_input = input("\n是否确认此计划？(y/n/r): ").strip().lower()
                
                if user_input == 'y':
                    state.plan_confirmed = True
                    state.add_user_input("plan_confirmation", "confirmed")
                    log_user_interaction("plan_confirmation", "用户确认计划")
                    log_workflow_step("plan_confirmation", "completed")
                elif user_input == 'n':
                    state.plan_confirmed = False
                    state.add_user_input("plan_confirmation", "cancelled")
                    log_user_interaction("plan_confirmation", "用户取消计划")
                    log_workflow_step("plan_confirmation", "completed")
                elif user_input == 'r':
                    state.plan_confirmed = False
                    state.add_user_input("plan_confirmation", "retry")
                    log_user_interaction("plan_confirmation", "用户要求重试")
                    log_workflow_step("plan_confirmation", "completed")
                else:
                    state.plan_confirmed = False
                    state.add_user_input("plan_confirmation", "cancelled")
                    log_user_interaction("plan_confirmation", "用户取消计划")
                    log_workflow_step("plan_confirmation", "completed")
            else:
                # 自动确认
                state.plan_confirmed = True
                log_workflow_step("plan_confirmation", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"计划确认节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("plan_confirmation", "failed")
            return state
    
    def _react_node(self, state: WorkflowState) -> WorkflowState:
        """React节点"""
        if state.current_step is None:
            # 开始执行第一个步骤
            pending_steps = state.get_pending_steps()
            if pending_steps:
                state.current_step = pending_steps[0].step_id
            else:
                # 没有待执行步骤，跳转到reflect
                state.workflow_status = WorkflowStatus.REFLECTING
                return state
        
        log_workflow_step("react", f"executing_step_{state.current_step}")
        
        try:
            from ..agents.react_agent import ReactAgent
            react_agent = ReactAgent()
            
            # 执行当前步骤
            result = react_agent.execute_step(state, state.current_step)
            
            # 更新状态
            state.update_step_status(state.current_step, AgentStatus.COMPLETED)
            state.add_execution_result(state.current_step, result)
            state.execution_logs.append(f"步骤 {state.current_step} 执行完成")
            
            # 检查是否有新生成的幻灯片内容需要立即返回
            if hasattr(state, 'slides_content') and state.slides_content:
                print(f"DEBUG - React node: Found slides_content with keys: {list(state.slides_content.keys())}")
                # 这里我们需要一种方式来通知streaming系统有新的幻灯片
                # 由于我们在节点内部，不能直接yield，需要设置一个标志
            
            # 查找下一个待执行步骤
            pending_steps = state.get_pending_steps()
            if pending_steps:
                state.current_step = pending_steps[0].step_id
                state.workflow_status = WorkflowStatus.EXECUTING
            else:
                # 所有步骤执行完成
                state.current_step = None
                state.workflow_status = WorkflowStatus.REFLECTING
            
            logger.info(f"React节点执行步骤 {state.current_step} 完成", agent_name="WorkflowManager")
            return state
            
        except Exception as e:
            logger.error(f"React节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.update_step_status(state.current_step, AgentStatus.FAILED)
            state.set_last_error(str(e))
            state.increment_error_count()
            return state
    
    def _reflect_node(self, state: WorkflowState) -> WorkflowState:
        """Reflect节点"""
        log_workflow_step("reflect", "running")
        
        try:
            from ..agents.reflect_agent import ReflectAgent
            reflect_agent = ReflectAgent()
            
            result = reflect_agent.execute(state)
            
            state.workflow_status = WorkflowStatus.REFLECTING
            state.current_agent = "reflect"
            state.quality_assessment = result.get("quality_assessment")
            state.reflection_notes = result.get("reflection_notes", "")
            
            logger.info("Reflect节点执行完成", agent_name="WorkflowManager")
            log_workflow_step("reflect", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"Reflect节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("reflect", "failed")
            return state
    
    def _memory_node(self, state: WorkflowState) -> WorkflowState:
        """Memory节点"""
        log_workflow_step("memory", "running")
        
        try:
            from ..agents.memory_agent import MemoryAgent
            memory_agent = MemoryAgent()
            
            result = memory_agent.execute(state)
            
            state.workflow_status = WorkflowStatus.MEMORIZING
            state.current_agent = "memory"
            state.memory_entries = result.get("memory_entries", [])
            state.context_summary = result.get("context_summary", "")
            
            logger.info("Memory节点执行完成", agent_name="WorkflowManager")
            log_workflow_step("memory", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"Memory节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("memory", "failed")
            return state
    
    def _report_node(self, state: WorkflowState) -> WorkflowState:
        """Report节点"""
        log_workflow_step("report", "running")
        
        try:
            from ..agents.report_agent import ReportAgent
            report_agent = ReportAgent()
            
            result = report_agent.execute(state)
            
            state.workflow_status = WorkflowStatus.REPORTING
            state.current_agent = "report"
            state.report_content = result.get("report_content")
            state.report_metadata = result.get("report_metadata", {})
            
            logger.info("Report节点执行完成", agent_name="WorkflowManager")
            log_workflow_step("report", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"Report节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("report", "failed")
            return state
    
    def _end_node(self, state: WorkflowState) -> WorkflowState:
        """结束节点"""
        log_workflow_step("end", "running")
        
        try:
            state.workflow_status = WorkflowStatus.COMPLETED
            state.end_time = datetime.now()
            state.current_agent = None
            state.current_step = None
            
            # 显示最终结果
            progress = state.get_progress_summary()
            print(f"\nCOMPLETE 工作流完成！")
            print(f"总步骤数: {progress['total_steps']}")
            print(f"完成步骤: {progress['completed_steps']}")
            print(f"失败步骤: {progress['failed_steps']}")
            print(f"完成率: {progress['progress_percentage']}%")
            
            if state.report_content:
                print(f"\nREPORT 报告已生成: {state.report_metadata.get('output_path', '未知路径')}")
            
            logger.info("工作流执行完成", agent_name="WorkflowManager")
            log_workflow_step("end", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"结束节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("end", "failed")
            return state
    
    def _content_confirmation_node(self, state: WorkflowState) -> WorkflowState:
        """内容确认节点 - 让用户确认每个章节的内容"""
        log_workflow_step("content_confirmation", "running")
        
        try:
            current_step_obj = state.get_step_by_id(state.current_step)
            if not current_step_obj:
                return state
            
            # 获取刚生成的内容
            execution_result = state.get_execution_result(state.current_step)
            if not execution_result:
                return state
            
            section_title = execution_result.get('section_title', current_step_obj.metadata.get('section_title', '未知章节'))
            content = execution_result.get('content', '')
            summary = execution_result.get('summary', '')
            
            # 显示内容给用户确认
            print(f"\nSECTION 章节内容已生成: {section_title}")
            print(f"内容摘要: {summary}")
            print(f"内容长度: {execution_result.get('word_count', '未知')}字")
            
            # 如果content是HTML，显示纯文本版本供预览
            if content.startswith('<'):
                # 简单的HTML标签移除（用于预览）
                import re
                text_content = re.sub(r'<[^>]+>', '', content)
                preview = text_content[:500] + "..." if len(text_content) > 500 else text_content
                print(f"\n内容预览:\n{preview}")
            else:
                preview = content[:500] + "..." if len(content) > 500 else content
                print(f"\n内容预览:\n{preview}")
            
            # 记录确认状态
            state.chapter_confirmations = getattr(state, 'chapter_confirmations', {})
            state.chapter_confirmations[state.current_step] = {
                "content": content,
                "confirmed": True,  # 自动确认，实际项目中可以添加用户交互
                "timestamp": datetime.now(),
                "section_title": section_title
            }
            
            logger.info(f"章节 {section_title} 内容已确认", agent_name="WorkflowManager")
            log_workflow_step("content_confirmation", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"内容确认节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("content_confirmation", "failed")
            return state
    
    def _report_integration_node(self, state: WorkflowState) -> WorkflowState:
        """报告整合节点 - 将所有确认的章节整合成完整报告"""
        log_workflow_step("report_integration", "running")
        
        try:
            from ..agents.report_integration_agent import ReportIntegrationAgent
            integration_agent = ReportIntegrationAgent()
            
            # 收集所有确认的章节内容
            confirmed_chapters = getattr(state, 'chapter_confirmations', {})
            
            # 如果没有确认的章节，尝试从执行结果中构建章节内容
            if not confirmed_chapters:
                logger.info("没有找到已确认的章节内容，尝试从执行结果中构建", agent_name="WorkflowManager")
                confirmed_chapters = self._build_chapters_from_execution_results(state)
            
            if not confirmed_chapters:
                logger.warning("无法获取章节内容，跳过PPT生成", agent_name="WorkflowManager")
                return state
            
            # 执行报告整合
            result = integration_agent.execute(state, confirmed_chapters)
            
            # 更新状态 - Report Integration完成后直接标记为完成
            state.report_content = result.get("integrated_content")
            state.report_metadata = result.get("metadata", {})
            state.workflow_status = WorkflowStatus.COMPLETED  # 直接设置为完成状态
            
            logger.info("报告整合完成", agent_name="WorkflowManager")
            log_workflow_step("report_integration", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"报告整合节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("report_integration", "failed")
            return state
    
    def _build_chapters_from_execution_results(self, state: WorkflowState) -> Dict[str, Any]:
        """从执行结果中构建章节内容"""
        chapters = {}
        
        try:
            # 获取所有已完成的步骤
            completed_steps = state.get_completed_steps()
            
            for step in completed_steps:
                step_id = step.step_id
                execution_result = state.get_execution_result(step_id)
                
                if execution_result and execution_result.get('content'):
                    # 从执行结果中提取章节信息
                    section_title = execution_result.get('section_title', step.description)
                    raw_content = execution_result.get('content', '')
                    
                    # 清理内容，移除任务要求和元信息
                    clean_content = self._clean_chapter_content(raw_content)
                    
                    chapters[step_id] = {
                        "content": clean_content,
                        "confirmed": True,
                        "timestamp": datetime.now(),
                        "section_title": section_title,
                        "step_description": step.description,
                        "word_count": len(clean_content)
                    }
            
            logger.info(f"从执行结果中构建了 {len(chapters)} 个章节", agent_name="WorkflowManager")
            return chapters
            
        except Exception as e:
            logger.error(f"构建章节内容失败: {str(e)}", agent_name="WorkflowManager")
            return {}
    
    def _clean_chapter_content(self, content: str) -> str:
        """清理章节内容，移除任务要求和元信息"""
        import re
        
        if not isinstance(content, str):
            content = str(content)
        
        # 移除明显的任务指示和元信息
        task_removal_patterns = [
            r'生成报告章节[:：][^。]*?[。\n]',
            r'章节要求[:：][^。]*?[。\n]', 
            r'关键要点[:：][^。]*?[。\n]',
            r'输出要求[:：][^。]*?[。\n]',
            r'章节内容已生成[:：][^。]*?[。\n]',
            r'内容摘要[:：][^。]*?[。\n]',
            r'内容长度[:：][^。]*?[。\n]',
            r'内容预览[:：][^。]*?[。\n]',
            r'\(\d+/\d+\)',  # 移除页码标记
            r'格式应该[^。]*?[。\n]',
            r'内容应该[^。]*?[。\n]',
            r'确保格式[^。]*?[。\n]',
            r'请基于[^。]*?进行[^。]*?[。\n]',
            r'基于文件内容[^。]*?[。\n]',
            r'不要泛泛而谈[^。]*?[。\n]',
            r'内容质量直接影响[^。]*?[。\n]',
            r'确保格式规范[^。]*?[。\n]'
        ]
        
        for pattern in task_removal_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
        
        # 按行清理
        lines = content.split('\n')
        clean_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 跳过明显的指令行
            skip_keywords = [
                '生成报告章节', '章节要求', '关键要点', '输出要求',
                '章节内容已生成', '内容摘要', '内容长度', '内容预览',
                '格式应该', '内容应该', '确保格式', '包含适当的',
                '生成完整的', '请基于', '基于文件内容', '不要泛泛而谈',
                '内容质量直接影响', '确保格式规范'
            ]
            
            should_skip = False
            for keyword in skip_keywords:
                if keyword in line:
                    should_skip = True
                    break
            
            # 跳过明显的任务描述行（包含冒号且很长）
            if ':' in line and len(line) > 80 and any(word in line for word in ['要求', '建议', '格式', '确保']):
                should_skip = True
            
            if not should_skip:
                clean_lines.append(line)
        
        # 重新组合内容
        cleaned_content = '\n'.join(clean_lines)
        
        # 清理多余的空白
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
        cleaned_content = cleaned_content.strip()
        
        # 如果内容为空，提供默认内容
        if not cleaned_content or len(cleaned_content) < 20:
            cleaned_content = "内容正在处理中，请稍后查看..."
        
        return cleaned_content
    
    def _should_continue_after_content_confirmation(self, state: WorkflowState) -> str:
        """判断内容确认后是否继续"""
        # 检查是否还有待执行的步骤
        pending_steps = state.get_pending_steps()
        if pending_steps:
            state.current_step = pending_steps[0].step_id
            return "continue"
        else:
            # 所有章节都已生成和确认，进入反思阶段
            state.current_step = None
            return "complete"
    
    def _should_continue_after_plan(self, state: WorkflowState) -> str:
        """判断计划确认后是否继续"""
        if state.plan_confirmed:
            return "continue"
        elif state.get_user_input("plan_confirmation") == "retry":
            return "retry"
        else:
            return "cancel"
    
    def _should_continue_execution(self, state: WorkflowState) -> str:
        """判断是否继续执行"""
        # 检查是否有当前正在执行的步骤
        if state.current_step is not None:
            # 检查当前步骤是否刚完成，需要确认
            current_step_obj = state.get_step_by_id(state.current_step)
            if current_step_obj and current_step_obj.status == AgentStatus.COMPLETED:
                return "confirm"  # 进入内容确认
            return "continue"
        
        # 检查普通执行步骤中是否还有待执行的步骤
        pending_steps = state.get_pending_steps()
        if pending_steps:
            state.current_step = pending_steps[0].step_id
            return "continue"
        
        # 如果没有待执行步骤，检查是否有失败的步骤
        if state.get_failed_steps():
            return "end"
        
        # 所有步骤都已完成，进入反思阶段
        return "reflect"
    
    def _final_confirmation_node(self, state: WorkflowState) -> WorkflowState:
        """最终确认节点"""
        log_workflow_step("final_confirmation", "running")
        
        try:
            if self.workflow_config.get("enable_user_interaction", True):
                # 显示生成的内容给用户确认
                content_summary = self._generate_content_summary(state)
                print("\n" + "="*50)
                print("CONTENT 内容生成完成")
                print("="*50)
                print(content_summary)
                print("="*50)
                
                # 获取用户输入
                user_input = input("\n是否确认生成最终报告？(y/n/r): ").strip().lower()
                
                if user_input == 'y':
                    state.final_confirmed = True
                    state.add_user_input("final_confirmation", "confirmed")
                    log_user_interaction("final_confirmation", "用户确认最终生成")
                    log_workflow_step("final_confirmation", "completed")
                elif user_input == 'n':
                    state.final_confirmed = False
                    state.add_user_input("final_confirmation", "cancelled")
                    log_user_interaction("final_confirmation", "用户取消最终生成")
                    log_workflow_step("final_confirmation", "completed")
                elif user_input == 'r':
                    state.final_confirmed = False
                    state.add_user_input("final_confirmation", "revise")
                    log_user_interaction("final_confirmation", "用户要求修改内容")
                    log_workflow_step("final_confirmation", "completed")
                else:
                    state.final_confirmed = False
                    state.add_user_input("final_confirmation", "cancelled")
                    log_user_interaction("final_confirmation", "用户取消最终生成")
                    log_workflow_step("final_confirmation", "completed")
            else:
                # 自动确认
                state.final_confirmed = True
                log_workflow_step("final_confirmation", "completed")
            
            return state
            
        except Exception as e:
            logger.error(f"最终确认节点执行失败: {str(e)}", agent_name="WorkflowManager")
            state.set_last_error(str(e))
            log_workflow_step("final_confirmation", "failed")
            return state
    
    def _should_generate_final_report(self, state: WorkflowState) -> str:
        """判断是否生成最终报告"""
        if state.final_confirmed:
            return "integrate"
        elif state.get_user_input("final_confirmation") == "revise":
            return "revise"
        else:
            return "cancel"
    
    def _generate_content_summary(self, state: WorkflowState) -> str:
        """生成内容摘要"""
        completed_steps = state.get_completed_steps()
        failed_steps = state.get_failed_steps()
        
        summary = "CONTENT 内容生成摘要:\n\n"
        summary += f"OK 已完成步骤: {len(completed_steps)}\n"
        summary += f"ERROR 失败步骤: {len(failed_steps)}\n\n"
        
        if completed_steps:
            summary += "已完成内容:\n"
            for step in completed_steps:
                result = state.get_execution_result(step.step_id)
                if result and "content" in result:
                    content_preview = result["content"][:100] + "..." if len(result["content"]) > 100 else result["content"]
                    summary += f"- {step.description}: {content_preview}\n"
        
        if failed_steps:
            summary += "\n失败内容:\n"
            for step in failed_steps:
                summary += f"- {step.description}: {step.error_message or '未知错误'}\n"
        
        return summary
    
    def _generate_plan_summary(self, state: WorkflowState) -> str:
        """生成计划摘要"""
        if not state.execution_steps:
            return "无执行步骤"
        
        summary = f"PLAN 执行计划 (共 {len(state.execution_steps)} 个步骤):\n\n"
        
        for i, step in enumerate(state.execution_steps, 1):
            status_icon = {"idle": "PENDING", "running": "RUNNING", "completed": "OK", "failed": "ERROR"}.get(step.status.value, "PENDING")
            summary += f"{i}. {status_icon} {step.description}\n"
            summary += f"   预期输出: {step.expected_output}\n"
            if step.required_tools:
                summary += f"   所需工具: {', '.join(step.required_tools)}\n"
            if step.dependencies:
                summary += f"   依赖步骤: {', '.join(step.dependencies)}\n"
            summary += "\n"
        
        return summary
    
    def execute_stream(self, user_request: str, user_constraints: List[str] = None, file_processing_results: List[Dict[str, Any]] = None, extract_only: bool = False, use_premium_template: bool = False):
        """
        使用LangGraph的stream方法进行流式执行
        
        Args:
            user_request: 用户请求
            user_constraints: 用户约束
            file_processing_results: 文件处理结果列表
            extract_only: 是否只提取HTML页面，不整合
            use_premium_template: 是否使用Premium高端模板直接生成
            
        Yields:
            工作流执行步骤的状态信息
        """
        try:
            # 创建工作流状态
            workflow_id = str(uuid.uuid4())
            state = create_workflow_state(workflow_id, user_request)
            
            # 首先发送workflow_id给调用者
            yield {
                'type': 'workflow_start',
                'workflow_id': workflow_id,
                'message': f'工作流 {workflow_id} 已启动'
            }
            
            if user_constraints:
                state.user_constraints = user_constraints
            
            # 将Premium模板标志添加到状态中
            if use_premium_template:
                state.use_premium_template = True
            
            # 设置extract_only模式
            state.extract_only = extract_only
            
            # 添加文件处理结果到状态
            if file_processing_results:
                for i, result in enumerate(file_processing_results):
                    file_id = result.get("result", {}).get("file_id", f"file_{i}")
                    state.add_file_processing_result(file_id, result)
                logger.info(f"添加了 {len(file_processing_results)} 个文件处理结果到工作流状态", agent_name="WorkflowManager")
            
            logger.info(f"开始流式执行工作流 {workflow_id}", agent_name="WorkflowManager")
            
            # 使用队列基础的流式执行方法
            from ..utils.slide_queue import slide_queue
            
            # 为当前工作流创建队列
            slide_queue.create_queue(workflow_id)
            
            step_count = 0
            sent_slides = set()  # 跟踪已发送的幻灯片
            
            # 使用混合模式：LangGraph流式执行 + 队列检查
            import time
            
            # 配置checkpointer所需的thread_id
            config = {"configurable": {"thread_id": workflow_id}}
            
            for chunk in self.graph.stream(state, config=config):
                step_count += 1
                
                # 分析当前执行的节点
                node_name = list(chunk.keys())[0] if chunk else "unknown"
                current_state = list(chunk.values())[0] if chunk else state
                print(f"DEBUG - Workflow chunk from node: {node_name}")
                
                # 在每个chunk后检查队列中的新幻灯片
                while True:
                    slide_event = slide_queue.get_slide(workflow_id, timeout=0.01)  # 非阻塞检查
                    if slide_event is None:
                        break
                    
                    if slide_event.slide_index not in sent_slides:
                        sent_slides.add(slide_event.slide_index)
                        print(f"DEBUG - Chunk loop: Yielding slide {slide_event.slide_index}")
                        
                        yield {
                            'type': 'slide_ready',
                            'slide_index': slide_event.slide_index,
                            'slide_content': slide_event.slide_content,
                            'slide_title': slide_event.slide_title,
                            'total_slides': slide_event.total_slides,
                            'progress': 30 + (len(sent_slides) * 50 // slide_event.total_slides) if slide_event.total_slides > 0 else 80
                        }
                
                # 根据节点类型返回不同的进度信息
                if node_name == "plan":
                    yield {
                        'type': 'progress', 
                        'message': '正在制定执行计划...', 
                        'progress': 10,
                        'node': node_name
                    }
                elif node_name == "plan_confirmation":
                    yield {
                        'type': 'progress', 
                        'message': '计划制定完成，开始执行...', 
                        'progress': 20,
                        'node': node_name
                    }
                elif node_name == "react":
                    yield {
                        'type': 'progress', 
                        'message': f'正在执行步骤 {step_count}...', 
                        'progress': 30 + min(step_count * 5, 40),
                        'node': node_name
                    }
                elif node_name == "reflect":
                    yield {
                        'type': 'progress', 
                        'message': '正在进行质量评估...', 
                        'progress': 80,
                        'node': node_name
                    }
            
            # 工作流完成后，检查是否还有剩余的幻灯片
            while True:
                slide_event = slide_queue.get_slide(workflow_id, timeout=0.1)
                if slide_event is None:
                    break
                
                if slide_event.slide_index not in sent_slides:
                    sent_slides.add(slide_event.slide_index)
                    print(f"DEBUG - Final check: Yielding slide {slide_event.slide_index}")
                    
                    yield {
                        'type': 'slide_ready',
                        'slide_index': slide_event.slide_index,
                        'slide_content': slide_event.slide_content,
                        'slide_title': slide_event.slide_title,
                        'total_slides': slide_event.total_slides,
                        'progress': 30 + (len(sent_slides) * 50 // slide_event.total_slides) if slide_event.total_slides > 0 else 80
                    }
            
            # 清理队列
            slide_queue.cleanup_queue(workflow_id)
            
            # 最终返回完成状态
            final_state = self.graph.get_state(config={'configurable': {'thread_id': workflow_id}})
            yield {
                'type': 'completed',
                'final_state': final_state.values.to_dict() if hasattr(final_state.values, 'to_dict') else str(final_state.values),
                'slides_content': final_state.values.slides_content.get('1') if hasattr(final_state.values, 'slides_content') and final_state.values.slides_content else None,
                'progress': 100
            }
            
            logger.info(f"工作流 {workflow_id} 执行完成", agent_name="WorkflowManager")
            
        except Exception as e:
            logger.error(f"LangGraph流式执行失败: {str(e)}", agent_name="WorkflowManager")
            yield {
                'type': 'error',
                'message': f'工作流执行出错: {str(e)}',
                'progress': 100
            }
    
    def execute(self, user_request: str, user_constraints: List[str] = None, file_processing_results: List[Dict[str, Any]] = None, extract_only: bool = False, use_premium_template: bool = False) -> WorkflowState:
        """
        执行工作流
        
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
            # 创建工作流状态
            workflow_id = str(uuid.uuid4())
            state = create_workflow_state(workflow_id, user_request)
            
            if user_constraints:
                state.user_constraints = user_constraints
            
            # 将Premium模板标志添加到状态中
            if use_premium_template:
                state.use_premium_template = True
            
            # 设置extract_only模式
            state.extract_only = extract_only
            
            # 添加文件处理结果到状态
            if file_processing_results:
                # 将列表转换为字典，以符合状态模型的要求
                for i, result in enumerate(file_processing_results):
                    file_id = result.get("result", {}).get("file_id", f"file_{i}")
                    state.add_file_processing_result(file_id, result)
                logger.info(f"添加了 {len(file_processing_results)} 个文件处理结果到工作流状态", agent_name="WorkflowManager")
            
            logger.info(f"开始执行工作流 {workflow_id}", agent_name="WorkflowManager")
            
            # 执行工作流
            result = self.graph.invoke(state)
            
            logger.info(f"工作流 {workflow_id} 执行完成", agent_name="WorkflowManager")
            
            return result
            
        except Exception as e:
            logger.error(f"工作流执行失败: {str(e)}", agent_name="WorkflowManager")
            raise
    
    def get_workflow_status(self, state: WorkflowState) -> Dict[str, Any]:
        """获取工作流状态"""
        return state.get_progress_summary()
    
    def pause_workflow(self, state: WorkflowState) -> WorkflowState:
        """暂停工作流"""
        state.workflow_status = WorkflowStatus.CANCELLED
        logger.info("工作流已暂停", agent_name="WorkflowManager")
        return state
    
    def resume_workflow(self, state: WorkflowState) -> WorkflowState:
        """恢复工作流"""
        # 重新执行工作流
        return self.graph.invoke(state)


# 全局工作流实例
workflow = MultiAgentWorkflow()


def get_workflow() -> MultiAgentWorkflow:
    """获取全局工作流实例"""
    return workflow


def execute_workflow(user_request: str, user_constraints: List[str] = None, extract_only: bool = False) -> WorkflowState:
    """执行工作流的便捷函数"""
    return workflow.execute(user_request, user_constraints, None, extract_only)
