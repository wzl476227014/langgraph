"""
内容生成器工具模块
提供智能内容生成功能
"""

import json
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from ..utils.config import get_config, get_agent_prompt
from ..utils.logger import get_logger
from ..utils.llm_config import generate_system_response

logger = get_logger(__name__)


class ContentGeneratorTool:
    """内容生成器工具"""
    
    def __init__(self):
        """初始化内容生成器工具"""
        self.config = get_config().get_tool_config("content_generator")
        self.enabled = self.config.get("enabled", True)
        self.max_content_length = self.config.get("max_content_length", 5000)
        self.system_prompt = get_agent_prompt("content_generator_tool")
        
        logger.info("内容生成器工具初始化完成", agent_name="ContentGeneratorTool")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行内容生成任务
        
        Args:
            input_data: 输入数据，包含生成任务和参数
            
        Returns:
            生成结果字典
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "内容生成器工具未启用",
                "content": None
            }
        
        task = input_data.get("task", "")
        content_type = input_data.get("content_type", "general")
        style = input_data.get("style", "formal")
        max_length = input_data.get("max_length", self.max_content_length)
        context = input_data.get("context", {})
        
        if not task:
            return {
                "success": False,
                "error": "生成任务不能为空",
                "content": None
            }
        
        try:
            logger.info(f"开始内容生成任务: {task}", agent_name="ContentGeneratorTool")
            
            # 根据内容类型选择生成方法
            if content_type == "report_section":
                result = self._generate_report_section(task, context, style, max_length)
            elif content_type == "summary":
                result = self._generate_summary(task, context, style, max_length)
            elif content_type == "analysis":
                result = self._generate_analysis(task, context, style, max_length)
            elif content_type == "recommendation":
                result = self._generate_recommendation(task, context, style, max_length)
            elif content_type == "introduction":
                result = self._generate_introduction(task, context, style, max_length)
            elif content_type == "conclusion":
                result = self._generate_conclusion(task, context, style, max_length)
            elif content_type == "ppt_slide":
                result = self._generate_ppt_slide(task, context, style, max_length)
            else:
                result = self._generate_general_content(task, context, style, max_length)
            
            generated_content = {
                "success": True,
                "task": task,
                "content_type": content_type,
                "style": style,
                "content": result,
                "generated_at": datetime.now().isoformat(),
                "metadata": {
                    "content_length": len(result),
                    "word_count": len(result.split()),
                    "paragraph_count": len([p for p in result.split('\n\n') if p.strip()]),
                    "max_length": max_length,
                    "generation_method": "ai_assisted"
                }
            }
            
            logger.info(f"内容生成任务完成: {task}", agent_name="ContentGeneratorTool")
            
            return generated_content
            
        except Exception as e:
            error_msg = f"内容生成失败: {str(e)}"
            logger.error(error_msg, agent_name="ContentGeneratorTool")
            
            return {
                "success": False,
                "error": error_msg,
                "task": task,
                "content": None
            }
    
    def _generate_report_section(self, task: str, context: Dict[str, Any], 
                               style: str, max_length: int) -> str:
        """生成报告章节"""
        # 构建输入提示
        prompt = self._build_report_section_prompt(task, context, style, max_length)
        
        # 生成内容
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        # 后处理内容
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _generate_summary(self, task: str, context: Dict[str, Any], 
                        style: str, max_length: int) -> str:
        """生成摘要"""
        prompt = self._build_summary_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.5
        )
        
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _generate_analysis(self, task: str, context: Dict[str, Any], 
                          style: str, max_length: int) -> str:
        """生成分析内容"""
        prompt = self._build_analysis_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.6
        )
        
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _generate_recommendation(self, task: str, context: Dict[str, Any], 
                               style: str, max_length: int) -> str:
        """生成建议内容"""
        prompt = self._build_recommendation_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _generate_introduction(self, task: str, context: Dict[str, Any], 
                             style: str, max_length: int) -> str:
        """生成引言内容"""
        prompt = self._build_introduction_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.8
        )
        
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _generate_conclusion(self, task: str, context: Dict[str, Any], 
                           style: str, max_length: int) -> str:
        """生成结论内容"""
        prompt = self._build_conclusion_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _generate_ppt_slide(self, task: str, context: Dict[str, Any], 
                           style: str, max_length: int) -> str:
        """生成PPT幻灯片内容"""
        prompt = self._build_ppt_slide_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _generate_general_content(self, task: str, context: Dict[str, Any], 
                                style: str, max_length: int) -> str:
        """生成通用内容"""
        prompt = self._build_general_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        
        return content
    
    def _build_report_section_prompt(self, task: str, context: Dict[str, Any], 
                                   style: str, max_length: int) -> str:
        """构建报告章节生成提示"""
        prompt = f"""
请为以下任务生成一个报告章节：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 内容应该结构清晰，逻辑性强
2. 使用{style}的写作风格
3. 包含适当的小标题和段落
4. 内容长度控制在{max_length}字符以内
5. 语言表达准确、专业

请直接生成报告章节内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_summary_prompt(self, task: str, context: Dict[str, Any], 
                            style: str, max_length: int) -> str:
        """构建摘要生成提示"""
        prompt = f"""
