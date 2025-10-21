"""
基于LLM的任务意图分析器
使用模型理解用户的真实意图，而不是简单的正则匹配
"""

import json
import logging
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum
from dataclasses import dataclass
from ..utils.llm_config import get_llm

logger = logging.getLogger(__name__)


class TaskIntent(Enum):
    """任务意图枚举"""
    # 报告生成
    GENERATE_NEW_REPORT = "generate_new_report"  # 生成全新报告
    
    # 页面级操作
    OPTIMIZE_SINGLE_PAGE = "optimize_single_page"  # 优化单个页面
    REGENERATE_SINGLE_PAGE = "regenerate_single_page"  # 重新生成单个页面
    
    # 批量优化
    OPTIMIZE_MULTIPLE_PAGES = "optimize_multiple_pages"  # 优化多个页面
    OPTIMIZE_ENTIRE_REPORT = "optimize_entire_report"  # 优化整份报告
    
    # 内容修改
    UPDATE_CONTENT = "update_content"  # 更新内容
    ADD_NEW_SECTION = "add_new_section"  # 添加新章节
    REMOVE_SECTION = "remove_section"  # 删除章节
    
    # 格式调整
    ADJUST_FORMAT = "adjust_format"  # 调整格式
    CHANGE_STYLE = "change_style"  # 改变风格
    
    # 文件操作
    EXTRACT_FILE_CONTENT = "extract_file_content"  # 提取文件内容
    CONVERT_FILE_FORMAT = "convert_file_format"  # 转换文件格式
    
    # 查询类
    QUERY_INFORMATION = "query_information"  # 查询信息
    CHECK_STATUS = "check_status"  # 检查状态
    
    # 其他
    UNCLEAR = "unclear"  # 意图不明确


@dataclass
class IntentAnalysisResult:
    """意图分析结果"""
    intent: TaskIntent
    confidence: float  # 置信度 0-1
    target_pages: List[int] = None  # 目标页面列表
    specific_requirements: Dict[str, Any] = None  # 具体要求
    reasoning: str = ""  # 分析理由
    suggested_workflow: str = ""  # 建议的工作流


