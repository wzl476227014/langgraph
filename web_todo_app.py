#!/usr/bin/env python3
"""
动态任务规划版Web服务器 - PPT AI助手
基于genspark.txt的动态工作流架构：LLM规划任务 → 动态选择工具 → 逐步执行
"""

from flask import Flask, request, jsonify, render_template_string, Response
import json
import uuid
import sys
import os
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入工具和代理
from src.agents.slide_workflow_agent import SlideWorkflowAgent
from src.graph.state import WorkflowState, create_workflow_state
from src.utils.logger import get_logger
from src.utils.llm_config import generate_system_response

logger = get_logger(__name__)


def safe_sse_json(data):
    """
    安全的SSE JSON序列化
    确保JSON字符串中的换行符被正确转义，避免破坏SSE格式
    """
    json_str = json.dumps(data, ensure_ascii=False)
    # SSE格式要求：data行不能包含未转义的换行符
    # json.dumps已经将\n转义为\\n，但我们需要确保没有真实的换行符
    json_str = json_str.replace('\n', '\\n').replace('\r', '\\r')
    return json_str


app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB（提高限制以支持大对话历史）
app.config['SECRET_KEY'] = os.urandom(24)

# 全局会话存储
sessions = {}

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'md', 'html', 'htm'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 幻灯片工作流代理
slide_workflow_agent = SlideWorkflowAgent()


# =========================
# 核心：动态任务规划器
# =========================