请为以下内容生成摘要：

主题：{task}

写作风格：{style}
最大长度：{max_length} 字符

原始内容：
"""
        
        # 添加原始内容
        if context.get("original_content"):
            prompt += f"\n{context['original_content']}"
        
        prompt += f"""
要求：
1. 摘要应该简洁明了，突出重点
2. 使用{style}的写作风格
3. 包含主要观点和关键信息
4. 内容长度控制在{max_length}字符以内
5. 保持客观性和准确性

请直接生成摘要内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_analysis_prompt(self, task: str, context: Dict[str, Any], 
                             style: str, max_length: int) -> str:
        """构建分析生成提示"""
        prompt = f"""
请对以下主题进行分析：

分析主题：{task}

写作风格：{style}
最大长度：{max_length} 字符

分析数据：
"""
        
        # 添加分析数据
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:300]}..."
        
        prompt += f"""
要求：
1. 分析应该深入、全面、客观
2. 使用{style}的写作风格
3. 包含数据支持和逻辑推理
4. 内容长度控制在{max_length}字符以内
5. 提供有价值的见解和结论

请直接生成分析内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_recommendation_prompt(self, task: str, context: Dict[str, Any], 
                                   style: str, max_length: int) -> str:
        """构建建议生成提示"""
        prompt = f"""
请为以下问题提供建议：

问题：{task}

写作风格：{style}
最大长度：{max_length} 字符

背景信息：
"""
        
        # 添加背景信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 建议应该具体、可行、实用
2. 使用{style}的写作风格
3. 提供清晰的步骤和理由
4. 内容长度控制在{max_length}字符以内
5. 考虑不同情况和可能性

请直接生成建议内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_introduction_prompt(self, task: str, context: Dict[str, Any], 
                                 style: str, max_length: int) -> str:
        """构建引言生成提示"""
        prompt = f"""
请为以下主题生成引言：

主题：{task}

写作风格：{style}
最大长度：{max_length} 字符

相关信息：
"""
        
        # 添加相关信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 引言应该吸引读者，明确主题
2. 使用{style}的写作风格
3. 包含背景介绍和目的说明
4. 内容长度控制在{max_length}字符以内
5. 为后续内容做好铺垫

请直接生成引言内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_conclusion_prompt(self, task: str, context: Dict[str, Any], 
                               style: str, max_length: int) -> str:
        """构建结论生成提示"""
        prompt = f"""
请为以下主题生成结论：

主题：{task}

写作风格：{style}
最大长度：{max_length} 字符

前文内容：
"""
        
        # 添加前文内容
        if context.get("previous_content"):
            prompt += f"\n{context['previous_content'][:500]}..."
        
        prompt += f"""
要求：
1. 结论应该总结要点，强调价值
2. 使用{style}的写作风格
3. 包含主要发现和最终观点
4. 内容长度控制在{max_length}字符以内
5. 给读者留下深刻印象

