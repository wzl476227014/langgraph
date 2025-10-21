"""
Plan Agent模块
负责分析用户需求并制定报告生成计划
"""

import json
import uuid
from typing import Dict, Any, List
from ..utils.config import get_agent_config, get_agent_prompt
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response, generate_system_response_stream
from ..utils.stream_output import AgentStreamOutput
from ..utils.task_analyzer import analyze_and_get_requirements
from typing import Iterator
from ..graph.state import ExecutionStep, create_execution_step

logger = get_logger(__name__)


class PlanAgent:
    """Plan Agent - 规划专家"""
    
    def __init__(self):
        """初始化Plan Agent"""
        self.config = get_agent_config("plan")
        self.system_prompt = get_agent_prompt("plan_agent")
        self.max_planning_steps = self.config.get("max_planning_steps", 10)
        
        # 初始化流式输出
        self.stream_output = AgentStreamOutput("PlanAgent", enable_stream=True)
        
        logger.info("Plan Agent初始化完成", agent_name="PlanAgent")
    
    def execute(self, state) -> Dict[str, Any]:
        """
        执行计划制定任务
        
        Args:
            state: 工作流状态
            
        Returns:
            执行结果字典
        """
        task_description = f"为用户请求制定报告生成计划: {state.user_request}"
        log_agent_start("PlanAgent", task_description)
        
        try:
            # 分析任务类型并获取输出要求
            task_analysis = analyze_and_get_requirements(state.user_request)
            requirements = task_analysis["requirements"]
            style_guide = task_analysis["style_guide"]
            
            # 保存任务要求到状态中供后续Agent使用
            state.task_requirements = requirements
            state.task_style_guide = style_guide
            
            logger.info(f"识别任务类型: {requirements['task_type']} (置信度: {requirements['confidence']:.2f})", agent_name="PlanAgent")
            
            # 构建用户输入（包含动态生成的要求）
            user_input = self._build_user_input_with_requirements(state, task_analysis)
            
            # 显示思考状态
            self.stream_output.print_thinking("正在制定报告生成计划")
            
            # 生成计划（使用流式输出）
            logger.info("开始生成计划（流式输出）...", agent_name="PlanAgent")
            log_agent_start("PlanAgent", user_input)
            # 获取流式响应迭代器
            stream_iterator = generate_system_response_stream(
                self.system_prompt,
                user_input,
                temperature=0.3  # 降低温度以获得更稳定的输出
            )
            
            # 使用流式输出显示
            plan_response = self.stream_output.stream_output(
                stream_iterator,
                task_type="制定计划"
            )
            
            logger.info("计划生成完成，开始解析...", agent_name="PlanAgent")
            
            # 解析计划响应
            print(f"DEBUG: PlanAgent生成的原始响应: {plan_response[:1000]}...")
            plan_data = self._parse_plan_response(plan_response)
            print(f"DEBUG: 解析后的计划数据: {plan_data}")
            print(f"DEBUG: 计划中的章节数量: {len(plan_data.get('sections', []))}")
            
            # 创建执行步骤
            execution_steps = self._create_execution_steps(plan_data, state)
            
            # 构建结果
            result = {
                "plan": plan_data,
                "execution_steps": execution_steps,
                "plan_summary": self._generate_plan_summary(plan_data),
                "total_steps": len(execution_steps)
            }
            
            logger.info(f"计划制定完成，共生成 {len(execution_steps)} 个执行步骤", agent_name="PlanAgent")
            log_agent_complete("PlanAgent", task_description, f"生成 {len(execution_steps)} 个步骤")
            
            return result
            
        except Exception as e:
            error_msg = f"计划制定失败: {str(e)}"
            logger.error(error_msg, agent_name="PlanAgent")
            raise Exception(error_msg)
    
    def _build_user_input_with_requirements(self, state, task_analysis) -> str:
        """构建包含动态要求的用户输入"""
        requirements = task_analysis["requirements"]
        style_guide = task_analysis["style_guide"]
        
        user_input = f"""
用户请求: {state.user_request}

用户约束条件:
"""
        
        if state.user_constraints:
            for constraint in state.user_constraints:
                user_input += f"- {constraint}\n"
        else:
            user_input += "- 无特殊约束\n"
        
        # 添加文件内容信息
        file_content = self._extract_file_content(state)
        if file_content:
            user_input += f"""
上传的文件内容概要:
{file_content[:2000]}...

请基于文件内容来制定报告大纲和执行计划。
"""
        
        # 添加任务类型特定的要求
        task_type = requirements["task_type"]
        confidence = requirements["confidence"]
        