class TaskIntentAnalyzer:
    """任务意图分析器"""
    
    def __init__(self):
        self.llm = get_llm()
    
    def analyze_intent(self, 
                       task_description: str, 
                       context: Optional[Dict[str, Any]] = None) -> IntentAnalysisResult:
        """分析任务意图
        
        Args:
            task_description: 任务描述
            context: 上下文信息（如已有报告、历史对话等）
            
        Returns:
            意图分析结果
        """
        # 构建分析prompt
        prompt = self._build_analysis_prompt(task_description, context)
        
        try:
            # 调用LLM进行分析
            response = self.llm.invoke(prompt)
            
            # 解析响应
            result = self._parse_llm_response(response.content)
            
            logger.info(f"任务意图分析完成: {result.intent.value} (置信度: {result.confidence})")
            
            return result
            
        except Exception as e:
            logger.error(f"任务意图分析失败: {str(e)}")
            # 返回默认结果
            return IntentAnalysisResult(
                intent=TaskIntent.UNCLEAR,
                confidence=0.0,
                reasoning=f"分析失败: {str(e)}"
            )
    
    def _build_analysis_prompt(self, task_description: str, context: Optional[Dict[str, Any]]) -> str:
        """构建分析prompt
        
        Args:
            task_description: 任务描述
            context: 上下文信息
            
        Returns:
            prompt字符串
        """
        prompt = f"""你是一个任务意图分析专家。请分析用户的任务描述，理解其真实意图。

任务描述: {task_description}

上下文信息:
- 是否有已生成的报告: {context.get('has_existing_report', False) if context else False}
- 是否有上传的文件: {context.get('has_files', False) if context else False}
- 上一个任务: {context.get('previous_task', '无') if context else '无'}

请分析这个任务的意图，并返回JSON格式的结果：

```json
{{
    "intent": "选择最匹配的意图类型",
    "confidence": 0.95,  // 置信度(0-1)
    "target_pages": [1, 2, 3],  // 如果涉及特定页面，列出页码
    "specific_requirements": {{
        "style": "professional",  // 风格要求
        "focus": "data analysis",  // 重点内容
        "modifications": ["添加图表", "增加案例"]  // 具体修改
    }},
    "reasoning": "分析理由说明",
    "suggested_workflow": "建议的工作流类型"
}}
```

意图类型说明:
- generate_new_report: 生成全新的报告
- optimize_single_page: 优化单个页面的内容（如"优化第3页"）
- regenerate_single_page: 完全重新生成某个页面（如"重做第5页"）
- optimize_multiple_pages: 优化多个页面（如"优化第2-5页"）
- optimize_entire_report: 优化整份报告
- update_content: 更新特定内容（如"更新数据"）
- add_new_section: 添加新章节
- remove_section: 删除章节
- adjust_format: 调整格式
- change_style: 改变风格（如"改为学术风格"）
- extract_file_content: 提取文件内容
- convert_file_format: 转换文件格式
- query_information: 查询信息
- check_status: 检查状态
- unclear: 意图不明确

关键判断点:
1. 如果提到"第X页"且包含"优化/改进/调整"等词，应该是optimize_single_page
2. 如果提到"第X页"且包含"重新生成/重做/重写"等词，应该是regenerate_single_page  
3. 如果说"生成报告"且没有已存在的报告，应该是generate_new_report
4. 如果说"优化报告"且有已存在的报告，应该是optimize_entire_report
5. 仔细识别页码，如"第3页"、"第三页"、"P3"、"页面3"等都指向页码3

请仔细分析并返回准确的意图。"""
        
        return prompt
    
    def _parse_llm_response(self, response_text: str) -> IntentAnalysisResult:
        """解析LLM响应
        
        Args:
            response_text: LLM的响应文本
            
        Returns:
            意图分析结果
        """
        try:
            # 提取JSON部分
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试直接解析整个响应
                json_str = response_text
            
            # 解析JSON
            data = json.loads(json_str)
            
            # 映射intent字符串到枚举
            intent_str = data.get('intent', 'unclear')
            try:
                intent = TaskIntent(intent_str)
            except ValueError:
                # 如果值不在枚举中，尝试匹配
                intent = self._match_intent_string(intent_str)
            
            return IntentAnalysisResult(
                intent=intent,
                confidence=float(data.get('confidence', 0.5)),
                target_pages=data.get('target_pages'),
                specific_requirements=data.get('specific_requirements'),
                reasoning=data.get('reasoning', ''),
                suggested_workflow=data.get('suggested_workflow', '')
            )
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {str(e)}")
            # 返回默认结果
            return IntentAnalysisResult(
                intent=TaskIntent.UNCLEAR,
                confidence=0.0,
                reasoning=f"解析失败: {str(e)}"
            )
    
    def _match_intent_string(self, intent_str: str) -> TaskIntent:
        """匹配意图字符串到枚举值
        
        Args:
            intent_str: 意图字符串
            
        Returns:
            匹配的TaskIntent枚举值
        """
        intent_str_lower = intent_str.lower().replace(' ', '_')
        
        for intent in TaskIntent:
            if intent.value == intent_str_lower:
                return intent
        
        # 尝试部分匹配
        if 'optimize' in intent_str_lower and 'single' in intent_str_lower:
            return TaskIntent.OPTIMIZE_SINGLE_PAGE
        elif 'regenerate' in intent_str_lower:
            return TaskIntent.REGENERATE_SINGLE_PAGE
        elif 'generate' in intent_str_lower:
            return TaskIntent.GENERATE_NEW_REPORT
        elif 'optimize' in intent_str_lower:
            return TaskIntent.OPTIMIZE_ENTIRE_REPORT
        
        return TaskIntent.UNCLEAR
    
    def get_workflow_recommendation(self, intent: TaskIntent) -> Dict[str, Any]:
        """根据意图获取工作流建议
        
        Args:
            intent: 任务意图
            
        Returns:
            工作流配置建议
        """
        workflow_mapping = {
            TaskIntent.GENERATE_NEW_REPORT: {
                "workflow": "full_workflow",
                "agents": ["plan", "react", "reflect", "report"],
                "tools": ["web_search", "content_generator", "report_generator"]
            },
            
            TaskIntent.OPTIMIZE_SINGLE_PAGE: {
                "workflow": "page_optimization",
                "agents": ["react"],
                "tools": ["create_slide"],
                "skip_steps": ["plan", "reflect", "report_integration"]
            },
            
            TaskIntent.REGENERATE_SINGLE_PAGE: {
                "workflow": "page_regeneration",
                "agents": ["react"],
                "tools": ["create_slide"],
                "skip_steps": ["plan", "reflect", "report_integration"],
                "regenerate_mode": True
            },
            
            TaskIntent.OPTIMIZE_MULTIPLE_PAGES: {
                "workflow": "batch_optimization",
                "agents": ["react", "report"],
                "tools": ["create_slide", "report_generator"],
                "skip_steps": ["plan", "reflect"]
            },
            
            TaskIntent.OPTIMIZE_ENTIRE_REPORT: {
                "workflow": "report_optimization",
                "agents": ["reflect", "report"],
                "tools": ["content_generator", "report_generator"],
                "skip_steps": ["plan"]
            },
            
            TaskIntent.UPDATE_CONTENT: {
                "workflow": "content_update",
                "agents": ["react"],
                "tools": ["content_generator"],
                "skip_steps": ["plan", "reflect", "report"]
            },
            
            TaskIntent.QUERY_INFORMATION: {
                "workflow": "query",
                "agents": ["react"],
                "tools": ["web_search"],
                "skip_steps": ["plan", "reflect", "report"]
            },
            
            TaskIntent.CHECK_STATUS: {
                "workflow": "status",
                "agents": ["memory"],
                "tools": [],
                "skip_steps": ["plan", "react", "reflect", "report"]
            }
        }
        
        return workflow_mapping.get(intent, {
            "workflow": "full_workflow",
            "agents": ["plan", "react", "reflect", "report"],
            "tools": []
        })


# 全局分析器实例
_analyzer = None

def get_intent_analyzer() -> TaskIntentAnalyzer:
    """获取全局意图分析器实例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = TaskIntentAnalyzer()
    return _analyzer

def analyze_task_intent(task: str, context: Optional[Dict[str, Any]] = None) -> IntentAnalysisResult:
    """便捷函数：分析任务意图"""
    return get_intent_analyzer().analyze_intent(task, context)