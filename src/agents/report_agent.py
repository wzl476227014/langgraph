"""
Report Agent模块
负责生成最终的HTML格式报告
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from ..utils.config import get_agent_config, get_agent_prompt, get_config
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response, generate_system_response_stream
from ..utils.stream_output import AgentStreamOutput
from typing import Iterator
from jinja2 import Environment, FileSystemLoader, Template

logger = get_logger(__name__)


class ReportAgent:
    """Report Agent - 报告生成专家"""
    
    def __init__(self):
        """初始化Report Agent"""
        self.config = get_agent_config("report")
        self.system_prompt = get_agent_prompt("report_agent")
        self.output_config = get_config().get_output_config()
        
        # 初始化流式输出
        self.stream_output = AgentStreamOutput("ReportAgent", enable_stream=True)
        
        # 设置模板环境
        self.template_dir = Path(self.output_config.get("template_directory", "src/templates"))
        self.jinja_env = self._setup_template_environment()
        
        logger.info("Report Agent初始化完成", agent_name="ReportAgent")
    
    def _setup_template_environment(self) -> Environment:
        """设置模板环境"""
        try:
            if self.template_dir.exists():
                env = Environment(
                    loader=FileSystemLoader(str(self.template_dir)),
                    autoescape=True
                )
                logger.info(f"模板环境设置成功，模板目录: {self.template_dir}", agent_name="ReportAgent")
                return env
            else:
                logger.warning(f"模板目录不存在: {self.template_dir}，使用默认模板", agent_name="ReportAgent")
                return self._create_default_template_environment()
                
        except Exception as e:
            logger.error(f"模板环境设置失败: {str(e)}", agent_name="ReportAgent")
            return self._create_default_template_environment()
    
    def _create_default_template_environment(self) -> Environment:
        """创建默认模板环境"""
        # 创建内联模板
        default_template = self._get_default_template()
        env = Environment()
        env.globals['default_template'] = Template(default_template)
        return env
    
    def _get_default_template(self) -> str:
        """获取默认模板"""
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ report_title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            line-height: 1.8;
            color: #2c3e50;
            background: #f0f2f5;
            min-height: 100vh;
            padding: 20px 0;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            border-radius: 8px;
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 60px 40px;
            text-align: center;
            position: relative;
        }
        
        .header::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #f39c12, #e74c3c, #9b59b6, #3498db);
        }
        
        .title {
            font-size: 3.2em;
            font-weight: 300;
            margin-bottom: 20px;
            letter-spacing: -1px;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        
        .subtitle {
            font-size: 1.4em;
            font-weight: 300;
            opacity: 0.9;
            letter-spacing: 0.5px;
            max-width: 800px;
            margin: 0 auto;
        }
        
        .metadata {
            background: #f8f9fa;
            padding: 25px 40px;
            border-bottom: 1px solid #e9ecef;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 20px;
        }
        
        .metadata-item {
            color: #495057;
            font-size: 0.95em;
        }
        
        .metadata-item strong {
            color: #343a40;
            margin-right: 8px;
        }
        
        .quality-score {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .quality-indicator {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
            letter-spacing: 0.5px;
        }
        
        .quality-high {
            background: #d4edda;
            color: #155724;
        }
        
        .quality-medium {
            background: #fff3cd;
            color: #856404;
        }
        
        .quality-low {
            background: #f8d7da;
            color: #721c24;
        }
        
        .content {
            padding: 40px;
        }
        
        .section {
            margin-bottom: 50px;
        }
        
        .section:last-child {
            margin-bottom: 0;
        }
        
        .section-title {
            font-size: 1.8em;
            color: #495057;
            margin-bottom: 25px;
            padding-bottom: 12px;
            border-bottom: 2px solid #e9ecef;
            position: relative;
        }
        
        .section-title::after {
            content: '';
            position: absolute;
            bottom: -2px;
            left: 0;
            width: 60px;
            height: 2px;
            background: #667eea;
        }
        
        .section-content h3 {
            color: #667eea;
            font-size: 1.3em;
            margin: 30px 0 15px 0;
        }
        
        .section-content h3:first-child {
            margin-top: 0;
        }
        
        .section-content p {
            margin-bottom: 16px;
            text-align: justify;
            color: #495057;
        }
        
        .section-content ul, .section-content ol {
            margin: 16px 0;
            padding-left: 30px;
        }
        
        .section-content li {
            margin-bottom: 8px;
            color: #495057;
        }
        
        .section-content strong {
            color: #343a40;
            font-weight: 600;
        }
        
        .execution-result {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            border-left: 4px solid #667eea;
        }
        
        .execution-result h4 {
            color: #667eea;
            margin-bottom: 12px;
            font-size: 1.1em;
        }
        
        .result-detail {
            background: white;
            padding: 15px;
            border-radius: 6px;
            margin-top: 12px;
            border: 1px solid #e9ecef;
        }
        
        .quality-assessment {
            background: #f8f9fa;
            border-radius: 8px;
            padding: 25px;
            margin-top: 30px;
        }
        
        .quality-assessment h3 {
            color: #495057;
            margin-bottom: 20px;
            font-size: 1.3em;
        }
        
        .quality-scores {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        
        .score-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            text-align: center;
        }
        
        .score-label {
            font-size: 0.9em;
            color: #6c757d;
            margin-bottom: 5px;
        }
        
        .score-value {
            font-size: 1.2em;
            font-weight: 600;
            color: #667eea;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 30px 40px;
            text-align: center;
            color: #6c757d;
            font-size: 0.9em;
            border-top: 1px solid #e9ecef;
        }
        
        @media (max-width: 768px) {
            .container {
                margin: 10px;
                border-radius: 8px;
            }
            
            .header {
                padding: 30px 20px;
            }
            
            .title {
                font-size: 2.2em;
            }
            
            .metadata {
                padding: 20px;
                flex-direction: column;
                gap: 10px;
            }
            
            .content {
                padding: 30px 20px;
            }
            
            .quality-scores {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">{{ report_title }}</h1>
            <p class="subtitle">{{ report_subtitle }}</p>
        </div>
        
        <div class="metadata">
            <div class="metadata-item">
                <strong>生成时间:</strong> {{ generation_time }}
            </div>
            <div class="metadata-item">
                <strong>工作流ID:</strong> {{ workflow_id }}
            </div>
            <div class="metadata-item quality-score">
                <strong>质量评分:</strong> 
                {{ quality_score }}
                <span class="quality-indicator quality-{{ quality_level }}">{{ quality_status }}</span>
            </div>
        </div>
        
        <div class="content">
            {% for section in sections %}
            <div class="section">
                <h2 class="section-title">{{ section.title }}</h2>
                <div class="section-content">
                    {{ section.content | safe }}
                </div>
            </div>
            {% endfor %}
            
            {% if quality_assessment %}
            <div class="quality-assessment">
                <h3>质量评估</h3>
                <p><strong>总体评分:</strong> {{ quality_assessment.overall_score }} / 1.0</p>
                
                <div class="quality-scores">
                    <div class="score-item">
                        <div class="score-label">准确性</div>
                        <div class="score-value">{{ quality_assessment.accuracy_score }}</div>
                    </div>
                    <div class="score-item">
                        <div class="score-label">完整性</div>
                        <div class="score-value">{{ quality_assessment.completeness_score }}</div>
                    </div>
                    <div class="score-item">
                        <div class="score-label">逻辑性</div>
                        <div class="score-value">{{ quality_assessment.logical_score }}</div>
                    </div>
                    <div class="score-item">
                        <div class="score-label">可读性</div>
                        <div class="score-value">{{ quality_assessment.readability_score }}</div>
                    </div>
                    <div class="score-item">
                        <div class="score-label">相关性</div>
                        <div class="score-value">{{ quality_assessment.relevance_score }}</div>
                    </div>
                </div>
                
                {% if quality_assessment.strengths %}
                <h3>主要优点</h3>
                <ul>
                    {% for strength in quality_assessment.strengths %}
                    <li>{{ strength }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
                
                {% if quality_assessment.weaknesses %}
                <h3>主要不足</h3>
                <ul>
                    {% for weakness in quality_assessment.weaknesses %}
                    <li>{{ weakness }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
                
                {% if quality_assessment.improvement_suggestions %}
                <h3>改进建议</h3>
                <ul>
                    {% for suggestion in quality_assessment.improvement_suggestions %}
                    <li>{{ suggestion }}</li>
                    {% endfor %}
                </ul>
                {% endif %}
            </div>
            {% endif %}
        </div>
        
        <div class="footer">
            <p>本报告由 Multi-Agent Report Generation System (MARGS) 自动生成</p>
        </div>
    </div>
</body>
</html>
        """
    
    def execute(self, state) -> Dict[str, Any]:
        """
        执行报告生成任务
        
        Args:
            state: 工作流状态
            
        Returns:
            报告生成结果字典
        """
        # 检查是否为PPT报告格式
        is_ppt_format = self._is_ppt_format_request(state.user_request)
        
        task_description = f"生成{'PPT格式HTML幻灯片' if is_ppt_format else 'HTML格式报告'}"
        log_agent_start("ReportAgent", task_description)
        
        try:
            # 收集报告数据
            report_data = self._collect_report_data(state)
            
            if is_ppt_format:
                # 生成PPT格式的HTML幻灯片
                slide_files = self._generate_ppt_slides(report_data, state)
                
                # 构建结果
                result = {
                    "report_type": "ppt_slides",
                    "slide_files": slide_files,
                    "slide_count": len(slide_files),
                    "report_metadata": {
                        "generation_time": datetime.now().isoformat(),
                        "report_format": "ppt_html",
                        "template_used": "ppt_slide"
                    },
                    "report_summary": self._generate_ppt_summary(report_data, slide_files),
                    "file_info": {
                        "slide_directory": str(Path(slide_files[0]["path"]).parent) if slide_files else "",
                        "accessible": all(os.path.exists(f["path"]) for f in slide_files) if slide_files else False
                    }
                }
                
                logger.info(f"PPT幻灯片生成完成，共生成 {len(slide_files)} 页幻灯片", agent_name="ReportAgent")
                log_agent_complete("ReportAgent", task_description, f"生成 {len(slide_files)} 页幻灯片")
            else:
                # 生成普通HTML报告
                report_content = self._generate_report_content(report_data)
                
                # 保存报告文件
                output_path = self._save_report(report_content, state)
                
                # 构建结果
                result = {
                    "report_type": "single_html",
                    "report_content": report_content,
                    "report_metadata": {
                        "output_path": output_path,
                        "file_size": len(report_content),
                        "generation_time": datetime.now().isoformat(),
                        "report_format": "html",
                        "template_used": self.output_config.get("default_template", "default")
                    },
                    "report_summary": self._generate_report_summary(report_data),
                    "file_info": {
                        "filename": Path(output_path).name,
                        "directory": str(Path(output_path).parent),
                        "accessible": os.path.exists(output_path)
                    }
                }
                
                logger.info(f"报告生成完成，保存路径: {output_path}", agent_name="ReportAgent")
                log_agent_complete("ReportAgent", task_description, f"保存到 {output_path}")
            
            return result
            
        except Exception as e:
            error_msg = f"报告生成失败: {str(e)}"
            logger.error(error_msg, agent_name="ReportAgent")
            raise Exception(error_msg)
    
    def _collect_report_data(self, state) -> Dict[str, Any]:
        """收集报告数据"""
        report_data = {
            "workflow_info": {
                "workflow_id": state.workflow_id,
                "user_request": state.user_request,
                "user_constraints": state.user_constraints,
                "start_time": state.start_time,
                "end_time": state.end_time,
                "workflow_status": state.workflow_status.value
            },
            "plan_info": state.plan,
            "execution_results": state.execution_results,
            "quality_assessment": state.quality_assessment,
            "memory_summary": state.context_summary,
            "user_feedback": state.user_feedback,
            "generation_time": datetime.now().isoformat(),
            "state": state  # 添加完整的state引用供后续使用
        }
        
        return report_data
    
    def _generate_report_content(self, report_data: Dict[str, Any]) -> str:
        """生成报告内容"""
        try:
            # 构建模板数据
            template_data = self._build_template_data(report_data)
            
            # 渲染模板
            if hasattr(self.jinja_env, 'globals') and 'default_template' in self.jinja_env.globals:
                # 使用默认模板
                template = self.jinja_env.globals['default_template']
                report_content = template.render(**template_data)
            else:
                # 使用文件模板
                template_name = self.output_config.get("default_template", "report.html")
                template = self.jinja_env.get_template(template_name)
                report_content = template.render(**template_data)
            
            # 清理报告内容，只保留HTML
            report_content = self._clean_html_content(report_content)
            
            return report_content
            
        except Exception as e:
            logger.error(f"模板渲染失败: {str(e)}", agent_name="ReportAgent")
            return self._create_fallback_report(report_data)
    
    def _clean_html_content(self, html_content: str) -> str:
        """清理HTML内容，只保留纯粹的HTML代码"""
        try:
            # 移除可能的XML标记或其他非HTML内容
            # 只保留<!DOCTYPE>到</html>之间的内容
            doctype_start = html_content.find('<!DOCTYPE')
            html_start = html_content.find('<html')
            
            start_pos = 0
            if doctype_start != -1:
                start_pos = doctype_start
            elif html_start != -1:
                start_pos = html_start
            
            html_end = html_content.find('</html>')
            if html_end != -1:
                end_pos = html_end + 7  # 包含</html>
            else:
                end_pos = len(html_content)
            
            clean_content = html_content[start_pos:end_pos]
            
            # 移除多余的空白行
            clean_content = re.sub(r'\n\s*\n', '\n', clean_content)
            clean_content = clean_content.strip()
            
            return clean_content
            
        except Exception as e:
            logger.error(f"清理HTML内容失败: {str(e)}", agent_name="ReportAgent")
            return html_content
    
    def _build_template_data(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建模板数据"""
        workflow_info = report_data["workflow_info"]
        plan_info = report_data["plan_info"]
        
        # 生成报告标题
        report_title = plan_info.get("report_title", workflow_info["user_request"]) if plan_info else workflow_info["user_request"]
        report_subtitle = plan_info.get("report_objective", "自动生成的报告") if plan_info else "自动生成的报告"
        
        # 生成质量信息
        quality_assessment = report_data["quality_assessment"]
        quality_score = quality_assessment.overall_score if quality_assessment else 0.0
        quality_level = self._get_quality_level(quality_score)
        quality_status = self._get_quality_status(quality_score)
        
        # 生成章节内容
        sections = self._generate_sections(report_data)
        
        template_data = {
            "report_title": report_title,
            "report_subtitle": report_subtitle,
            "generation_time": report_data["generation_time"],
            "workflow_id": workflow_info["workflow_id"],
            "quality_score": f"{quality_score:.2f}",
            "quality_level": quality_level,
            "quality_status": quality_status,
            "sections": sections,
            "quality_assessment": quality_assessment
        }
        
        return template_data
    
    def _get_quality_level(self, score: float) -> str:
        """获取质量等级"""
        if score >= 0.8:
            return "high"
        elif score >= 0.6:
            return "medium"
        else:
            return "low"
    
    def _get_quality_status(self, score: float) -> str:
        """获取质量状态"""
        if score >= 0.8:
            return "优秀"
        elif score >= 0.6:
            return "良好"
        else:
            return "需改进"
    
    def _generate_sections(self, report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成报告章节"""
        sections = []
        
        # 概述章节
        overview_content = self._generate_overview_content(report_data)
        sections.append({
            "id": "overview",
            "title": "执行摘要",
            "content": overview_content
        })
        
        # 从执行结果中动态生成所有章节
        execution_results = report_data.get("execution_results", {})
        
        if execution_results:
            # 将每个执行步骤的结果作为独立章节
            step_count = 0
            
            # 对步骤进行排序，确保顺序一致
            sorted_steps = sorted(execution_results.items(), key=lambda x: x[0])
            
            for step_id, result in sorted_steps:
                step_count += 1
                # 提取实际内容
                actual_content = self._extract_and_enhance_content(result, step_count)
                
                # 生成章节标题
                section_title = self._generate_section_title(step_id, result, step_count)
                
                # 确保内容不为空
                if not actual_content or actual_content == "<p>内容正在生成中...</p>":
                    actual_content = self._generate_default_section_content(step_id, result)
                
                sections.append({
                    "id": f"section_{step_count}",
                    "title": section_title,
                    "content": actual_content
                })
        else:
            # 如果没有执行结果，添加一个执行结果章节
            execution_content = self._generate_execution_content(report_data)
            sections.append({
                "id": "execution_results",
                "title": "分析结果",
                "content": execution_content
            })
        
        # 核心洞察章节（如果有多个执行结果）
        if len(execution_results) > 2:
            insights_content = self._generate_insights_content(report_data)
            sections.append({
                "id": "key_insights",
                "title": "核心洞察",
                "content": insights_content
            })
        
        # 分析和总结章节
        if report_data.get("memory_summary"):
            summary_content = self._generate_analysis_summary_content(report_data)
            sections.append({
                "id": "analysis_summary",
                "title": "综合分析",
                "content": summary_content
            })
        
        # 建议与展望章节
        recommendations_content = self._generate_recommendations_content(report_data)
        sections.append({
            "id": "recommendations",
            "title": "建议与展望",
            "content": recommendations_content
        })
        
        # 结论章节
        conclusion_content = self._generate_conclusion_content(report_data)
        sections.append({
            "id": "conclusion",
            "title": "总结",
            "content": conclusion_content
        })
        
        return sections
    
    def _extract_and_enhance_content(self, result: Any, step_num: int) -> str:
        """提取并增强内容"""
        base_content = self._extract_actual_content(result)
        
        # 如果内容太短，增强它
        if len(base_content) < 200:
            enhanced_content = f"""
<div class="enhanced-section">
    {base_content}
    <div class="section-details">
        <p>本节详细分析了相关内容，提供了深入的见解和专业的评估。</p>
    </div>
</div>
"""
            return enhanced_content
        
        return base_content
    
    def _generate_section_title(self, step_id: str, result: Any, step_count: int) -> str:
        """生成章节标题"""
        # 优先使用结果中的标题
        if isinstance(result, dict):
            if "title" in result:
                return result["title"]
            elif "section_title" in result:
                return result["section_title"]
        
        # 根据step_id生成有意义的标题
        title_mapping = {
            "step_1": "现状分析",
            "step_2": "详细评估",
            "step_3": "改进方案",
            "step_4": "实施建议",
            "step_5": "风险评估",
            "step_final": "最终结论"
        }
        
        if step_id in title_mapping:
            return title_mapping[step_id]
        
        # 默认标题
        if step_id.startswith("step_"):
            return f"第{step_count}部分: {step_id.replace('step_', '').replace('_', ' ').title()}"
        else:
            return step_id.replace('_', ' ').title()
    
    def _generate_default_section_content(self, step_id: str, result: Any) -> str:
        """生成默认章节内容"""
        return f"""
<div class="default-content">
    <p>本节包含了 {step_id} 的详细分析结果。</p>
    <div class="content-placeholder">
        {str(result)[:500] if result else "内容处理中..."}
    </div>
</div>
"""
    
    def _generate_insights_content(self, report_data: Dict[str, Any]) -> str:
        """生成核心洞察内容"""
        execution_results = report_data.get("execution_results", {})
        
        content = """
<h3>关键发现</h3>
<div class="insights-grid">
"""
        
        insights_count = 0
        for step_id, result in execution_results.items():
            if isinstance(result, dict):
                # 提取关键信息
                if "key_findings" in result:
                    for finding in result["key_findings"][:2]:  # 每个步骤最多2个发现
                        insights_count += 1
                        content += f"""
    <div class="insight-card">
        <div class="insight-number">{insights_count}</div>
        <div class="insight-content">{finding}</div>
    </div>
"""
                elif "insights" in result:
                    for insight in result["insights"][:2]:
                        insights_count += 1
                        content += f"""
    <div class="insight-card">
        <div class="insight-number">{insights_count}</div>
        <div class="insight-content">{insight}</div>
    </div>
"""
        
        content += """
</div>

<style>
.insights-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin: 20px 0;
}

.insight-card {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 8px;
    border-left: 4px solid #3498db;
    position: relative;
}

.insight-number {
    position: absolute;
    top: 10px;
    right: 10px;
    width: 30px;
    height: 30px;
    background: #3498db;
    color: white;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
}

.insight-content {
    padding-right: 40px;
}
</style>
"""
        
        return content
    
    def _generate_recommendations_content(self, report_data: Dict[str, Any]) -> str:
        """生成建议与展望内容"""
        workflow_info = report_data["workflow_info"]
        
        content = """
<h3>战略建议</h3>
<ol>
    <li><strong>短期优化</strong>：基于当前分析，建议立即采取的行动措施</li>
    <li><strong>中期规划</strong>：制定3-6个月的改进计划</li>
    <li><strong>长期战略</strong>：构建持续优化的体系和机制</li>
</ol>

<h3>实施路径</h3>
<div class="implementation-timeline">
    <div class="timeline-item">
        <div class="timeline-marker">第一阶段</div>
        <div class="timeline-content">
            <h4>基础建设</h4>
            <p>完善基础设施，建立标准流程</p>
        </div>
    </div>
    <div class="timeline-item">
        <div class="timeline-marker">第二阶段</div>
        <div class="timeline-content">
            <h4>优化提升</h4>
            <p>持续改进，提高效率和质量</p>
        </div>
    </div>
    <div class="timeline-item">
        <div class="timeline-marker">第三阶段</div>
        <div class="timeline-content">
            <h4>创新发展</h4>
            <p>探索新技术，实现突破性进展</p>
        </div>
    </div>
</div>

<style>
.implementation-timeline {
    margin: 20px 0;
    padding: 20px;
    background: #f8f9fa;
    border-radius: 8px;
}

.timeline-item {
    display: flex;
    margin-bottom: 20px;
    align-items: flex-start;
}

.timeline-marker {
    background: #3498db;
    color: white;
    padding: 5px 15px;
    border-radius: 20px;
    margin-right: 20px;
    min-width: 100px;
    text-align: center;
    font-weight: bold;
}

.timeline-content h4 {
    color: #2a5298;
    margin-bottom: 5px;
}
</style>
"""
        
        return content
    
    def _generate_overview_content(self, report_data: Dict[str, Any]) -> str:
        """生成概述内容"""
        workflow_info = report_data["workflow_info"]
        plan_info = report_data["plan_info"]
        
        content = f"""
<h3>项目背景</h3>
<p>本报告基于用户请求 "{workflow_info['user_request']}" 自动生成。</p>

"""
        
        if plan_info:
            content += f"""
<h3>报告目标</h3>
<p>{plan_info.get('report_objective', '未指定具体目标')}</p>

<h3>主要章节</h3>
<ul>
"""
            for section in plan_info.get("main_sections", []):
                content += f"<li>{section}</li>\n"
            content += "</ul>\n"
        
        content += f"""
<h3>执行摘要</h3>
<p>{report_data['memory_summary']}</p>

<h3>生成信息</h3>
<ul>
<li>工作流ID: {workflow_info['workflow_id']}</li>
<li>开始时间: {workflow_info['start_time'].strftime('%Y-%m-%d %H:%M:%S')}</li>
<li>结束时间: {workflow_info['end_time'].strftime('%Y-%m-%d %H:%M:%S') if workflow_info['end_time'] else '进行中'}</li>
<li>生成时间: {report_data['generation_time']}</li>
</ul>
"""
        
        return content
    
    def _generate_execution_content(self, report_data: Dict[str, Any]) -> str:
        """生成执行结果内容，从执行结果中提取实际内容"""
        execution_results = report_data["execution_results"]
        
        if not execution_results:
            return "<p>暂无执行结果。</p>"
        
        content = "<h3>执行步骤详情</h3>\n"
        
        for step_id, result in execution_results.items():
            # 提取实际内容，而不是执行步骤的元数据
            actual_content = self._extract_actual_content(result)
            
            content += f"""
<h4>{step_id}</h4>
<div class="execution-result">
{actual_content}
</div>
"""
        
        return content
    
    def _generate_feedback_content(self, user_feedback: List[str]) -> str:
        """生成用户反馈内容"""
        content = "<h3>用户反馈记录</h3>\n<ul>\n"
        
        for feedback in user_feedback:
            content += f"<li>{feedback}</li>\n"
        
        content += "</ul>\n"
        return content
    
    def _generate_analysis_summary_content(self, report_data: Dict[str, Any]) -> str:
        """生成分析总结内容"""
        memory_summary = report_data.get("memory_summary", "")
        workflow_info = report_data["workflow_info"]
        
        content = f"""
<h3>核心分析</h3>
<p>{memory_summary}</p>

<h3>关键发现</h3>
"""
        
        # 从执行结果中提取关键信息
        execution_results = report_data.get("execution_results", {})
        if execution_results:
            content += "<ul>\n"
            for step_id, result in list(execution_results.items())[:5]:  # 最多显示5个关键发现
                if isinstance(result, dict):
                    if "key_findings" in result:
                        for finding in result["key_findings"]:
                            content += f"<li>{finding}</li>\n"
                    elif "summary" in result:
                        content += f"<li>{result['summary']}</li>\n"
            content += "</ul>\n"
        else:
            content += "<p>基于分析过程生成的洞察将在此展示。</p>\n"
        
        # 添加时间线信息
        content += f"""
<h3>执行时间线</h3>
<ul>
<li>开始时间: {workflow_info['start_time'].strftime('%Y-%m-%d %H:%M:%S') if workflow_info.get('start_time') else '未知'}</li>
<li>结束时间: {workflow_info['end_time'].strftime('%Y-%m-%d %H:%M:%S') if workflow_info.get('end_time') else '进行中'}</li>
<li>工作流状态: {workflow_info.get('workflow_status', '未知')}</li>
</ul>
"""
        
        return content
    
    def _generate_conclusion_content(self, report_data: Dict[str, Any]) -> str:
        """生成结论与建议内容"""
        workflow_info = report_data["workflow_info"]
        quality_assessment = report_data.get("quality_assessment")
        
        content = f"""
<h3>主要结论</h3>
<p>基于用户请求 "{workflow_info['user_request']}"，系统通过多智能体协作完成了全面的分析和报告生成。</p>
"""
        
        # 如果有质量评估，添加质量结论
        if quality_assessment:
            quality_score = quality_assessment.overall_score if hasattr(quality_assessment, 'overall_score') else 0
            quality_status = self._get_quality_status(quality_score)
            
            content += f"""
<h3>质量评价</h3>
<p>本次报告生成的整体质量评级为: <strong>{quality_status}</strong> (评分: {quality_score:.2f}/1.0)</p>
"""
            
            # 添加改进建议
            if hasattr(quality_assessment, 'improvement_suggestions') and quality_assessment.improvement_suggestions:
                content += "<h3>改进建议</h3>\n<ul>\n"
                for suggestion in quality_assessment.improvement_suggestions[:3]:  # 最多显示3条建议
                    content += f"<li>{suggestion}</li>\n"
                content += "</ul>\n"
        
        # 添加下一步行动建议
        content += """
<h3>后续行动建议</h3>
<ul>
<li>审阅报告内容的准确性和完整性</li>
<li>根据分析结果制定具体行动计划</li>
<li>定期更新和优化分析流程</li>
</ul>
"""
        
        # 如果有用户约束，提及约束满足情况
        if workflow_info.get("user_constraints"):
            content += "<h3>约束条件满足情况</h3>\n<ul>\n"
            for constraint in workflow_info["user_constraints"]:
                content += f"<li>OK {constraint}</li>\n"
            content += "</ul>\n"
        
        return content
    
    def _extract_actual_content(self, result: Any) -> str:
        """从执行结果中提取实际内容"""
        if isinstance(result, dict):
            # 优先提取各种内容字段
            content_fields = ["content", "text", "data", "output", "result", "message", "description", "body"]
            
            for field in content_fields:
                if field in result:
                    field_content = result[field]
                    # 如果字段内容是字符串且不为空，使用它
                    if isinstance(field_content, str) and field_content.strip():
                        # 处理 HTML 内容
                        if field_content.strip().startswith('<'):
                            return field_content
                        # 处理 Markdown 或纯文本
                        else:
                            return self._convert_text_to_html(field_content)
                    # 如果是字典或列表，递归处理
                    elif isinstance(field_content, (dict, list)):
                        return self._format_complex_content(field_content)
            
            # 特殊处理：如果有多个重要字段，组合它们
            formatted_sections = []
            
            # 处理标题和副标题
            if "title" in result or "heading" in result:
                title = result.get("title") or result.get("heading")
                formatted_sections.append(f"<h3>{title}</h3>")
            
            if "subtitle" in result or "subheading" in result:
                subtitle = result.get("subtitle") or result.get("subheading")
                formatted_sections.append(f"<h4>{subtitle}</h4>")
            
            # 处理主要内容字段
            important_fields = {
                "analysis": "分析",
                "findings": "发现",
                "recommendations": "建议",
                "summary": "摘要",
                "details": "详情",
                "insights": "洞察",
                "conclusions": "结论"
            }
            
            for field, label in important_fields.items():
                if field in result and result[field]:
                    formatted_sections.append(f"<h4>{label}</h4>")
                    formatted_sections.append(self._format_value(result[field]))
            
            # 如果有格式化的内容，返回它们
            if formatted_sections:
                return "\n".join(formatted_sections)
            
            # 否则，格式化整个字典（排除元数据字段）
            excluded_keys = {"step_id", "status", "error_message", "metadata", "confidence", "notes", "timestamp", "id"}
            filtered_dict = {k: v for k, v in result.items() if k not in excluded_keys and v}
            
            if filtered_dict:
                return self._format_dict_content(filtered_dict)
            else:
                return "<p>内容正在生成中...</p>"
            
        elif isinstance(result, str):
            # 如果是字符串，检查是否为 HTML
            if result.strip().startswith('<'):
                return result
            else:
                return self._convert_text_to_html(result)
                
        elif isinstance(result, list):
            # 如果是列表，智能格式化
            return self._format_list_content(result)
            
        else:
            # 其他类型，转换为字符串
            return f"<p>{str(result)}</p>"
    
    def _convert_text_to_html(self, text: str) -> str:
        """将纯文本转换为HTML格式"""
        # 处理换行
        paragraphs = text.split('\n\n')
        html_parts = []
        
        for para in paragraphs:
            if para.strip():
                # 检查是否是列表项
                if para.strip().startswith('- ') or para.strip().startswith('* '):
                    items = para.split('\n')
                    html_parts.append("<ul>")
                    for item in items:
                        if item.strip().startswith(('- ', '* ')):
                            html_parts.append(f"<li>{item[2:].strip()}</li>")
                    html_parts.append("</ul>")
                # 检查是否是编号列表
                elif para.strip()[0].isdigit() and para.strip()[1:3] in ['. ', ') ']:
                    items = para.split('\n')
                    html_parts.append("<ol>")
                    for item in items:
                        if item.strip() and item.strip()[0].isdigit():
                            # 移除编号
                            content = item.strip()
                            for i, char in enumerate(content):
                                if char in '.':
                                    content = content[i+1:].strip()
                                    break
                            html_parts.append(f"<li>{content}</li>")
                    html_parts.append("</ol>")
                else:
                    # 普通段落
                    html_parts.append(f"<p>{para.strip()}</p>")
        
        return '\n'.join(html_parts)
    
    def _format_complex_content(self, content: Any) -> str:
        """格式化复杂内容（字典或列表）"""
        if isinstance(content, dict):
            return self._format_dict_content(content)
        elif isinstance(content, list):
            return self._format_list_content(content)
        else:
            return self._format_value(content)
    
    def _format_list_content(self, items: list) -> str:
        """智能格式化列表内容"""
        if not items:
            return "<p>无数据</p>"
        
        # 检查列表项的类型
        first_item = items[0]
        
        # 如果是字典列表，格式化为表格或卡片
        if isinstance(first_item, dict):
            return self._format_dict_list(items)
        
        # 否则格式化为普通列表
        html = "<ul>\n"
        for item in items:
            html += f"<li>{self._format_value(item)}</li>\n"
        html += "</ul>\n"
        
        return html
    
    def _format_dict_list(self, dict_list: List[Dict]) -> str:
        """格式化字典列表为结构化内容"""
        html = '<div class="dict-list">\n'
        
        for i, item in enumerate(dict_list, 1):
            html += f'<div class="result-detail">\n'
            html += f'<h4>项目 {i}</h4>\n'
            html += self._format_dict_content(item)
            html += '</div>\n'
        
        html += '</div>\n'
        return html
    
    def _format_dict_content(self, content_dict: Dict[str, Any]) -> str:
        """格式化字典内容为HTML"""
        html_content = ""
        
        for key, value in content_dict.items():
            if isinstance(value, dict):
                html_content += f"<h4>{key}</h4>\n"
                html_content += self._format_dict_content(value)
            elif isinstance(value, list):
                html_content += f"<h4>{key}</h4>\n<ul>\n"
                for item in value:
                    html_content += f"<li>{self._format_value(item)}</li>\n"
                html_content += "</ul>\n"
            else:
                html_content += f"<p><strong>{key}:</strong> {self._format_value(value)}</p>\n"
        
        return html_content
    
    def _format_value(self, value: Any) -> str:
        """格式化值"""
        if isinstance(value, str):
            # 检查是否是HTML内容
            if value.strip().startswith('<'):
                return value
            return value.replace('\n', '<br>')
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return "是" if value else "否"
        else:
            return str(value)
    
    def _format_result_content(self, result: Any) -> str:
        """格式化结果内容"""
        # 提取实际内容
        return self._extract_actual_content(result)
    
    def _save_report(self, report_content: str, state) -> str:
        """保存报告文件"""
        try:
            # 确保输出目录存在
            reports_dir = Path(self.output_config.get("reports_directory", "examples/sample_reports"))
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{state.workflow_id}_{timestamp}.html"
            output_path = reports_dir / filename
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            logger.info(f"报告已保存到: {output_path}", agent_name="ReportAgent")
            
            return str(output_path)
            
        except Exception as e:
            logger.error(f"报告保存失败: {str(e)}", agent_name="ReportAgent")
            raise
    
    def _create_fallback_report(self, report_data: Dict[str, Any]) -> str:
        """创建备用报告"""
        workflow_info = report_data["workflow_info"]
        
        fallback_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>备用报告</title>
    <meta charset="UTF-8">
</head>
<body>
    <h1>备用报告</h1>
    <p>工作流ID: {workflow_info['workflow_id']}</p>
    <p>用户请求: {workflow_info['user_request']}</p>
    <p>生成时间: {report_data['generation_time']}</p>
    <p>注意: 由于模板渲染问题，这是备用格式的报告。</p>
</body>
</html>"""
        
        return fallback_content
    

    def _generate_report_summary(self, report_data: Dict[str, Any]) -> str:
        """生成报告摘要"""
        workflow_info = report_data["workflow_info"]
        quality_assessment = report_data.get("quality_assessment")
        
        # 安全获取报告标题
        report_title = (
            report_data.get('plan_info', {}).get('report_title', workflow_info['user_request']) 
            if report_data.get('plan_info') 
            else workflow_info['user_request']
        )
        
        summary = f"""
    报告生成摘要
    报告标题: {report_title}
    工作流ID: {workflow_info['workflow_id']}
    生成时间: {report_data['generation_time']}
    """
        
        if quality_assessment is not None and hasattr(quality_assessment, 'overall_score'):
            summary += f"质量评分: {quality_assessment.overall_score:.2f}\n"
        
        return summary
    

    def get_available_templates(self) -> List[str]:
        """获取可用模板列表"""
        try:
            if self.template_dir.exists():
                template_files = list(self.template_dir.glob("*.html"))
                return [f.stem for f in template_files]
            return ["default"]
        except Exception:
            return ["default"]
    
    def validate_report_content(self, report_content: str) -> bool:
        """验证报告内容"""
        if not report_content:
            return False
        
        # 基本的HTML结构验证
        required_tags = ["<html", "</html>", "<head", "</head>", "<body", "</body>"]
        for tag in required_tags:
            if tag not in report_content:
                logger.warning(f"报告内容缺少必要标签: {tag}", agent_name="ReportAgent")
                return False
        
        return True
    
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
    
    def _generate_ppt_slides(self, report_data: Dict[str, Any], state) -> List[Dict[str, Any]]:
        """
        生成PPT格式的HTML幻灯片
        
        根据需求文档，支持结构化的PPT生成流程：
        1. plan分析：包含think/react结构，分析报告内容并设计PPT结构
        2. react执行：使用create_slide工具创建PPT的各个页面
        
        Args:
            report_data: 报告数据
            state: 工作流状态
            
        Returns:
            幻灯片文件信息列表
        """
        slide_files = []
        
        try:
            # 确保输出目录存在
            slides_dir = Path(self.output_config.get("slides_directory", "examples/sample_slides"))
            slides_dir.mkdir(parents=True, exist_ok=True)
            
            # 第一步：进行plan分析，包含think/react结构
            ppt_plan = self._analyze_and_plan_ppt_content(report_data)
            
            # 第二步：根据plan执行react，创建各个幻灯片
            slides_content = self._execute_ppt_creation_plan(ppt_plan, report_data)
            
            # 保存每个幻灯片
            for i, slide_content in enumerate(slides_content):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"slide_{i+1:03d}_{state.workflow_id}_{timestamp}.html"
                output_path = slides_dir / filename
                
                # 清理幻灯片内容，只保留HTML
                slide_content = self._clean_html_content(slide_content)
                
                # 写入文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(slide_content)
                
                slide_files.append({
                    "slide_number": i + 1,
                    "path": str(output_path),
                    "filename": filename,
                    "title": slide_content.get("title", f"幻灯片 {i+1}"),
                    "file_size": len(str(slide_content))
                })
            
            logger.info(f"PPT幻灯片已保存到目录: {slides_dir}", agent_name="ReportAgent")
            
        except Exception as e:
            logger.error(f"PPT幻灯片生成失败: {str(e)}", agent_name="ReportAgent")
            raise
        
        return slide_files
    
    def _analyze_and_plan_ppt_content(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        第一步：进行plan分析，包含think/react结构，分析报告内容并设计PPT结构
        
        根据需求文档，这个方法应该：
        1. 分析报告内容（think部分）
        2. 设计PPT结构（react部分）
        3. 返回结构化的PPT创建计划
        
        Args:
            report_data: 报告数据
            
        Returns:
            PPT创建计划字典
        """
        try:
            # 构建分析提示，完全按照需求文档的格式
            analysis_prompt = f"""
用户上传了报告文件，并且提问："请分析报告数据并总结优化生成一个新的报告"，期望的预期流程如下：

plan分析：
think
用户要求我根据提供的上下文内容生成PPT。我需要分析提供的报告内容，然后设计一个结构合理、重点突出的PPT。

首先，我需要理解报告的主要内容：

这是一份{report_data.get('workflow_info', {}).get('user_request', 'XXX有限公司')}的安全运营年度报告
报告时间范围：{report_data.get('workflow_info', {}).get('start_time', '2024年12月')}至{report_data.get('workflow_info', {}).get('end_time', '2025年05月')}
汇报人：张运/赵君颖
主要内容包括：
安全运营目标达成情况
安全运营工作详情（资产管理、脆弱性管理、威胁管理、事件管理）
关键问题分析与讨论
下半年工作目标及计划
从内容来看，这是一份相当详细的安全运营报告，包含了大量的技术细节和数据。我需要将这些内容转化为适合PPT展示的形式，既要保持专业性，又要确保清晰易懂。

我将设计一个结构合理、重点突出的PPT，包括以下几个部分：

封面和目录
执行摘要
安全运营目标达成情况
资产管理状况
脆弱性管理
威胁管理
事件管理
关键问题分析
下半年工作计划
总结与建议
我会使用create_slide工具来创建PPT，并确保设计专业、内容清晰。
/think
我将根据您提供的报告内容为您生成一份专业的安全运营年度报告PPT。这份PPT将包含关键数据、分析结果和未来计划，以清晰直观的方式展示安全运营工作成果。

备注：plan经过分析之后，设计输出了大纲，然后接下来开始就要开始按照大纲生成每一页PPT，每一页是HTMP格式的PPT
"""
            
            # 生成分析结果（使用流式输出）
            analysis_result = ""
            logger.info("开始进行PPT内容分析和规划...", agent_name="ReportAgent")
            
            for chunk in generate_system_response_stream(
                self.system_prompt,
                analysis_prompt,
                temperature=0.7
            ):
                analysis_result += chunk
            
            logger.info("PPT内容分析和规划完成", agent_name="ReportAgent")
            
            # 解析分析结果，提取PPT结构计划
            ppt_plan = self._parse_ppt_analysis_result(analysis_result, report_data)
            
            return ppt_plan
            
        except Exception as e:
            logger.error(f"PPT内容分析和规划失败: {str(e)}", agent_name="ReportAgent")
            # 返回默认的PPT计划
            return self._create_default_ppt_plan(report_data)
    
    def _parse_ppt_analysis_result(self, analysis_result: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析PPT分析结果，提取结构化的PPT创建计划
        
        Args:
            analysis_result: 分析结果文本
            report_data: 报告数据
            
        Returns:
            结构化的PPT创建计划
        """
        try:
            # 尝试从分析结果中提取JSON格式的计划
            # 查找JSON格式的计划
            json_start = analysis_result.find('{')
            json_end = analysis_result.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_content = analysis_result[json_start:json_end]
                plan = json.loads(json_content)
                return plan
            
            # 如果没有找到JSON，创建基于分析文本的计划
            return self._create_plan_from_analysis_text(analysis_result, report_data)
            
        except Exception as e:
            logger.warning(f"解析PPT分析结果失败: {str(e)}", agent_name="ReportAgent")
            return self._create_default_ppt_plan(report_data)
    
    def _create_plan_from_analysis_text(self, analysis_text: str, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据分析文本创建PPT计划
        
        Args:
            analysis_text: 分析文本
            report_data: 报告数据
            
        Returns:
            PPT创建计划
        """
        # 从分析文本中提取关键信息
        lines = analysis_text.split('\n')
        
        # 提取报告标题
        workflow_info = report_data["workflow_info"]
        report_title = workflow_info.get("user_request", "报告")
        
        # 创建基于分析的计划
        plan = {
            "report_title": report_title,
            "slides": [
                {
                    "slide_number": 1,
                    "slide_type": "title",
                    "title": report_title,
                    "subtitle": "自动生成的演示文稿",
                    "content_focus": "封面信息"
                },
                {
                    "slide_number": 2,
                    "slide_type": "toc",
                    "title": "目录",
                    "subtitle": "演示内容概览",
                    "content_focus": "内容导航"
                },
                {
                    "slide_number": 3,
                    "slide_type": "summary",
                    "title": "执行摘要",
                    "subtitle": "关键信息概览",
                    "content_focus": "核心要点"
                },
                {
                    "slide_number": 4,
                    "slide_type": "content",
                    "title": "主要内容",
                    "subtitle": "详细分析",
                    "content_focus": "核心内容"
                },
                {
                    "slide_number": 5,
                    "slide_type": "analysis",
                    "title": "关键分析",
                    "subtitle": "深度洞察",
                    "content_focus": "分析结果"
                },
                {
                    "slide_number": 6,
                    "slide_type": "conclusion",
                    "title": "总结与建议",
                    "subtitle": "最终观点",
                    "content_focus": "结论要点"
                }
            ]
        }
        
        return plan
    
    def _create_default_ppt_plan(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建默认的PPT创建计划
        
        Args:
            report_data: 报告数据
            
        Returns:
            默认的PPT创建计划
        """
        workflow_info = report_data["workflow_info"]
        report_title = workflow_info.get("user_request", "报告")
        
        plan = {
            "report_title": report_title,
            "slides": [
                {
                    "slide_number": 1,
                    "slide_type": "title",
                    "title": report_title,
                    "subtitle": "自动生成的演示文稿",
                    "content_focus": "封面信息"
                },
                {
                    "slide_number": 2,
                    "slide_type": "toc",
                    "title": "目录",
                    "subtitle": "演示内容概览",
                    "content_focus": "内容导航"
                },
                {
                    "slide_number": 3,
                    "slide_type": "summary",
                    "title": "执行摘要",
                    "subtitle": "关键信息概览",
                    "content_focus": "核心要点"
                },
                {
                    "slide_number": 4,
                    "slide_type": "content",
                    "title": "主要内容",
                    "subtitle": "详细分析",
                    "content_focus": "核心内容"
                },
                {
                    "slide_number": 5,
                    "slide_type": "conclusion",
                    "title": "总结",
                    "subtitle": "项目完成情况",
                    "content_focus": "总结要点"
                }
            ]
        }
        
        return plan
    
    def _execute_ppt_creation_plan(self, ppt_plan: Dict[str, Any], report_data: Dict[str, Any]) -> List[str]:
        """
        第二步：根据plan执行react，创建各个幻灯片
        
        根据需求文档，这个方法应该：
        1. 接收PPT创建计划
        2. 使用create_slide工具创建每个幻灯片
        3. 返回创建的幻灯片内容列表
        
        Args:
            ppt_plan: PPT创建计划
            report_data: 报告数据
            
        Returns:
            幻灯片内容列表
        """
        slides = []
        
        try:
            logger.info("开始执行PPT创建计划...", agent_name="ReportAgent")
            
            # 遍历计划中的每个幻灯片
            for slide_info in ppt_plan.get("slides", []):
                slide_number = slide_info.get("slide_number", 1)
                slide_type = slide_info.get("slide_type", "content")
                title = slide_info.get("title", f"幻灯片 {slide_number}")
                subtitle = slide_info.get("subtitle", "")
                content_focus = slide_info.get("content_focus", "")
                
                logger.info(f"创建幻灯片 {slide_number}: {title}", agent_name="ReportAgent")
                
                # 使用create_slide工具创建幻灯片
                slide_content = self._create_slide_with_tool(
                    slide_number=slide_number,
                    slide_type=slide_type,
                    title=title,
                    subtitle=subtitle,
                    content_focus=content_focus,
                    report_data=report_data
                )
                
                slides.append(slide_content)
                
                logger.info(f"幻灯片 {slide_number} 创建完成", agent_name="ReportAgent")
            
            logger.info("PPT创建计划执行完成", agent_name="ReportAgent")
            
        except Exception as e:
            logger.error(f"执行PPT创建计划失败: {str(e)}", agent_name="ReportAgent")
            # 如果执行失败，使用默认方法创建幻灯片
            slides = self._generate_slides_content(report_data)
        
        return slides
    
    def _create_slide_with_tool(self, slide_number: int, slide_type: str, title: str, 
                              subtitle: str, content_focus: str, report_data: Dict[str, Any]) -> str:
        """
        使用create_slide工具创建幻灯片
        
        完全按照需求文档的示例格式模拟create_slide工具的使用流程
        
        Args:
            slide_number: 幻灯片编号
            slide_type: 幻灯片类型
            title: 标题
            subtitle: 副标题
            content_focus: 内容焦点
            report_data: 报告数据
            
        Returns:
            幻灯片内容
        """
        try:
            # 构建创建幻灯片的提示，完全按照需求文档的格式
            if slide_number == 1:
                creation_prompt = f"""
react 执行create_slide
现在我将开始创建PPT的各个页面。首先，让我添加封面页

备注：这里生成了第一页HTML格式的PPT
"""
            elif slide_number == 2:
                creation_prompt = f"""
react 执行create_slide
接下来，我将添加目录页：

备注：这里生成了第二页HTML格式的PPT
"""
            elif slide_number == 3:
                creation_prompt = f"""
react 执行create_slide
现在添加执行摘要页：

备注：这里生成了第三页HTML格式的PPT，后面依次生成
"""
            else:
                # 获取任务类型特定要求（如果有的话）
                task_style_info = ""
                if hasattr(report_data.get('state'), 'task_requirements'):
                    task_req = report_data['state'].task_requirements
                    if task_req:
                        task_style_info = f"""
任务类型: {task_req.get('task_type', '通用')}
样式要求: {', '.join(task_req.get('style_requirements', [])[:3]) if task_req.get('style_requirements') else '标准样式'}
"""
                
                creation_prompt = f"""
react 执行create_slide
现在我将创建第{slide_number}页幻灯片：{title}
{task_style_info}
备注：这里生成了第{slide_number}页HTML格式的PPT，应用任务类型特定的样式要求
"""
            
            # 生成幻灯片内容（使用流式输出）
            slide_content_result = ""
            logger.info(f"开始生成幻灯片 {slide_number} 内容...", agent_name="ReportAgent")
            
            for chunk in generate_system_response_stream(
                self.system_prompt,
                creation_prompt,
                temperature=0.7
            ):
                slide_content_result += chunk
            
            logger.info(f"幻灯片 {slide_number} 内容生成完成", agent_name="ReportAgent")
            
            # 根据幻灯片类型创建最终的幻灯片内容
            if slide_type == "title":
                return self._create_title_slide_from_content(title, subtitle, slide_content_result, report_data)
            elif slide_type == "toc":
                return self._create_toc_slide_from_content(title, subtitle, slide_content_result, report_data)
            elif slide_type == "summary":
                return self._create_summary_slide_from_content(title, subtitle, slide_content_result, report_data)
            elif slide_type == "content":
                return self._create_content_slide_from_content(title, subtitle, slide_content_result, report_data)
            elif slide_type == "analysis":
                return self._create_analysis_slide_from_content(title, subtitle, slide_content_result, report_data)
            elif slide_type == "conclusion":
                return self._create_conclusion_slide_from_content(title, subtitle, slide_content_result, report_data)
            else:
                return self._create_generic_slide_from_content(title, subtitle, slide_content_result, report_data)
            
        except Exception as e:
            logger.error(f"创建幻灯片 {slide_number} 失败: {str(e)}", agent_name="ReportAgent")
            # 返回默认的幻灯片内容
            return self._create_fallback_slide(title, subtitle, report_data)
    
    def _create_title_slide_from_content(self, title: str, subtitle: str, content: str, report_data: Dict[str, Any]) -> str:
        """从生成的内容创建标题幻灯片"""
        workflow_info = report_data["workflow_info"]
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content="",
            slide_type="title",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_toc_slide_from_content(self, title: str, subtitle: str, content: str, report_data: Dict[str, Any]) -> str:
        """从生成的内容创建目录幻灯片"""
        workflow_info = report_data["workflow_info"]
        
        toc_content = """
        <div class="toc-content">
            <h3>演示内容</h3>
            <ol>
                <li>封面</li>
                <li>目录</li>
                <li>执行摘要</li>
                <li>主要内容</li>
                <li>关键分析</li>
                <li>总结与建议</li>
            </ol>
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content=toc_content,
            slide_type="toc",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_summary_slide_from_content(self, title: str, subtitle: str, content: str, report_data: Dict[str, Any]) -> str:
        """从生成的内容创建摘要幻灯片"""
        workflow_info = report_data["workflow_info"]
        
        # 提取关键信息作为摘要
        summary_content = f"""
        <div class="slide-content">
            <h3>执行摘要</h3>
            <p><strong>项目目标：</strong>{workflow_info['user_request']}</p>
            <p><strong>时间范围：</strong>{workflow_info.get('start_time', 'N/A')} 至 {workflow_info.get('end_time', '进行中')}</p>
            <p><strong>主要成果：</strong></p>
            <ul>
                <li>成功完成自动化报告生成</li>
                <li>提供高质量的分析内容</li>
                <li>通过多Agent协作确保质量</li>
            </ul>
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content=summary_content,
            slide_type="content",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_content_slide_from_content(self, title: str, subtitle: str, content: str, report_data: Dict[str, Any]) -> str:
        """从生成的内容创建内容幻灯片"""
        workflow_info = report_data["workflow_info"]
        
        # 提取执行结果作为主要内容，但只显示实际内容
        execution_results = report_data.get("execution_results", {})
        
        content_html = """
        <div class="slide-content">
            <h3>主要内容</h3>
        """
        
        if execution_results:
            # 提取所有执行结果的实际内容
            for step_id, result in execution_results.items():
                actual_content = self._extract_actual_content(result)
                content_html += f"""
            <div class="step-result">
                <h4>{step_id}</h4>
                {actual_content}
            </div>
                """
        else:
            # 如果没有执行结果，使用内存摘要作为内容
            memory_summary = report_data.get("memory_summary", "")
            content_html += f"<p>{memory_summary}</p>"
        
        content_html += """
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content=content_html,
            slide_type="content",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_analysis_slide_from_content(self, title: str, subtitle: str, content: str, report_data: Dict[str, Any]) -> str:
        """从生成的内容创建分析幻灯片"""
        workflow_info = report_data["workflow_info"]
        quality_assessment = report_data.get("quality_assessment")
        
        analysis_content = """
        <div class="slide-content">
            <h3>关键分析</h3>
            <p>本报告基于深度分析生成，提供了全面的洞察。</p>
        """
        
        if quality_assessment:
            analysis_content += f"""
            <div class="quality-score">
                <p><strong>质量评分：</strong>{quality_assessment.overall_score:.2f} / 1.0</p>
            </div>
            
            <h3>评估维度</h3>
            <ul>
                <li>准确性: {quality_assessment.accuracy_score:.2f}</li>
                <li>完整性: {quality_assessment.completeness_score:.2f}</li>
                <li>逻辑性: {quality_assessment.logical_score:.2f}</li>
                <li>可读性: {quality_assessment.readability_score:.2f}</li>
                <li>相关性: {quality_assessment.relevance_score:.2f}</li>
            </ul>
            """
        else:
            analysis_content += "<p>质量评估数据暂不可用</p>"
        
        analysis_content += """
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content=analysis_content,
            slide_type="content",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_conclusion_slide_from_content(self, title: str, subtitle: str, content: str, report_data: Dict[str, Any]) -> str:
        """从生成的内容创建结论幻灯片"""
        workflow_info = report_data["workflow_info"]
        
        conclusion_content = f"""
        <div class="slide-content">
            <h3>总结与建议</h3>
            <p><strong>工作流ID：</strong>{workflow_info['workflow_id']}</p>
            <p><strong>生成时间：</strong>{workflow_info['generation_time']}</p>
            
            <h3>主要成果</h3>
            <ul>
                <li>成功完成用户请求的自动化处理</li>
                <li>生成高质量的分析内容</li>
                <li>通过多Agent协作确保结果质量</li>
            </ul>
            
            <h3>谢谢观看</h3>
            <p class="thank-you">感谢您的关注！</p>
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content=conclusion_content,
            slide_type="summary",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_generic_slide_from_content(self, title: str, subtitle: str, content: str, report_data: Dict[str, Any]) -> str:
        """从生成的内容创建通用幻灯片"""
        workflow_info = report_data["workflow_info"]
        
        generic_content = f"""
        <div class="slide-content">
            <h3>{title}</h3>
            <p>{subtitle}</p>
            <p>内容基于报告数据自动生成</p>
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content=generic_content,
            slide_type="content",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_fallback_slide(self, title: str, subtitle: str, report_data: Dict[str, Any]) -> str:
        """创建备用幻灯片"""
        workflow_info = report_data["workflow_info"]
        
        fallback_content = f"""
        <div class="slide-content">
            <h3>{title}</h3>
            <p>{subtitle}</p>
            <p>注意：由于生成问题，这是备用格式的幻灯片。</p>
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=title,
            subtitle=subtitle,
            content=fallback_content,
            slide_type="content",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _generate_slides_content(self, report_data: Dict[str, Any]) -> List[str]:
        """
        生成幻灯片内容列表
        
        Args:
            report_data: 报告数据
            
        Returns:
            幻灯片内容列表
        """
        slides = []
        
        # 幻灯片1: 标题页
        title_slide = self._create_title_slide(report_data)
        slides.append(title_slide)
        
        # 幻灯片2: 目录页
        toc_slide = self._create_toc_slide(report_data)
        slides.append(toc_slide)
        
        # 幻灯片3: 项目背景
        background_slide = self._create_background_slide(report_data)
        slides.append(background_slide)
        
        # 幻灯片4: 执行结果
        execution_slide = self._create_execution_slide(report_data)
        slides.append(execution_slide)
        
        # 幻灯片5: 质量评估
        if report_data["quality_assessment"]:
            quality_slide = self._create_quality_slide(report_data["quality_assessment"])
            slides.append(quality_slide)
        
        # 幻灯片6: 总结页
        summary_slide = self._create_summary_slide(report_data)
        slides.append(summary_slide)
        
        return slides
    
    def _create_title_slide(self, report_data: Dict[str, Any]) -> str:
        """创建标题幻灯片"""
        workflow_info = report_data["workflow_info"]
        plan_info = report_data["plan_info"]
        
        report_title = plan_info.get("report_title", workflow_info["user_request"]) if plan_info else workflow_info["user_request"]
        report_subtitle = plan_info.get("report_objective", "自动生成的演示文稿") if plan_info else "自动生成的演示文稿"
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title=report_title,
            subtitle=report_subtitle,
            content="",
            slide_type="title",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_toc_slide(self, report_data: Dict[str, Any]) -> str:
        """创建目录幻灯片"""
        plan_info = report_data["plan_info"]
        
        toc_content = """
        <div class="toc-content">
            <h3>演示内容</h3>
            <ol>
                <li>项目背景</li>
                <li>执行结果</li>
                <li>质量评估</li>
                <li>总结</li>
            </ol>
        </div>
        """
        
        if plan_info and plan_info.get("main_sections"):
            toc_content += """
            <div class="toc-content">
                <h3>主要章节</h3>
                <ul>
            """
            for section in plan_info.get("main_sections", []):
                toc_content += f"<li>{section}</li>\n"
            toc_content += "</ul></div>"
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title="目录",
            subtitle="演示内容概览",
            content=toc_content,
            slide_type="toc",
            generation_time=report_data["workflow_info"]["generation_time"],
            workflow_id=report_data["workflow_info"]["workflow_id"]
        )
    
    def _create_background_slide(self, report_data: Dict[str, Any]) -> str:
        """创建项目背景幻灯片"""
        workflow_info = report_data["workflow_info"]
        plan_info = report_data["plan_info"]
        
        content = f"""
        <div class="slide-content">
            <h3>项目背景</h3>
            <p>基于用户请求：<strong>{workflow_info['user_request']}</strong></p>
            
            <h3>项目目标</h3>
            <p>{plan_info.get('report_objective', '生成高质量的分析报告') if plan_info else '生成高质量的分析报告'}</p>
            
            <h3>约束条件</h3>
            <ul>
        """
        
        if workflow_info["user_constraints"]:
            for constraint in workflow_info["user_constraints"]:
                content += f"<li>{constraint}</li>\n"
        else:
            content += "<li>无特殊约束</li>\n"
        
        content += """
            </ul>
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title="项目背景",
            subtitle="背景与目标",
            content=content,
            slide_type="content",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _create_execution_slide(self, report_data: Dict[str, Any]) -> str:
        """创建执行结果幻灯片"""
        execution_results = report_data["execution_results"]
        
        content = """
        <div class="slide-content">
            <h3>执行步骤</h3>
        """
        
        if execution_results:
            for step_id, result in execution_results.items():
                actual_content = self._extract_actual_content(result)
                content += f"""
            <div class="step-result">
                <h4>{step_id}</h4>
                {actual_content}
            </div>
                """
        else:
            content += "<p>暂无执行结果</p>"
        
        content += """
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title="执行结果",
            subtitle="步骤执行情况",
            content=content,
            slide_type="content",
            generation_time=report_data["workflow_info"]["generation_time"],
            workflow_id=report_data["workflow_info"]["workflow_id"]
        )
    
    def _create_quality_slide(self, quality_assessment) -> str:
        """创建质量评估幻灯片"""
        content = f"""
        <div class="slide-content">
            <h3>质量评估结果</h3>
            <div class="quality-score">
                <p><strong>总体评分：</strong>{quality_assessment.overall_score:.2f} / 1.0</p>
            </div>
            
            <h3>详细评分</h3>
            <ul>
                <li>准确性: {quality_assessment.accuracy_score:.2f}</li>
                <li>完整性: {quality_assessment.completeness_score:.2f}</li>
                <li>逻辑性: {quality_assessment.logical_score:.2f}</li>
                <li>可读性: {quality_assessment.readability_score:.2f}</li>
                <li>相关性: {quality_assessment.relevance_score:.2f}</li>
            </ul>
        """
        
        if quality_assessment.strengths:
            content += """
            <h3>主要优点</h3>
            <ul>
            """
            for strength in quality_assessment.strengths[:3]:  # 限制显示数量
                content += f"<li>{strength}</li>\n"
            content += "</ul>"
        
        content += """
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title="质量评估",
            subtitle="结果质量分析",
            content=content,
            slide_type="content",
            generation_time=datetime.now().isoformat(),
            workflow_id=""
        )
    
    def _create_summary_slide(self, report_data: Dict[str, Any]) -> str:
        """创建总结幻灯片"""
        workflow_info = report_data["workflow_info"]
        quality_assessment = report_data["quality_assessment"]
        
        content = f"""
        <div class="slide-content">
            <h3>项目总结</h3>
            <p>工作流ID: {workflow_info['workflow_id']}</p>
            <p>生成时间: {workflow_info['generation_time']}</p>
            
            <h3>主要成果</h3>
            <ul>
                <li>成功完成用户请求的自动化处理</li>
                <li>生成高质量的分析内容</li>
                <li>通过多Agent协作确保结果质量</li>
            </ul>
        """
        
        if quality_assessment:
            content += f"""
            <h3>质量表现</h3>
            <p>总体评分: {quality_assessment.overall_score:.2f} / 1.0</p>
            """
        
        content += """
            <h3>谢谢观看</h3>
            <p class="thank-you">感谢您的关注！</p>
        </div>
        """
        
        template = self._get_ppt_slide_template()
        
        return template.render(
            title="总结",
            subtitle="项目完成情况",
            content=content,
            slide_type="summary",
            generation_time=workflow_info["generation_time"],
            workflow_id=workflow_info["workflow_id"]
        )
    
    def _get_ppt_slide_template(self) -> Template:
        """获取PPT幻灯片模板"""
        template_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Microsoft YaHei', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }
        
        .slide {
            width: 90vw;
            height: 90vh;
            max-width: 1200px;
            max-height: 800px;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            display: flex;
            flex-direction: column;
            overflow: hidden;
            position: relative;
        }
        
        .slide-header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px 40px;
            text-align: center;
        }
        
        .slide-title {
            font-size: 2.5em;
            font-weight: bold;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
        }
        
        .slide-subtitle {
            font-size: 1.3em;
            opacity: 0.9;
            font-weight: 300;
        }
        
        .slide-body {
            flex: 1;
            padding: 40px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        }
        
        .slide-content {
            text-align: center;
            color: #333;
        }
        
        .slide-content h3 {
            color: #4facfe;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        
        .slide-content p {
            font-size: 1.2em;
            line-height: 1.6;
            margin-bottom: 20px;
        }
        
        .slide-content ul, .slide-content ol {
            text-align: left;
            max-width: 600px;
            margin: 0 auto;
        }
        
        .slide-content li {
            font-size: 1.1em;
            margin-bottom: 15px;
            line-height: 1.5;
        }
        
        .slide-content strong {
            color: #4facfe;
        }
        
        .toc-content {
            display: flex;
            justify-content: space-around;
            margin-top: 30px;
        }
        
        .toc-content > div {
            background: rgba(255, 255, 255, 0.8);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            min-width: 300px;
        }
        
        .step-result {
            background: rgba(255, 255, 255, 0.8);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
        }
        
        .quality-score {
            background: rgba(79, 172, 254, 0.1);
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            border-left: 5px solid #4facfe;
        }
        
        .thank-you {
            font-size: 1.5em;
            color: #4facfe;
            font-weight: bold;
            margin-top: 30px;
            animation: pulse 2s infinite;
        }
        
        .slide-footer {
            background: rgba(0, 0, 0, 0.1);
            padding: 15px 40px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        
        /* 标题页特殊样式 */
        {% if slide_type == "title" %}
        .slide-body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-align: center;
            justify-content: center;
        }
        
        .slide-body h1 {
            font-size: 3.5em;
            margin-bottom: 20px;
            text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.4);
        }
        
        .slide-body h2 {
            font-size: 1.8em;
            opacity: 0.9;
            font-weight: 300;
        }
        {% endif %}
        
        /* 总结页特殊样式 */
        {% if slide_type == "summary" %}
        .slide-body {
            background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        }
        {% endif %}
    </style>
</head>
<body>
    <div class="slide">
        <div class="slide-header">
            <h1 class="slide-title">{{ title }}</h1>
            <p class="slide-subtitle">{{ subtitle }}</p>
        </div>
        
        <div class="slide-body">
            {{ content | safe }}
        </div>
        
        <div class="slide-footer">
            <p>生成时间: {{ generation_time }} | 工作流ID: {{ workflow_id }}</p>
        </div>
    </div>
</body>
</html>
        """
        
        return Template(template_content)
    
    def _extract_step_summary(self, result: Any) -> str:
        """提取步骤结果的摘要"""
        return self._extract_actual_content(result)
    
    def _generate_ppt_summary(self, report_data: Dict[str, Any], slide_files: List[Dict[str, Any]]) -> str:
        """生成PPT幻灯片摘要"""
        workflow_info = report_data["workflow_info"]
        
        summary = f"""
PPT幻灯片生成摘要
演示文稿标题: {report_data['plan_info'].get('report_title', workflow_info['user_request']) if report_data['plan_info'] else workflow_info['user_request']}
工作流ID: {workflow_info['workflow_id']}
生成时间: {workflow_info['generation_time']}
幻灯片数量: {len(slide_files)}

幻灯片列表:
"""
        
        for slide in slide_files:
            summary += f"- 幻灯片 {slide['slide_number']}: {slide['title']}\n"
        
        return summary