#         user_input += f"""
# 任务类型识别: {self._get_task_type_name(task_type)} (置信度: {confidence:.2f})

# 特定内容要求:
# """
#         for req in requirements.get("content_requirements", []):
#             user_input += f"- {req}\n"
        
#         user_input += """
# 样式要求:
# """
#         for req in requirements.get("style_requirements", []):
#             user_input += f"- {req}\n"
        
#         # 添加建议的章节结构
#         if "structure" in requirements:
#             user_input += f"""
# 建议的章节结构: {', '.join(requirements["structure"])}
# """
        
        user_input += """
任务要求:
1. 制定详细的报告大纲，分解为独立的章节
2. 每个章节有明确的主题和内容要求
3. 确保章节间有逻辑关系
4. **重要**：封面页和目录页必须作为独立的章节生成，不要合并为"封面与目录"

请生成JSON格式计划:
{
    "report_title": "报告标题",
    "report_objective": "报告目标", 
    "sections": [
        {
            "section_id": "section_1", 
            "title": "章节标题",
            "description": "章节具体内容要求",
            "key_points": ["要点1", "要点2"],
            "estimated_pages": 1
        }
    ],
    "total_sections": 数字,
    "execution_sequence": ["section_1", "section_2", "..."]
}

注意：不要创建"封面与目录"或"封面和目录"这样的合并章节。如果需要封面和目录，请分别创建独立的"封面页"和"目录"章节。
"""
        
        return user_input
    
    def _get_task_type_name(self, task_type: str) -> str:
        """获取任务类型的中文名称"""
        type_names = {
            "technical_report": "技术报告",
            "business_report": "商业报告", 
            "research_paper": "研究论文",
            "security_assessment": "安全评估报告",
            "data_analysis": "数据分析报告",
            "project_documentation": "项目文档",
            "user_manual": "用户手册",
            "summary_report": "总结报告",
            "general": "通用报告"
        }
        return type_names.get(task_type, "专业报告")

    def _build_user_input(self, state) -> str:
        """构建用户输入"""
        user_input = f"""
用户请求: {state.user_request}

用户约束条件:
"""
        
        if state.user_constraints:
            for constraint in state.user_constraints:
                user_input += f"- {constraint}\n"
        else:
            user_input += "- 无特殊约束\n"
        
        # 添加文件内容信息
        file_content = self._extract_file_content(state)
        if file_content:
            user_input += f"""
上传的文件内容概要:
{file_content[:2000]}...

请基于文件内容来制定报告大纲和执行计划。
"""
        
        user_input += """
任务要求:
1. 请制定一个详细的报告生成大纲
2. 将报告分解为多个独立的章节/页面
3. 每个章节应该有明确的主题和内容要求
4. 确保章节之间有逻辑关系
5. 考虑到每个章节将单独生成并需要人工确认

请生成一个包含以下结构的JSON格式计划:
{
    "report_title": "报告标题",
    "report_objective": "报告目标",
    "sections": [
        {
            "section_id": "section_1",
            "title": "章节标题",
            "description": "章节描述和内容要求",
            "key_points": ["要点1", "要点2"],
            "estimated_pages": 1
        }
    ],
    "total_sections": 数字,
    "execution_sequence": ["section_1", "section_2", "..."]
}

注意: 每个章节都应该是独立的，能够单独生成和确认。
"""
        
        return user_input
    
    def _parse_plan_response(self, response: str) -> Dict[str, Any]:
        """解析计划响应"""
        try:
            # 清理响应文本
            cleaned_response = response.strip()
            
            # 尝试直接解析JSON
            plan_data = json.loads(cleaned_response)
            
            # 确保包含必要的标准页面
            plan_data = self._ensure_standard_sections(plan_data)
            
            return plan_data
            
        except json.JSONDecodeError as e:
            # 如果直接解析失败，尝试提取JSON部分
            try:
                # 查找JSON开始和结束位置
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = response[start_idx:end_idx]
                    
                    # 清理常见的JSON格式问题
                    # 1. 移除注释
                    import re
                    json_str = re.sub(r'//.*?\n', '\n', json_str)  # 移除单行注释
                    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)  # 移除多行注释
                    
                    # 2. 修复尾部逗号
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                    
                    # 3. 处理字符串值中的单引号问题
                    # 不要替换JSON字符串内的单引号，而是转义它们
                    # 先找到所有字符串字段值中的单引号并转义
                    def escape_single_quotes_in_strings(match):
                        key = match.group(1)
                        value = match.group(2)
                        # 将字符串值内的单引号替换为转义的双引号
                        escaped_value = value.replace("'", '\\"')
                        return f'"{key}": "{escaped_value}"'
                    
                    # 匹配 "key": "value containing 'single quotes'" 的模式
                    json_str = re.sub(r'"([\w_]+)"\s*:\s*"([^"]*\'[^"]*)"', escape_single_quotes_in_strings, json_str)
                    
                    # 4. 处理数字类型（移除 "数字" 这样的字符串）
                    json_str = re.sub(r'"数字"', '0', json_str)
                    json_str = re.sub(r'"(total_sections|estimated_pages)":\s*"(\d+)"', r'"\1": \2', json_str)
                    
                    # 尝试解析清理后的JSON
                    plan_data = json.loads(json_str)
                    
                    # 确保包含必要的标准页面
                    plan_data = self._ensure_standard_sections(plan_data)
                    
                    # 验证必要字段
                    if "sections" not in plan_data and "main_sections" in plan_data:
                        # 转换旧格式
                        sections = []
                        for idx, section in enumerate(plan_data["main_sections"]):
                            if isinstance(section, str):
                                sections.append({
                                    "section_id": f"section_{idx + 1}",
                                    "title": section,
                                    "description": f"生成{section}的详细内容",
                                    "key_points": [],
                                    "estimated_pages": 1
                                })
                            else:
                                sections.append(section)
                        plan_data["sections"] = sections
                    
                    return plan_data
                else:
                    raise ValueError("响应中未找到有效的JSON格式")
                    
            except Exception as e:
                logger.warning(f"JSON解析失败，尝试文本解析: {str(e)}", agent_name="PlanAgent")
                # 如果JSON解析完全失败，使用文本解析作为备选
                return self._parse_text_response(response)
    
    def _ensure_standard_sections(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """确保计划包含必要的标准页面"""
        sections = plan_data.get("sections", [])
        
        # 检查是否已有封面页（排除组合页面）
        has_cover = any(
            ("封面" in section.get("title", "").lower() or "cover" in section.get("title", "").lower()) and
            "目录" not in section.get("title", "").lower()  # 排除封面与目录的组合页
            for section in sections
        )
        
        # 检查是否已有目录页（独立的）
        has_separate_toc = any(
            ("目录" in section.get("title", "").lower() or "toc" in section.get("title", "").lower()) and
            "封面" not in section.get("title", "").lower()  # 排除封面与目录的组合页
            for section in sections
        )
        
        # 如果没有封面，添加封面页
        if not has_cover:
            cover_section = {
                "section_id": "section_cover",
                "title": "封面页",
                "description": "报告封面，包含报告标题、客户信息、服务团队、报告日期等基本信息",
                "key_points": ["报告标题", "客户信息", "服务团队", "报告日期"],
                "estimated_pages": 1
            }
            sections.insert(0, cover_section)
        
        # 收集所有章节标题用于目录（无论是否已有目录页）
        chapter_titles = []
        for section in sections:
            title = section.get("title", "")
            # 跳过封面和目录本身
            if title and title not in ["封面页", "目录"]:
                chapter_titles.append(title)
        
        # 如果没有独立的目录页，添加目录页
        if not has_separate_toc and len(sections) > 2:  # 降低阈值，确保更多情况下生成独立目录页
            # 构建包含实际章节信息的描述
            toc_description = "报告目录页，包含以下章节：\n"
            for i, chapter in enumerate(chapter_titles, 1):
                toc_description += f"{i}. {chapter}\n"
            
            toc_section = {
                "section_id": "section_toc", 
                "title": "目录",
                "description": toc_description,
                "key_points": chapter_titles[:5],  # 取前5个章节作为要点
                "estimated_pages": 1,
                "metadata": {
                    "all_chapters": chapter_titles,
                    "is_toc": True
                }
            }
            # 插入到封面后面
            insert_index = 1 if has_cover or sections[0].get("title") == "封面页" else 0
            sections.insert(insert_index, toc_section)
        else:
            # 如果已有目录页，确保它包含正确的metadata
            for section in sections:
                title = section.get("title", "").lower()
                if ("目录" in title or "toc" in title) and "封面" not in title:
                    # 为现有的目录页添加元数据
                    if "metadata" not in section:
                        section["metadata"] = {}
                    section["metadata"]["all_chapters"] = chapter_titles
                    section["metadata"]["is_toc"] = True
                    logger.info(f"为现有目录页添加元数据: {len(chapter_titles)}个章节", agent_name="PlanAgent")
                    
                    # 更新描述包含实际章节
                    toc_description = "报告目录页，包含以下章节：\n"
                    for i, chapter in enumerate(chapter_titles, 1):
                        toc_description += f"{i}. {chapter}\n"
                    section["description"] = toc_description
                    section["key_points"] = chapter_titles[:5]
                    break
        
        # 重新编号section_id
        for i, section in enumerate(sections):
            if not section.get("section_id", "").startswith("section_"):
                section["section_id"] = f"section_{i + 1}"
        
        # 更新计划数据
        plan_data["sections"] = sections
        plan_data["total_sections"] = len(sections)
        plan_data["execution_sequence"] = [section["section_id"] for section in sections]
        
        return plan_data
    
    def _parse_text_response(self, response: str) -> Dict[str, Any]:
        """解析文本响应（备选方案）"""
        lines = response.split('\n')
        
        # 使用标准格式，确保兼容性
        plan_data = {
            "report_title": "专业分析报告",
            "report_objective": "提供全面的分析和建议",
            "sections": [],  # 使用 sections 而不是 main_sections
            "total_sections": 0,
            "execution_sequence": []
        }
        
        current_section = None
        section_counter = 1
        collected_sections = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 简单的文本解析逻辑
            if "标题" in line or "title" in line.lower():
                title_text = line.split(":", 1)[-1].strip() if ":" in line else "专业分析报告"
                plan_data["report_title"] = title_text if title_text else "专业分析报告"
            elif "目标" in line or "objective" in line.lower():
                obj_text = line.split(":", 1)[-1].strip() if ":" in line else "提供全面的分析和建议"
                plan_data["report_objective"] = obj_text if obj_text else "提供全面的分析和建议"
            elif "章节" in line or "section" in line.lower():
                current_section = "sections"
            elif current_section == "sections" and line.startswith(('-', '•', '*', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
                # 提取章节内容
                section_text = line.lstrip('-•*0123456789. ').strip()
                if section_text:
                    collected_sections.append(section_text)
        
        # 如果没有找到章节，创建默认章节
        if not collected_sections:
            collected_sections = [
                "执行摘要",
                "背景介绍",
                "现状分析",
                "问题识别",
                "解决方案",
                "实施建议",
                "总结与展望"
            ]
        
        # 将收集的章节转换为标准格式
        for idx, section_title in enumerate(collected_sections):
            section_id = f"section_{idx + 1}"
            plan_data["sections"].append({
                "section_id": section_id,
                "title": section_title,
                "description": f"生成{section_title}的详细内容",
                "key_points": [f"{section_title}的核心内容", "数据支撑", "案例分析"],
                "estimated_pages": 1
            })
            plan_data["execution_sequence"].append(section_id)
        
        plan_data["total_sections"] = len(plan_data["sections"])
        
        # 为了兼容性，也保留 main_sections
        plan_data["main_sections"] = collected_sections
        
        return plan_data
    
    def _clean_dependency_reference(self, dep_ref: Any) -> str:
        """
        清理和验证依赖引用
        
        Args:
            dep_ref: 原始依赖引用
            
        Returns:
            清理后的依赖引用，如果无效则返回空字符串
        """
        if not dep_ref:
            return ""
        
        # 转换为字符串
        dep_str = str(dep_ref).strip()
        
        # 如果是空字符串，直接返回
        if not dep_str:
            return ""
        
        # 如果已经是正确的格式，直接返回
        if dep_str.startswith("step_") and len(dep_str) == 8:
            # 验证格式是否正确 (step_XXX)
            try:
                num_part = dep_str[5:]
                if num_part.isdigit() and len(num_part) == 3:
                    return dep_str
            except:
                pass
        
        # 尝试从部分字符中提取数字
        # 处理像 "步", "骤", "step_1", "1" 等情况
        import re
        
        # 查找所有数字
        numbers = re.findall(r'\d+', dep_str)
        if numbers:
            # 使用找到的第一个数字
            num = int(numbers[0])
            if 1 <= num <= 999:  # 合理的步骤编号范围
                return f"step_{num:03d}"
        
        # 如果没有找到数字，尝试其他模式
        # 检查是否包含 "step" 但格式不正确
        if "step" in dep_str.lower():
            # 尝试提取数字部分
            match = re.search(r'step[_\s]*(\d+)', dep_str.lower())
            if match:
                num = int(match.group(1))
                if 1 <= num <= 999:
                    return f"step_{num:03d}"
        
        # 如果所有尝试都失败，记录警告并返回空字符串
        logger.warning(f"无法解析依赖引用: '{dep_ref}'，将忽略此依赖", agent_name="PlanAgent")
        return ""
    
    def _create_execution_steps(self, plan_data: Dict[str, Any], state=None) -> List[ExecutionStep]:
        """创建执行步骤 - 基于章节生成"""
        execution_steps = []
        
        # 从计划数据中提取章节信息
        sections = plan_data.get("sections", [])
        
        if not sections:
            # 兼容旧格式
            main_sections = plan_data.get("main_sections", [])
            sections = [{"title": section, "description": f"生成{section}内容"} 
                       for section in main_sections]
        
        step_counter = 1
        
        for i, section in enumerate(sections):
            section_id = section.get("section_id", f"section_{i+1}")
            section_title = section.get("title", f"章节 {i+1}")
            section_description = section.get("description", f"生成{section_title}内容")
            key_points = section.get("key_points", [])
            
            step_id = f"step_{step_counter:03d}"
            
            # 构建详细的步骤描述（包含动态要求）
            # 从状态中获取任务分析结果
            task_requirements = getattr(state, 'task_requirements', {}) if state else {}
            
            full_description = f"""生成报告章节: {section_title}
            
章节要求:
{section_description}

关键要点:
{chr(10).join(['- ' + point for point in key_points]) if key_points else '- 无特定要点'}

输出要求:
- 生成完整的章节内容，内容应该专业、详细、有深度
- 确保内容与章节主题高度相关
"""
            
            # 添加任务类型特定的内容要求 (已注释掉，避免所有章节都有相同的通用要求)
#             if task_requirements.get("content_requirements"):
#                 for req in task_requirements["content_requirements"]:
#                     full_description += f"- {req}\n"
#             else:
#                 # 默认要求
#                 full_description += """- 生成完整的章节内容
# - 内容应该专业、详细、有深度
# """
            
            # 添加样式要求 (已注释掉)
#             full_description += "\n样式要求:\n"
#             if task_requirements.get("style_requirements"):
#                 for req in task_requirements["style_requirements"]:
#                     full_description += f"- {req}\n"
#             else:
#                 # 默认样式要求
#                 full_description += """- 格式应该清晰易读
# - 包含适当的标题、段落、列表等结构
# """
            
            # 依赖关系：每个步骤依赖前一个步骤
            dependencies = [f"step_{step_counter-1:03d}"] if step_counter > 1 else []
            
            step = create_execution_step(
                step_id=step_id,
                description=full_description,
                expected_output=f"完整的 '{section_title}' 章节内容（HTML格式）",
                required_tools=[],  # 不指定特定工具，让React Agent自由选择
                dependencies=dependencies
            )
            
            # 添加章节元数据
            step.metadata = {
                "section_id": section_id,
                "section_title": section_title,
                "section_type": section.get("type", "content"),
                "key_points": key_points,
                "estimated_pages": section.get("estimated_pages", 1)
            }
            
            # 如果章节有额外的元数据，合并到执行步骤中（如TOC页面的all_chapters）
            section_metadata = section.get("metadata", {})
            if section_metadata:
                step.metadata.update(section_metadata)
                logger.info(f"步骤 {step_id} 继承章节元数据: {list(section_metadata.keys())}", agent_name="PlanAgent")
            
            execution_steps.append(step)
            step_counter += 1
        
        return execution_steps
    
    def _generate_plan_summary(self, plan_data: Dict[str, Any]) -> str:
        """生成计划摘要"""
        summary = f"""
报告标题: {plan_data.get('report_title', '未指定')}
报告目标: {plan_data.get('report_objective', '未指定')}

主要章节:
"""
        
        for section in plan_data.get("main_sections", []):
            if isinstance(section, dict):
                # 新格式：包含multi_page信息
                section_title = section.get("title", "未命名章节")
                multi_page = section.get("multi_page", False)
                if multi_page:
                    page_count = section.get("page_count", 1)
                    summary += f"- {section_title} (多页: {page_count}页)\n"
                else:
                    summary += f"- {section_title} (单页)\n"
            else:
                # 旧格式：字符串
                summary += f"- {section}\n"
        
        summary += f"""
预估完成时间: {plan_data.get('estimated_duration', '未知')}

潜在风险:
"""
        
        for risk in plan_data.get("potential_risks", []):
            summary += f"- {risk}\n"
        
        summary += "\n缓解策略:\n"
        
        for strategy in plan_data.get("mitigation_strategies", []):
            summary += f"- {strategy}\n"
        
        return summary
    
    def validate_plan(self, plan_data: Dict[str, Any]) -> bool:
        """验证计划的有效性"""
        required_fields = ["report_title", "report_objective", "main_sections"]
        
        for field in required_fields:
            if not plan_data.get(field):
                logger.warning(f"计划缺少必要字段: {field}", agent_name="PlanAgent")
                return False
        
        main_sections = plan_data.get("main_sections", [])
        if not main_sections:
            logger.warning("计划没有主要章节", agent_name="PlanAgent")
            return False
        
        if len(main_sections) > self.max_planning_steps:
            logger.warning(f"章节数量超过限制: {len(main_sections)} > {self.max_planning_steps}", agent_name="PlanAgent")
            return False
        
        return True
    
    def refine_plan(self, plan_data: Dict[str, Any], feedback: str) -> Dict[str, Any]:
        """根据反馈优化计划"""
        refinement_prompt = f"""
基于以下反馈优化现有的报告生成计划:

原始计划:
{json.dumps(plan_data, ensure_ascii=False, indent=2)}

用户反馈:
{feedback}

请优化计划，保持JSON格式不变，仅修改需要调整的部分。
"""
        
        try:
            refined_response = generate_system_response(
                self.system_prompt,
                refinement_prompt,
                temperature=0.3
            )
            
            refined_plan = self._parse_plan_response(refined_response)
            return refined_plan
            
        except Exception as e:
            logger.error(f"计划优化失败: {str(e)}", agent_name="PlanAgent")
        return plan_data  # 返回原始计划
    
    def _extract_file_content(self, state) -> str:
        """
        从状态中提取文件内容
        
        Args:
            state: 工作流状态
            
        Returns:
            文件内容字符串
        """
        file_content = ""
        
        try:
            print(f"DEBUG PlanAgent: state attributes: {dir(state)}")
            print(f"DEBUG PlanAgent: hasattr file_processing_results: {hasattr(state, 'file_processing_results')}")
            if hasattr(state, 'file_processing_results'):
                print(f"DEBUG PlanAgent: file_processing_results: {state.file_processing_results}")
                print(f"DEBUG PlanAgent: file_processing_results type: {type(state.file_processing_results)}")
            
            # 检查状态中是否有文件处理结果
            if hasattr(state, 'file_processing_results') and state.file_processing_results:
                # file_processing_results 现在是字典格式 {file_id: result}
                for file_id, result in state.file_processing_results.items():
                    print(f"DEBUG PlanAgent: Processing file {file_id}: {result}")
                    
                    # 检查不同的数据结构
                    file_info = None
                    if result.get("success"):
                        file_info = result.get("result", {})
                    else:
                        # 直接从result中提取信息
                        file_info = result
                    
                    if file_info:
                        filename = file_info.get("filename", "未知文件")
                        file_type = file_info.get("file_type", filename.split('.')[-1].lower() if '.' in filename else "")
                        
                        file_content += f"\n=== 文件内容 (文件: {filename}) ===\n"
                        
                        # 提取文本内容 - 检查多个可能的字段
                        text_content = ""
                        if "text_content" in file_info:
                            text_content = file_info.get("text_content", "")
                        elif "content_summary" in file_info:
                            text_content = file_info.get("content_summary", "")
                        elif "full_content" in file_info:
                            text_content = file_info.get("full_content", "")
                        elif "content" in file_info:
                            text_content = file_info.get("content", "")
                        
                        if text_content:
                            file_content += text_content[:2000]  # 限制长度，避免过长
                            if len(text_content) > 2000:
                                file_content += "\n... (内容过长，已截断)"
                            file_content += "\n"
                        else:
                            file_content += "文件内容为空或无法提取\n"
                        
                        # 处理Excel文件的特殊情况
                        if file_type == "excel" and "sheets" in file_info:
                            sheets = file_info.get("sheets", {})
                            file_content += f"\n=== Excel文件内容 (文件ID: {file_id}) ===\n"
                            for sheet_name, sheet_data in sheets.items():
                                file_content += f"\n工作表: {sheet_name}\n"
                                if isinstance(sheet_data, dict) and "data" in sheet_data:
                                    # 显示前几行数据
                                    data = sheet_data["data"]
                                    if isinstance(data, list) and len(data) > 0:
                                        file_content += "数据预览:\n"
                                        for i, row in enumerate(data[:5]):  # 只显示前5行
                                            file_content += f"  行{i+1}: {row}\n"
                                        if len(data) > 5:
                                            file_content += f"  ... (共{len(data)}行)\n"
                                file_content += "\n"
            
            # 检查是否有用户输入的文件信息
            elif hasattr(state, 'user_files') and state.user_files:
                for file_info in state.user_files:
                    file_content += f"\n=== 用户文件信息 ===\n"
                    file_content += f"文件名: {file_info.get('file_name', '未知')}\n"
                    file_content += f"文件类型: {file_info.get('file_type', '未知')}\n"
                    
                    # 如果有文本内容，添加进去
                    if "text_content" in file_info:
                        text_content = file_info["text_content"]
                        if text_content:
                            file_content += f"文件内容:\n{text_content[:1000]}\n"
                            if len(text_content) > 1000:
                                file_content += "... (内容过长，已截断)\n"
                    file_content += "\n"
            
            # 如果没有找到文件内容，检查内存条目中是否有文件相关信息
            elif hasattr(state, 'memory_entries') and state.memory_entries:
                for entry in state.memory_entries:
                    if (entry.entry_type == "file_processing" or 
                        "file" in entry.content.lower() or 
                        "pdf" in entry.content.lower() or
                        "excel" in entry.content.lower()):
                        
                        file_content += f"\n=== 文件处理记录 ===\n"
                        file_content += f"处理时间: {entry.timestamp}\n"
                        file_content += f"处理内容: {entry.content[:1000]}\n"
                        if len(entry.content) > 1000:
                            file_content += "... (内容过长，已截断)\n"
                        file_content += "\n"
            
            if not file_content:
                file_content = "未找到上传的文件内容"
            
            return file_content
            
        except Exception as e:
            logger.error(f"提取文件内容失败: {str(e)}", agent_name="PlanAgent")
            return "提取文件内容时出错"
    
    def _is_ppt_format_request(self, user_request: str) -> bool:
        """
        检查用户请求是否为PPT格式
        
        Args:
            user_request: 用户请求字符串
            
        Returns:
            是否为PPT格式请求
        """
        ppt_keywords = ["ppt", "幻灯片", "slide", "演示文稿", "presentation"]
        request_lower = user_request.lower()
        
        return any(keyword in request_lower for keyword in ppt_keywords)