请直接生成结论内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_ppt_slide_prompt(self, task: str, context: Dict[str, Any], 
                              style: str, max_length: int) -> str:
        """构建PPT幻灯片生成提示"""
        prompt = f"""
请为以下任务生成HTML样式的PPT幻灯片内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 生成适合HTML幻灯片展示的内容
2. 使用{style}的写作风格
3. 内容应该简洁明了，重点突出
4. 包含适当的标题和要点
5. 内容长度控制在{max_length}字符以内
6. 适合在单个幻灯片页面展示

请直接生成幻灯片内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_general_prompt(self, task: str, context: Dict[str, Any], 
                            style: str, max_length: int) -> str:
        """构建通用内容生成提示"""
        prompt = f"""
请为以下任务生成内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 内容应该符合任务要求，质量高
2. 使用{style}的写作风格
3. 结构清晰，表达流畅
4. 内容长度控制在{max_length}字符以内
5. 语言准确，逻辑合理

请直接生成内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _post_process_content(self, content: str, style: str, max_length: int) -> str:
        """后处理生成的内容"""
        # 清理内容
        content = content.strip()
        
        # 移除可能的格式标记
        content = re.sub(r'^```[\w\s]*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'\n```$', '', content)
        
        # 根据风格调整内容
        content = self._adjust_content_by_style(content, style)
        
        # 确保长度限制
        if len(content) > max_length:
            content = self._truncate_content(content, max_length)
        
        # 确保内容完整性
        content = self._ensure_content_completeness(content)
        
        return content
    
    def _adjust_content_by_style(self, content: str, style: str) -> str:
        """根据风格调整内容"""
        if style == "formal":
            # 正式风格：使用更正式的表达
            content = re.sub(r'\b我觉得\b', '笔者认为', content)
            content = re.sub(r'\b可能\b', '或许', content)
            content = re.sub(r'\b很\b', '非常', content)
        elif style == "casual":
            # 随意风格：使用更轻松的表达
            content = re.sub(r'\b笔者认为\b', '我觉得', content)
            content = re.sub(r'\b或许\b', '可能', content)
            content = re.sub(r'\b非常\b', '很', content)
        elif style == "academic":
            # 学术风格：使用更专业的表达
            content = re.sub(r'\b我觉得\b', '研究表明', content)
            content = re.sub(r'\b可能\b', '有可能', content)
            content = re.sub(r'\b很\b', '相当', content)
        
        return content
    
    def _truncate_content(self, content: str, max_length: int) -> str:
        """截断内容"""
        if len(content) <= max_length:
            return content
        
        # 尝试在句子边界截断
        sentences = re.split(r'[。！？.!?]', content)
        truncated = ""
        
        for sentence in sentences:
            if len(truncated + sentence + "。") <= max_length:
                truncated += sentence + "。"
            else:
                break
        
        # 如果还是太长，在单词边界截断
        if len(truncated) > max_length:
            words = truncated.split()
            truncated = ""
            
            for word in words:
                if len(truncated + word + " ") <= max_length:
                    truncated += word + " "
                else:
                    break
        
        # 添加省略号
        if truncated and len(truncated) < len(content):
            truncated += "..."
        
        return truncated.strip()
    
    def _ensure_content_completeness(self, content: str) -> str:
        """确保内容完整性"""
        if not content:
            return "内容生成失败，请重试。"
        
        # 确保以适当的标点符号结束
        if not content[-1] in ['。', '！', '？', '.', '!', '?']:
            content += '。'
        
        return content
    
    def generate_content_variations(self, task: str, content_type: str, 
                                 variations: int = 3) -> List[Dict[str, Any]]:
        """生成内容变体"""
        if variations < 1:
            return []
        
        results = []
        
        for i in range(variations):
            # 使用不同的温度参数生成变体
            temperature = 0.5 + (i * 0.2)  # 0.5, 0.7, 0.9
            
            input_data = {
                "task": task,
                "content_type": content_type,
                "style": "formal",
                "max_length": self.max_content_length,
                "context": {}
            }
            
            try:
                result = self.execute(input_data)
                if result["success"]:
                    results.append({
                        "variation_id": i + 1,
                        "content": result["content"],
                        "temperature": temperature,
                        "metadata": result["metadata"]
                    })
            except Exception as e:
                logger.warning(f"生成变体 {i + 1} 失败: {str(e)}", agent_name="ContentGeneratorTool")
        
        return results
    
    def improve_content(self, original_content: str, improvement_areas: List[str]) -> Dict[str, Any]:
        """改进内容"""
        if not original_content or not improvement_areas:
            return {
                "success": False,
                "error": "原始内容和改进区域不能为空",
                "improved_content": None
            }
        
        try:
            prompt = f"""
请改进以下内容，重点关注以下方面：

改进重点：{', '.join(improvement_areas)}

原始内容：
{original_content}

要求：
1. 保持原意和核心信息
2. 针对指定方面进行改进
3. 提升内容质量和表达效果
4. 保持逻辑连贯性

请直接生成改进后的内容。
"""
            
            improved_content = generate_system_response(
                self.system_prompt,
                prompt,
                temperature=0.6
            )
            
            return {
                "success": True,
                "improvement_areas": improvement_areas,
                "original_content": original_content,
                "improved_content": improved_content,
                "improvement_summary": self._generate_improvement_summary(original_content, improved_content)
            }
            
        except Exception as e:
            error_msg = f"内容改进失败: {str(e)}"
            logger.error(error_msg, agent_name="ContentGeneratorTool")
            
            return {
                "success": False,
                "error": error_msg,
                "improved_content": None
            }
    
    def _generate_improvement_summary(self, original: str, improved: str) -> str:
        """生成改进摘要"""
        original_length = len(original)
        improved_length = len(improved)
        length_change = improved_length - original_length
        
        summary = f"内容改进摘要：\n"
        summary += f"- 原始长度：{original_length} 字符\n"
        summary += f"- 改进后长度：{improved_length} 字符\n"
        summary += f"- 长度变化：{length_change:+d} 字符\n"
        
        # 简单的变化分析
        if length_change > 0:
            summary += "- 内容有所扩展\n"
        elif length_change < 0:
            summary += "- 内容有所精简\n"
        else:
            summary += "- 内容长度保持不变\n"
        
        return summary
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "ContentGeneratorTool",
            "description": "内容生成器工具，提供智能内容生成功能",
            "version": "1.0.0",
            "enabled": self.enabled,
            "max_content_length": self.max_content_length,
            "supported_types": [
                "report_section", "summary", "analysis", "recommendation", 
                "introduction", "conclusion", "ppt_slide", "general"
            ],
            "supported_styles": ["formal", "casual", "academic", "business"],
            "capabilities": [
                "智能内容生成",
                "多种内容类型支持",
                "风格自适应",
                "内容长度控制",
                "内容变体生成",
                "内容质量改进",
                "上下文感知生成",
                "PPT幻灯片生成"
            ]
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        if not isinstance(input_data, dict):
            return False
        
        task = input_data.get("task", "")
        content_type = input_data.get("content_type", "")
        style = input_data.get("style", "")
        max_length = input_data.get("max_length", 0)
        
        if not task or not isinstance(task, str):
            return False
        
        if not isinstance(content_type, str):
            return False
        
        if not isinstance(style, str):
            return False
        
        if not isinstance(max_length, int) or max_length <= 0:
            return False
        
        return True
    
    def enable_tool(self) -> None:
        """启用工具"""
        self.enabled = True
        logger.info("内容生成器工具已启用", agent_name="ContentGeneratorTool")
    
    def disable_tool(self) -> None:
        """禁用工具"""
        self.enabled = False
        logger.info("内容生成器工具已禁用", agent_name="ContentGeneratorTool")
    
    def set_max_content_length(self, max_length: int) -> None:
        """设置最大内容长度"""
        if max_length > 0:
            self.max_content_length = max_length
            logger.info(f"最大内容长度已设置为: {max_length}", agent_name="ContentGeneratorTool")
        else:
            raise ValueError("最大内容长度必须大于0")
