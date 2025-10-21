"""
Reflect Agent模块
负责评估执行结果质量并提供改进建议
"""

import json
from typing import Dict, Any, List
from ..utils.config import get_agent_config, get_agent_prompt
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response, generate_system_response_stream
from typing import Iterator
from ..graph.state import QualityAssessment, create_quality_assessment

logger = get_logger(__name__)


class ReflectAgent:
    """Reflect Agent - 质量评估专家"""
    
    def __init__(self):
        """初始化Reflect Agent"""
        self.config = get_agent_config("reflect")
        self.system_prompt = get_agent_prompt("reflect_agent")
        self.quality_threshold = self.config.get("quality_threshold", 0.8)
        
        logger.info("Reflect Agent初始化完成", agent_name="ReflectAgent")
    
    def execute(self, state) -> Dict[str, Any]:
        """
        执行质量评估任务
        
        Args:
            state: 工作流状态
            
        Returns:
            评估结果字典
        """
        task_description = "评估执行结果质量并提供改进建议"
        log_agent_start("ReflectAgent", task_description)
        
        try:
            # 收集执行结果
            execution_results = self._collect_execution_results(state)
            
            # 构建评估上下文
            assessment_context = self._build_assessment_context(state, execution_results)
            
            # 执行质量评估
            assessment_result = self._perform_quality_assessment(assessment_context)
            
            # 创建质量评估对象
            quality_assessment = create_quality_assessment(
                overall_score=assessment_result.get("overall_score", 0.0),
                accuracy_score=assessment_result.get("accuracy_score", 0.0),
                completeness_score=assessment_result.get("completeness_score", 0.0),
                logical_score=assessment_result.get("logical_score", 0.0),
                readability_score=assessment_result.get("readability_score", 0.0),
                relevance_score=assessment_result.get("relevance_score", 0.0),
                strengths=assessment_result.get("strengths", []),
                weaknesses=assessment_result.get("weaknesses", []),
                improvement_suggestions=assessment_result.get("improvement_suggestions", []),
                assessment_notes=assessment_result.get("assessment_notes", "")
            )
            
            # 生成反思备注
            reflection_notes = self._generate_reflection_notes(quality_assessment, state)
            
            # 构建结果
            result = {
                "quality_assessment": quality_assessment,
                "reflection_notes": reflection_notes,
                "assessment_summary": self._generate_assessment_summary(quality_assessment),
                "needs_improvement": quality_assessment.overall_score < self.quality_threshold,
                "recommendation": self._generate_recommendation(quality_assessment)
            }
            
            logger.info(f"质量评估完成，总体评分: {quality_assessment.overall_score:.2f}", agent_name="ReflectAgent")
            log_agent_complete("ReflectAgent", task_description, f"总体评分: {quality_assessment.overall_score:.2f}")
            
            return result
            
        except Exception as e:
            error_msg = f"质量评估失败: {str(e)}"
            logger.error(error_msg, agent_name="ReflectAgent")
            raise Exception(error_msg)
    
    def _collect_execution_results(self, state) -> Dict[str, Any]:
        """收集执行结果"""
        execution_results = {
            "completed_steps": [],
            "failed_steps": [],
            "step_results": {},
            "execution_logs": state.execution_logs,
            "total_steps": len(state.execution_steps),
            "completed_count": len(state.get_completed_steps()),
            "failed_count": len(state.get_failed_steps())
        }
        
        # 收集已完成步骤的结果
        for step in state.get_completed_steps():
            step_result = {
                "step_id": step.step_id,
                "description": step.description,
                "expected_output": step.expected_output,
                "actual_output": state.get_execution_result(step.step_id),
                "execution_time": self._calculate_execution_time(step),
                "attempts": step.execution_attempts
            }
            execution_results["completed_steps"].append(step_result)
            execution_results["step_results"][step.step_id] = step_result
        
        # 收集失败步骤的信息
        for step in state.get_failed_steps():
            failed_step = {
                "step_id": step.step_id,
                "description": step.description,
                "error_message": step.error_message,
                "attempts": step.execution_attempts
            }
            execution_results["failed_steps"].append(failed_step)
        
        return execution_results
    
    def _calculate_execution_time(self, step) -> float:
        """计算步骤执行时间"""
        if step.start_time and step.end_time:
            return (step.end_time - step.start_time).total_seconds()
        return 0.0
    
    def _build_assessment_context(self, state, execution_results: Dict[str, Any]) -> Dict[str, Any]:
        """构建评估上下文"""
        context = {
            "user_request": state.user_request,
            "user_constraints": state.user_constraints,
            "original_plan": state.plan,
            "execution_results": execution_results,
            "workflow_id": state.workflow_id,
            "quality_threshold": self.quality_threshold,
            "assessment_criteria": self._get_assessment_criteria()
        }
        
        return context
    
    def _get_assessment_criteria(self) -> Dict[str, str]:
        """获取评估标准"""
        return {
            "accuracy": "信息的准确性和真实性",
            "completeness": "内容是否完整覆盖所有必要信息",
            "logical": "内容组织是否逻辑清晰、结构合理",
            "readability": "语言表达是否清晰易懂、格式规范",
            "relevance": "内容是否符合用户需求和约束条件"
        }
    
    def _perform_quality_assessment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """执行质量评估"""
        # 构建评估输入
        assessment_input = self._build_assessment_input(context)
        
        # 生成评估结果（使用流式输出）
        response = ""
        logger.info("开始质量评估（流式输出）...", agent_name="ReflectAgent")
        
        for chunk in generate_system_response_stream(
            self.system_prompt,
            assessment_input,
            temperature=0.3  # 降低温度以获得更稳定的评估
        ):
            response += chunk
            # 可以在这里添加实时处理逻辑
            # 例如：logger.debug(f"质量评估收到流式响应块: {chunk}")
        
        logger.info("质量评估完成，开始解析响应...", agent_name="ReflectAgent")
        
        # 解析评估结果
        assessment_result = self._parse_assessment_response(response)
        
        return assessment_result
    
    def _build_assessment_input(self, context: Dict[str, Any]) -> str:
        """构建评估输入"""
        input_text = f"""
请对以下报告生成执行结果进行质量评估:

用户请求: {context['user_request']}

用户约束条件:
"""
        
        if context['user_constraints']:
            for constraint in context['user_constraints']:
                input_text += f"- {constraint}\n"
        else:
            input_text += "- 无特殊约束\n"
        
        input_text += f"""
执行统计:
- 总步骤数: {context['execution_results']['total_steps']}
- 完成步骤: {context['execution_results']['completed_count']}
- 失败步骤: {context['execution_results']['failed_count']}
- 质量阈值: {context['quality_threshold']}

评估标准:
"""
        
        for criterion, description in context['assessment_criteria'].items():
            input_text += f"- {criterion}: {description}\n"
        
        input_text += """
执行结果详情:
"""
        
        # 添加已完成步骤的详细信息
        for step_result in context['execution_results']['completed_steps']:
            input_text += f"""
步骤 {step_result['step_id']}: {step_result['description']}
预期输出: {step_result['expected_output']}
实际输出: {str(step_result['actual_output'])[:200]}...
执行时间: {step_result['execution_time']:.2f}秒
尝试次数: {step_result['attempts']}
"""
        
        # 添加失败步骤的信息
        if context['execution_results']['failed_steps']:
            input_text += "\n失败步骤:\n"
            for failed_step in context['execution_results']['failed_steps']:
                input_text += f"""
步骤 {failed_step['step_id']}: {failed_step['description']}
错误信息: {failed_step['error_message']}
尝试次数: {failed_step['attempts']}
"""
        
        input_text += """
请根据以上信息进行质量评估，并返回JSON格式的结果，包含以下字段:
- overall_score: 总体质量评分 (0-1)
- accuracy_score: 准确性评分 (0-1)
- completeness_score: 完整性评分 (0-1)
- logical_score: 逻辑性评分 (0-1)
- readability_score: 可读性评分 (0-1)
- relevance_score: 相关性评分 (0-1)
- strengths: 优点列表
- weaknesses: 不足列表
- improvement_suggestions: 改进建议列表
- assessment_notes: 评估备注

请确保评分合理，并提供具体的分析和建议。
"""
        
        return input_text
    
    def _parse_assessment_response(self, response: str) -> Dict[str, Any]:
        """解析评估响应"""
        try:
            # 尝试直接解析JSON
            assessment_result = json.loads(response)
            return assessment_result
            
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            try:
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response[start_idx:end_idx]
                    assessment_result = json.loads(json_str)
                    return assessment_result
                else:
                    raise ValueError("响应中未找到有效的JSON格式")
                    
            except Exception as e:
                logger.warning(f"JSON解析失败，使用默认评估: {str(e)}", agent_name="ReflectAgent")
                return self._create_default_assessment()
    
    def _create_default_assessment(self) -> Dict[str, Any]:
        """创建默认评估结果"""
        return {
            "overall_score": 0.7,
            "accuracy_score": 0.7,
            "completeness_score": 0.7,
            "logical_score": 0.7,
            "readability_score": 0.7,
            "relevance_score": 0.7,
            "strengths": ["基本功能正常"],
            "weaknesses": ["评估过程遇到技术问题"],
            "improvement_suggestions": ["建议重新评估"],
            "assessment_notes": "由于技术问题，使用了默认评估结果"
        }
    
    def _generate_reflection_notes(self, quality_assessment: QualityAssessment, state) -> str:
        """生成反思备注"""
        notes = f"""
质量评估反思报告
===================

总体评分: {quality_assessment.overall_score:.2f}
质量阈值: {self.quality_threshold}
评估结果: {'通过' if quality_assessment.overall_score >= self.quality_threshold else '未通过'}

详细分析:
"""
        
        notes += f"- 准确性: {quality_assessment.accuracy_score:.2f}\n"
        notes += f"- 完整性: {quality_assessment.completeness_score:.2f}\n"
        notes += f"- 逻辑性: {quality_assessment.logical_score:.2f}\n"
        notes += f"- 可读性: {quality_assessment.readability_score:.2f}\n"
        notes += f"- 相关性: {quality_assessment.relevance_score:.2f}\n\n"
        
        if quality_assessment.strengths:
            notes += "主要优点:\n"
            for strength in quality_assessment.strengths:
                notes += f"- {strength}\n"
            notes += "\n"
        
        if quality_assessment.weaknesses:
            notes += "主要不足:\n"
            for weakness in quality_assessment.weaknesses:
                notes += f"- {weakness}\n"
            notes += "\n"
        
        if quality_assessment.improvement_suggestions:
            notes += "改进建议:\n"
            for suggestion in quality_assessment.improvement_suggestions:
                notes += f"- {suggestion}\n"
            notes += "\n"
        
        notes += f"评估备注: {quality_assessment.assessment_notes}\n"
        
        return notes
    
    def _generate_assessment_summary(self, quality_assessment: QualityAssessment) -> str:
        """生成评估摘要"""
        status = "优秀" if quality_assessment.overall_score >= 0.9 else \
                 "良好" if quality_assessment.overall_score >= 0.8 else \
                 "一般" if quality_assessment.overall_score >= 0.6 else "需改进"
        
        summary = f"""
质量评估摘要
===========
总体评分: {quality_assessment.overall_score:.2f} ({status})
评估维度: 准确性({quality_assessment.accuracy_score:.2f}) 完整性({quality_assessment.completeness_score:.2f}) 
          逻辑性({quality_assessment.logical_score:.2f}) 可读性({quality_assessment.readability_score:.2f}) 
          相关性({quality_assessment.relevance_score:.2f})
"""
        
        return summary
    
    def _generate_recommendation(self, quality_assessment: QualityAssessment) -> str:
        """生成改进建议"""
        if quality_assessment.overall_score >= self.quality_threshold:
            return "质量评估通过，可以继续生成最终报告。"
        else:
            return "质量评估未通过，建议根据改进建议重新执行相关步骤。"
    
    def validate_assessment(self, quality_assessment: QualityAssessment) -> bool:
        """验证评估结果的有效性"""
        # 检查评分范围
        scores = [
            quality_assessment.overall_score,
            quality_assessment.accuracy_score,
            quality_assessment.completeness_score,
            quality_assessment.logical_score,
            quality_assessment.readability_score,
            quality_assessment.relevance_score
        ]
        
        for score in scores:
            if not (0.0 <= score <= 1.0):
                logger.warning(f"评分超出范围: {score}", agent_name="ReflectAgent")
                return False
        
        # 检查必要字段
        if not quality_assessment.strengths and not quality_assessment.weaknesses:
            logger.warning("评估结果缺少分析内容", agent_name="ReflectAgent")
            return False
        
        return True
    
    def get_quality_threshold(self) -> float:
        """获取质量阈值"""
        return self.quality_threshold
    
    def set_quality_threshold(self, threshold: float) -> None:
        """设置质量阈值"""
        if 0.0 <= threshold <= 1.0:
            self.quality_threshold = threshold
            logger.info(f"质量阈值已更新为: {threshold}", agent_name="ReflectAgent")
        else:
            raise ValueError("质量阈值必须在0.0到1.0之间")
