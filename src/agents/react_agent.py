"""
React Agent模块
负责逐步执行计划中的每个步骤
"""

import json
import re
import time
from typing import Dict, Any, List, Optional
from ..utils.config import get_agent_config, get_agent_prompt
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response, generate_system_response_stream
from ..utils.stream_output import AgentStreamOutput
from typing import Iterator
from ..graph.state import AgentStatus

logger = get_logger(__name__)


class ReactAgent:
    """React Agent - 执行专家"""
    
    def __init__(self):
        """初始化React Agent"""
        self.config = get_agent_config("react")
        self.system_prompt = get_agent_prompt("react_agent")
        self.max_execution_attempts = self.config.get("max_execution_attempts", 3)
        
        # 初始化流式输出
        self.stream_output = AgentStreamOutput("ReactAgent", enable_stream=True)
        
        # 导入工具
        self.tools = self._load_tools()
        
        logger.info("React Agent初始化完成", agent_name="ReactAgent")
    
    def _load_tools(self) -> Dict[str, Any]:
        """加载可用工具"""
        tools = {}
        
        try:
            # 动态导入工具
            from ..tools.create_slide import CreateSlideTool
            
            tools["create_slide"] = CreateSlideTool()
            
            logger.info("幻灯片创建工具加载完成", agent_name="ReactAgent")
            
        except ImportError as e:
            logger.warning(f"幻灯片创建工具加载失败: {str(e)}", agent_name="ReactAgent")
        
        return tools
    
    def execute_step(self, state, step_id: str) -> Dict[str, Any]:
        """
        执行指定的步骤
        
        Args:
            state: 工作流状态
            step_id: 步骤ID
            
        Returns:
            执行结果字典
        """
        # 保存state以供其他方法使用
        self.state = state
        
        step = state.get_step_by_id(step_id)
        if not step:
            raise ValueError(f"未找到步骤: {step_id}")
        
        task_description = f"执行步骤: {step.description}"
        log_agent_start("ReactAgent", task_description)
        
        try:
            # 更新步骤状态
            state.update_step_status(step_id, AgentStatus.RUNNING)
            step.execution_attempts += 1
            
            # 检查依赖
            if not self._check_dependencies(state, step):
                raise ValueError(f"步骤 {step_id} 的依赖条件未满足")
            
            # 执行步骤
            result = self._execute_single_step(state, step)
            
            # 如果结果包含幻灯片内容，添加到状态中
            if result and ("slide_content" in result or "content" in result):
                # 确保slides_content字典存在
                if not hasattr(state, 'slides_content') or state.slides_content is None:
                    state.slides_content = {}
                
                # 获取当前步骤的索引（用作幻灯片索引）
                slide_index = self._get_slide_index_for_step(state, step_id)
                
                # 优先使用slide_content，如果没有则使用content
                # 确保slide_index是字符串，因为Pydantic需要Dict[str, str]
                slide_key = str(slide_index)
                content = ""
                if "slide_content" in result:
                    # 确保内容是字符串
                    content = str(result["slide_content"]) if result["slide_content"] is not None else ""
                    state.slides_content[slide_key] = content
                    logger.info(f"步骤 {step_id} 生成的幻灯片内容已添加到slides_content[{slide_key}] (来源: slide_content)", agent_name="ReactAgent")
                elif "content" in result:
                    # 确保内容是字符串
                    content = str(result["content"]) if result["content"] is not None else ""
                    state.slides_content[slide_key] = content
                    logger.info(f"步骤 {step_id} 生成的幻灯片内容已添加到slides_content[{slide_key}] (来源: content)", agent_name="ReactAgent")
                
                # 立即将新生成的幻灯片添加到队列中，实现实时流式传输
                if content:
                    try:
                        from ..utils.slide_queue import slide_queue, SlideEvent
                        slide_event = SlideEvent(
                            slide_index=str(slide_key),
                            slide_content=content,
                            slide_title=f'第{str(slide_key)}页',
                            total_slides=len(state.slides_content),
                            workflow_id=state.workflow_id
                        )
                        slide_queue.add_slide(state.workflow_id, slide_event)
                        print(f"DEBUG - ReactAgent: Added slide {slide_key} to queue for streaming")
                    except Exception as e:
                        logger.error(f"添加幻灯片到队列失败: {str(e)}", agent_name="ReactAgent")
                
                # 添加调试信息
                print(f"DEBUG - ReactAgent: Added slide content to slides_content[{slide_key}], current slides_content keys: {list(state.slides_content.keys())}")
                print(f"DEBUG - ReactAgent: Content length: {len(state.slides_content[slide_key]) if state.slides_content[slide_key] else 0}")
                print(f"DEBUG - ReactAgent: Content preview: {state.slides_content[slide_key][:100] if state.slides_content[slide_key] else 'None'}...")
            
            # 记录执行结果
            logger.info(f"步骤 {step_id} 执行成功", agent_name="ReactAgent")
            log_agent_complete("ReactAgent", task_description, f"成功完成")
            
            return result
            
        except Exception as e:
            error_msg = f"步骤 {step_id} 执行失败: {str(e)}"
            logger.error(error_msg, agent_name="ReactAgent")
            
            # 检查是否需要重试
            if step.execution_attempts < self.max_execution_attempts:
                logger.info(f"步骤 {step_id} 将进行重试 (尝试 {step.execution_attempts}/{self.max_execution_attempts})", agent_name="ReactAgent")
                state.update_step_status(step_id, AgentStatus.IDLE)
                raise Exception(f"步骤执行失败，将重试: {str(e)}")
            else:
                logger.error(f"步骤 {step_id} 达到最大重试次数", agent_name="ReactAgent")
                state.update_step_status(step_id, AgentStatus.FAILED)
                step.error_message = str(e)
                raise Exception(f"步骤执行失败，达到最大重试次数: {str(e)}")
    
    def _check_dependencies(self, state, step) -> bool:
        """检查步骤依赖"""
        if not step.dependencies:
            return True
        
        for dep_id in step.dependencies:
            dep_step = state.get_step_by_id(dep_id)
            if not dep_step or dep_step.status != AgentStatus.COMPLETED:
                logger.warning(f"步骤 {step.step_id} 的依赖 {dep_id} 未完成", agent_name="ReactAgent")
                return False
        
        return True
    
    def _execute_single_step(self, state, step) -> Dict[str, Any]:
        """执行单个步骤"""
        # 构建执行上下文
        context = self._build_execution_context(state, step)
        
        # 根据步骤需求选择执行策略
        if step.required_tools:
            # 使用工具执行
            result = self._execute_with_tools(context, step)
        else:
            # 使用LLM直接执行
            result = self._execute_with_llm(context, step)
        
        # 验证执行结果
        print(result)
        if not self._validate_execution_result(result, step):
            raise ValueError("执行结果验证失败")
        
        return result
    
    def _build_execution_context(self, state, step) -> Dict[str, Any]:
        """构建执行上下文"""
        context = {
            "step_id": step.step_id,
            "step_description": step.description,
            "expected_output": step.expected_output,
            "user_request": state.user_request,
            "user_constraints": state.user_constraints,
            "workflow_id": state.workflow_id,
            "previous_results": {},
            "memory_context": self._extract_memory_context(state),
            "file_content": self._extract_file_content(state)
        }
        
        # 获取依赖步骤的结果
        for dep_id in step.dependencies:
            dep_result = state.get_execution_result(dep_id)
            if dep_result:
                context["previous_results"][dep_id] = dep_result
        
        return context
    
    def _get_slide_index_for_step(self, state, step_id: str) -> int:
        """根据步骤ID获取幻灯片索引"""
        if hasattr(state, 'execution_plan') and state.execution_plan:
            for i, step in enumerate(state.execution_plan.steps, 1):
                if step.step_id == step_id:
                    return i
        
        # 如果无法从execution_plan获取索引，使用步骤ID中的数字
        import re
        match = re.search(r'section_(\d+)', step_id)
        if match:
            return int(match.group(1))
        
        # 默认返回当前slides_content的长度+1
        current_count = len(state.slides_content) if hasattr(state, 'slides_content') and state.slides_content else 0
        return current_count + 1
    
    def _extract_memory_context(self, state) -> Dict[str, Any]:
        """提取记忆上下文"""
        memory_context = {
            "plan_summary": state.plan.get("plan_summary", "") if state.plan else "",
            "context_summary": state.context_summary,
            "relevant_memories": []
        }
        
        # 获取相关的记忆条目
        for entry in state.memory_entries:
            if any(tag in ["execution", "result", "context"] for tag in entry.tags):
                memory_context["relevant_memories"].append({
                    "type": entry.entry_type,
                    "content": entry.content,
                    "importance": entry.importance
                })
        
        return memory_context
    
    def _execute_with_tools(self, context: Dict[str, Any], step) -> Dict[str, Any]:
        """使用工具执行步骤"""
        results = {}
        
        for tool_name in step.required_tools:
            if tool_name not in self.tools:
                logger.warning(f"工具 {tool_name} 不可用", agent_name="ReactAgent")
                continue
            
            tool = self.tools[tool_name]
            
            try:
                # 构建工具输入
                print(step)
                tool_input = self._build_tool_input(tool_name, context, step)
                
                # 执行工具
                logger.info(f"使用工具 {tool_name} 执行步骤 {step.step_id}", agent_name="ReactAgent")
                tool_result = tool.execute(tool_input)
                
                results[tool_name] = tool_result
                
            except Exception as e:
                logger.error(f"工具 {tool_name} 执行失败: {str(e)}", agent_name="ReactAgent")
                results[tool_name] = {"error": str(e)}
        
        # 如果使用了多个工具，需要整合结果
        if len(results) == 1:
            # 处理单个工具结果，确保包含content和confidence字段
            single_result = list(results.values())[0]
            if isinstance(single_result, dict):
                # 确保包含content字段
                if "content" not in single_result:
                    # 如果没有content字段，尝试从其他字段获取内容
                    if "slide_content" in single_result:
                        # create_slide工具的特殊处理
                        single_result["content"] = single_result["slide_content"]
                    elif "result" in single_result:
                        single_result["content"] = str(single_result["result"])
                    elif "data" in single_result:
                        single_result["content"] = str(single_result["data"])
                    elif "output" in single_result:
                        single_result["content"] = str(single_result["output"])
                    elif "error" in single_result:
                        single_result["content"] = f"工具执行错误: {single_result['error']}"
                    else:
                        single_result["content"] = str(single_result)
                
                # 确保包含confidence字段
                if "confidence" not in single_result:
                    single_result["confidence"] = 0.8  # 工具结果的默认置信度
                
                # 添加章节标题信息
                if "section_title" not in single_result:
                    single_result["section_title"] = self._extract_slide_title(step, context)
                
                return single_result
            else:
                # 如果工具结果不是字典格式，转换为字典
                return {
                    "content": str(single_result),
                    "confidence": 0.8,
                    "section_title": self._extract_slide_title(step, context),
                    "notes": "工具结果已转换为字典格式"
                }
        else:
            return self._integrate_tool_results(results, context, step)
    
    def _execute_with_llm(self, context: Dict[str, Any], step) -> Dict[str, Any]:
        """使用LLM执行步骤 - 优先使用Create Slide Tool"""
        
        # 检查是否是章节生成任务，如果是则直接使用Create Slide Tool
        if (step.metadata and step.metadata.get('section_id') and 
            'create_slide' in self.tools and
            ('生成报告章节' in step.description or '章节' in step.description)):
            
            logger.info(f"检测到章节生成任务，直接使用Create Slide Tool: {step.step_id}", agent_name="ReactAgent")
            
            return self._execute_with_slide_tool(context, step)
        
        # 否则使用原来的LLM执行逻辑
        # 构建LLM输入
        llm_input = self._build_llm_input(context, step)
        
        # 显示执行进度
        self.stream_output.print_thinking(f"正在执行步骤: {step.description[:30]}...")
        
        # 生成响应（使用流式输出）
        logger.info(f"开始执行步骤 {step.step_id}（流式输出）...", agent_name="ReactAgent")
        
        # 获取流式响应迭代器
        stream_iterator = generate_system_response_stream(
            self.system_prompt,
            llm_input,
            temperature=0.7
        )
        
        # 使用流式输出显示
        response = self.stream_output.stream_output(
            stream_iterator,
            task_type=f"步骤 {step.step_id}"
        )
        
        logger.info(f"步骤 {step.step_id} 执行完成，开始解析响应...", agent_name="ReactAgent")
        
        # 解析响应
        result = self._parse_llm_response(response, step)
        
        return result
    
    def _execute_with_slide_tool(self, context: Dict[str, Any], step) -> Dict[str, Any]:
        """直接使用Create Slide Tool执行章节生成，支持智能分页"""
        try:
            slide_tool = self.tools['create_slide']
            
            # 从步骤描述中提取实际内容
            task_content = step.description
            
            # 如果描述包含格式化的章节要求，提取核心任务
            if "章节要求:" in task_content:
                parts = task_content.split("章节要求:")
                if len(parts) > 1:
                    task_content = parts[1].strip()
            
            # 预估内容复杂度，决定是否需要分页
            content_complexity = self._estimate_content_complexity(task_content, context)
            section_title = step.metadata.get('section_title', '章节内容')
            
            content_complexity['needs_multiple_pages']=0
            if content_complexity['needs_multiple_pages']:
                logger.info(f"检测到复杂内容，将生成多页PPT: {section_title} (预估:{content_complexity['estimated_pages']}页)", agent_name="ReactAgent")
                return self._generate_multi_page_slides(slide_tool, task_content, step, context, content_complexity)
            else:
                logger.info(f"内容适合单页，生成单页PPT: {section_title}", agent_name="ReactAgent")
                return self._generate_single_page_slide(slide_tool, task_content, step, context)
                
        except Exception as e:
            logger.error(f"使用Create Slide Tool执行失败: {str(e)}", agent_name="ReactAgent")
            # 回退到原来的LLM执行方式
            return self._execute_with_llm_fallback(context, step)
    
    def _estimate_content_complexity(self, task_content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """预估内容复杂度，判断是否需要分页"""
        import re
        
        # 基础指标
        content_length = len(task_content)
        line_count = len(task_content.split('\n'))
        
        # 统计关键内容元素
        bullet_points = len(re.findall(r'[-•*]\s+|^\d+\.\s+', task_content, re.MULTILINE))
        sections = len(re.findall(r'#+\s+|^[一二三四五六七八九十]、|^第[一二三四五六七八九十]|^\d+、', task_content, re.MULTILINE))
        data_points = len(re.findall(r'\d+(?:\.\d+)?[%分个台次起万千]', task_content))
        
        # 复杂度评分 - 更敏感的评分系统
        complexity_score = 0
        complexity_score += min(content_length / 50, 30)   # 内容长度更敏感 (最多30分)
        complexity_score += min(bullet_points * 1.5, 12)   # 要点数量 (最多12分)
        complexity_score += min(sections * 4, 20)          # 章节数量更重要 (最多20分)
        complexity_score += min(data_points * 1, 8)        # 数据点数量 (最多8分)
        
        # 从文件内容中获取额外信息
        file_content = context.get('file_content', '')
        if file_content:
            file_data_points = len(re.findall(r'\d+(?:\.\d+)?[%分个台次起万千]', file_content))
            complexity_score += min(file_data_points * 0.05, 5)  # 文件数据丰富度 (最多5分)
        
        # 特殊情况：内容过长强制分页
        if content_length > 2000:  # 超过2000字符强制分页
            complexity_score += 20
            
        # 判断分页需求 - 降低阈值
        needs_multiple_pages = complexity_score > 15  # 降低到15分需要分页
        estimated_pages = max(1, min(6, int(complexity_score / 12)))  # 1-6页之间，更细分
        
        logger.info(f"内容复杂度评估: 总分{complexity_score:.1f}, 字符数{content_length}, 要点{bullet_points}, 数据{data_points}", agent_name="ReactAgent")
        
        return {
            "needs_multiple_pages": needs_multiple_pages,
            "estimated_pages": estimated_pages,
            "complexity_score": complexity_score,
            "content_length": content_length,
            "bullet_points": bullet_points,
            "data_points": data_points,
            "sections": sections
        }
    
    def _generate_single_page_slide(self, slide_tool, task_content: str, step, context: Dict[str, Any]) -> Dict[str, Any]:
        """生成单页PPT"""
        # 识别幻灯片类型
        slide_type = self._identify_slide_type(step, context)

        # 构建简洁的任务描述
        section_title = step.metadata.get('section_title', '章节内容')
        task_description = f"生成{section_title}的{slide_type}类型幻灯片"

        slide_input = {
            "task": task_description,  # 使用简洁的任务描述
            "material_content": task_content,  # 实际内容作为材料
            "slide_type": slide_type,  # 使用识别出的类型
            "style": "professional", 
            "max_length": 1200,  # 生成丰富详实的内容，充分利用PPT页面空间
            "context": {
                "slide_title": step.metadata.get('section_title', '章节内容'),
                "report_title": step.metadata.get('section_title', '安全运营工作报告'),
                "report_subtitle": "7*24H全时守护 安全效果护航业务稳定运行",
                "section_id": step.metadata.get('section_id'),
                "step_id": step.step_id,
                "file_content": context.get('file_content', ''),
                "key_points": step.metadata.get('key_points', []),
                "generation_time": context.get('generation_time', ''),
                "slide_number": 1,
                "total_slides": 1
            }
        }
        
        # 如果是目录页，添加所有章节信息
        if slide_type == "toc":
            all_chapters = step.metadata.get('all_chapters')
            logger.info(f"TOC步骤metadata包含: {list(step.metadata.keys())}", agent_name="ReactAgent")
            if all_chapters:
                logger.info(f"找到all_chapters，包含{len(all_chapters)}个章节: {all_chapters}", agent_name="ReactAgent")
                slide_input["context"]["all_chapters"] = all_chapters
                slide_input["context"]["chapter_list"] = all_chapters
                # 更新任务描述，包含实际章节
                chapter_list_str = "\n".join([f"{i}. {ch}" for i, ch in enumerate(all_chapters, 1)])
                slide_input["task"] = f"生成报告目录页，包含以下章节：\n{chapter_list_str}"
                logger.info(f"更新了TOC任务描述：{slide_input['task'][:100]}...", agent_name="ReactAgent")
            else:
                logger.warning("TOC步骤缺少all_chapters元数据，将使用通用模板", agent_name="ReactAgent")
        
        # 检查是否使用Premium模板 - 现在总是使用AI模板
        if hasattr(self, 'state') and getattr(self.state, 'use_premium_template', False):
            slide_input["material_content"] = f"""title: {step.metadata.get('section_title', '章节内容')}
content: {task_content}
total_slides: {context.get('total_slides', 10)}"""
            slide_input["slide_number"] = context.get('slide_number', 1)
            logger.info("使用AI模板生成模式", agent_name="ReactAgent")
        
        # 执行幻灯片生成
        slide_result = slide_tool.execute(slide_input)
        
        if slide_result.get('success'):
            # 返回符合React Agent预期的结果格式
            return {
                "success": True,
                "content": slide_result['slide_content'],
                "confidence": 0.9,
                "section_title": step.metadata.get('section_title', '章节内容'),
                "metadata": {
                    "section_id": step.metadata.get('section_id'),
                    "section_title": step.metadata.get('section_title'),
                    "content_length": len(slide_result['slide_content']),
                    "generated_by": "CreateSlideTool",
                    "has_charts": slide_result.get('metadata', {}).get('has_charts', False),
                    "chart_count": len(slide_result.get('metadata', {}).get('charts', [])),
                    "slide_type": "content",
                    "page_count": 1
                },
                "reasoning": f"使用Create Slide Tool成功生成章节'{step.metadata.get('section_title')}'的单页PPT内容",
                "final_answer": slide_result['slide_content']
            }
        else:
            # 如果Create Slide Tool失败，回退到LLM生成
            logger.warning(f"Create Slide Tool执行失败，回退到LLM生成: {slide_result.get('error')}", agent_name="ReactAgent")
            return self._execute_with_llm_fallback(context, step)
    
    def _generate_multi_page_slides(self, slide_tool, task_content: str, step, context: Dict[str, Any], complexity: Dict[str, Any]) -> Dict[str, Any]:
        """生成多页PPT"""
        section_title = step.metadata.get('section_title', '章节内容')
        estimated_pages = complexity['estimated_pages']
        
        # 确保传入的是纯文本，不是HTML
        if task_content.strip().startswith('<') and '<!DOCTYPE html' in task_content:
            logger.warning(f"检测到传入的是完整HTML内容，提取纯文本进行拆分: {section_title}", agent_name="ReactAgent")
            import re
            # 提取HTML中的文本内容
            text_only = re.sub(r'<[^>]+>', '', task_content)
            text_only = re.sub(r'\s+', ' ', text_only).strip()
            task_content = text_only
        
        # 智能拆分内容为多个子主题
        content_parts = self._split_content_for_pages(task_content, estimated_pages)
        
        all_slides = []
        page_number = 1
        
        for i, content_part in enumerate(content_parts):
            # 为每个部分创建独立的幻灯片，使用子章节标题
            if content_part.get('title') and content_part['title'] != "章节内容":
                # 使用子章节的具体标题
                page_title = content_part['title']
            else:
                # 回退到原来的编号方式
                page_title = f"{section_title}"
                if len(content_parts) > 1:
                    page_title += f" ({page_number}/{len(content_parts)})"
            
            # 确保传递给CreateSlideTool的是纯文本，不是HTML片段
            task_text = content_part['content']
            if task_text.strip().startswith('<'):
                # 如果是HTML片段，提取纯文本
                import re
                task_text = re.sub(r'<[^>]+>', '', task_text)
                task_text = re.sub(r'\s+', ' ', task_text).strip()
                # 如果提取后内容太少，使用focus和title重新构建
                if len(task_text) < 50:
                    task_text = f"生成关于'{content_part.get('title', content_part.get('focus', '内容'))}'的详细分析"
            
            # 构建简洁的任务描述
            task_description = f"生成{page_title}内容页"

            slide_input = {
                "task": task_description,  # 使用简洁的任务描述
                "material_content": task_text,  # 实际内容作为材料
                "slide_type": "content",
                "style": "professional",
                "max_length": 1000,  # 多页时每页也要有丰富内容
                "context": {
                    "slide_title": page_title,
                    "report_title": page_title,
                    "report_subtitle": "7*24H全时守护 安全效果护航业务稳定运行",
                    "section_id": step.metadata.get('section_id'),
                    "step_id": f"{step.step_id}_page_{page_number}",
                    "file_content": context.get('file_content', ''),
                    "key_points": content_part.get('key_points', []),
                    "page_number": page_number,
                    "total_pages": len(content_parts),
                    "focus_area": content_part.get('focus', '综合分析'),
                    "generation_time": context.get('generation_time', ''),
                    "slide_number": page_number,
                    "total_slides": len(content_parts)
                }
            }
            
            # 检查是否使用Premium模板
            if hasattr(self, 'state') and getattr(self.state, 'use_premium_template', False):
                slide_input["use_template_direct"] = True
                slide_input["template_data"] = {
                    "title": page_title,
                    "content": task_text,
                    "total_slides": len(content_parts),
                    "current_page": page_number
                }
                if page_number == 1:
                    logger.info("多页生成模式下启用Premium高端模板", agent_name="ReactAgent")
            
            logger.info(f"生成第{page_number}页: {page_title}", agent_name="ReactAgent")
            
            # 执行幻灯片生成
            slide_result = slide_tool.execute(slide_input)
            
            if slide_result.get('success'):
                all_slides.append({
                    "page_number": page_number,
                    "title": page_title,
                    "content": slide_result['slide_content'],
                    "focus": content_part.get('focus', '综合分析')
                })
                page_number += 1
            else:
                logger.warning(f"第{page_number}页生成失败: {slide_result.get('error')}", agent_name="ReactAgent")
        
        if all_slides:
            # 合并所有幻灯片的内容，用特殊标记分隔
            combined_content = self._combine_multi_page_content(all_slides)
            
            return {
                "success": True,
                "content": combined_content,
                "confidence": 0.9,
                "section_title": section_title,
                "metadata": {
                    "section_id": step.metadata.get('section_id'),
                    "section_title": section_title,
                    "content_length": len(combined_content),
                    "generated_by": "CreateSlideTool",
                    "slide_type": "content",
                    "page_count": len(all_slides),
                    "is_multi_page": True,
                    "pages": all_slides
                },
                "reasoning": f"使用Create Slide Tool成功生成章节'{section_title}'的{len(all_slides)}页PPT内容",
                "final_answer": combined_content
            }
        else:
            # 如果所有页面都失败，回退到单页生成
            logger.warning("多页生成全部失败，回退到单页生成", agent_name="ReactAgent")
            return self._generate_single_page_slide(slide_tool, task_content, step, context)
    
    def _split_content_for_pages(self, content: str, target_pages: int) -> List[Dict[str, Any]]:
        """智能拆分内容为多个页面，根据章节大纲进行合理拆分"""
        import re
        
        # 识别内容中的主要结构
        lines = content.split('\n')
        sections = []
        current_section = {"content": "", "focus": "综合分析", "key_points": []}
        
        # 增强的章节识别模式
        section_patterns = [
            r'^[一二三四五六七八九十]、',   # 中文数字序号（顿号）
            r'^[一二三四五六七八九十]\.',   # 中文数字序号（句号）
            r'^第[一二三四五六七八九十]',   # 第一、第二等
            r'^#+\s+',                     # Markdown标题
            r'^##',                        # 二级标题
            r'^\d+、',                     # 阿拉伯数字序号（顿号）
            r'^\d+\.',                     # 阿拉伯数字序号（句号）
            r'^[A-Z]\.',                   # 英文字母序号
        ]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检测是否是新的主题/章节（使用增强的模式）
            is_new_section = any(re.match(pattern, line) for pattern in section_patterns)
            
            if is_new_section:
                # 保存当前节（如果有内容）
                if current_section["content"].strip():
                    sections.append(current_section)
                
                # 开始新节
                section_title = self._extract_section_title(line)
                current_section = {
                    "content": line + "\n",
                    "focus": self._extract_focus_from_line(line),
                    "key_points": [],
                    "title": section_title,
                    "estimated_length": 0
                }
            else:
                current_section["content"] += line + "\n"
                
                # 收集要点
                if re.match(r'[-•*]\s+', line) or re.match(r'^\d+\.\s+', line):
                    current_section["key_points"].append(line)
        
        # 添加最后一节
        if current_section["content"].strip():
            sections.append(current_section)
        
        # 估算每个章节的内容量
        for section in sections:
            section["estimated_length"] = len(section["content"])
            section["complexity"] = len(section["key_points"]) + (section["estimated_length"] / 100)
        
        # 如果结构化分割的节数合适，直接使用
        if len(sections) >= target_pages and len(sections) <= target_pages + 1:
            return sections[:target_pages]
        
        # 否则按内容长度均匀分割
        if len(sections) < target_pages:
            # 节数少于目标页数，需要进一步拆分
            return self._split_by_length(content, target_pages)
        else:
            # 节数太多，需要合并
            return self._merge_sections(sections, target_pages)
    
    def _extract_focus_from_line(self, line: str) -> str:
        """从标题行提取重点领域"""
        focus_keywords = {
            "威胁|攻击|防护|安全": "威胁防护",
            "事件|响应|处理": "事件管理", 
            "漏洞|修复|补丁": "漏洞管理",
            "资产|设备|系统": "资产管理",
            "监控|运维|运营": "安全运营",
            "评分|指标|绩效": "绩效分析",
            "建议|改进|优化": "改进建议"
        }
        
        for keywords, focus in focus_keywords.items():
            if re.search(keywords, line):
                return focus
        
        return "综合分析"
    
    def _extract_section_title(self, line: str) -> str:
        """从标题行提取章节标题"""
        import re
        
        # 移除序号，提取纯标题
        title = line
        
        # 移除各种序号格式
        title = re.sub(r'^[一二三四五六七八九十]、\s*', '', title)
        title = re.sub(r'^[一二三四五六七八九十]\.\s*', '', title)
        title = re.sub(r'^第[一二三四五六七八九十]\s*', '', title)
        title = re.sub(r'^#+\s*', '', title)
        title = re.sub(r'^\d+、\s*', '', title)
        title = re.sub(r'^\d+\.\s*', '', title)
        title = re.sub(r'^[A-Z]\.\s*', '', title)
        
        return title.strip() or "章节内容"
    
    def _split_by_length(self, content: str, target_pages: int) -> List[Dict[str, Any]]:
        """按内容长度均匀分割"""
        lines = content.split('\n')
        lines_per_page = max(1, len(lines) // target_pages)
        
        pages = []
        for i in range(0, len(lines), lines_per_page):
            page_lines = lines[i:i + lines_per_page]
            pages.append({
                "content": '\n'.join(page_lines),
                "focus": f"内容分析 {len(pages) + 1}",
                "key_points": [line for line in page_lines if re.match(r'[-•*]\s+|^\d+\.\s+', line.strip())]
            })
            
            if len(pages) >= target_pages:
                break
        
        return pages
    
    def _merge_sections(self, sections: List[Dict[str, Any]], target_pages: int) -> List[Dict[str, Any]]:
        """合并节为目标页数"""
        if len(sections) <= target_pages:
            return sections
        
        # 简单合并相邻节
        merged = []
        sections_per_page = len(sections) // target_pages
        
        for i in range(0, len(sections), sections_per_page):
            page_sections = sections[i:i + sections_per_page]
            merged_content = ""
            merged_points = []
            focus_areas = []
            
            for section in page_sections:
                merged_content += section["content"] + "\n"
                merged_points.extend(section["key_points"])
                if section["focus"] not in focus_areas:
                    focus_areas.append(section["focus"])
            
            merged.append({
                "content": merged_content,
                "focus": " & ".join(focus_areas[:2]),  # 最多显示2个重点
                "key_points": merged_points
            })
            
            if len(merged) >= target_pages:
                break
        
        return merged
    
    def _combine_multi_page_content(self, slides: List[Dict[str, Any]]) -> str:
        """合并多页内容，确保每页都是完整的独立HTML文档"""
        slide_contents = []
        
        for slide in slides:
            content = slide['content'].strip()
            
            # 确保内容是完整的HTML文档
            if not content.startswith('<!DOCTYPE html'):
                logger.warning(f"页面{slide['page_number']}不是完整HTML，尝试修复", agent_name="ReactAgent")
                # 如果不是完整HTML，包装成完整HTML
                content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{slide['title']}</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .slide-content {{ max-width: 800px; margin: 0 auto; }}
    </style>
</head>
<body>
    <div class="slide-content">
        {content}
    </div>
</body>
</html>'''
            
            # 验证HTML完整性
            if '</html>' not in content:
                logger.error(f"页面{slide['page_number']}缺少</html>结束标签", agent_name="ReactAgent")
                content += '\n</html>'
            
            # 添加页面标记注释（在DOCTYPE之前）
            page_content = f"<!-- PAGE_{slide['page_number']}: {slide['title']} -->\n{content}"
            slide_contents.append(page_content)
        
        # 用PAGE_BREAK分隔各页内容
        combined = "\n\n<!-- PAGE_BREAK -->\n\n".join(slide_contents)
        
        logger.info(f"成功合并{len(slides)}页内容，总长度:{len(combined)}字符", agent_name="ReactAgent")
        return combined
    
    def _execute_with_llm_fallback(self, context: Dict[str, Any], step) -> Dict[str, Any]:
        """LLM执行的回退方法"""
        # 构建LLM输入
        llm_input = self._build_llm_input(context, step)
        
        # 显示回退提示
        self.stream_output.print_thinking("使用LLM执行...")
        
        # 生成响应
        logger.info(f"使用LLM回退方式执行步骤 {step.step_id}...", agent_name="ReactAgent")
        
        # 获取流式响应迭代器
        stream_iterator = generate_system_response_stream(
            self.system_prompt,
            llm_input,
            temperature=0.7
        )
        
        # 使用流式输出显示
        response = self.stream_output.stream_output(
            stream_iterator,
            task_type=f"LLM步骤 {step.step_id}"
        )
        
        # 解析响应
        result = self._parse_llm_response(response, step)
        return result
    
    def _build_tool_input(self, tool_name: str, context: Dict[str, Any], step) -> Dict[str, Any]:
        """构建工具输入"""
        base_input = {
            "task": step.description,
            "context": context,
            "requirements": step.expected_output
        }
        
        # 根据工具类型添加特定参数
        if tool_name == "create_slide":
            # 识别幻灯片类型
            slide_type = self._identify_slide_type(step, context)
            
            # 添加幻灯片特定的上下文信息
            enhanced_context = context.copy()
            enhanced_context.update({
                "slide_title": self._extract_slide_title(step, context),
                "chapter_title": self._extract_chapter_title(step, context),
                "slide_number": self._extract_slide_number(step, context)
            })
            
            base_input.update({
                "slide_type": slide_type,
                "style": "professional",
                "max_length": 2000,
                "context": enhanced_context
            })
        
        return base_input
    
    def _build_llm_input(self, context: Dict[str, Any], step) -> str:
        """构建LLM输入 - 专注于生成单个章节内容"""
        # 提取章节元数据
        step_metadata = getattr(step, 'metadata', {})
        section_title = step_metadata.get('section_title', '未知章节')
        section_type = step_metadata.get('section_type', 'content')
        key_points = step_metadata.get('key_points', [])
        
        # 从步骤描述中提取任务要求
        task_requirements = self._extract_task_requirements(step.description)
        
        input_text = f"""
你正在为一个专业报告生成单个章节的内容。

章节信息:
- 章节标题: {section_title}
- 章节类型: {section_type}
- 任务描述: {step.description}

用户背景:
- 原始请求: {context['user_request']}
- 工作流ID: {context['workflow_id']}
"""
        
        if context['user_constraints']:
            input_text += "\n用户约束条件:\n"
            for constraint in context['user_constraints']:
                input_text += f"- {constraint}\n"
        
        # 添加章节关键要点
        if key_points:
            input_text += f"\n本章节关键要点:\n"
            for point in key_points:
                input_text += f"- {point}\n"
        
        # 添加前序章节的简要信息（用于保持连贯性）
        if context['previous_results']:
            input_text += "\n前序章节概要（用于保持内容连贯性）:\n"
            for dep_id, result in list(context['previous_results'].items())[-2:]:  # 只显示最近2个
                if isinstance(result, dict):
                    title = result.get('title', dep_id)
                    summary = result.get('summary', str(result)[:200])
                    input_text += f"- {title}: {summary}\n"
        
        # 添加文件内容
        if context.get('file_content') and context['file_content'] != "未找到上传的文件内容":
            input_text += f"""
================================================================================
参考文件内容:
{context['file_content']}
================================================================================
"""
        
        # 添加任务类型特定要求
        if task_requirements.get("content_requirements"):
            input_text += f"""
特定内容要求 (基于任务类型: {task_requirements.get('task_type', '通用')}):
"""
            for i, req in enumerate(task_requirements["content_requirements"], 1):
                input_text += f"{i}. {req}\n"
        
        if task_requirements.get("style_requirements"):
            input_text += f"""
样式要求:
"""
            for i, req in enumerate(task_requirements["style_requirements"], 1):
                input_text += f"{i}. {req}\n"
        
        input_text += f"""
章节生成基本要求:
1. 生成完整的单个章节内容，专注于 "{section_title}"
2. 必须与上传的文件内容高度相关
3. 内容长度应该充实（至少800-1500字）
4. 确保与前面章节的逻辑连贯性

输出格式要求（JSON）:
{{
    "section_title": "{section_title}",
    "content": "完整的HTML页面内容，必须包含完整的HTML结构（<!DOCTYPE html>、<html>、<head>、<body>等）",
    "summary": "本章节的简要总结（100-200字）",
    "key_insights": ["洞察1", "洞察2", "洞察3"],
    "word_count": 实际字数,
    "confidence": 0.9,
    "status": "completed",
    "next_section_suggestion": "对下一章节的建议"
}}

HTML结构要求:
- 必须是完整的HTML5文档，包含<!DOCTYPE html>声明
- 必须包含完整的<head>部分，含title、meta、style等
- 必须包含完整的<body>结构和导航
- 样式必须内嵌在<style>标签中，不依赖外部CSS
- 确保页面可以独立运行和显示

重要提醒:
- 生成的是完整的独立HTML页面，不是片段
- 必须包含完整的页面结构和样式
- 请基于文件内容进行深度分析，不要泛泛而谈
- 确保HTML结构完整，避免后续修复工作
"""
        
        return input_text
    
    def _extract_task_requirements(self, step_description: str) -> Dict[str, Any]:
        """从步骤描述中提取任务要求"""
        requirements = {
            "task_type": "general",
            "content_requirements": [],
            "style_requirements": []
        }
        
        if "输出要求:" in step_description:
            # 提取输出要求部分
            parts = step_description.split("输出要求:")
            if len(parts) > 1:
                requirements_text = parts[1]
                
                # 查找样式要求部分
                if "样式要求:" in requirements_text:
                    req_parts = requirements_text.split("样式要求:")
                    content_part = req_parts[0]
                    style_part = req_parts[1] if len(req_parts) > 1 else ""
                    
                    # 提取内容要求
                    import re
                    content_reqs = re.findall(r'- ([^\n]+)', content_part)
                    requirements["content_requirements"] = content_reqs
                    
                    # 提取样式要求
                    style_reqs = re.findall(r'- ([^\n]+)', style_part)
                    requirements["style_requirements"] = style_reqs
        
        # 从描述中推断任务类型
        description_lower = step_description.lower()
        if any(word in description_lower for word in ["技术", "架构", "系统", "开发", "api"]):
            requirements["task_type"] = "技术报告"
        elif any(word in description_lower for word in ["商业", "业务", "市场", "财务"]):
            requirements["task_type"] = "商业报告"
        elif any(word in description_lower for word in ["安全", "漏洞", "威胁", "风险"]):
            requirements["task_type"] = "安全评估报告"
        elif any(word in description_lower for word in ["数据", "统计", "分析", "指标"]):
            requirements["task_type"] = "数据分析报告"
        
        return requirements
    
    def _generate_search_query(self, step_description: str, context: Dict[str, Any]) -> str:
        """生成搜索查询"""
        # 基于步骤描述和用户请求生成搜索查询
        query_parts = [step_description]
        
        # 从用户请求中提取关键词
        user_request = context.get('user_request', '')
        if user_request:
            query_parts.append(user_request)
        
        # 组合查询
        query = " ".join(query_parts)
        
        # 限制查询长度
        if len(query) > 100:
            query = query[:100] + "..."
        
        return query
    
    def _integrate_tool_results(self, results: Dict[str, Any], context: Dict[str, Any], step) -> Dict[str, Any]:
        """整合多个工具的结果"""
        # 首先处理工具结果，确保它们包含content和confidence字段
        processed_results = {}
        for tool_name, tool_result in results.items():
            if isinstance(tool_result, dict):
                # 确保包含content字段
                if "content" not in tool_result:
                    # 如果没有content字段，尝试从其他字段获取内容
                    if "slide_content" in tool_result:
                        # create_slide工具的特殊处理
                        tool_result["content"] = tool_result["slide_content"]
                    elif "result" in tool_result:
                        tool_result["content"] = str(tool_result["result"])
                    elif "data" in tool_result:
                        tool_result["content"] = str(tool_result["data"])
                    elif "output" in tool_result:
                        tool_result["content"] = str(tool_result["output"])
                    elif "error" in tool_result:
                        tool_result["content"] = f"工具执行错误: {tool_result['error']}"
                    else:
                        tool_result["content"] = str(tool_result)
                
                # 确保包含confidence字段
                if "confidence" not in tool_result:
                    tool_result["confidence"] = 0.8  # 工具结果的默认置信度
                
                # 添加章节标题信息
                if "section_title" not in tool_result:
                    tool_result["section_title"] = self._extract_slide_title(step, context)
                
                processed_results[tool_name] = tool_result
            else:
                # 如果工具结果不是字典格式，转换为字典
                processed_results[tool_name] = {
                    "content": str(tool_result),
                    "confidence": 0.8,
                    "section_title": self._extract_slide_title(step, context),
                    "notes": f"工具 {tool_name} 结果已转换为字典格式"
                }
        
        integration_prompt = f"""
请整合以下多个工具的执行结果，生成最终的执行输出:

任务描述: {step.description}
预期输出: {step.expected_output}

工具执行结果:
{json.dumps(processed_results, ensure_ascii=False, indent=2)}

请生成一个整合后的结果，包含:
- content: 整合后的主要内容
- metadata: 整合的元数据
- confidence: 整合结果的置信度
- notes: 整合过程备注
"""
        
        try:
            # 显示整合提示
            self.stream_output.print_thinking("正在整合工具执行结果")
            
            # 整合结果（使用流式输出）
            logger.info(f"开始整合工具结果（流式输出）...", agent_name="ReactAgent")
            
            # 获取流式响应迭代器
            stream_iterator = generate_system_response_stream(
                self.system_prompt,
                integration_prompt,
                temperature=0.5
            )
            
            # 使用流式输出显示
            response = self.stream_output.stream_output(
                stream_iterator,
                task_type="整合结果"
            )
            
            logger.info("工具结果整合完成，开始解析响应...", agent_name="ReactAgent")
            
            integrated_result = self._parse_llm_response(response, step)
            return integrated_result
            
        except Exception as e:
            logger.error(f"工具结果整合失败: {str(e)}", agent_name="ReactAgent")
            # 返回原始结果的简单整合
            return {
                "content": str(processed_results),
                "metadata": {"tool_count": len(processed_results)},
                "confidence": 0.5,
                "section_title": self._extract_slide_title(step, context),
                "notes": "工具结果自动整合"
            }
    
    def _parse_llm_response(self, response: str, step) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 清理响应内容
            cleaned_response = self._clean_response_content(response)
            
            # 尝试解析JSON
            result = json.loads(cleaned_response)
            
            # 清理结果中的内容字段
            if "content" in result:
                # 先提取纯净的内容
                pure_content = self._extract_pure_content(result["content"])
                result["content"] = self._clean_content_for_html(pure_content)
            
            # 确保JSON响应中包含confidence字段
            if "confidence" not in result:
                result["confidence"] = 0.8  # 为有效的JSON响应设置默认置信度
            
            # 添加章节标题信息
            if "section_title" not in result:
                result["section_title"] = self._extract_slide_title(step, {})
            
            return result
            
        except json.JSONDecodeError:
            # 如果不是JSON，清理后创建结构化结果
            cleaned_content = self._clean_content_for_html(response)
            return {
                "content": cleaned_content,
                "metadata": {
                    "step_id": step.step_id,
                    "parsed": False
                },
                "confidence": 0.8,
                "section_title": self._extract_slide_title(step, {}),
                "notes": "响应已自动结构化"
            }
    
    def _clean_response_content(self, response: str) -> str:
        """清理响应内容，移除markdown代码块标记"""
        import re
        
        # 移除 ```json 和 ``` 标记
        cleaned = re.sub(r'```json\s*', '', response)
        cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'```', '', cleaned)
        
        return cleaned.strip()
    
    def _extract_pure_content(self, content: str) -> str:
        """提取纯净的报告内容，移除所有任务要求和元信息"""
        import re
        
        if not isinstance(content, str):
            content = str(content)
        
        # 按段落分割内容
        paragraphs = content.split('\n\n')
        clean_paragraphs = []
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # 跳过明显的任务说明段落
            skip_patterns = [
                r'生成报告章节.*?章节要求.*?关键要点.*?输出要求',
                r'章节内容已生成.*?内容摘要.*?内容长度',
                r'格式应该.*?内容应该.*?确保',
                r'请基于.*?不要泛泛而谈',
                r'这是独立的章节内容.*?需要完整且自成体系',
                r'内容质量直接影响.*?确保格式规范',
                r'\(\d+/\d+\)$',  # 页码如 (1/3)
                r'^section_title:',
                r'^content:',
                r'^summary:',
                r'^key_insights:',
                r'^word_count:',
                r'^confidence:',
                r'^status:',
                r'^next_section_suggestion:'
            ]
            
            # 检查是否匹配跳过模式
            should_skip = False
            for pattern in skip_patterns:
                if re.search(pattern, paragraph, re.IGNORECASE | re.DOTALL):
                    should_skip = True
                    break
            
            # 跳过包含大量任务关键词的段落
            task_keywords_count = 0
            task_keywords = ['要求', '格式', '确保', '应该', '内容', '生成', '章节', '建议', '输出']
            for keyword in task_keywords:
                task_keywords_count += paragraph.count(keyword)
            
            # 如果任务关键词密度过高，跳过
            if task_keywords_count > 5 and len(paragraph) < 200:
                should_skip = True
            
            # 保留实际的报告内容
            if not should_skip:
                # 进一步清理单个段落中的任务要求
                cleaned_paragraph = self._clean_task_requirements_from_paragraph(paragraph)
                if cleaned_paragraph and len(cleaned_paragraph.strip()) > 10:
                    clean_paragraphs.append(cleaned_paragraph)
        
        return '\n\n'.join(clean_paragraphs)
    
    def _clean_task_requirements_from_paragraph(self, paragraph: str) -> str:
        """清理段落中的任务要求"""
        import re
        
        # 移除行内的任务要求
        paragraph = re.sub(r'生成报告章节[:：][^。]*?[。\.]', '', paragraph)
        paragraph = re.sub(r'章节要求[:：][^。]*?[。\.]', '', paragraph)
        paragraph = re.sub(r'关键要点[:：][^。]*?[。\.]', '', paragraph)
        paragraph = re.sub(r'输出要求[:：][^。]*?[。\.]', '', paragraph)
        paragraph = re.sub(r'\(\d+/\d+\)', '', paragraph)  # 移除页码
        
        # 移除明显的指令性语句
        instruction_patterns = [
            r'请基于[^。]*?进行[^。]*?[。\.]',
            r'确保[^。]*?格式[^。]*?[。\.]',
            r'内容应该[^。]*?[。\.]',
            r'格式应该[^。]*?[。\.]'
        ]
        
        for pattern in instruction_patterns:
            paragraph = re.sub(pattern, '', paragraph, flags=re.IGNORECASE)
        
        # 清理多余的空白
        paragraph = re.sub(r'\s+', ' ', paragraph)
        paragraph = paragraph.strip()
        
        return paragraph
    
    def _clean_content_for_html(self, content: str) -> str:
        """清理内容用于HTML显示"""
        import re
        import json
        
        if not isinstance(content, str):
            content = str(content)
        
        # 移除JSON格式标记
        content = re.sub(r'```json\s*', '', content)
        content = re.sub(r'```\s*', '', content)
        
        # 移除所有常见的JSON字段标记和元数据
        json_fields_to_remove = [
            r'"section_title":\s*"[^"]*",?\s*',
            r'"content":\s*"',
            r'"summary":\s*"[^"]*",?\s*',
            r'"key_insights":\s*\[[^\]]*\],?\s*',
            r'"word_count":\s*\d+,?\s*',
            r'"confidence":\s*[\d\.]+,?\s*',
            r'"status":\s*"[^"]*",?\s*',
            r'"next_section_suggestion":\s*"[^"]*",?\s*',
            r'"metadata":\s*\{[^\}]*\},?\s*',
            r'"notes":\s*"[^"]*",?\s*',
            r'"timestamp":\s*"[^"]*",?\s*',
            r'"generated_by":\s*"[^"]*",?\s*',
            r'"version":\s*"[^"]*",?\s*'
        ]
        
        for pattern in json_fields_to_remove:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        # 移除JSON结构标记
        content = re.sub(r'^\s*\{\s*', '', content)
        content = re.sub(r'\s*\}\s*$', '', content)
        content = re.sub(r'^\s*\[\s*', '', content)
        content = re.sub(r'\s*\]\s*$', '', content)
        
        # 移除多余的引号和逗号
        content = re.sub(r'^"', '', content)
        content = re.sub(r'"$', '', content)
        content = re.sub(r'",\s*$', '', content)
        content = re.sub(r',\s*$', '', content)
        
        # 移除包含元数据关键词和任务要求的整行
        lines = content.split('\n')
        filtered_lines = []
        
        # 扩展的过滤关键词列表
        metadata_keywords = [
            'confidence', 'word_count', 'summary', 'key_insights', 
            'status', 'next_section_suggestion', 'metadata', 'notes',
            'timestamp', 'generated_by', 'version'
        ]
        
        # 任务要求相关的关键词
        task_keywords = [
            '生成报告章节', '章节要求', '关键要点', '输出要求', 
            '章节内容已生成', '内容摘要', '内容长度', '内容预览',
            '格式应该', '内容应该', '确保格式', '包含适当的',
            '生成完整的', '(1/3)', '(2/3)', '(3/3)', '/3)',
            '请基于', '基于文件内容', '不要泛泛而谈',
            '内容质量直接影响', '确保格式规范',
            'section_title', 'HTML格式', 'JSON格式'
        ]
        
        # 合并所有过滤关键词
        all_filter_keywords = metadata_keywords + task_keywords
        
        for line in lines:
            line = line.strip()
            
            # 跳过包含过滤关键词的行
            should_skip = False
            for keyword in all_filter_keywords:
                if keyword.lower() in line.lower():
                    should_skip = True
                    break
            
            # 跳过明显的任务描述行（包含冒号且很长的行）
            if ':' in line and len(line) > 80 and ('要求' in line or '建议' in line or '格式' in line):
                should_skip = True
            
            # 跳过以特殊符号开头的说明行
            if line.startswith(('- ', '* ', '• ', '+ ', '1. ', '2. ', '3. ')) and len(line) > 50:
                if any(word in line for word in ['要求', '格式', '确保', '内容', '应该']):
                    should_skip = True
            
            if not should_skip and line:
                # 跳过空行和只包含特殊字符的行
                if not re.match(r'^[\s\-\=\*\_\+\,\:\"\{\}\[\]]*$', line):
                    filtered_lines.append(line)
        
        content = '\n'.join(filtered_lines)
        
        # 移除多余的换行符，但保留段落结构
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # 处理特殊的转义字符
        content = content.replace('\\n', '\n')
        content = content.replace('\\"', '"')
        content = content.replace('\\/', '/')
        
        # 移除残留的JSON片段
        content = re.sub(r'\s*[\{\}\[\]]\s*', ' ', content)
        content = re.sub(r'\s*,\s*"[^"]*"\s*:\s*', ' ', content)
        
        # 将换行符转换为HTML格式
        # 双换行符转换为段落分隔
        paragraphs = content.split('\n\n')
        html_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if para:
                # 单个换行符转换为<br>
                para_with_br = para.replace('\n', '<br>')
                html_paragraphs.append(f'<p>{para_with_br}</p>')
        
        content = ''.join(html_paragraphs)
        
        # 如果没有任何内容，提供默认内容
        if not content.strip() or content == '<p></p>':
            content = '<p>内容生成中...</p>'
        
        return content
    
    def _validate_execution_result(self, result: Dict[str, Any], step) -> bool:
        """验证执行结果"""
        if not isinstance(result, dict):
            logger.warning("执行结果不是字典格式", agent_name="ReactAgent")
            return False
        
        # 检查必要字段
        required_fields = ["content"]
        for field in required_fields:
            if field not in result:
                logger.warning(f"执行结果缺少字段: {field}", agent_name="ReactAgent")
                return False
        
        # 检查内容是否为空
        if not result.get("content"):
            logger.warning("执行结果内容为空", agent_name="ReactAgent")
            return False
        
        # 检查置信度
        confidence = result.get("confidence", 0.0)
        if confidence < 0.3:
            logger.warning(f"执行结果置信度过低: {confidence}", agent_name="ReactAgent")
            return False
        
        return True
    
    def get_available_tools(self) -> List[str]:
        """获取可用工具列表"""
        return list(self.tools.keys())
    
    def get_tool_status(self, tool_name: str) -> Dict[str, Any]:
        """获取工具状态"""
        if tool_name not in self.tools:
            return {"available": False, "reason": "工具不存在"}
        
        tool = self.tools[tool_name]
        return {
            "available": True,
            "name": tool.__class__.__name__,
            "description": getattr(tool, 'description', '无描述')
        }
    
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
            # 检查状态中是否有文件处理结果
            if hasattr(state, 'file_processing_results') and state.file_processing_results:
                # file_processing_results 现在是字典格式 {file_id: result}
                for file_id, result in state.file_processing_results.items():
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
                            # 增加内容长度限制，以便LLM能处理更多内容
                            file_content += text_content[:100000]  # 增加到10000字符
                            if len(text_content) > 100000:
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
                                        for i, row in enumerate(data[:10]):  # 只显示前10行
                                            file_content += f"  行{i+1}: {row}\n"
                                        if len(data) > 10:
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
                            file_content += f"文件内容:\n{text_content[:1500]}\n"
                            if len(text_content) > 1500:
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
                        file_content += f"处理内容: {entry.content[:1500]}\n"
                        if len(entry.content) > 1500:
                            file_content += "... (内容过长，已截断)\n"
                        file_content += "\n"
            
            if not file_content:
                file_content = "未找到上传的文件内容"
            
            return file_content
            
        except Exception as e:
            logger.error(f"提取文件内容失败: {str(e)}", agent_name="ReactAgent")
            return "提取文件内容时出错"
    
    def retry_step(self, state, step_id: str) -> Dict[str, Any]:
        """重试步骤"""
        step = state.get_step_by_id(step_id)
        if not step:
            raise ValueError(f"未找到步骤: {step_id}")
        
        # 重置步骤状态
        step.execution_attempts = 0
        step.error_message = None
        
        # 重新执行
        return self.execute_step(state, step_id)
    
    def _identify_slide_type(self, step, context: Dict[str, Any]) -> str:
        """识别幻灯片类型"""
        step_desc = step.description.lower()
        
        # 优先从元数据中的章节标题识别
        step_metadata = getattr(step, 'metadata', {})
        section_title = step_metadata.get('section_title', '').lower()
        
        # 合并描述和标题进行识别
        combined_text = f"{step_desc} {section_title}"
        
        print(f"DEBUG: slide_type识别 - step_desc: '{step_desc}'")
        print(f"DEBUG: slide_type识别 - section_title: '{section_title}'")
        print(f"DEBUG: slide_type识别 - combined_text: '{combined_text}'")
        
        # 根据步骤描述和标题识别幻灯片类型
        # 优先识别目录类型（包括原来的"封面与目录"合并情况）
        if any(keyword in combined_text for keyword in ["目录", "toc", "contents", "大纲", "封面与目录", "封面和目录"]):
            print(f"DEBUG: 匹配到目录关键词，返回toc")
            return "toc"
        elif any(keyword in combined_text for keyword in ["封面", "cover", "标题页", "首页"]):
            print(f"DEBUG: 匹配到封面关键词，返回cover")
            return "cover"
        elif any(keyword in combined_text for keyword in ["图表", "chart", "数据", "graph", "统计"]):
            print(f"DEBUG: 匹配到图表关键词，返回chart")
            return "chart"
        elif any(keyword in combined_text for keyword in ["总结", "summary", "结论", "conclusion", "收尾"]):
            print(f"DEBUG: 匹配到总结关键词，返回summary")
            return "summary"
        else:
            # 默认为内容页
            print(f"DEBUG: 没有匹配到特殊关键词，返回content")
            return "content"
    
    def _extract_slide_title(self, step, context: Dict[str, Any]) -> str:
        """提取幻灯片标题"""
        # 优先从步骤元数据中获取章节标题
        step_metadata = getattr(step, 'metadata', {})
        if step_metadata.get('section_title'):
            return step_metadata['section_title']
        
        # 如果没有元数据，从步骤描述中提取标题
        step_desc = step.description
        
        # 如果描述中包含"章节要求:"或类似格式，提取实际的章节标题
        if "生成报告章节:" in step_desc:
            # 提取实际的章节名称（在冒号后面，章节要求前面）
            parts = step_desc.split("生成报告章节:")
            if len(parts) > 1:
                title_part = parts[1].strip()
                # 进一步提取到"章节要求"之前的内容
                if "章节要求:" in title_part:
                    title = title_part.split("章节要求:")[0].strip()
                    return title
        
        # 移除常见的动词和前缀
        title = step_desc.replace("生成", "").replace("创建", "").replace("制作", "").strip()
        
        # 如果标题太长（可能包含了详细说明），尝试截取第一句或第一个短语
        if len(title) > 50:
            # 尝试在标点符号处截断
            for delimiter in ['，', '。', '：', ':', '（', '(']:
                if delimiter in title:
                    title = title.split(delimiter)[0].strip()
                    break
        
        # 如果标题为空，使用默认标题
        if not title:
            title = "幻灯片标题"
        
        return title
    
    def _extract_chapter_title(self, step, context: Dict[str, Any]) -> str:
        """提取章节标题"""
        # 优先从步骤元数据中获取章节类型或主题
        step_metadata = getattr(step, 'metadata', {})
        if step_metadata.get('section_type'):
            section_type = step_metadata['section_type']
            # 将section_type转换为更友好的章节标题
            type_mapping = {
                'executive_summary': '执行摘要',
                'threat_analysis': '威胁分析',
                'security_monitoring': '安全监控',
                'incident_response': '事件响应',
                'vulnerability_management': '漏洞管理',
                'compliance': '合规性',
                'recommendations': '建议与改进',
                'conclusion': '总结'
            }
            if section_type in type_mapping:
                return type_mapping[section_type]
        
        # 从上下文中提取章节标题
        if context.get("chapter_title"):
            return context["chapter_title"]
        
        # 从用户请求中提取可能的章节信息
        user_request = context.get("user_request", "")
        if "安全运营" in user_request:
            return "安全运营报告"
        elif "年度报告" in user_request:
            return "年度报告"
        
        # 默认章节标题
        return ""
    
    def _extract_slide_number(self, step, context: Dict[str, Any]) -> str:
        """提取幻灯片编号"""
        # 从步骤ID中提取数字
        step_id = step.step_id
        
        # 提取数字部分
        import re
        numbers = re.findall(r'\d+', step_id)
        if numbers:
            return numbers[-1]  # 返回最后一个数字
        
        # 默认编号
        return "1"