class DynamicTaskPlanner:
    """
    动态任务规划器
    根据用户请求，使用LLM规划任务列表，然后逐步执行
    """

    def __init__(self, workflow_agent: SlideWorkflowAgent):
        self.agent = workflow_agent
        self.available_tools = {
            "analyze_user_intent": {
                "description": "分析用户意图，提取页数、意图类型等",
                "method": self.agent.analyze_user_intent
            },
            "analyze_document": {
                "description": "分析PDF文档，提取关键数据、章节、指标等",
                "method": self.agent.analyze_document
            },
            "create_outline": {
                "description": "创建PPT大纲，确定页数、模板类型、并行策略",
                "method": self.agent.create_outline
            },
            "generate_single_slide": {
                "description": "生成单个幻灯片页面（用于串行生成模板）",
                "method": self._generate_single_slide
            },
            "generate_content_slides_parallel": {
                "description": "并行生成多个幻灯片页面（最多5页/轮）",
                "method": self._generate_slides_parallel_batched
            },
            "assemble_all_slides": {
                "description": "组装所有幻灯片，生成最终HTML",
                "method": self.agent.assemble_all_slides
            }
        }

    def _generate_single_slide(self, state: WorkflowState, page_num: int = None) -> WorkflowState:
        """
        生成单个幻灯片页面并立即保存

        Args:
            state: 工作流状态
            page_num: 页码（从任务参数中获取）

        Returns:
            更新后的状态
        """
        if page_num is None:
            logger.error("page_num is required for generate_single_slide", agent_name="TaskPlanner")
            return state

        try:
            outline = state.slide_outline
            # 处理outline数据格式
            if isinstance(outline, dict):
                outline_list = outline.get("outline", [])
            elif isinstance(outline, str):
                import json
                parsed = json.loads(outline)
                outline_list = parsed.get("outline", []) if isinstance(parsed, dict) else parsed
            else:
                outline_list = outline

            page_info = next((s for s in outline_list if s["page"] == page_num), None)
            if not page_info:
                logger.error(f"Page {page_num} not found in outline", agent_name="TaskPlanner")
                return state

            logger.info(
                f"Generating slide {page_num}: {page_info.get('title', '')} ({page_info.get('template', '')})",
                agent_name="TaskPlanner"
            )

            # 生成幻灯片，传入用户的优化需求
            result = self.agent.generator.generate_slide(
                page_info=page_info,
                template_cache=state.slide_templates or {},
                extracted_data=state.slide_data or {},
                user_requirements=state.user_request  # 传入用户请求作为特殊要求
            )

            # 缓存到 slide_templates
            if not state.slide_templates:
                state.slide_templates = {}

            template_key = f"page_{page_num}"
            state.slide_templates[template_key] = result

            # 立即保存HTML文件
            import os
            from datetime import datetime

            # 使用workflow_id创建目录（确保所有页面保存在同一目录）
            output_dir = "examples/sample_reports"
            if not hasattr(state, '_task_dir') or not state._task_dir:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                task_id = state.workflow_id[:8] if state.workflow_id else "unknown"
                task_dir = os.path.join(output_dir, f"task_{task_id}_{timestamp}")
                os.makedirs(task_dir, exist_ok=True)
                state._task_dir = task_dir
            else:
                task_dir = state._task_dir

            # 保存单页HTML
            html_filename = f"slide_{page_num:03d}.html"
            html_path = os.path.join(task_dir, html_filename)

            # 获取总页数
            total_pages = outline.get("total_slides", len(outline_list)) if isinstance(outline, dict) else len(outline_list)

            # 直接使用生成的HTML内容，不添加额外包装
            html_content = result.get("html_content", "")

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # 将生成的页面路径存储到state中，供前端获取
            if not hasattr(state, '_generated_pages'):
                state._generated_pages = {}
            state._generated_pages[page_num] = html_path.replace("\\", "/")

            logger.info(f"Slide {page_num} generated and saved to {html_path}", agent_name="TaskPlanner")

            return state

        except Exception as e:
            logger.error(f"Failed to generate slide {page_num}: {str(e)}", agent_name="TaskPlanner")
            state.set_last_error(f"生成第{page_num}页失败: {str(e)}")
            return state

    def _generate_slides_parallel_batched(self, state: WorkflowState) -> WorkflowState:
        """
        分批并行生成幻灯片（每批最多5页）

        Args:
            state: 工作流状态

        Returns:
            更新后的状态
        """
        try:
            # 获取outline
            outline = state.slide_outline
            if isinstance(outline, dict):
                outline_list = outline.get("outline", [])
                creation_order = outline.get("creation_order", {})
            elif isinstance(outline, str):
                import json
                parsed = json.loads(outline)
                outline_list = parsed.get("outline", [])
                creation_order = parsed.get("creation_order", {})
            else:
                outline_list = outline
                creation_order = {}

            # 获取并行页面列表
            parallel_pages = creation_order.get("parallel", [])
            if not parallel_pages:
                logger.warning("No parallel pages found", agent_name="TaskPlanner")
                return state

            logger.info(f"Generating {len(parallel_pages)} pages in parallel (max 5 per batch)", agent_name="TaskPlanner")

            # 分批处理，每批最多3页
            BATCH_SIZE = 3
            for i in range(0, len(parallel_pages), BATCH_SIZE):
                batch = parallel_pages[i:i+BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                total_batches = (len(parallel_pages) + BATCH_SIZE - 1) // BATCH_SIZE

                logger.info(
                    f"Processing batch {batch_num}/{total_batches}: pages {batch}",
                    agent_name="TaskPlanner"
                )

                # 构建页面列表
                slide_list = []
                for page_num in batch:
                    page_info = next((s for s in outline_list if s["page"] == page_num), None)
                    if page_info:
                        slide_list.append(page_info)

                # 调用原有的并行生成方法
                if slide_list:
                    from src.utils.parallel_slide_manager import ParallelSlideManager
                    manager = ParallelSlideManager(max_workers=5)

                    results = manager.generate_slides_batch(
                        slide_list=slide_list,
                        template_cache=state.slide_templates or {},
                        extracted_data=state.slide_data or {},
                        generator=self.agent.generator,
                        batch_size=len(slide_list)
                    )

                    # 保存结果（results是列表）
                    if not state.generated_slides:
                        state.generated_slides = {}

                    for result in results:
                        page_num = result.get("page_number")
                        if page_num:
                            state.generated_slides[page_num] = result

                            # 立即保存HTML
                            self._save_slide_html(state, page_num, result)

            logger.info(f"Parallel generation completed: {len(parallel_pages)} pages", agent_name="TaskPlanner")
            return state

        except Exception as e:
            logger.error(f"Parallel generation failed: {str(e)}", agent_name="TaskPlanner")
            state.set_last_error(f"并行生成失败: {str(e)}")
            return state

    def _save_slide_html(self, state: WorkflowState, page_num: int, result: dict):
        """保存单个幻灯片HTML文件"""
        import os
        from datetime import datetime

        # 获取或创建任务目录
        output_dir = "examples/sample_reports"
        if not hasattr(state, '_task_dir') or not state._task_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            task_id = state.workflow_id[:8] if state.workflow_id else "unknown"
            task_dir = os.path.join(output_dir, f"task_{task_id}_{timestamp}")
            os.makedirs(task_dir, exist_ok=True)
            state._task_dir = task_dir
        else:
            task_dir = state._task_dir

        # 保存HTML文件
        html_filename = f"slide_{page_num:03d}.html"
        html_path = os.path.join(task_dir, html_filename)

        # 直接使用生成的HTML内容，不添加额外包装
        html_content = result.get("html_content", "")

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        # 存储到state
        if not hasattr(state, '_generated_pages'):
            state._generated_pages = {}
        state._generated_pages[page_num] = html_path.replace("\\", "/")

        logger.info(f"Saved slide {page_num} to {html_path}", agent_name="TaskPlanner")

    def plan_tasks(self, user_request: str, has_files: bool, conversation_history: list = None, intent_analysis: dict = None) -> list:
        """
        使用LLM规划任务列表

        Args:
            user_request: 用户请求
            has_files: 是否上传了文件
            conversation_history: 对话历史
            intent_analysis: 意图分析结果

        Returns:
            任务列表 [{"task_id": 1, "tool": "analyze_document", "description": "分析PDF文档"}]
        """
        logger.info(f"Planning tasks for request: {user_request}", agent_name="TaskPlanner")

        # 构建工具描述
        tools_desc = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.available_tools.items()
        ])

        # 检查对话历史中是否已有文档分析和大纲
        has_previous_analysis = False
        has_previous_outline = False
        has_previous_slides = False
        if conversation_history:
            for msg in conversation_history:
                if msg.get('role') == 'assistant' and 'session_state' in msg:
                    state = msg.get('session_state', {})
                    if state.get('file_processing_results'):
                        has_previous_analysis = True
                    if state.get('outline'):
                        has_previous_outline = True
                    if state.get('slides_generated'):
                        has_previous_slides = True

        # 构建上下文信息
        context_info = f"""
【对话上下文】
- 已有文档分析: {'是' if has_previous_analysis else '否'}
- 已有PPT大纲: {'是' if has_previous_outline else '否'}
- 已有生成的幻灯片: {'是' if has_previous_slides else '否'}
"""

        # 如果有意图分析结果，添加到上下文
        intent_info = ""
        if intent_analysis:
            intent_type = intent_analysis.get('intent_type', 'unknown')
            intent_info = f"""
【意图分析结果】
- 意图类型: {intent_type}
"""

        planning_prompt = f"""你是一个智能任务规划助手，需要根据用户请求规划执行步骤。

【用户请求】
{user_request}

【文件上传情况】
{'已上传文件' if has_files else '未上传文件'}
{context_info}
{intent_info}

【可用工具】
{tools_desc}

【规划要求】
1. 分析用户意图，确定需要执行的工具序列
2. 返回JSON数组格式的任务列表
3. 每个任务包含: task_id(数字), tool(工具名), description(任务描述)
4. 对于 generate_single_slide 工具，必须包含 page_num 参数（从用户请求中提取页码）
5. 任务顺序应该符合逻辑
6. 注意：大纲创建后，系统会自动生成细粒度的页面制作任务

【典型场景】
- 生成新PPT: analyze_user_intent → analyze_document → create_outline (后续任务会根据大纲自动生成)
- 仅分析文档: analyze_user_intent → analyze_document
- 优化已有PPT（单页）: analyze_user_intent → generate_single_slide (跳过文档分析和大纲，直接优化指定页)
- 优化已有PPT（多页）: analyze_user_intent → create_outline (跳过文档分析，只更新大纲)

【重要规则】
- 如果对话上下文中已有文档分析结果，且本次请求是优化单个页面，则跳过 analyze_document 和 create_outline
- 如果对话上下文中已有大纲和幻灯片，且本次请求只是优化个别页面，则只需要 analyze_user_intent 和 generate_single_slide
- 使用 generate_single_slide 时，必须从用户请求中提取页码并添加 page_num 字段

【输出格式】
直接返回JSON数组，不要添加markdown代码块标记:
示例1 - 生成新PPT:
[
  {{"task_id": 1, "tool": "analyze_user_intent", "description": "分析用户意图"}},
  {{"task_id": 2, "tool": "analyze_document", "description": "分析PDF文档内容"}},
  {{"task_id": 3, "tool": "create_outline", "description": "创建PPT大纲"}}
]

示例2 - 优化第4页:
[
  {{"task_id": 1, "tool": "analyze_user_intent", "description": "分析用户意图"}},
  {{"task_id": 2, "tool": "generate_single_slide", "page_num": 4, "description": "优化第4页"}}
]
"""

        try:
            logger.info(f"LLM planning : {planning_prompt}", agent_name="TaskPlanner")
            llm_response = generate_system_response(
                system_prompt="你是一个专业的任务规划专家，擅长将用户需求拆解为可执行的步骤序列。",
                user_message=planning_prompt,
                temperature=0.7,
                max_tokens=1000
            )

            logger.info(f"LLM planning response: {llm_response}", agent_name="TaskPlanner")

            # 提取JSON
            import re
            json_match = re.search(r'\[[\s\S]*?\]', llm_response)
            if json_match:
                task_list = json.loads(json_match.group())

                # 验证任务列表
                valid_tasks = []
                for task in task_list:
                    if task.get("tool") in self.available_tools:
                        valid_tasks.append(task)
                    else:
                        logger.warning(f"Invalid tool in task: {task}", agent_name="TaskPlanner")

                logger.info(f"Planned {len(valid_tasks)} tasks", agent_name="TaskPlanner")
                return valid_tasks
            else:
                logger.warning("Failed to extract JSON from LLM response", agent_name="TaskPlanner")
                return self._fallback_plan(has_files)

        except Exception as e:
            logger.error(f"Task planning failed: {str(e)}", agent_name="TaskPlanner")
            return self._fallback_plan(has_files)

    def _fallback_plan(self, has_files: bool) -> list:
        """兜底任务规划（初始粗粒度任务，大纲后会细化）"""
        if has_files:
            return [
                {"task_id": 1, "tool": "analyze_user_intent", "description": "分析用户意图"},
                {"task_id": 2, "tool": "analyze_document", "description": "分析文档内容"},
                {"task_id": 3, "tool": "create_outline", "description": "创建PPT大纲"}
                # 注意：后续任务会在create_outline完成后根据大纲自动生成
            ]
        else:
            return [
                {"task_id": 1, "tool": "analyze_user_intent", "description": "分析用户意图"}
            ]

    def plan_detailed_tasks(self, state: WorkflowState, start_task_id: int = 4) -> list:
        """
        根据大纲创建细粒度任务列表（GenSpark风格）

        Args:
            state: 包含slide_outline的工作流状态
            start_task_id: 起始任务ID（前面任务已完成）

        Returns:
            细粒度任务列表
        """
        if not state.slide_outline:
            logger.warning("No outline found, cannot plan detailed tasks", agent_name="TaskPlanner")
            return []

        # Extract outline list from the outline result dict
        outline_data = state.slide_outline
        logger.info(f"Outline data type: {type(outline_data)}", agent_name="TaskPlanner")

        # If it's a dict, extract the 'outline' key
        if isinstance(outline_data, dict):
            outline = outline_data.get("outline", [])
        elif isinstance(outline_data, str):
            import json
            try:
                parsed = json.loads(outline_data)
                outline = parsed.get("outline", []) if isinstance(parsed, dict) else parsed
            except Exception as e:
                logger.error(f"Failed to parse outline JSON: {e}", agent_name="TaskPlanner")
                return []
        else:
            outline = outline_data

        if not outline:
            logger.warning("No outline list found", agent_name="TaskPlanner")
            return []

        creation_order = self.agent.outliner._calculate_creation_order(outline)
        serial_pages = creation_order.get("serial", [])
        parallel_pages = creation_order.get("parallel", [])

        detailed_tasks = []
        current_id = start_task_id

        # 为每个串行页面创建单独任务
        for page_num in serial_pages:
            page_info = next((s for s in outline if s["page"] == page_num), None)
            if page_info:
                template_name = page_info.get("template", "未知模板")
                title = page_info.get("title", f"第{page_num}页")
                detailed_tasks.append({
                    "task_id": current_id,
                    "tool": "generate_single_slide",
                    "description": f"制作第{page_num}页：{title}({template_name})",
                    "page_num": page_num
                })
                current_id += 1

        # 并行页面作为一个批量任务
        if parallel_pages:
            page_range = f"{min(parallel_pages)}-{max(parallel_pages)}"
            detailed_tasks.append({
                "task_id": current_id,
                "tool": "generate_content_slides_parallel",
                "description": f"并行制作第{page_range}页"
            })
            current_id += 1

        # 最后组装
        detailed_tasks.append({
            "task_id": current_id,
            "tool": "assemble_all_slides",
            "description": "组装所有幻灯片"
        })

        logger.info(f"Planned {len(detailed_tasks)} detailed tasks", agent_name="TaskPlanner")
        return detailed_tasks

    def execute_task(self, task: dict, state: WorkflowState) -> WorkflowState:
        """
        执行单个任务

        Args:
            task: 任务字典（可能包含额外参数如page_num）
            state: 当前状态

        Returns:
            更新后的状态
        """
        tool_name = task["tool"]
        logger.info(f"Executing task {task['task_id']}: {tool_name}", agent_name="TaskPlanner")

        if tool_name not in self.available_tools:
            logger.error(f"Unknown tool: {tool_name}", agent_name="TaskPlanner")
            return state

        tool_method = self.available_tools[tool_name]["method"]

        try:
            # 检查任务是否包含额外参数（如page_num）
            if "page_num" in task:
                updated_state = tool_method(state, page_num=task["page_num"])
            else:
                updated_state = tool_method(state)

            logger.info(f"Task {task['task_id']} completed successfully", agent_name="TaskPlanner")
            return updated_state
        except Exception as e:
            logger.error(f"Task {task['task_id']} failed: {str(e)}", agent_name="TaskPlanner")
            return state


