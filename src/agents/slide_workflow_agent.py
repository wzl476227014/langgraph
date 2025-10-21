"""
Slide Workflow Agent
幻灯片工作流代理 - 管理优化后的幻灯片生成流程
"""

from typing import Dict, Any, Optional
from ..utils.logger import get_logger
from ..utils.config import get_config
from ..tools.slide_analyzer import SlideAnalyzerTool
from ..tools.slide_outliner import SlideOutlinerTool
from ..tools.slide_generator import SlideGeneratorTool
from ..utils.parallel_slide_manager import ParallelSlideManager, TemplateCache
from ..graph.state import WorkflowState

logger = get_logger(__name__)


class SlideWorkflowAgent:
    """幻灯片工作流代理"""

    def __init__(self):
        """初始化幻灯片工作流代理"""
        self.config = get_config()
        self.analyzer = SlideAnalyzerTool()
        self.outliner = SlideOutlinerTool()
        self.generator = SlideGeneratorTool()
        self.parallel_manager = ParallelSlideManager(
            max_workers=self.config.get_tool_config("parallel_slide_manager").get("max_workers", 5)
        )

        logger.info("SlideWorkflowAgent initialized", agent_name="SlideWorkflow")

    def analyze_user_intent(self, state: WorkflowState) -> WorkflowState:
        """
        分析用户意图 (使用LLM进行智能分析)

        Args:
            state: 工作流状态

        Returns:
            更新后的WorkflowState，metadata中包含:
            - intent_type: 意图类型 (generate_new, optimize_existing, analyze_only, chat)
            - slide_count: 目标页数
            - task_description: 任务描述
            - should_proceed: 是否继续生成流程
            - confidence: 置信度
        """
        logger.info("Analyzing user intent using LLM", agent_name="SlideWorkflow")

        try:
            from ..utils.llm_config import generate_system_response
            import json
            import re

            # 构建提示词
            file_status = f"已上传{len(state.uploaded_files)}个文件" if state.uploaded_files else "未上传文件"

            intent_prompt = f"""请分析以下用户请求的意图,并以JSON格式返回结果。

【用户请求】
{state.user_request}

【文件上传情况】
{file_status}

【分析要求】
1. intent_type: 判断用户意图类型
   - generate_new: 生成全新的PPT（如"生成5页PPT"）
   - optimize_existing: 优化已有PPT（如"优化第4页"、"修改第2页标题"）
   - analyze_only: 仅分析文档不生成PPT
   - chat: 闲聊或咨询（无实际生成需求）

2. slide_count: 提取用户请求的**PPT总页数**（整数，⚠️ 注意区分总页数和页码）

   ✅ 提取总页数的情况：
     * "生成3页报告" → 3（明确要生成3页）
     * "帮我做20页PPT" → 20（明确要生成20页）
     * "5张幻灯片" → 5（明确要生成5页）
     * "10个页面的PPT" → 10

   ❌ 不要提取页码的情况（返回 null）：
     * "优化第5页" → null（这是页码，不是总页数）
     * "修改第3页的标题" → null（这是页码）
     * "查看第10页" → null（这是页码）
     * "第2页到第5页需要优化" → null（这是页码范围）

   未提及页数时返回 null：
     * "生成一份报告" → null
     * "做个PPT" → null

3. should_proceed: 是否应该继续后续流程
   - generate_new, optimize_existing → true
   - analyze_only, chat → false

4. confidence: 置信度 (0.0-1.0)

【输出格式】
请直接返回JSON对象,不要添加任何解释或markdown标记:
{{"intent_type": "generate_new", "slide_count": 5, "should_proceed": true, "confidence": 0.95}}"""

            # 调用LLM分析
            logger.info(f"LLM intent_prompt: {intent_prompt}", agent_name="SlideWorkflow")
            llm_response = generate_system_response(
                system_prompt="""你是一个专业的意图识别助手,擅长准确理解用户的PPT生成需求。

重要提示：
1. 仔细区分"总页数"和"页码"
   - 总页数：用户想生成多少页PPT（如"生成3页"）
   - 页码：用户想操作哪一页（如"优化第5页"）
2. 只有在用户明确要生成新PPT并指定页数时，才提取slide_count
3. 如果用户是要修改/优化已有的某一页，slide_count应返回null""",
                user_message=intent_prompt,
                temperature=0.7,
                max_tokens=300
            )

            logger.info(f"LLM intent analysis response: {llm_response}", agent_name="SlideWorkflow")

            # 提取JSON
            json_match = re.search(r'\{[\s\S]*?\}', llm_response)
            if json_match:
                intent_data = json.loads(json_match.group())

                # 验证必需字段
                required_fields = ["intent_type", "should_proceed"]
                if all(field in intent_data for field in required_fields):
                    # 补充任务描述和文件信息
                    intent_data["task_description"] = state.user_request
                    intent_data["has_files"] = len(state.uploaded_files) > 0 if state.uploaded_files else False

                    logger.info(f"LLM intent analysis result: {intent_data}", agent_name="SlideWorkflow")

                    # 将意图分析结果存储到state的user_inputs中
                    state.user_inputs["intent_analysis"] = intent_data

                    return state
                else:
                    logger.warning(f"LLM response missing required fields, using fallback", agent_name="SlideWorkflow")
                    return self._fallback_intent_analysis(state)
            else:
                logger.warning(f"Failed to extract JSON from LLM response, using fallback", agent_name="SlideWorkflow")
                return self._fallback_intent_analysis(state)

        except Exception as e:
            logger.error(f"LLM intent analysis failed: {str(e)}, using fallback", agent_name="SlideWorkflow")
            return self._fallback_intent_analysis(state)

    def _fallback_intent_analysis(self, state: WorkflowState) -> WorkflowState:
        """
        意图分析的兜底方案 (使用正则表达式和关键词匹配)

        Args:
            state: 工作流状态

        Returns:
            更新后的WorkflowState
        """
        logger.info("Using fallback intent analysis (regex/keywords)", agent_name="SlideWorkflow")

        user_request = state.user_request.lower()

        # 提取页数
        slide_count = self._extract_slide_count(state.user_request)

        # 判断意图类型
        intent_type = "generate_new"  # 默认为生成新PPT
        should_proceed = True
        task_description = state.user_request

        # 优化类关键词
        if any(keyword in user_request for keyword in ['优化', '改进', '修改', '调整']):
            intent_type = "optimize_existing"
            logger.info("User wants to optimize existing PPT", agent_name="SlideWorkflow")

        # 纯分析类关键词
        elif any(keyword in user_request for keyword in ['分析', '总结', '提取', '查看']) and '生成' not in user_request:
            intent_type = "analyze_only"
            should_proceed = False  # 只分析，不生成
            logger.info("User wants to analyze document only", agent_name="SlideWorkflow")

        # 闲聊类关键词
        elif not state.uploaded_files and any(keyword in user_request for keyword in ['你好', '帮我', '请问', '如何', '怎么']):
            intent_type = "chat"
            should_proceed = False
            logger.info("User is chatting", agent_name="SlideWorkflow")

        # 生成新PPT关键词
        elif any(keyword in user_request for keyword in ['生成', '创建', '制作', 'ppt', '报告', '幻灯片']):
            intent_type = "generate_new"
            logger.info(f"User wants to generate new PPT with {slide_count} slides", agent_name="SlideWorkflow")

        result = {
            "intent_type": intent_type,
            "slide_count": slide_count,
            "task_description": task_description,
            "should_proceed": should_proceed,
            "has_files": len(state.uploaded_files) > 0 if state.uploaded_files else False,
            "confidence": 0.7  # 兜底方案的置信度较低
        }

        logger.info(f"Fallback intent analysis result: {result}", agent_name="SlideWorkflow")

        # 将意图分析结果存储到state的user_inputs中
        state.user_inputs["intent_analysis"] = result

        return state

    def analyze_document(self, state: WorkflowState) -> WorkflowState:
        """
        步骤1: 分析文档,提取关键信息

        Args:
            state: 工作流状态

        Returns:
            更新后的状态
        """
        logger.info("Starting document analysis", agent_name="SlideWorkflow")

        try:
            # 如果没有处理结果，先处理上传的文件
            if not state.file_processing_results and state.uploaded_files:
                logger.info("Processing uploaded files first", agent_name="SlideWorkflow")
                from ..tools.file_upload_tool import FileUploadTool
                import os
                file_tool = FileUploadTool()

                for file_path in state.uploaded_files:
                    # 处理文件路径格式
                    if isinstance(file_path, dict):
                        actual_path = file_path.get("file_path", file_path)
                    else:
                        actual_path = file_path

                    # 处理文件
                    result = file_tool.execute({
                        "task": "分析文档内容",
                        "file_path": actual_path,
                        "operation": "process"
                    })

                    if result.get("success"):
                        file_id = os.path.basename(actual_path)
                        state.add_file_processing_result(file_id, {
                            "status": "success",
                            "content": result.get("result", {}).get("text_content", ""),
                            "metadata": result.get("result", {})
                        })
                        logger.info(f"File processed successfully: {file_id}", agent_name="SlideWorkflow")
                    else:
                        logger.error(f"File processing failed: {result.get('error')}", agent_name="SlideWorkflow")

            # 获取文档内容
            file_processing_results = state.file_processing_results
            document_content = ""

            for file_id, result in file_processing_results.items():
                if result.get("status") == "success":
                    content = result.get("content", "")
                    document_content += content + "\n\n"

            if not document_content:
                logger.warning("No document content found", agent_name="SlideWorkflow")
                document_content = "无文档内容"

            # 分析文档
            file_path_for_analysis = None
            if state.uploaded_files:
                first_file = state.uploaded_files[0]
                if isinstance(first_file, dict):
                    file_path_for_analysis = first_file.get("file_path")
                else:
                    file_path_for_analysis = first_file

            analysis_result = self.analyzer.analyze_document(
                document_content=document_content,
                user_requirements=state.user_request,
                file_path=file_path_for_analysis
            )

            # 检查解析是否失败
            if analysis_result.get("parse_failed", False):
                error_msg = analysis_result.get("metadata", {}).get("error", "文档解析失败，无法提取有效内容")
                logger.error(f"Document parsing failed: {error_msg}", agent_name="SlideWorkflow")
                state.set_last_error(error_msg)
                # 设置工作流状态为失败
                from ..graph.state import WorkflowStatus
                state.workflow_status = WorkflowStatus.FAILED
                return state

            # 更新状态
            state.slide_data = analysis_result

            logger.info("Document analysis completed", agent_name="SlideWorkflow")

            return state

        except Exception as e:
            logger.error(f"Document analysis failed: {str(e)}", agent_name="SlideWorkflow")
            state.set_last_error(f"文档分析失败: {str(e)}")
            return state

    def create_outline(self, state: WorkflowState) -> WorkflowState:
        """
        步骤2: 创建幻灯片大纲

        Args:
            state: 工作流状态

        Returns:
            更新后的状态
        """
        logger.info("Creating slide outline", agent_name="SlideWorkflow")

        try:
            # 智能页数决策（三级优先级）
            intent_analysis = state.user_inputs.get("intent_analysis", {})
            slide_count = None
            source = ""

            # 1. 最高优先级：用户明确指定的页数（意图分析提取）
            if intent_analysis.get("slide_count"):
                slide_count = intent_analysis.get("slide_count")
                source = "用户明确指定"
                logger.info(f"Priority 1: Using user-specified slide count from intent: {slide_count}", agent_name="SlideWorkflow")

            # 2. 次优先级：正则提取（兜底用户指定）
            elif slide_count is None:
                regex_count = self._extract_slide_count_regex_only(state.user_request)
                if regex_count is not None:
                    slide_count = regex_count
                    source = "正则提取用户指定"
                    logger.info(f"Priority 2: Using regex extracted slide count: {slide_count}", agent_name="SlideWorkflow")

            # 3. 最低优先级：LLM根据文档内容推荐的页数
            if slide_count is None:
                doc_analysis = state.slide_data or {}
                outline_suggestion = doc_analysis.get("outline_suggestion", {})
                recommended_count = outline_suggestion.get("recommended_page_count")
                reasoning = outline_suggestion.get("reasoning", "")

                if recommended_count:
                    slide_count = recommended_count
                    source = f"文档分析推荐（{reasoning}）"
                    logger.info(
                        f"Priority 3: Using LLM recommended slide count: {slide_count} - {reasoning}",
                        agent_name="SlideWorkflow"
                    )

            # 4. 最后兜底：配置文件默认值
            if slide_count is None:
                slide_count = self.config.get_tool_config("slide_outliner").get("default_slide_count", 20)
                source = "配置默认值"
                logger.warning(
                    f"Priority 4 (fallback): Using default slide count: {slide_count}",
                    agent_name="SlideWorkflow"
                )

            logger.info(f"Final slide count decision: {slide_count} 页（来源：{source}）", agent_name="SlideWorkflow")

            # 创建大纲
            outline_result = self.outliner.create_outline(
                slide_count=slide_count,
                task_brief=state.user_request,
                extracted_data=state.slide_data or {},
                user_requirements=state.user_request
            )

            # 更新状态
            state.slide_outline = outline_result

            logger.info(
                f"Outline created: {outline_result['total_slides']} slides",
                agent_name="SlideWorkflow"
            )

            return state

        except Exception as e:
            logger.error(f"Outline creation failed: {str(e)}", agent_name="SlideWorkflow")
            state.set_last_error(f"大纲创建失败: {str(e)}")
            return state

    def generate_template_slides(self, state: WorkflowState) -> WorkflowState:
        """
        步骤3: 串行生成基础模板幻灯片

        Args:
            state: 工作流状态

        Returns:
            更新后的状态
        """
        logger.info("Generating template slides", agent_name="SlideWorkflow")

        try:
            outline = state.slide_outline
            serial_pages = outline["creation_order"]["serial"]

            template_results = {}

            for page_num in serial_pages:
                page_info = self._get_page_info(outline, page_num)

                logger.info(
                    f"Generating template slide {page_num} ({page_info['template']})",
                    agent_name="SlideWorkflow"
                )

                result = self.generator.generate_slide(
                    page_info=page_info,
                    template_cache=template_results,
                    extracted_data=state.slide_data or {}
                )

                # 缓存模板
                template_key = page_info["template"]
                template_results[template_key] = result
                TemplateCache.set_template(template_key, result)

                logger.info(
                    f"Template slide {page_num} generated successfully",
                    agent_name="SlideWorkflow"
                )

            # 更新状态
            state.slide_templates = template_results

            logger.info(
                f"Template generation completed: {len(template_results)} templates created",
                agent_name="SlideWorkflow"
            )

            return state

        except Exception as e:
            logger.error(f"Template slide generation failed: {str(e)}", agent_name="SlideWorkflow")
            state.set_last_error(f"模板生成失败: {str(e)}")
            return state

    def generate_content_slides_parallel(self, state: WorkflowState) -> WorkflowState:
        """
        步骤4: 并行生成内容幻灯片

        Args:
            state: 工作流状态

        Returns:
            更新后的状态
        """
        logger.info("Starting parallel slide generation", agent_name="SlideWorkflow")

        try:
            outline = state.slide_outline
            parallel_pages = outline["creation_order"]["parallel"]

            if not parallel_pages:
                logger.info("No parallel slides to generate", agent_name="SlideWorkflow")
                state.generated_slides = []
                return state

            # 准备幻灯片信息列表
            slide_list = [
                self._get_page_info(outline, page_num)
                for page_num in parallel_pages
            ]

            # 并行生成
            batch_size = self.config.get_tool_config("parallel_slide_manager").get("batch_size", 5)

            results = self.parallel_manager.generate_slides_batch(
                slide_list=slide_list,
                template_cache=state.slide_templates or {},
                extracted_data=state.slide_data or {},
                generator=self.generator,
                batch_size=batch_size
            )

            # 更新状态
            state.generated_slides = results

            # 更新生成状态
            state.slide_generation_status = {
                "total_parallel": len(parallel_pages),
                "generated": len(results),
                "failed": len(parallel_pages) - len(results),
                "success_rate": len(results) / len(parallel_pages) * 100 if parallel_pages else 100
            }

            logger.info(
                f"Parallel generation completed: {len(results)}/{len(parallel_pages)} slides generated",
                agent_name="SlideWorkflow"
            )

            return state

        except Exception as e:
            logger.error(f"Parallel slide generation failed: {str(e)}", agent_name="SlideWorkflow")
            state.set_last_error(f"并行生成失败: {str(e)}")
            return state

    def assemble_all_slides(self, state: WorkflowState) -> WorkflowState:
        """
        步骤5: 组装所有幻灯片并生成输出文件

        Args:
            state: 工作流状态

        Returns:
            更新后的WorkflowState，包含output_file路径
        """
        logger.info("Assembling all slides", agent_name="SlideWorkflow")

        try:
            all_slides = {}

            # 添加模板幻灯片
            if state.slide_templates:
                for template_key, slide_data in state.slide_templates.items():
                    page_num = slide_data["page_number"]
                    all_slides[page_num] = slide_data["html_content"]

            # 添加并行生成的幻灯片
            if state.generated_slides:
                for page_num, slide_data in state.generated_slides.items():
                    all_slides[page_num] = slide_data["html_content"]

            # 按页码排序
            sorted_slides = dict(sorted(all_slides.items()))

            logger.info(
                f"Slide assembly completed: {len(sorted_slides)} slides assembled",
                agent_name="SlideWorkflow"
            )

            # 保存每一页为单独的HTML文件
            import os
            from datetime import datetime

            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            task_dir = os.path.join(output_dir, f"task_{timestamp}")
            os.makedirs(task_dir, exist_ok=True)

            # HTML模板（每一页独立）
            slide_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Slide {page_num}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: #1a202c;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
        }}
        .slide-wrapper {{
            position: relative;
        }}
        .slide-container {{
            width: 1920px;
            height: 1080px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 60px;
            box-sizing: border-box;
            overflow: auto;
        }}
        .slide-number {{
            position: absolute;
            top: -30px;
            right: 0;
            color: #94a3b8;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="slide-wrapper">
        <div class="slide-number">第 {page_num} 页 / 共 {total_pages} 页</div>
        <div class="slide-container">
            {content}
        </div>
    </div>
</body>
</html>
"""

            # 保存每一页HTML（直接使用生成的内容，不添加包装）
            saved_files = []
            total_pages = len(sorted_slides)

            for page_num, content in sorted_slides.items():
                html_filename = f"slide_{page_num:03d}.html"
                html_path = os.path.join(task_dir, html_filename)

                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                saved_files.append(html_path)

            logger.info(f"Saved {len(saved_files)} individual slide HTML files", agent_name="SlideWorkflow")

            # 创建索引页面（用于预览导航）
            index_html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PPT Preview</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: #0f172a;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif;
        }}
        .preview-container {{
            width: 100%;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }}
        .nav-bar {{
            background: #1e293b;
            padding: 15px;
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
        }}
        .nav-btn {{
            padding: 8px 16px;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }}
        .nav-btn:hover:not(:disabled) {{
            background: #2563eb;
            transform: translateY(-1px);
        }}
        .nav-btn:disabled {{
            background: #475569;
            cursor: not-allowed;
            opacity: 0.5;
        }}
        .page-info {{
            color: #e2e8f0;
            font-size: 14px;
            min-width: 150px;
            text-align: center;
        }}
        .slide-frame {{
            flex: 1;
            border: none;
            background: #1a202c;
        }}
    </style>
</head>
<body>
    <div class="preview-container">
        <div class="nav-bar">
            <button class="nav-btn" onclick="firstSlide()">⏮ 首页</button>
            <button class="nav-btn" onclick="previousSlide()" id="prevBtn">← 上一页</button>
            <span class="page-info" id="pageInfo">第 1 / {total} 页</span>
            <button class="nav-btn" onclick="nextSlide()" id="nextBtn">下一页 →</button>
            <button class="nav-btn" onclick="lastSlide()">末页 ⏭</button>
        </div>
        <iframe id="slideFrame" class="slide-frame" src="slide_001.html"></iframe>
    </div>

    <script>
        let currentSlide = 1;
        const totalSlides = {total};

        function updateSlide() {{
            const frame = document.getElementById('slideFrame');
            const pageInfo = document.getElementById('pageInfo');
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');

            frame.src = `slide_${{String(currentSlide).padStart(3, '0')}}.html`;
            pageInfo.textContent = `第 ${{currentSlide}} / ${{totalSlides}} 页`;

            prevBtn.disabled = currentSlide === 1;
            nextBtn.disabled = currentSlide === totalSlides;
        }}

        function firstSlide() {{ currentSlide = 1; updateSlide(); }}
        function lastSlide() {{ currentSlide = totalSlides; updateSlide(); }}
        function previousSlide() {{ if (currentSlide > 1) {{ currentSlide--; updateSlide(); }} }}
        function nextSlide() {{ if (currentSlide < totalSlides) {{ currentSlide++; updateSlide(); }} }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowLeft' || e.key === 'PageUp') previousSlide();
            if (e.key === 'ArrowRight' || e.key === 'PageDown' || e.key === ' ') nextSlide();
            if (e.key === 'Home') firstSlide();
            if (e.key === 'End') lastSlide();
        }});

        updateSlide();
    </script>
</body>
</html>
""".format(total=total_pages)

            index_path = os.path.join(task_dir, "index.html")
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(index_html)

            logger.info(f"Created index page with navigation: {index_path}", agent_name="SlideWorkflow")

            # 更新state（不生成PPTX，使用HTML索引作为输出）
            state.output_file = index_path
            # 将整数键转换为字符串键，以符合Dict[str, str]类型定义
            state.slides_content = {str(k): v for k, v in sorted_slides.items()}

            logger.info(
                f"All slides saved: {len(saved_files)} files in {task_dir}",
                agent_name="SlideWorkflow"
            )

            return state

        except Exception as e:
            logger.error(f"Slide assembly failed: {str(e)}", agent_name="SlideWorkflow")
            state.set_last_error(f"幻灯片组装失败: {str(e)}")
            return state

    def _extract_slide_count_regex_only(self, user_request: str) -> Optional[int]:
        """
        仅使用正则提取幻灯片数量（不返回默认值）

        Returns:
            int: 提取到的页数
            None: 未提取到页数
        """
        import re

        # 尝试匹配 "20页", "20 页", "生成20页"等模式
        match = re.search(r'(\d+)\s*页', user_request)
        if match:
            slide_count = int(match.group(1))
            logger.info(f"Regex extracted slide count: {slide_count}", agent_name="SlideWorkflow")
            return slide_count

        return None

    def _extract_slide_count(self, user_request: str) -> int:
        """
        从用户请求中提取幻灯片数量（保留向后兼容）

        Returns:
            int: 提取到的页数或默认值
        """
        regex_count = self._extract_slide_count_regex_only(user_request)
        if regex_count is not None:
            return regex_count

        # 默认值
        default_count = self.config.get_tool_config("slide_outliner").get("default_slide_count", 20)
        logger.info(f"Using default slide count: {default_count}", agent_name="SlideWorkflow")
        return default_count

    def _get_page_info(self, outline: Dict[str, Any], page_number: int) -> Dict[str, Any]:
        """获取指定页面的信息"""
        for slide in outline.get("outline", []):
            if slide["page"] == page_number:
                return slide

        # 如果没找到,返回默认信息
        return {
            "page": page_number,
            "title": f"第{page_number}页",
            "subtitle": "",
            "content_brief": "",
            "template": "content",
            "template_name": "内容页",
            "data_requirements": [],
            "priority": "medium"
        }

    def get_generation_summary(self, state: WorkflowState) -> Dict[str, Any]:
        """获取生成摘要"""
        total_slides = 0
        generated_slides = 0

        if state.slide_outline:
            total_slides = state.slide_outline.get("total_slides", 0)

        if state.slide_templates:
            generated_slides += len(state.slide_templates)

        if state.generated_slides:
            generated_slides += len(state.generated_slides)

        return {
            "total_slides": total_slides,
            "generated_slides": generated_slides,
            "template_slides": len(state.slide_templates) if state.slide_templates else 0,
            "parallel_slides": len(state.generated_slides) if state.generated_slides else 0,
            "success_rate": (generated_slides / total_slides * 100) if total_slides > 0 else 0,
            "status": state.slide_generation_status
        }