# =========================
# HTML模板
# =========================

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PPT AI助手 (动态规划版)</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif; background: #f5f7fa; height: 100vh; overflow: hidden; }
        .container { background: white; width: 100%; height: 100vh; display: flex; overflow: hidden; }

        /* 左侧面板 */
        .left-panel { width: 380px; min-width: 380px; border-right: 1px solid #e5e7eb; display: flex; flex-direction: column; }
        .chat-header { padding: 20px; border-bottom: 1px solid #e5e7eb; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .chat-title { font-size: 18px; font-weight: 600; margin-bottom: 5px; }
        .chat-subtitle { font-size: 13px; opacity: 0.9; }

        /* 聊天区域 */
        .messages { flex: 1; overflow-y: auto; padding: 15px; max-height: 45%; border-bottom: 1px solid #e5e7eb; }
        .message { margin-bottom: 12px; animation: fadeIn 0.3s; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .user-msg { background: #667eea; color: white; padding: 10px 14px; border-radius: 16px 16px 4px 16px; margin-left: 30px; word-wrap: break-word; font-size: 14px; }
        .ai-msg { background: #f3f4f6; color: #1f2937; padding: 10px 14px; border-radius: 16px 16px 16px 4px; margin-right: 30px; word-wrap: break-word; font-size: 14px; }

        /* 任务面板 */
        .task-panel { flex: 1; overflow-y: auto; padding: 15px; background: #fafbfc; }
        .task-panel-title { font-size: 14px; font-weight: 600; color: #374151; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 2px solid #e5e7eb; }
        .task-item { background: white; border-left: 3px solid #3b82f6; padding: 10px 12px; margin: 8px 0; border-radius: 4px; font-size: 13px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .task-completed { background: #f0fdf4; border-left-color: #22c55e; }
        .task-active { background: #fef3c7; border-left-color: #f59e0b; animation: pulse 2s infinite; }
        .task-failed { background: #fef2f2; border-left-color: #ef4444; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.8; } }

        .progress-bar { height: 6px; background: #e5e7eb; border-radius: 3px; margin: 8px 0; overflow: hidden; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #667eea, #764ba2); transition: width 0.3s; }

        /* 输入区域 */
        .input-area { padding: 15px; border-top: 1px solid #e5e7eb; background: white; }
        input[type="text"] { width: 100%; padding: 10px; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 14px; }
        input[type="file"] { margin-bottom: 8px; font-size: 12px; }
        button { width: 100%; padding: 10px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; margin-top: 8px; font-size: 14px; transition: all 0.3s ease; }
        button:hover:not(:disabled) { opacity: 0.9; transform: translateY(-1px); }
        button:disabled { background: #9ca3af; cursor: not-allowed; opacity: 0.6; }
        input:disabled { background: #f3f4f6; cursor: not-allowed; }

        /* 右侧预览面板 */
        .preview-panel { flex: 1; display: flex; flex-direction: column; background: #f9fafb; }
        .preview-header { padding: 15px 20px; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center; background: white; }
        .preview-header h3 { font-size: 16px; color: #374151; }
        .preview-controls { display: flex; gap: 10px; }
        .preview-controls button { width: auto; padding: 6px 12px; font-size: 13px; margin: 0; }
        .preview-content {
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
            padding: 20px;
            background: #f0f2f5;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }
        .slide-frame {
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            border-radius: 4px;
            position: relative;
            width: 100%;
            max-width: 1400px;
            aspect-ratio: 16 / 9;
            flex-shrink: 0;
            overflow: hidden;
        }
        .slide-frame iframe {
            width: 1920px;
            height: 1080px;
            border: none;
            display: block;
            transform-origin: top left;
        }
        .slide-placeholder {
            background: #fafafa;
            border: 2px dashed #d1d5db;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #9ca3af;
            font-size: 16px;
        }
        .slide-page-number {
            position: absolute;
            top: -30px;
            left: 0;
            color: #6b7280;
            font-size: 13px;
            font-weight: 500;
        }
        .preview-placeholder { color: #9ca3af; font-size: 14px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <!-- 左侧面板：聊天 + 任务 -->
        <div class="left-panel">
            <div class="chat-header">
                <div class="chat-title">PPT AI助手</div>
                <div class="chat-subtitle">动态任务规划 · 智能生成</div>
            </div>
            <div class="messages" id="messages"></div>
            <div class="task-panel">
                <div class="task-panel-title">📋 任务执行面板</div>
                <div id="taskPanel"></div>
            </div>
            <div class="input-area">
                <input type="file" id="fileInput" accept=".pdf,.doc,.docx,.txt,.md" />
                <input type="text" id="messageInput" placeholder="描述您的需求，例如：生成5页PPT..." />
                <button onclick="sendMessage()">发送</button>
            </div>
        </div>

        <!-- 右侧面板：PPT预览 -->
        <div class="preview-panel">
            <div class="preview-header">
                <h3>🎨 PPT 预览</h3>
                <div class="preview-controls">
                    <button onclick="exportToPDF()" id="exportPDFBtn" disabled>📄 导出PDF</button>
                    <button onclick="refreshPreview()">🔄 刷新</button>
                </div>
            </div>
            <div class="preview-content" id="previewContent">
                <div class="preview-placeholder">PPT 预览区域<br>生成完成后将在此显示</div>
            </div>
        </div>
    </div>

    <script>
        let sessionId = generateUUID();
        let conversationHistory = []; // 对话历史消息
        let currentSessionState = {
            task_list: [],
            slides_generated: {},
            outline: null,
            file_processing_results: {}
        }; // 当前会话状态
        let isProcessing = false; // 标记是否正在处理请求
        let currentTaskDir = null; // 当前任务目录路径

        function generateUUID() {
            return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
                const r = Math.random() * 16 | 0;
                return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
            });
        }

        function addMessage(content, isUser = false, metadata = {}) {
            const messagesDiv = document.getElementById('messages');
            const msgDiv = document.createElement('div');
            msgDiv.className = 'message';
            msgDiv.innerHTML = `<div class="${isUser ? 'user-msg' : 'ai-msg'}">${content}</div>`;
            messagesDiv.appendChild(msgDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;

            // 添加到对话历史（GenSpark格式）
            const message = {
                id: generateUUID(),
                role: isUser ? 'user' : 'assistant',
                content: content,
                timestamp: new Date().toISOString(),
                ...metadata
            };

            conversationHistory.push(message);
        }

        function addAssistantMessageWithState(content, sessionState = null) {
            // 添加带session_state的assistant消息
            const metadata = {};
            if (sessionState) {
                metadata.session_state = sessionState;
            }
            addMessage(content, false, metadata);
        }

        function updateTaskPanel(tasks) {
            const panel = document.getElementById('taskPanel');
            panel.innerHTML = tasks.map(task => {
                let cssClass = '';
                let icon = '○';

                if (task.status === 'completed') {
                    cssClass = 'task-completed';
                    icon = '✓';
                } else if (task.status === 'in_progress') {
                    cssClass = 'task-active';
                    icon = '▶';
                } else if (task.status === 'failed') {
                    cssClass = 'task-failed';
                    icon = '✗';
                }

                return `<div class="task-item ${cssClass}">
                    ${icon} ${task.description}
                </div>`;
            }).join('');
        }

        async function sendMessage() {
            // 如果正在处理请求，忽略
            if (isProcessing) {
                return;
            }

            const input = document.getElementById('messageInput');
            const fileInput = document.getElementById('fileInput');
            const sendButton = document.querySelector('button');
            const message = input.value.trim();

            if (!message && !fileInput.files.length) {
                alert('请输入消息或上传文件');
                return;
            }

            // 设置处理状态
            isProcessing = true;
            sendButton.disabled = true;
            sendButton.style.opacity = '0.5';
            sendButton.style.cursor = 'not-allowed';
            sendButton.textContent = '处理中...';
            input.disabled = true;
            fileInput.disabled = true;

            addMessage(message, true);
            input.value = '';

            const formData = new FormData();
            formData.append('message', message);
            formData.append('session_id', sessionId);

            // 精简对话历史：移除HTML内容以避免413错误
            // 只保留最近20条消息，避免payload过大
            const recentHistory = conversationHistory.slice(-20);
            const compactHistory = recentHistory.map(msg => {
                const compact = {
                    id: msg.id,
                    role: msg.role,
                    content: msg.content.length > 200 ? msg.content.substring(0, 200) + '...' : msg.content,
                    timestamp: msg.timestamp
                };

                // 精简session_state：移除HTML内容，只保留元数据
                if (msg.session_state) {
                    compact.session_state = {
                        tasks: msg.session_state.tasks,
                        outline: msg.session_state.outline ? {
                            total_pages: msg.session_state.outline.total_pages
                            // 不包含完整大纲数据
                        } : null,
                        // 精简file_processing_results，移除大量文本内容
                        file_processing_results: msg.session_state.file_processing_results ?
                            Object.keys(msg.session_state.file_processing_results).reduce((acc, key) => {
                                acc[key] = { processed: true }; // 只标记已处理
                                return acc;
                            }, {}) : {},
                        // 精简slides_generated，只保留页码信息
                        slides_generated: msg.session_state.slides_generated ?
                            Object.keys(msg.session_state.slides_generated).reduce((acc, key) => {
                                acc[key] = { generated: true }; // 只标记已生成
                                return acc;
                            }, {}) : {}
                        // 不包含 slides (HTML内容太大)
                    };
                }

                return compact;
            });

            formData.append('conversation_history', JSON.stringify(compactHistory));

            if (fileInput.files.length > 0) {
                formData.append('file', fileInput.files[0]);
            }

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    body: formData
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const {value, done} = await reader.read();
                    if (done) {
                        // 请求完成，恢复按钮状态
                        isProcessing = false;
                        sendButton.disabled = false;
                        sendButton.style.opacity = '1';
                        sendButton.style.cursor = 'pointer';
                        sendButton.textContent = '发送';
                        input.disabled = false;
                        fileInput.disabled = false;
                        fileInput.value = '';
                        break;
                    }

                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\\n\\n');

                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = JSON.parse(line.slice(6));

                            if (data.type === 'task_plan') {
                                updateTaskPanel(data.tasks);
                                currentSessionState.task_list = data.tasks;
                                addAssistantMessageWithState(`规划了${data.tasks.length}个任务`, {
                                    task_list: data.tasks
                                });
                            } else if (data.type === 'task_update') {
                                updateTaskPanel(data.tasks);
                                currentSessionState.task_list = data.tasks;
                            } else if (data.type === 'init_slides') {
                                // 初始化空白占位符
                                initSlidePlaceholders(data.total_pages);
                                currentSessionState.outline = {total_pages: data.total_pages};
                                addAssistantMessageWithState(`准备生成 ${data.total_pages} 页PPT...`, {
                                    outline: currentSessionState.outline
                                });
                            } else if (data.type === 'progress') {
                                addMessage(`<div class="progress-bar"><div class="progress-fill" style="width: ${data.progress}%"></div></div>${data.step}`);
                            } else if (data.type === 'response') {
                                addMessage(data.content);
                            } else if (data.type === 'slide_preview') {
                                // 填充单个页面
                                fillSlide(data.page_num, data.html_path);

                                // 从html_path提取任务目录（例如：examples/sample_reports/task_xxx）
                                const pathParts = data.html_path.split('/');
                                if (pathParts.length >= 3) {
                                    currentTaskDir = pathParts.slice(0, -1).join('/');
                                    // 启用导出按钮
                                    document.getElementById('exportPDFBtn').disabled = false;
                                }

                                // 只保存路径和元数据，不保存HTML内容（避免payload过大）
                                currentSessionState.slides_generated[data.page_num] = {
                                    html_path: data.html_path,
                                    generated: true
                                };
                                addAssistantMessageWithState(`✓ 第${data.page_num}页生成完成`, {
                                    slides_generated: currentSessionState.slides_generated
                                });
                            } else if (data.type === 'ppt_preview') {
                                // 显示PPT预览
                                showPPTPreview(data.html_path);
                            } else if (data.type === 'complete') {
                                addMessage('✓ 任务完成');
                            }
                        }
                    }
                }
            } catch (error) {
                addMessage('错误: ' + error.message);

                // 发生错误时恢复按钮状态
                isProcessing = false;
                sendButton.disabled = false;
                sendButton.style.opacity = '1';
                sendButton.style.cursor = 'pointer';
                sendButton.textContent = '发送';
                input.disabled = false;
                fileInput.disabled = false;
                fileInput.value = '';
            }
        }

        function initSlidePlaceholders(totalPages) {
            const previewContent = document.getElementById('previewContent');
            previewContent.innerHTML = '';

            for (let i = 1; i <= totalPages; i++) {
                const slideDiv = document.createElement('div');
                slideDiv.className = 'slide-frame slide-placeholder';
                slideDiv.id = `slide-${i}`;
                slideDiv.innerHTML = `
                    <div class="slide-page-number">第 ${i} 页 / 共 ${totalPages} 页</div>
                    <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;">
                        等待生成...
                    </div>
                `;
                previewContent.appendChild(slideDiv);
            }
        }

        function fillSlide(pageNum, htmlPath) {
            const slideDiv = document.getElementById(`slide-${pageNum}`);
            if (slideDiv) {
                slideDiv.className = 'slide-frame';
                slideDiv.innerHTML = `
                    <div class="slide-page-number">第 ${pageNum} 页</div>
                    <iframe src="${htmlPath}"></iframe>
                `;

                // 等待iframe加载后应用缩放
                setTimeout(() => {
                    scaleIframe(slideDiv);
                }, 200);
            }
        }

        function scaleIframe(slideDiv) {
            const iframe = slideDiv.querySelector('iframe');
            if (!iframe) return;

            const containerWidth = slideDiv.clientWidth;
            const containerHeight = slideDiv.clientHeight;

            // iframe原始尺寸 1920x1080
            const iframeWidth = 1920;
            const iframeHeight = 1080;

            // 计算缩放比例
            const scaleX = containerWidth / iframeWidth;
            const scaleY = containerHeight / iframeHeight;
            const scale = Math.min(scaleX, scaleY);

            // 应用缩放
            iframe.style.transform = `scale(${scale})`;

            console.log(`Iframe scaled to ${(scale * 100).toFixed(2)}% (container: ${containerWidth}x${containerHeight})`);
        }

        // 窗口调整大小时重新缩放所有iframe
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                document.querySelectorAll('.slide-frame').forEach(scaleIframe);
            }, 100);
        });

        function showPPTPreview(htmlPath) {
            // 已经使用垂直平铺方式，不需要替换内容
            // 只是滚动到顶部
            const previewContent = document.getElementById('previewContent');
            previewContent.scrollTop = 0;
            console.log('PPT preview ready (using vertical layout)');
        }

        function refreshPreview() {
            const iframes = document.querySelectorAll('.preview-content iframe');
            iframes.forEach(iframe => {
                iframe.src = iframe.src;
            });
        }

        async function exportToPDF() {
            if (!currentTaskDir) {
                alert('没有可导出的任务目录');
                return;
            }

            const exportBtn = document.getElementById('exportPDFBtn');
            const originalText = exportBtn.textContent;

            try {
                // 禁用按钮
                exportBtn.disabled = true;
                exportBtn.textContent = '⏳ 导出中...';

                // 发送导出请求
                const response = await fetch('/export_pdf', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        task_dir: currentTaskDir
                    })
                });

                const result = await response.json();

                if (result.success) {
                    // 显示成功消息
                    addMessage(`✓ PDF导出成功！<br>` +
                               `单页数量: ${result.page_count}<br>` +
                               `合并文件: <a href="${result.merged_pdf}" target="_blank">${result.merged_pdf.split('/').pop()}</a>`, false);

                    // 自动下载合并的PDF
                    const link = document.createElement('a');
                    link.href = result.merged_pdf;
                    link.download = result.merged_pdf.split('/').pop();
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    addMessage(`❌ PDF导出失败: ${result.error}`, false);
                }
            } catch (error) {
                addMessage(`❌ 导出错误: ${error.message}`, false);
            } finally {
                // 恢复按钮
                exportBtn.disabled = false;
                exportBtn.textContent = originalText;
            }
        }

        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !isProcessing) {
                sendMessage();
            }
        });
    </script>
</body>
</html>
'''


# =========================
# Flask路由
# =========================

@app.route('/')
def index():
    """主页"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/chat', methods=['POST'])
def chat():
    """动态任务规划聊天接口（SSE流式响应）"""
    # ⚠️ Fix: 在生成器外部提前提取所有request数据，避免"Working outside of request context"错误
    # 原因: Response().stream的generator执行时已脱离Flask request上下文
    session_id = request.form.get('session_id', str(uuid.uuid4()))
    message = request.form.get('message', '').strip()

    # 获取对话历史
    conversation_history_json = request.form.get('conversation_history', '[]')
    try:
        conversation_history = json.loads(conversation_history_json)
    except:
        conversation_history = []
        logger.warning("Failed to parse conversation_history")

    # 文件上传处理
    uploaded_files = []
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, f"{session_id}_{filename}")
            file.save(filepath)
            uploaded_files.append(filepath)
            logger.info(f"File uploaded: {filepath}")

    def generate():
        try:

            # 获取或创建session状态
            if session_id not in sessions:
                # create_workflow_state需要workflow_id和user_request参数
                sessions[session_id] = create_workflow_state(
                    workflow_id=session_id,
                    user_request=message
                )

            current_state = sessions[session_id]

            # 从对话历史中提取已分析的文件信息
            analyzed_files = set()
            for msg in conversation_history:
                if msg.get('role') == 'assistant' and 'session_state' in msg:
                    state = msg.get('session_state', {})
                    if 'file_processing_results' in state and state['file_processing_results']:
                        # 现在file_processing_results只包含 {file_id: {processed: true}}
                        for file_id in state['file_processing_results'].keys():
                            analyzed_files.add(file_id)

            # 处理文件上传：只有本次请求上传了新文件才更新
            has_new_files = len(uploaded_files) > 0
            if has_new_files:
                # 将路径列表转换为字典列表
                file_dicts = [{"file_path": fp} for fp in uploaded_files]
                current_state.uploaded_files = file_dicts
                logger.info(f"New files uploaded: {uploaded_files}")
            else:
                # 没有新上传文件
                # 检查对话历史中是否有已分析的文件，如果有则不需要重新上传文件
                if analyzed_files:
                    logger.info(f"Found {len(analyzed_files)} analyzed files in conversation history, skipping file requirement")
                    # 清空uploaded_files，避免任务规划认为有文件
                    current_state.uploaded_files = []
                    has_new_files = False  # 标记为无新文件
                elif current_state.uploaded_files:
                    logger.info("No new files uploaded, clearing old files")
                    current_state.uploaded_files = []

            # 更新用户请求
            if message and current_state.user_request != message:
                current_state.user_request = message
                logger.info(f"Updated user_request to: {message}")

            # 存储对话历史到state的user_inputs中
            current_state.user_inputs["conversation_history"] = conversation_history
            logger.info(f"Stored conversation history with {len(conversation_history)} messages")

            # 从对话历史中恢复之前的状态信息（文档分析、大纲等）
            # 注意：由于传递的是精简数据，我们只能判断是否存在，不能恢复完整内容
            # 完整内容已经保存在current_state中
            has_previous_file_analysis = False
            has_previous_outline = False

            if conversation_history:
                for msg in reversed(conversation_history):  # 从最新消息向前查找
                    if msg.get('role') == 'assistant' and 'session_state' in msg:
                        state_data = msg.get('session_state', {})

                        # 检查是否有文档分析（精简数据只包含标记）
                        if state_data.get('file_processing_results'):
                            has_previous_file_analysis = True

                        # 检查是否有大纲（精简数据只包含总页数）
                        if state_data.get('outline') and state_data['outline'].get('total_pages'):
                            has_previous_outline = True

                        # 如果两者都找到了标记，就不需要继续查找
                        if has_previous_file_analysis and has_previous_outline:
                            break

            # 日志记录状态恢复情况
            if has_previous_file_analysis:
                logger.info("Found file analysis marker in conversation history")
            if has_previous_outline:
                logger.info("Found outline marker in conversation history")

            # 步骤1: 使用LLM规划任务
            yield f"data: {safe_sse_json({'type': 'progress', 'step': '正在规划任务...', 'progress': 5})}\n\n"

            planner = DynamicTaskPlanner(slide_workflow_agent)
            # 传递对话历史供任务规划使用
            tasks = planner.plan_tasks(message, has_new_files, conversation_history=conversation_history)

            # 添加状态字段
            task_list = [
                {**task, "status": "pending"}
                for task in tasks
            ]

            # 发送任务计划
            yield f"data: {safe_sse_json({'type': 'task_plan', 'tasks': task_list})}\n\n"

            # 步骤2: 逐个执行任务（使用while循环支持动态任务列表）
            idx = 0
            while idx < len(task_list):
                task = task_list[idx]
                total_tasks = len(task_list)

                # 更新任务状态为进行中
                task_list[idx]["status"] = "in_progress"
                yield f"data: {safe_sse_json({'type': 'task_update', 'tasks': task_list})}\n\n"

                progress = int((idx + 1) / total_tasks * 90) + 5
                task_desc = task["description"]
                yield f"data: {safe_sse_json({'type': 'progress', 'step': f'执行: {task_desc}', 'progress': progress})}\n\n"

                # 执行任务
                current_state = planner.execute_task(task, current_state)

                # 检查工作流状态是否失败
                from src.graph.state import WorkflowStatus
                if hasattr(current_state, 'workflow_status') and current_state.workflow_status == WorkflowStatus.FAILED:
                    # 任务失败，获取错误信息
                    error_message = current_state.last_error or "任务执行失败"
                    logger.error(f"Workflow failed: {error_message}", agent_name="Chat")

                    # 更新任务状态为失败
                    task_list[idx]["status"] = "failed"
                    yield f"data: {safe_sse_json({'type': 'task_update', 'tasks': task_list})}\n\n"

                    # 发送错误消息
                    error_response = f"❌ {error_message}"
                    yield f"data: {safe_sse_json({'type': 'error', 'content': error_response})}\n\n"
                    yield f"data: {safe_sse_json({'type': 'complete'})}\n\n"

                    # 保存失败状态
                    sessions[session_id] = current_state
                    return

                # 更新任务状态为完成
                task_list[idx]["status"] = "completed"
                yield f"data: {safe_sse_json({'type': 'task_update', 'tasks': task_list})}\n\n"

                # 特殊处理：大纲创建后，生成细粒度任务列表
                if task["tool"] == "create_outline" and current_state.slide_outline:
                    logger.info("Outline created, planning detailed tasks", agent_name="Chat")

                    # 获取总页数并发送初始化事件
                    outline_data = current_state.slide_outline
                    total_pages = outline_data.get("total_slides", 0) if isinstance(outline_data, dict) else 0
                    if total_pages > 0:
                        init_data = {'type': 'init_slides', 'total_pages': total_pages}
                        yield f"data: {safe_sse_json(init_data)}\n\n"
                        logger.info(f"Initialized {total_pages} slide placeholders", agent_name="Chat")

                    # 生成细粒度任务
                    detailed_tasks = planner.plan_detailed_tasks(current_state, start_task_id=idx+2)

                    if detailed_tasks:
                        # 移除原有的generate_template_slides和generate_content_slides_parallel任务
                        remaining_tasks = [t for t in task_list[idx+1:]
                                         if t["tool"] not in ["generate_template_slides", "generate_content_slides_parallel"]]

                        # 插入细粒度任务
                        task_list = task_list[:idx+1] + [
                            {**t, "status": "pending"} for t in detailed_tasks
                        ] + remaining_tasks

                        # 发送更新后的任务列表
                        yield f"data: {safe_sse_json({'type': 'task_plan', 'tasks': task_list})}\n\n"
                        logger.info(f"Updated task list with {len(detailed_tasks)} detailed tasks", agent_name="Chat")

                # 特殊处理：单页生成完成后立即发送预览
                if task["tool"] == "generate_single_slide" and hasattr(current_state, '_generated_pages'):
                    page_num = task.get("page_num")
                    if page_num and page_num in current_state._generated_pages:
                        html_path = current_state._generated_pages[page_num]
                        preview_data = {
                            'type': 'slide_preview',
                            'page_num': page_num,
                            'html_path': html_path
                        }
                        yield f"data: {safe_sse_json(preview_data)}\n\n"
                        logger.info(f"Sent preview for page {page_num}: {html_path}", agent_name="Chat")

                # 特殊处理：并行生成完成后发送每页预览
                if task["tool"] == "generate_content_slides_parallel" and hasattr(current_state, '_generated_pages'):
                    for page_num, html_path in sorted(current_state._generated_pages.items()):
                        preview_data = {
                            'type': 'slide_preview',
                            'page_num': page_num,
                            'html_path': html_path
                        }
                        yield f"data: {safe_sse_json(preview_data)}\n\n"
                        logger.info(f"Sent preview for page {page_num}: {html_path}", agent_name="Chat")

                # 特殊处理：如果是意图分析，检查是否需要继续
                if task["tool"] == "analyze_user_intent":
                    # 从user_inputs中获取意图分析结果
                    intent_result = current_state.user_inputs.get("intent_analysis", {})

                    if not intent_result.get("should_proceed", True):
                        response_content = f"已理解您的请求。意图: {intent_result.get('intent_type', 'unknown')}"
                        yield f"data: {safe_sse_json({'type': 'response', 'content': response_content})}\n\n"
                        yield f"data: {safe_sse_json({'type': 'complete'})}\n\n"
                        return

                # 移动到下一个任务
                idx += 1

            # 步骤3: 返回最终结果
            if current_state.output_file:
                final_message = f"✅ PPT生成成功！共 {len(current_state.slides_content) if current_state.slides_content else 0} 页"

                # 发送HTML预览路径（output_file现在指向index.html）
                import os

                if os.path.exists(current_state.output_file):
                    # 构建Web访问路径
                    html_path = current_state.output_file.replace("\\", "/")

                    # 发送预览信息（不再需要pptx_path）
                    preview_data = {'type': 'ppt_preview', 'html_path': html_path}
                    yield f"data: {safe_sse_json(preview_data)}\n\n"
                    logger.info(f"Sending preview: {html_path}")
                else:
                    logger.warning(f"HTML index file not found: {current_state.output_file}")
            else:
                final_message = "任务执行完成"

            yield f"data: {safe_sse_json({'type': 'response', 'content': final_message})}\n\n"
            yield f"data: {safe_sse_json({'type': 'complete'})}\n\n"

            # 保存状态
            sessions[session_id] = current_state

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Chat error: {str(e)}\n{error_trace}")
            error_msg = f"错误: {str(e)}"
            yield f"data: {safe_sse_json({'type': 'error', 'content': error_msg})}\n\n"

    return Response(generate(), mimetype='text/event-stream')


@app.route('/reset', methods=['POST'])
def reset():
    """重置会话"""
    data = request.json
    session_id = data.get('session_id')

    if session_id in sessions:
        del sessions[session_id]

    return jsonify({"status": "ok"})


@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    """导出任务目录为PDF"""
    try:
        data = request.json
        task_dir = data.get('task_dir')

        if not task_dir:
            return jsonify({"success": False, "error": "未提供任务目录"}), 400

        # 导入PDF转换器
        from force_16_9_pdf import Force169PDFConverter

        task_path = Path(task_dir)
        if not task_path.exists() or not task_path.is_dir():
            return jsonify({"success": False, "error": f"任务目录不存在: {task_dir}"}), 404

        # 创建转换器（输出到源目录）
        logger.info(f"开始导出PDF: {task_dir}", agent_name="ExportPDF")

        try:
            converter = Force169PDFConverter(output_to_source=True)
        except RuntimeError as e:
            logger.error(f"PDF转换器初始化失败: {str(e)}", agent_name="ExportPDF")
            return jsonify({"success": False, "error": f"未找到Chrome浏览器: {str(e)}"}), 500

        # 转换目录中的所有HTML文件并自动合并
        pdf_files, merged_pdf = converter.convert_directory(str(task_path), auto_merge=True)

        if not pdf_files:
            return jsonify({"success": False, "error": "PDF转换失败，未生成任何文件"}), 500

        # 构建Web访问路径
        merged_pdf_web = merged_pdf.replace("\\", "/") if merged_pdf else None

        logger.info(f"PDF导出成功: {len(pdf_files)} 页, 合并文件: {merged_pdf}", agent_name="ExportPDF")

        return jsonify({
            "success": True,
            "page_count": len(pdf_files),
            "pdf_files": [str(p).replace("\\", "/") for p in pdf_files],
            "merged_pdf": merged_pdf_web,
            "task_dir": task_dir
        })

    except Exception as e:
        logger.error(f"PDF导出失败: {str(e)}", agent_name="ExportPDF")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/static/<path:filepath>')
def serve_static(filepath):
    """提供本地CSS和字体文件访问"""
    import os
    from flask import send_file

    # 首先尝试从项目根目录的static文件夹查找
    static_dir = os.path.join(os.getcwd(), 'static')
    file_path = os.path.join(static_dir, filepath)
    
    # 如果根目录static文件夹不存在，尝试从src/templates目录查找
    if not os.path.exists(static_dir):
        static_dir = os.path.join(os.path.dirname(__file__), 'src', 'templates')
        file_path = os.path.join(static_dir, filepath)
    
    # 安全检查：确保文件在static_dir下
    abs_path = os.path.abspath(file_path)
    abs_static_dir = os.path.abspath(static_dir)
    
    if not abs_path.startswith(abs_static_dir):
        return "Forbidden", 403
    
    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        # 设置正确的MIME类型
        if filepath.endswith('.css'):
            return send_file(abs_path, mimetype='text/css')
        elif filepath.endswith('.woff2'):
            return send_file(abs_path, mimetype='font/woff2')
        elif filepath.endswith('.woff'):
            return send_file(abs_path, mimetype='font/woff')
        elif filepath.endswith('.ttf'):
            return send_file(abs_path, mimetype='font/ttf')
        elif filepath.endswith('.js'):
            return send_file(abs_path, mimetype='application/javascript')
        else:
            return send_file(abs_path)
    else:
        # 如果文件不存在，返回404并记录日志
        print(f"Static file not found: {abs_path}")
        return "File not found", 404


@app.route('/<path:filepath>')
def serve_file(filepath):
    """提供静态文件访问（HTML和PPTX）"""
    import os
    from flask import send_file

    # 安全检查：确保文件在工作目录下
    abs_path = os.path.abspath(filepath)
    work_dir = os.path.abspath(os.getcwd())

    if not abs_path.startswith(work_dir):
        return "Forbidden", 403

    if os.path.exists(abs_path) and os.path.isfile(abs_path):
        return send_file(abs_path)
    else:
        return "File not found", 404


if __name__ == '__main__':
    print("=" * 60)
    print("PPT AI助手 - 动态任务规划版")
    print("基于genspark.txt架构：LLM规划 → 动态执行")
    print("访问地址: http://127.0.0.1:5001")
    print("=" * 60)

    # 使用waitress作为生产级WSGI服务器（如果可用）
    try:
        from waitress import serve
        print("使用 Waitress WSGI 服务器...")
        serve(app, host='0.0.0.0', port=5001, threads=4)
    except ImportError:
        print("未安装 Waitress，使用 Flask 开发服务器...")
        print("提示: 生产环境请运行 'pip install waitress'")
        app.run(debug=False, host='0.0.0.0', port=5001)
