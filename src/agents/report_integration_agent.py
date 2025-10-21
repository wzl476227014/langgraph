"""
Report Integration Agent模块
负责将所有确认的章节整合成完整的HTML报告
"""

import json
import uuid
import os
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
from ..utils.config import get_agent_config, get_agent_prompt
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response
from jinja2 import Environment, FileSystemLoader, Template
from ..tools.create_slide import CreateSlideTool

logger = get_logger(__name__)


class ReportIntegrationAgent:
    """Report Integration Agent - 报告整合专家"""
    
    def __init__(self):
        """初始化Report Integration Agent"""
        self.config = get_agent_config("report_integration")
        self.system_prompt = get_agent_prompt("report_integration_agent")
        
        # 设置模板环境
        self.template_env = self._setup_template_environment()
        
        # 初始化幻灯片工具
        self.slide_tool = CreateSlideTool()
        
        logger.info("Report Integration Agent初始化完成", agent_name="ReportIntegrationAgent")
    
    def _setup_template_environment(self) -> Environment:
        """设置Jinja2模板环境"""
        try:
            # 获取模板目录
            template_dir = Path("src/templates")
            if template_dir.exists():
                env = Environment(loader=FileSystemLoader(str(template_dir)))
                logger.info(f"模板环境设置成功，模板目录: {template_dir}", agent_name="ReportIntegrationAgent")
                return env
            else:
                logger.warning(f"模板目录不存在: {template_dir}，使用默认模板", agent_name="ReportIntegrationAgent")
                # 使用默认模板
                env = Environment()
                return env
        except Exception as e:
            logger.error(f"模板环境设置失败: {str(e)}", agent_name="ReportIntegrationAgent")
            return Environment()
    
    def execute(self, state, confirmed_chapters: Dict[str, Any], extract_only: bool = False) -> Dict[str, Any]:
        """
        执行报告整合任务
        
        Args:
            state: 工作流状态
            confirmed_chapters: 已确认的章节内容
            extract_only: 是否只提取不整合（默认False）
            
        Returns:
            整合结果字典
        """
        # 检查是否从状态中获取extract_only参数
        if hasattr(state, 'extract_only'):
            extract_only = state.extract_only
        
        # 检查是否使用Premium模板
        use_premium_template = False
        if hasattr(state, 'use_premium_template'):
            use_premium_template = state.use_premium_template
            logger.info(f"检测到use_premium_template标志: {use_premium_template}", agent_name="ReportIntegrationAgent")
            
        if extract_only:
            task_description = f"提取 {len(confirmed_chapters)} 个章节的HTML内容"
            logger.info("使用extract_only模式，只提取不整合", agent_name="ReportIntegrationAgent")
        else:
            task_description = f"整合 {len(confirmed_chapters)} 个章节成完整报告"
            
        log_agent_start("ReportIntegrationAgent", task_description)
        
        try:
            # 构建整合数据
            integration_data = self._build_integration_data(state, confirmed_chapters)
            
            if extract_only:
                # 只提取模式：将每个章节的HTML保存为独立文件
                output_paths = self._extract_chapters_to_files(integration_data)
                
                # 构建结果
                result = {
                    "integrated_content": "EXTRACT_ONLY_MODE",
                    "metadata": {
                        "output_paths": output_paths,
                        "mode": "extract_only",
                        "chapter_count": len(confirmed_chapters),
                        "extraction_time": datetime.now().isoformat(),
                        "report_title": integration_data.get("report_title", "专业报告"),
                        "report_format": "独立HTML文件集合"
                    },
                    "chapter_summary": self._generate_chapter_summary(confirmed_chapters),
                    "integration_notes": f"已提取 {len(output_paths)} 个HTML页面到独立文件"
                }
                
                logger.info(f"内容提取完成，生成 {len(output_paths)} 个HTML文件", agent_name="ReportIntegrationAgent")
                log_agent_complete("ReportIntegrationAgent", task_description, f"成功提取 {len(output_paths)} 个HTML页面")
            else:
                # 正常整合模式
                # 生成完整报告内容
                integrated_content = self._generate_integrated_report(integration_data)
                
                # 生成报告文件
                output_path = self._save_report_to_file(integrated_content, integration_data)
                
                # 构建结果
                result = {
                    "integrated_content": integrated_content,
                    "metadata": {
                        "output_path": str(integration_data.get('output_path', output_path)),
                        "file_size": len(integrated_content),
                        "chapter_count": len(confirmed_chapters),
                        "integration_time": datetime.now().isoformat(),
                        "report_title": integration_data.get("report_title", "专业报告"),
                        "report_format": "独立HTML PPT" if 'task_' in str(integration_data.get('output_path', '')) else "标准HTML报告"
                    },
                    "chapter_summary": self._generate_chapter_summary(confirmed_chapters),
                    "integration_notes": "所有章节已成功整合为独立HTML PPT页面" if 'task_' in str(integration_data.get('output_path', '')) else "所有章节已成功整合为完整报告"
                }
                
                logger.info(f"报告整合完成，生成文件: {output_path}", agent_name="ReportIntegrationAgent")
                log_agent_complete("ReportIntegrationAgent", task_description, f"成功整合 {len(confirmed_chapters)} 个章节")
            
            return result
            
        except Exception as e:
            error_msg = f"报告{'提取' if extract_only else '整合'}失败: {str(e)}"
            logger.error(error_msg, agent_name="ReportIntegrationAgent")
            raise Exception(error_msg)
    
    def _build_integration_data(self, state, confirmed_chapters: Dict[str, Any]) -> Dict[str, Any]:
        """构建整合数据"""
        # 获取报告基本信息
        plan_data = getattr(state, 'plan', {}) or {}
        report_title = plan_data.get('report_title', '专业分析报告')
        report_objective = plan_data.get('report_objective', '提供专业的分析和建议')
        
        # 获取Premium模板标志
        use_premium_template = getattr(state, 'use_premium_template', False)
        
        # 按步骤顺序排序章节
        sorted_chapters = []
        for step_id in sorted(confirmed_chapters.keys()):
            chapter_data = confirmed_chapters[step_id]
            chapter_data['step_id'] = step_id
            
            # 检查是否是Create Slide Tool生成的内容
            content = chapter_data.get('content', '')
            metadata = chapter_data.get('metadata', {})
            
            # 简化判断：信任React Agent生成的所有内容
            # 检查是否是React Agent生成的多页内容
            if metadata.get('is_multi_page', False) or 'PAGE_BREAK' in content:
                chapter_data['is_complete_ppt'] = True
                chapter_data['is_multi_page'] = True
                chapter_data['page_count'] = metadata.get('page_count', content.count('PAGE_BREAK') + 1)
                logger.info(f"章节 {step_id} 是React Agent生成的{chapter_data['page_count']}页PPT", agent_name="ReportIntegrationAgent")
            elif metadata.get('generated_by') == 'CreateSlideTool' or '<!DOCTYPE html' in content:
                # Create Slide Tool生成的或者包含DOCTYPE的都认为是完整PPT
                chapter_data['is_complete_ppt'] = True
                chapter_data['is_multi_page'] = False
                chapter_data['page_count'] = 1
                logger.info(f"章节 {step_id} 已经是完整PPT格式", agent_name="ReportIntegrationAgent")
            else:
                chapter_data['is_complete_ppt'] = False
                chapter_data['is_multi_page'] = False
                chapter_data['page_count'] = 1
                
            sorted_chapters.append(chapter_data)
        
        integration_data = {
            "report_title": report_title,
            "report_subtitle": report_objective,
            "generation_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "workflow_id": state.workflow_id,
            "user_request": state.user_request,
            "chapters": sorted_chapters,
            "total_chapters": len(sorted_chapters),
            "quality_assessment": getattr(state, 'quality_assessment', None),
            "use_premium_template": use_premium_template,  # 添加Premium模板标志
            "workflow_info": {
                "start_time": state.start_time,
                "end_time": datetime.now(),
                "workflow_status": str(state.workflow_status),
                "user_request": state.user_request,
                "user_constraints": state.user_constraints
            }
        }
        
        return integration_data
    
    def _generate_integrated_report(self, integration_data: Dict[str, Any]) -> str:
        """生成整合的报告内容 - 现在生成独立的PPT文件"""
        try:
            # 确保有章节内容
            if not integration_data.get('chapters'):
                logger.warning("没有章节内容，无法生成PPT", agent_name="ReportIntegrationAgent")
                return self._generate_default_integrated_report(integration_data)
            
            # 处理章节内容分页
            processed_chapters = self._process_chapters_for_ppt(integration_data['chapters'])
            
            # 计算总幻灯片数
            total_slides = 2  # 封面 + 目录
            for chapter in processed_chapters:
                total_slides += len(chapter.get('slides', [{'content': chapter.get('content', '')}]))
            
            # 为本次任务创建独立目录
            task_dir = self._create_task_directory(integration_data['workflow_id'])
            
            # 生成所有独立的PPT文件
            slide_files = self._generate_individual_slides(
                processed_chapters, 
                integration_data, 
                total_slides, 
                task_dir
            )
            
            # 生成索引页面
            index_content = self._generate_index_page(slide_files, integration_data, task_dir)
            
            # 更新输出路径指向任务目录的index.html
            integration_data['output_path'] = os.path.join(task_dir, 'index.html')
            
            return index_content
            
        except Exception as e:
            logger.warning(f"生成独立PPT文件失败: {str(e)}，回退到标准模板", agent_name="ReportIntegrationAgent")
            try:
                # 回退到标准模板
                template = self.template_env.get_template('integrated_report.html')
                content = template.render(**integration_data)
                return content
            except Exception as e2:
                logger.warning(f"使用标准模板失败: {str(e2)}，使用默认模板", agent_name="ReportIntegrationAgent")
                # 使用默认模板
                return self._generate_default_integrated_report(integration_data)
    
    def _create_task_directory(self, workflow_id: str) -> str:
        """为当前任务创建独立目录"""
        import os
        from datetime import datetime
        
        # 创建任务目录名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        task_dir_name = f"task_{workflow_id[:8]}_{timestamp}"
        task_dir = os.path.join("examples", "sample_reports", task_dir_name)
        
        # 创建目录
        os.makedirs(task_dir, exist_ok=True)
        
        logger.info(f"为任务创建目录: {task_dir}", agent_name="ReportIntegrationAgent")
        return task_dir
    
    def _generate_individual_slides(self, chapters: List[Dict[str, Any]], integration_data: Dict[str, Any], total_slides: int, task_dir: str) -> List[Dict[str, str]]:
        """生成独立的PPT幻灯片文件"""
        slide_files = []
        slide_counter = 1
        
        # 保存use_premium_template状态供后续使用
        self.use_premium_template = integration_data.get('use_premium_template', False)
        
        try:
            template = self.template_env.get_template('single_slide.html')
        except Exception as e:
            logger.warning(f"无法加载单页模板: {str(e)}，使用内置模板", agent_name="ReportIntegrationAgent")
            # 使用内置模板而不是返回空列表
            template = None
        
        # 生成封面
        cover_file = f"slide_{slide_counter:03d}_cover.html"
        cover_data = {
            'slide_type': 'cover',
            'slide_title': integration_data['report_title'],
            'slide_number': slide_counter,
            'total_slides': total_slides,
            'report_title': integration_data['report_title'],
            'report_subtitle': integration_data['report_subtitle'],
            'generation_time': integration_data['generation_time'],
            'workflow_id': integration_data['workflow_id'],
            'next_slide_file': f"slide_{slide_counter+1:03d}_toc.html"
        }
        
        if template:
            cover_content = template.render(**cover_data)
        else:
            cover_content = self._generate_built_in_slide_template(cover_data)
            
        cover_path = os.path.join(task_dir, cover_file)
        
        with open(cover_path, 'w', encoding='utf-8') as f:
            f.write(cover_content)
        
        slide_files.append({
            'file': cover_file,
            'title': '封面',
            'type': 'cover',
            'number': slide_counter
        })
        slide_counter += 1
        
        # 生成目录
        toc_file = f"slide_{slide_counter:03d}_toc.html"
        toc_data = {
            'slide_type': 'toc',
            'slide_title': '目录',
            'slide_number': slide_counter,
            'total_slides': total_slides,
            'chapters': chapters,
            'prev_slide_file': f"slide_{slide_counter-1:03d}_cover.html",
            'next_slide_file': f"slide_{slide_counter+1:03d}_content.html" if chapters else None
        }
        
        if template:
            toc_content = template.render(**toc_data)
        else:
            toc_content = self._generate_built_in_slide_template(toc_data)
            
        toc_path = os.path.join(task_dir, toc_file)
        
        with open(toc_path, 'w', encoding='utf-8') as f:
            f.write(toc_content)
        
        slide_files.append({
            'file': toc_file,
            'title': '目录',
            'type': 'toc',
            'number': slide_counter
        })
        slide_counter += 1
        
        # 生成章节内容
        for chapter_idx, chapter in enumerate(chapters):
            chapter_slides = chapter.get('slides', [{'content': chapter.get('content', '')}])
            
            for slide_idx, slide in enumerate(chapter_slides):
                slide_file = f"slide_{slide_counter:03d}_content.html"
                
                # 确定导航链接
                prev_file = f"slide_{slide_counter-1:03d}_{'toc' if slide_counter == 3 else 'content'}.html"
                next_file = None
                if slide_counter < total_slides:
                    next_file = f"slide_{slide_counter+1:03d}_content.html"
                
                # 从章节标题中提取简洁的标题
                raw_title = chapter['section_title']
                clean_title = self._extract_clean_title(raw_title)
                
                slide_title = clean_title
                if len(chapter_slides) > 1:
                    slide_title += f" ({slide_idx + 1}/{len(chapter_slides)})"
                
                # 检查内容是否已经是完整的HTML PPT格式
                content_to_check = slide['content']
                
                # 检测内容类型
                has_doctype = '<!DOCTYPE html' in content_to_check
                has_chartjs = 'chart.js' in content_to_check
                slide_class_exists = 'class="slide' in content_to_check
                is_long_enough = len(content_to_check) > 300
                
                # 检查是否是HTML片段（Integration Agent拆分产生的）
                # 更准确的判断：只有当内容以HTML标签开头但不包含完整HTML结构时才认为是片段
                is_html_fragment = (
                    content_to_check.strip().startswith('<') and 
                    not content_to_check.startswith('<!DOCTYPE') and
                    not has_doctype and
                    not ('<html' in content_to_check and '</html>' in content_to_check and '<body' in content_to_check)
                )
                
                # 简化判断：只要包含基本HTML结构就认为是完整PPT
                # 信任React Agent生成的内容
                is_complete_ppt = (
                    # 有DOCTYPE声明
                    has_doctype or
                    # 或者有完整的HTML标签结构
                    ('<html' in content_to_check and '</html>' in content_to_check) or
                    # 或者是Create Slide Tool生成的（包含slide类）
                    slide_class_exists or
                    # 或者内容足够长（可能是完整内容）
                    (is_long_enough and content_to_check.strip().startswith('<'))
                )
                
                # 特殊处理：如果是HTML片段，直接重新生成（不显示调试信息）
                if is_html_fragment:
                    logger.info(f"检测到HTML片段内容，需要重新生成: {slide_title}", agent_name="ReportIntegrationAgent")
                elif not is_complete_ppt:
                    # 只有非HTML片段且检测失败时才显示详细调试信息
                    logger.info(f"PPT格式检测详情 - {slide_title}:", agent_name="ReportIntegrationAgent")
                    logger.info(f"  内容长度: {len(content_to_check)}", agent_name="ReportIntegrationAgent") 
                    logger.info(f"  开头: {content_to_check[:50]}...", agent_name="ReportIntegrationAgent")
                    logger.info(f"  包含<!DOCTYPE html: {has_doctype}", agent_name="ReportIntegrationAgent")
                    logger.info(f"  包含chart.js: {has_chartjs}", agent_name="ReportIntegrationAgent")
                    logger.info(f"  包含class=\"slide: {slide_class_exists}", agent_name="ReportIntegrationAgent")
                    logger.info(f"  长度足够(>300): {is_long_enough}", agent_name="ReportIntegrationAgent")
                
                if is_complete_ppt:
                    
                    # 内容已经是完整的PPT HTML，检查是否需要使用Premium模板重新处理
                    logger.info(f"✓ 检测到完整PPT内容: {slide_title}", agent_name="ReportIntegrationAgent")
                    
                    # 如果启用了Premium模板且内容包含嵌套HTML，需要重新处理
                    if (hasattr(self, 'use_premium_template') and self.use_premium_template and 
                        content_to_check.count('<!DOCTYPE') > 1):
                        logger.info(f"检测到嵌套HTML且使用Premium模板，重新处理: {slide_title}", agent_name="ReportIntegrationAgent")
                        # 使用CreateSlide工具重新处理，避免嵌套HTML
                        slide_input = {
                            'task': slide['content'],
                            'slide_type': 'content',
                            'slide_number': slide_counter,
                            'material_content': f"""title: {clean_title}
content: {content_to_check}""",
                            'context': {
                                'slide_title': clean_title,
                                'slide_number': slide_counter,
                                'total_slides': total_slides,
                                'prev_slide_file': prev_file,
                                'next_slide_file': next_file
                            }
                        }
                        
                        try:
                            slide_result = self.slide_tool.execute(slide_input)
                            if slide_result['success']:
                                slide_content = slide_result['slide_content']
                            else:
                                # 回退到简单导航更新
                                slide_content = self._simple_update_navigation(content_to_check, slide_counter, total_slides, prev_file, next_file)
                        except Exception as e:
                            logger.warning(f"Premium模板处理失败，回退到简单处理: {e}")
                            slide_content = self._simple_update_navigation(content_to_check, slide_counter, total_slides, prev_file, next_file)
                    
                    elif content_to_check.startswith('<!DOCTYPE'):
                        # 标准处理：直接更新导航
                        slide_content = self._simple_update_navigation(content_to_check, slide_counter, total_slides, prev_file, next_file)
                    else:
                        # 实际上不是完整HTML，需要包装
                        logger.info(f"内容需要包装成完整HTML: {slide_title}", agent_name="ReportIntegrationAgent")
                        slide_data = {
                            'slide_type': 'content',
                            'slide_title': slide_title,
                            'slide_number': slide_counter,
                            'total_slides': total_slides,
                            'slide_content': content_to_check,
                            'prev_slide_file': prev_file,
                            'next_slide_file': next_file
                        }
                        slide_content = self._generate_built_in_slide_template(slide_data)
                    
                else:
                    # 内容需要生成PPT，使用Create Slide工具
                    if is_html_fragment:
                        logger.info(f"HTML片段转换为完整PPT: {slide_title}", agent_name="ReportIntegrationAgent")
                    else:
                        logger.warning(f"内容不是完整PPT格式，使用Create Slide工具重新生成: {slide_title}", agent_name="ReportIntegrationAgent")
                    slide_input = {
                        'task': slide['content'],
                        'slide_type': 'content',
                        'style': 'professional',
                        'max_length': 600,  # 严格控制内容长度，确保单页适配
                        'context': {
                            'slide_title': clean_title,
                            'slide_number': slide_counter,
                            'total_slides': total_slides,
                            'prev_slide_file': prev_file,
                            'next_slide_file': next_file
                        }
                    }
                    
                    # 如果启用了Premium模板，添加对应参数
                    if hasattr(self, 'use_premium_template'):
                        slide_input['use_template_direct'] = self.use_premium_template
                        slide_input['template_data'] = {
                            'title': clean_title,
                            'content': slide['content']
                        }
                        logger.info(f"使用Premium模板生成幻灯片: {slide_title}", agent_name="ReportIntegrationAgent")
                    
                    try:
                        slide_result = self.slide_tool.execute(slide_input)
                        if slide_result['success']:
                            slide_content = slide_result['slide_content']
                        else:
                            # 回退到内置模板
                            slide_data = {
                                'slide_type': 'content',
                                'slide_title': slide_title,
                                'slide_number': slide_counter,
                                'total_slides': total_slides,
                                'slide_content': slide['content'],
                                'prev_slide_file': prev_file,
                                'next_slide_file': next_file
                            }
                            slide_content = self._generate_built_in_slide_template(slide_data)
                    except Exception as e:
                        logger.warning(f"使用Create Slide工具失败: {str(e)}，回退到内置模板")
                        slide_data = {
                            'slide_type': 'content',
                            'slide_title': slide_title,
                            'slide_number': slide_counter,
                            'total_slides': total_slides,
                            'slide_content': slide['content'],
                            'prev_slide_file': prev_file,
                            'next_slide_file': next_file
                        }
                        slide_content = self._generate_built_in_slide_template(slide_data)
                    
                # 检查内容是否需要包装成完整HTML
                if not slide_content.startswith('<!DOCTYPE'):
                    # 内容不是完整HTML，需要包装
                    logger.info(f"页面 {slide_counter} 需要包装成完整HTML", agent_name="ReportIntegrationAgent")
                    slide_data = {
                        'slide_type': 'content',
                        'slide_title': slide_title,
                        'slide_number': slide_counter,
                        'total_slides': total_slides,
                        'slide_content': slide_content,
                        'prev_slide_file': prev_file,
                        'next_slide_file': next_file
                    }
                    slide_content = self._generate_built_in_slide_template(slide_data)
                else:
                    logger.info(f"✓ 页面 {slide_counter} 已是完整HTML", agent_name="ReportIntegrationAgent")
                
                slide_path = os.path.join(task_dir, slide_file)
                
                with open(slide_path, 'w', encoding='utf-8') as f:
                    f.write(slide_content)
                
                slide_files.append({
                    'file': slide_file,
                    'title': slide_title,
                    'type': 'content',
                    'number': slide_counter,
                    'chapter': chapter['section_title']
                })
                slide_counter += 1
        
        logger.info(f"生成了 {len(slide_files)} 个独立PPT文件", agent_name="ReportIntegrationAgent")
        return slide_files
    
    def _extract_clean_title(self, raw_title: str) -> str:
        """从原始标题中提取简洁的章节标题"""
        if not raw_title:
            return "章节标题"
        
        # 如果标题包含"生成报告章节:"格式，提取实际的章节名称
        if "生成报告章节:" in raw_title:
            # 提取实际的章节名称（在冒号后面，章节要求前面）
            parts = raw_title.split("生成报告章节:")
            if len(parts) > 1:
                title_part = parts[1].strip()
                # 进一步提取到"章节要求"之前的内容
                if "章节要求:" in title_part:
                    title = title_part.split("章节要求:")[0].strip()
                    return title
        
        # 移除常见的动词和前缀
        title = raw_title.replace("生成", "").replace("创建", "").replace("制作", "").strip()
        
        # 如果标题太长（可能包含了详细说明），尝试截取第一句或第一个短语
        if len(title) > 50:
            # 尝试在标点符号处截断
            for delimiter in ['，', '。', '：', ':', '（', '(']:
                if delimiter in title:
                    title = title.split(delimiter)[0].strip()
                    break
        
        # 如果标题为空，使用默认标题
        if not title:
            title = "章节标题"
        
        return title
    
    def _simple_update_navigation(self, html_content: str, slide_number: int, total_slides: int,
                                 prev_file: str, next_file: str) -> str:
        """简单更新导航链接，不做其他修改"""
        import re
        
        # 只更新导航链接部分
        if 'class="navigation"' in html_content:
            nav_buttons = []
            if prev_file:
                nav_buttons.append(f'<a href="{prev_file}" class="nav-button">上一页</a>')
            if next_file:
                nav_buttons.append(f'<a href="{next_file}" class="nav-button">下一页</a>')
            
            if nav_buttons:
                nav_html = '\n                '.join(nav_buttons)
                nav_pattern = r'<div class="navigation">.*?</div>'
                new_nav = f'<div class="navigation">\n                {nav_html}\n            </div>'
                html_content = re.sub(nav_pattern, new_nav, html_content, flags=re.DOTALL)
        
        # 更新页码（如果存在）
        if 'class="slide-number"' in html_content:
            html_content = re.sub(r'<div class="slide-number">[^<]+</div>',
                                 f'<div class="slide-number">{slide_number} / {total_slides}</div>',
                                 html_content)
        
        return html_content
    
    def _update_slide_navigation(self, html_content: str, slide_number: int, total_slides: int, 
                                prev_file: str, next_file: str) -> str:
        """更新已生成PPT的导航信息"""
        import re
        
        # 更新页码
        html_content = re.sub(r'<div class="slide-number">[^<]+</div>', 
                             f'<div class="slide-number">{slide_number} / {total_slides}</div>', 
                             html_content)
        
        # 更新导航链接
        nav_buttons = []
        if prev_file:
            nav_buttons.append(f'<a href="{prev_file}" class="nav-button">上一页</a>')
        if next_file:
            nav_buttons.append(f'<a href="{next_file}" class="nav-button">下一页</a>')
        
        nav_html = '\n                '.join(nav_buttons)
        
        # 替换导航部分
        nav_pattern = r'<div class="navigation">.*?</div>'
        new_nav = f'<div class="navigation">\n                {nav_html}\n            </div>'
        html_content = re.sub(nav_pattern, new_nav, html_content, flags=re.DOTALL)
        
        return html_content
    
    def _ensure_page_title(self, html_content: str, slide_title: str, slide_number: int) -> str:
        """确保页面有合适的标题"""
        
        # 如果没有提供有效的章节标题，不添加标题
        if not slide_title or slide_title == f"页面 {slide_number}":
            return html_content
        
        # 检查是否已经有h1标题
        if '<h1>' in html_content or '<h1 ' in html_content:
            return html_content
        
        # 提取清洁的标题（去掉页码信息）
        clean_title = slide_title.split(' (')[0].strip()
        if not clean_title:
            return html_content
        
        # 找到合适的位置插入标题
        # 1. 如果有slide-content div，在其开头插入
        if '<div class="slide-content">' in html_content:
            html_content = html_content.replace(
                '<div class="slide-content">',
                f'<div class="slide-content">\n<h1>{clean_title}</h1>'
            )
        # 2. 如果有slide div，在其开头插入
        elif '<div class="slide">' in html_content:
            html_content = html_content.replace(
                '<div class="slide">',
                f'<div class="slide">\n<h1>{clean_title}</h1>'
            )
        # 3. 如果有body，在body开头插入
        elif '<body>' in html_content:
            html_content = html_content.replace(
                '<body>',
                f'<body>\n<h1>{clean_title}</h1>'
            )
        # 4. 其他情况，在内容开头添加
        else:
            html_content = f'<h1>{clean_title}</h1>\n{html_content}'
        
        return html_content
    
    def _ensure_html_completeness(self, html_content: str, slide_number: int, total_slides: int, prev_file: str, next_file: str, slide_title: str = "") -> str:
        """确保HTML内容完整性，修复截断问题"""
        
        # 首先检查并添加缺失的标题（无论HTML是否完整）
        html_content = self._ensure_page_title(html_content, slide_title, slide_number)
        
        # 检查基本HTML结构 - 更宽容的检查逻辑
        has_doctype = '<!DOCTYPE html' in html_content
        has_html_tags = '<html' in html_content and '</html>' in html_content  
        has_body_tags = '<body' in html_content and '</body>' in html_content
        
        # 如果HTML结构基本完整（允许更灵活的检查）
        if (has_doctype or html_content.startswith('<html')) and has_html_tags and has_body_tags:
            # 修复缺少的DOCTYPE
            if not has_doctype and not html_content.startswith('<!DOCTYPE'):
                html_content = '<!DOCTYPE html>\n' + html_content
                logger.info(f"页面 {slide_number} 补充DOCTYPE声明", agent_name="ReportIntegrationAgent")
            
            # 检查是否有导航部分
            if 'class="navigation"' not in html_content:
                logger.info(f"页面 {slide_number} 缺少导航，添加导航部分", agent_name="ReportIntegrationAgent")
                html_content = self._add_navigation_to_html(html_content, slide_number, total_slides, prev_file, next_file)
            
            logger.info(f"页面 {slide_number} HTML结构完整，无需修复", agent_name="ReportIntegrationAgent")
            return html_content
        
        # HTML结构确实不完整，需要修复
        logger.warning(f"页面 {slide_number} HTML结构不完整（DOCTYPE:{has_doctype}, HTML标签:{has_html_tags}, BODY标签:{has_body_tags}），尝试修复", agent_name="ReportIntegrationAgent")
        
        # 提取主要内容
        content_start = html_content.find('<div class="slide-content">')
        if content_start == -1:
            # 找不到slide-content，尝试提取body内的内容
            content_start = html_content.find('<body>')
            if content_start != -1:
                content_start = html_content.find('>', content_start) + 1
        
        if content_start != -1:
            # 提取主要内容部分
            main_content = html_content[content_start:].strip()
            
            # 清理不完整的标签
            import re
            main_content = re.sub(r'<[^>]*$', '', main_content)  # 移除末尾不完整的标签
            
            # 重新构建完整的HTML
            page_title = slide_title if slide_title else f"页面 {slide_number}"
            fixed_html = self._build_complete_html(main_content, page_title, slide_number, total_slides, prev_file, next_file)
            
            logger.info(f"页面 {slide_number} HTML结构已修复", agent_name="ReportIntegrationAgent")
            return fixed_html
        
        # 如果无法提取内容，生成一个基本的错误页面
        logger.error(f"页面 {slide_number} 无法修复，生成错误页面", agent_name="ReportIntegrationAgent")
        return self._build_error_page(slide_number, total_slides, prev_file, next_file)
    
    def _add_navigation_to_html(self, html_content: str, slide_number: int, total_slides: int, prev_file: str, next_file: str) -> str:
        """为HTML添加导航部分"""
        
        # 生成导航按钮
        nav_buttons = []
        if prev_file:
            nav_buttons.append(f'<a href="{prev_file}" class="nav-button">上一页</a>')
        if next_file:
            nav_buttons.append(f'<a href="{next_file}" class="nav-button">下一页</a>')
        
        nav_html = '\n                '.join(nav_buttons)
        
        # 添加footer
        footer_html = f"""        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                {nav_html}
            </div>
        </div>"""
        
        # 在</div>前插入footer
        if '</div>' in html_content and '</body>' in html_content:
            # 在最后一个</div></body>之间插入footer
            body_end = html_content.rfind('</body>')
            last_div = html_content[:body_end].rfind('</div>')
            
            if last_div != -1:
                html_content = html_content[:last_div] + footer_html + '\n    ' + html_content[last_div:]
        
        return html_content
    
    def _build_complete_html(self, content: str, title: str, slide_number: int, total_slides: int, prev_file: str, next_file: str) -> str:
        """构建完整的HTML页面"""
        
        # 生成导航按钮
        nav_buttons = []
        if prev_file:
            nav_buttons.append(f'<a href="{prev_file}" class="nav-button">上一页</a>')
        if next_file:
            nav_buttons.append(f'<a href="{next_file}" class="nav-button">下一页</a>')
        
        nav_html = '\n                '.join(nav_buttons)
        
        # 检查内容是否已经有标题
        has_h1_title = '<h1>' in content or '<h1 ' in content
        
        # 如果没有标题且有有效的章节标题，添加标题
        if not has_h1_title and title != f"页面 {slide_number}" and title.strip():
            # 提取实际的章节名（去掉页码信息）
            clean_title = title.split(' (')[0].strip()  # 移除 "(1/2)" 这样的页码信息
            if clean_title:  # 确保标题不为空
                content = f'<h1>{clean_title}</h1>\n{content}'
        
        # Premium深蓝渐变模板
        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background: #0a0a0a;
            overflow-x: hidden;
            margin: 0;
            padding: 0;
        }}
        
        /* 高级深蓝渐变背景 */
        .slide {{
            width: 100%;
            min-height: 100vh;
            background: linear-gradient(135deg, 
                #0a1426 0%, 
                #1e3c72 25%, 
                #2a5298 50%, 
                #1e3c72 75%, 
                #0a1426 100%
            );
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 80px 60px;
            color: white;
            overflow: hidden;
        }}
        
        /* 动态背景图案 */
        .slide::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 199, 255, 0.05) 0%, transparent 50%);
            z-index: 1;
        }}
        
        /* 网格背景图案 */
        .slide::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(rgba(120, 199, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(120, 199, 255, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            z-index: 1;
        }}
        
        /* 内容容器 */
        .slide-content {{
            position: relative;
            z-index: 10;
            max-width: 1000px;
            width: 100%;
            text-align: left;
        }}
        
        .slide h1, h1 {{
            font-size: 2.5em !important;
            margin-bottom: 50px;
            background: linear-gradient(135deg, #ffffff 0%, #a8d8ff 100%) !important;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            position: relative;
            text-align: center;
            color: #ffffff !important;
        }}
        
        .slide h1::after {{
            content: '';
            position: absolute;
            bottom: -15px;
            left: 50%;
            transform: translateX(-50%);
            width: 80px;
            height: 3px;
            background: linear-gradient(90deg, #78c7ff, #4a9eff);
            border-radius: 2px;
        }}
        
        .content-body {{
            font-size: 1.1em;
            line-height: 1.8;
            color: #d1e7ff;
        }}
        
        .content-body h2 {{
            font-size: 1.6em;
            color: #a8d8ff;
            margin: 30px 0 20px 0;
            font-weight: 500;
        }}
        
        .content-body h3 {{
            font-size: 1.3em;
            color: #ffffff;
            margin: 25px 0 15px 0;
            font-weight: 500;
        }}
        
        .content-body p {{
            margin-bottom: 18px;
            text-align: justify;
        }}
        
        .content-body ul, .content-body ol {{
            margin: 20px 0;
            padding-left: 30px;
        }}
        
        .content-body li {{
            margin-bottom: 10px;
            line-height: 1.7;
        }}
        
        /* 页码和导航 */
        .slide-footer {{
            position: absolute;
            bottom: 40px;
            left: 60px;
            right: 60px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
        }}
        
        .slide-number {{
            font-size: 0.9em;
            color: rgba(255, 255, 255, 0.6);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            padding: 8px 16px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }}
        
        .navigation {{
            display: flex;
            gap: 10px;
        }}
        
        .nav-button {{
            padding: 10px 20px;
            background: linear-gradient(45deg, #78c7ff, #4a9eff);
            color: #0a1426;
            text-decoration: none;
            border-radius: 25px;
            font-size: 0.9em;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
        }}
        
        .nav-button:hover {{
            background: linear-gradient(45deg, #4a9eff, #2e7cff);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(120, 199, 255, 0.3);
        }}
        
        /* 动画效果 */
        .slide {{
            animation: slideIn 0.8s ease-out;
        }}
        
        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .slide {{
                padding: 40px 25px;
            }}
            
            .slide h1 {{
                font-size: 2em;
            }}
            
            .slide-footer {{
                flex-direction: column;
                gap: 15px;
                bottom: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="slide content">
        <div class="slide-content">
            <div class="content-body">
                {content}
            </div>
        </div>
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                {nav_html}
            </div>
        </div>
    </div>
</body>
</html>"""
        
        return html_template
    
    def _build_error_page(self, slide_number: int, total_slides: int, prev_file: str, next_file: str) -> str:
        """构建错误页面"""
        return self._build_complete_html(
            '<h1>页面生成错误</h1><p>该页面内容生成时出现错误，请重新生成。</p>',
            f'错误页面 {slide_number}',
            slide_number,
            total_slides,
            prev_file,
            next_file
        )
    
    def _generate_index_page(self, slide_files: List[Dict[str, str]], integration_data: Dict[str, Any], task_dir: str) -> str:
        """生成PPT索引页面"""
        # 清理标题
        clean_report_title = self._clean_title_string(integration_data.get('report_title', '专业分析报告'))
        
        index_html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{clean_report_title} - PPT导航</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            padding: 40px;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #2a5298;
        }}
        .header h1 {{
            color: #1e3c72;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .header p {{
            color: #666;
            font-size: 1.1em;
        }}
        .slides-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .slide-card {{
            border: 1px solid #e1e4e8;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .slide-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
        }}
        .slide-card.cover {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
        }}
        .slide-card.toc {{
            background: #f8f9fa;
        }}
        .slide-card h3 {{
            margin-bottom: 10px;
            font-size: 1.2em;
        }}
        .slide-card p {{
            margin-bottom: 15px;
            color: #666;
        }}
        .slide-card.cover p {{
            color: rgba(255, 255, 255, 0.8);
        }}
        .slide-link {{
            display: inline-block;
            padding: 10px 20px;
            background: #2a5298;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            transition: background 0.3s ease;
        }}
        .slide-link:hover {{
            background: #1e3c72;
        }}
        .slide-card.cover .slide-link {{
            background: rgba(255, 255, 255, 0.2);
        }}
        .slide-card.cover .slide-link:hover {{
            background: rgba(255, 255, 255, 0.3);
        }}
        .footer {{
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #e1e4e8;
            color: #666;
        }}
        .start-button {{
            display: inline-block;
            padding: 15px 30px;
            background: #1e3c72;
            color: white;
            text-decoration: none;
            border-radius: 25px;
            font-size: 1.2em;
            font-weight: 500;
            margin: 20px 0;
            transition: background 0.3s ease;
        }}
        .start-button:hover {{
            background: #2a5298;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{integration_data['report_title']}</h1>
            <p>{integration_data['report_subtitle']}</p>
            <a href="{slide_files[0]['file']}" class="start-button">开始演示</a>
        </div>
        
        <div class="slides-grid">
"""
        
        for slide in slide_files:
            card_class = slide['type']
            index_html += f"""
            <div class="slide-card {card_class}">
                <h3>第 {slide['number']} 页</h3>
                <p>{slide['title']}</p>
                <a href="{slide['file']}" class="slide-link">查看幻灯片</a>
            </div>
"""
        
        index_html += f"""
        </div>
        
        <div class="footer">
            <p>生成时间: {integration_data['generation_time']} | 工作流ID: {integration_data['workflow_id']}</p>
            <p>总共 {len(slide_files)} 页PPT | 本报告由 MARGS 自动生成</p>
        </div>
    </div>
</body>
</html>
"""
        
        # 保存索引页面
        index_path = os.path.join(task_dir, 'index.html')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_html)
        
        logger.info(f"生成PPT索引页面: {index_path}", agent_name="ReportIntegrationAgent")
        return index_html
    
    def _process_chapters_for_ppt(self, chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理章节内容，将长内容分页成多个幻灯片，并智能合并稀薄内容"""
        processed_chapters = []
        pending_merge_chapter = None  # 待合并的稀薄章节
        
        for chapter in chapters:
            processed_chapter = chapter.copy()
            content = chapter.get('content', '')
            
            # 如果已经是完整PPT格式，检查是否需要进一步分页
            if chapter.get('is_complete_ppt', False):
                # 如果React Agent已经生成了多页内容，直接拆分使用
                if chapter.get('is_multi_page', False):
                    logger.info(f"章节 '{chapter.get('section_title')}' 已由React Agent拆分为{chapter.get('page_count', 1)}页，直接使用", agent_name="ReportIntegrationAgent")
                    slides = self._split_react_multi_page_content(content)
                    processed_chapter['slides'] = slides
                    processed_chapters.append(processed_chapter)
                    continue
                
                # 提取HTML中的实际内容文本来判断长度
                import re
                text_only = re.sub(r'<[^>]+>', '', content)
                text_only = re.sub(r'\s+', ' ', text_only).strip()
                
                # 统计内容元素数量
                li_count = content.count('<li>')
                p_count = content.count('<p>')
                
                # 更严格的稀薄内容判断标准：
                # 1. 少于4个要点且少于300字符纯文本
                # 2. 或者内容总长度少于150字符（极少内容）
                # 3. 同时检查实际可见内容密度
                visible_content_ratio = len(text_only) / max(len(content), 1) * 100
                
                is_sparse = (
                    (li_count < 4 and len(text_only) < 300) or  # 要点少且文本短
                    len(text_only) < 150 or                     # 内容极少
                    (li_count < 6 and len(text_only) < 250 and visible_content_ratio < 20)  # HTML标签多但实际内容少
                )
                
                if is_sparse:
                    logger.info(f"检测到稀薄内容章节: '{chapter.get('section_title')}' (要点:{li_count}个, 文本:{len(text_only)}字符)", agent_name="ReportIntegrationAgent")
                    
                    if pending_merge_chapter is None:
                        # 暂存这个稀薄章节，等待与下一个合并
                        pending_merge_chapter = processed_chapter
                        pending_merge_chapter['slides'] = [{'content': content}]
                        continue
                    else:
                        # 将当前稀薄章节与之前的稀薄章节合并
                        merged_chapter = self._merge_sparse_chapters(pending_merge_chapter, processed_chapter)
                        processed_chapters.append(merged_chapter)
                        pending_merge_chapter = None
                        continue
                
                # 如果当前章节不稀薄，但有待合并章节，先处理待合并章节
                if pending_merge_chapter is not None:
                    # 检查主题相关性和合并可行性
                    combined_length = len(re.sub(r'<[^>]+>', '', pending_merge_chapter['content'])) + len(text_only)
                    themes_related = self._check_content_similarity(pending_merge_chapter, processed_chapter)
                    
                    # 更宽松的合并条件：主题相关或合并后长度仍适中
                    if (combined_length < 800 and themes_related) or combined_length < 500:
                        logger.info(f"将稀薄章节与当前章节合并: '{pending_merge_chapter.get('section_title')}' + '{chapter.get('section_title')}' (主题相关:{themes_related}, 总长度:{combined_length})", agent_name="ReportIntegrationAgent")
                        merged_chapter = self._merge_sparse_chapters(pending_merge_chapter, processed_chapter)
                        processed_chapters.append(merged_chapter)
                        pending_merge_chapter = None
                        continue
                    else:
                        # 无法合并，分别处理
                        logger.info(f"稀薄章节无法与当前章节合并，分别处理: 总长度{combined_length}, 主题相关:{themes_related}", agent_name="ReportIntegrationAgent")
                        processed_chapters.append(pending_merge_chapter)
                        pending_merge_chapter = None
                
                # 如果内容太长（大于800字符纯文本），说明需要分页
                if len(text_only) > 800:
                    logger.warning(f"章节 '{chapter.get('section_title')}' PPT内容过长({len(text_only)}字符)，需要分页", agent_name="ReportIntegrationAgent")
                    # 提取body内容进行分页
                    body_match = re.search(r'<div class="slide-content">(.*?)</div>\s*<div class="slide-footer">', content, re.DOTALL)
                    if body_match:
                        inner_content = body_match.group(1)
                        slides = self._split_html_content_into_slides(inner_content)
                    else:
                        slides = [{'content': content}]
                else:
                    logger.info(f"章节 '{chapter.get('section_title')}' PPT内容适合单页", agent_name="ReportIntegrationAgent")
                    slides = [{'content': content}]
            else:
                # 原始内容需要分页处理
                slides = self._split_content_into_slides(content)
                
            processed_chapter['slides'] = slides
            processed_chapters.append(processed_chapter)
        
        # 处理最后剩余的待合并章节
        if pending_merge_chapter is not None:
            logger.info(f"添加最后的稀薄章节: '{pending_merge_chapter.get('section_title')}'", agent_name="ReportIntegrationAgent")
            processed_chapters.append(pending_merge_chapter)
        
        return processed_chapters
    
    def _merge_sparse_chapters(self, chapter1: Dict[str, Any], chapter2: Dict[str, Any]) -> Dict[str, Any]:
        """合并两个稀薄的章节"""
        import re
        
        # 创建合并后的章节
        merged_chapter = chapter1.copy()
        
        # 合并标题
        title1 = self._extract_clean_title(chapter1.get('section_title', ''))
        title2 = self._extract_clean_title(chapter2.get('section_title', ''))
        
        # 如果两个标题相似（都包含相同的关键词），使用较简洁的标题
        if self._titles_are_similar(title1, title2):
            merged_title = title1 if len(title1) <= len(title2) else title2
        else:
            merged_title = f"{title1}与{title2}"
        
        merged_chapter['section_title'] = f"生成报告章节:{merged_title}"
        
        # 合并内容
        content1 = chapter1.get('content', '')
        content2 = chapter2.get('content', '')
        
        # 提取两个章节的主要内容部分
        content1_main = self._extract_slide_main_content(content1)
        content2_main = self._extract_slide_main_content(content2)
        
        # 智能合并内容，优化格式
        merged_content = self._smart_merge_content(content1_main, content2_main, merged_title)
        
        # 使用第一个章节的HTML结构，替换主要内容
        merged_html = self._rebuild_slide_with_content(content1, merged_content, merged_title)
        
        merged_chapter['content'] = merged_html
        merged_chapter['slides'] = [{'content': merged_html}]
        
        logger.info(f"成功合并章节: '{title1}' + '{title2}' -> '{merged_title}'", agent_name="ReportIntegrationAgent")
        return merged_chapter
    
    def _check_content_similarity(self, chapter1: Dict[str, Any], chapter2: Dict[str, Any]) -> bool:
        """检查两个章节内容的相关性"""
        import re
        
        # 获取标题
        title1 = self._extract_clean_title(chapter1.get('section_title', ''))
        title2 = self._extract_clean_title(chapter2.get('section_title', ''))
        
        # 检查标题相关性
        if self._titles_are_similar(title1, title2):
            return True
        
        # 提取内容中的关键词
        content1 = chapter1.get('content', '')
        content2 = chapter2.get('content', '')
        
        # 移除HTML标签，提取纯文本
        text1 = re.sub(r'<[^>]+>', ' ', content1).strip()
        text2 = re.sub(r'<[^>]+>', ' ', content2).strip()
        
        # 安全相关关键词
        security_keywords = [
            '安全', '漏洞', '攻击', '防护', '事件', '风险', '威胁', 
            '监控', '检测', '响应', '修复', '闭环', '运营',
            '资产', '评估', '管控', '合规', '审计'
        ]
        
        # 数据相关关键词  
        data_keywords = [
            '数据', '指标', '统计', '分析', '报告', '趋势',
            '百分比', '数量', '次数', '率', '分', '评分'
        ]
        
        # 业务相关关键词
        business_keywords = [
            '业务', '流程', '管理', '优化', '效率', '质量',
            '目标', '计划', '措施', '举措', '成果', '效果'
        ]
        
        all_keywords = security_keywords + data_keywords + business_keywords
        
        # 统计两个内容中共同关键词的数量
        common_keywords = 0
        for keyword in all_keywords:
            if keyword in text1 and keyword in text2:
                common_keywords += 1
        
        # 如果有3个以上共同关键词，认为内容相关
        if common_keywords >= 3:
            return True
        
        # 检查是否都包含统计数字（表明可能是数据分析相关）
        has_numbers1 = bool(re.search(r'\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:个|次|分|万|千)', text1))
        has_numbers2 = bool(re.search(r'\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:个|次|分|万|千)', text2))
        
        if has_numbers1 and has_numbers2 and common_keywords >= 2:
            return True
        
        return False
    
    def _titles_are_similar(self, title1: str, title2: str) -> bool:
        """判断两个标题是否相似"""
        import re
        # 提取关键词
        keywords1 = set(re.findall(r'[\u4e00-\u9fff]+', title1))
        keywords2 = set(re.findall(r'[\u4e00-\u9fff]+', title2))
        
        # 如果有共同关键词，认为相似
        common_keywords = keywords1.intersection(keywords2)
        return len(common_keywords) > 0
    
    def _extract_slide_main_content(self, html_content: str) -> str:
        """从PPT HTML中提取主要内容"""
        import re
        
        # 提取slide-content区域的内容
        content_match = re.search(r'<div class="slide-content">(.*?)</div>\s*<div class="slide-footer">', html_content, re.DOTALL)
        if content_match:
            return content_match.group(1).strip()
        
        # 如果没有找到，返回整个内容
        return html_content
    
    def _smart_merge_content(self, content1: str, content2: str, title: str) -> str:
        """智能合并两个内容，优化格式"""
        import re
        
        # 提取两个内容中的列表项
        items1 = re.findall(r'<li>(.*?)</li>', content1, re.DOTALL)
        items2 = re.findall(r'<li>(.*?)</li>', content2, re.DOTALL)
        
        # 清理和优化列表项格式
        all_items = []
        
        # 处理第一个内容的项目
        for item in items1:
            cleaned_item = self._clean_and_format_item(item)
            if cleaned_item:
                all_items.append(cleaned_item)
        
        # 处理第二个内容的项目
        for item in items2:
            cleaned_item = self._clean_and_format_item(item)
            if cleaned_item:
                all_items.append(cleaned_item)
        
        # 根据项目数量和类型构建更丰富的内容结构
        if len(all_items) <= 8:
            # 分析项目类型，按类别组织
            data_items = []
            achievement_items = []
            other_items = []
            
            for item in all_items:
                if any(keyword in item for keyword in ['%', '率', '数量', '次', '分', '万', '千', '个']):
                    data_items.append(item)
                elif any(keyword in item for keyword in ['完成', '实现', '达成', '成功', '提升', '优化']):
                    achievement_items.append(item)
                else:
                    other_items.append(item)
            
            # 使用三栏或双栏布局
            if len(data_items) > 0 and len(achievement_items) > 0:
                merged_content = f'''
                <div class="three-column">
                    <div class="column-left">
                        <h5 class="section-heading">关键指标</h5>
                        <ul class="styled-list">'''
                
                for item in data_items[:4]:  # 最多显示4个数据项
                    merged_content += f'<li class="metric-item">{item}</li>'
                merged_content += '</ul></div>'
                
                merged_content += '''
                    <div class="column-center">
                        <h5 class="section-heading">核心成果</h5>
                        <ul class="styled-list">'''
                
                for item in achievement_items[:4]:
                    merged_content += f'<li class="achievement-item">{item}</li>'
                merged_content += '</ul></div>'
                
                merged_content += '''
                    <div class="column-right">
                        <h5 class="section-heading">其他要点</h5>
                        <ul class="styled-list">'''
                
                # 合并剩余项目
                remaining_items = data_items[4:] + achievement_items[4:] + other_items
                for item in remaining_items[:4]:
                    merged_content += f'<li class="standard-item">{item}</li>'
                    
                merged_content += f'''</ul>
                        <div class="summary-box">
                            <p><strong>综合评估:</strong> {title}各项指标表现良好，安全运营体系效果显著。</p>
                        </div>
                    </div>
                </div>'''
            else:
                # 使用双栏布局
                mid_point = len(all_items) // 2
                left_items = all_items[:mid_point + (len(all_items) % 2)]
                right_items = all_items[mid_point + (len(all_items) % 2):]
                
                merged_content = f'''
                <div class="two-column">
                    <div class="column-left">
                        <h5 class="section-heading">主要发现</h5>
                        <ul class="styled-list">'''
                
                for item in left_items:
                    merged_content += f'<li>{item}</li>'
                
                merged_content += f'''</ul>
                    </div>
                    <div class="column-right">
                        <h5 class="section-heading">关键要点</h5>
                        <ul class="styled-list">'''
                
                for item in right_items:
                    merged_content += f'<li>{item}</li>'
                
                merged_content += f'''</ul>
                        <div class="highlight-box">
                            <h4>重点总结</h4>
                            <p>{title}体现了全面的安全运营能力，各项措施协调统一，效果良好。</p>
                        </div>
                    </div>
                </div>'''
        else:
            # 内容较多，使用分组列表格式
            merged_content = f'''
            <div class="content-sections">
                <div class="section-header">
                    <h4>{title} - 详细分析</h4>
                </div>
                <div class="two-column">
                    <div class="column-left">
                        <ul class="styled-list">'''
            
            mid_point = len(all_items) // 2
            for item in all_items[:mid_point]:
                merged_content += f'<li>{item}</li>'
            
            merged_content += '''</ul>
                    </div>
                    <div class="column-right">
                        <ul class="styled-list">'''
            
            for item in all_items[mid_point:]:
                merged_content += f'<li>{item}</li>'
                
            merged_content += '''</ul>
                    </div>
                </div>
            </div>'''
        
        return merged_content
    
    def _clean_and_format_item(self, item: str) -> str:
        """清理和格式化单个列表项，去除单调的编号格式"""
        import re
        
        # 移除原有的单调格式
        cleaned = re.sub(r'^要点\d+\*\*：', '', item)
        cleaned = re.sub(r'^\d+\*\*：', '', cleaned)
        cleaned = re.sub(r'^\*\*', '', cleaned)
        cleaned = cleaned.strip()
        
        # 如果清理后内容为空，返回空字符串
        if not cleaned:
            return ''
        
        # 确保内容简洁明了
        if len(cleaned) > 30:
            # 尝试在合适位置截断
            for delimiter in ['，', '。', '：', ':']:
                if delimiter in cleaned:
                    parts = cleaned.split(delimiter)
                    if len(parts[0]) <= 25:
                        cleaned = parts[0] + delimiter
                        break
        
        return cleaned
    
    def _rebuild_slide_with_content(self, original_html: str, new_content: str, new_title: str) -> str:
        """使用新内容重建PPT HTML"""
        import re
        
        # 更新标题
        updated_html = re.sub(r'<h1>.*?</h1>', f'<h1>{new_title}</h1>', original_html)
        
        # 更新slide-content区域
        updated_html = re.sub(
            r'<div class="slide-content">(.*?)</div>\s*<div class="slide-footer">',
            f'<div class="slide-content">\\n            {new_content}\\n            \\n        </div>\\n        <div class="slide-footer">',
            updated_html,
            flags=re.DOTALL
        )
        
        return updated_html
    
    def _split_react_multi_page_content(self, combined_content: str) -> List[Dict[str, str]]:
        """拆分React Agent生成的多页内容 - 完全信任React生成的内容"""
        import re
        
        # 按照PAGE_BREAK标记拆分，支持多种格式
        # 处理可能的换行符变化：标准格式、紧贴格式等
        pages = re.split(r'(?:\n\n)?<!-- PAGE_BREAK -->(?:\n\n)?', combined_content)
        slides = []
        
        for page in pages:
            if not page.strip():
                continue
                
            # 移除页面标记注释，但保留HTML内容
            page = re.sub(r'<!-- PAGE_\d+:.*?-->\n?', '', page)
            page = page.strip()
            
            # 检查并使用React Agent生成的内容
            if page:
                # 如果页面已经是完整HTML，直接使用
                # 否则记录为需要后续包装
                slides.append({'content': page, 'is_complete': page.startswith('<!DOCTYPE')})
                if page.startswith('<!DOCTYPE'):
                    logger.info(f"✓ React Agent生成的页面是完整HTML", agent_name="ReportIntegrationAgent")
                else:
                    logger.info(f"React Agent生成的页面需要包装", agent_name="ReportIntegrationAgent")
        
        logger.info(f"成功拆分React Agent多页内容为 {len(slides)} 个独立页面", agent_name="ReportIntegrationAgent")
        return slides
    
    def _split_html_content_into_slides(self, html_content: str, max_items_per_slide: int = 5) -> List[Dict[str, str]]:
        """将HTML格式的内容智能分页"""
        import re
        
        slides = []
        
        # 提取所有列表项
        list_items = re.findall(r'<li>(.*?)</li>', html_content, re.DOTALL)
        
        if len(list_items) <= max_items_per_slide:
            # 内容不多，保持单页
            return [{'content': html_content}]
        
        # 需要分页，每页最多max_items_per_slide个要点
        current_items = []
        for i, item in enumerate(list_items):
            current_items.append(item)
            
            if len(current_items) >= max_items_per_slide or i == len(list_items) - 1:
                # 创建新页面
                slide_content = '<ul class="styled-list">'
                for ci in current_items:
                    slide_content += f'<li>{ci}</li>'
                slide_content += '</ul>'
                
                slides.append({'content': slide_content})
                current_items = []
        
        logger.info(f"HTML内容分页完成，共生成 {len(slides)} 页", agent_name="ReportIntegrationAgent")
        return slides
    
    def _split_content_into_slides(self, content: str, max_chars_per_slide: int = 600) -> List[Dict[str, str]]:
        """将内容分割成多个幻灯片"""
        import re
        
        if not content:
            return [{'content': ''}]
        
        # 如果内容较短，直接返回单个幻灯片
        if len(content) <= max_chars_per_slide:
            return [{'content': content}]
        
        slides = []
        
        # 按段落分割内容，保持HTML结构
        content = content.strip()
        
        # 先按主要标题分割
        main_sections = re.split(r'<h[1-3][^>]*>(.*?)</h[1-3]>', content)
        
        if len(main_sections) > 3:  # 有多个主标题
            current_slide = ""
            current_length = 0
            
            for i, section in enumerate(main_sections):
                if i % 2 == 1:  # 这是标题
                    title = f"<h3>{section}</h3>"
                    if current_length + len(title) > max_chars_per_slide and current_slide:
                        slides.append({'content': current_slide.strip()})
                        current_slide = title
                        current_length = len(title)
                    else:
                        current_slide += title
                        current_length += len(title)
                else:  # 这是内容
                    if section.strip():
                        section_content = f"<p>{section}</p>"
                        if current_length + len(section_content) > max_chars_per_slide and current_slide:
                            slides.append({'content': current_slide.strip()})
                            current_slide = section_content
                            current_length = len(section_content)
                        else:
                            current_slide += section_content
                            current_length += len(section_content)
            
            if current_slide.strip():
                slides.append({'content': current_slide.strip()})
                
        else:
            # 按段落分割内容
            paragraphs = re.split(r'</p>\s*<p>', content)
            if not paragraphs:
                # 如果没有段落标签，按换行符分割
                paragraphs = content.split('\n\n')
            
            current_slide_content = ""
            current_length = 0
            
            for paragraph in paragraphs:
                # 确保段落有适当的标签
                if paragraph and not paragraph.startswith('<p>'):
                    paragraph = f'<p>{paragraph}</p>'
                elif paragraph and not paragraph.endswith('</p>'):
                    paragraph = f'{paragraph}</p>'
                
                paragraph_length = len(paragraph)
                
                # 如果当前段落太长，需要单独分页
                if paragraph_length > max_chars_per_slide:
                    # 保存当前幻灯片
                    if current_slide_content:
                        slides.append({'content': current_slide_content})
                        current_slide_content = ""
                        current_length = 0
                    
                    # 将长段落分割成多个幻灯片
                    long_slides = self._split_long_paragraph(paragraph, max_chars_per_slide)
                    slides.extend(long_slides)
                else:
                    # 检查是否可以添加到当前幻灯片
                    if current_length + paragraph_length <= max_chars_per_slide:
                        current_slide_content += paragraph
                        current_length += paragraph_length
                    else:
                        # 保存当前幻灯片，开始新幻灯片
                        if current_slide_content:
                            slides.append({'content': current_slide_content})
                        current_slide_content = paragraph
                        current_length = paragraph_length
            
            # 添加最后一个幻灯片
            if current_slide_content:
                slides.append({'content': current_slide_content})
        
        # 确保至少有一个幻灯片
        if not slides:
            slides = [{'content': content}]
        
        return slides
    
    def _split_long_paragraph(self, paragraph: str, max_chars: int) -> List[Dict[str, str]]:
        """分割过长的段落"""
        import re
        
        slides = []
        
        # 移除段落标签进行处理
        clean_text = re.sub(r'</?p>', '', paragraph)
        
        # 按句子分割
        sentences = re.split(r'([。！？])', clean_text)
        
        current_content = ""
        current_length = 0
        
        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
            else:
                sentence = sentences[i]
            
            sentence_length = len(sentence)
            
            if current_length + sentence_length <= max_chars:
                current_content += sentence
                current_length += sentence_length
            else:
                # 保存当前内容
                if current_content:
                    slides.append({'content': f'<p>{current_content}</p>'})
                current_content = sentence
                current_length = sentence_length
        
        # 添加最后的内容
        if current_content:
            slides.append({'content': f'<p>{current_content}</p>'})
        
        return slides if slides else [{'content': f'<p>{clean_text}</p>'}]
    
    def _clean_title_string(self, title: str) -> str:
        """清理标题字符串中的多余引号和逗号"""
        if isinstance(title, str):
            title = title.strip()
            # 移除开头和结尾的引号
            if title.startswith('"') and title.endswith('",'):
                title = title[1:-2]
            elif title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            # 移除末尾的逗号
            title = title.rstrip(',')
        return title
    
    def _clean_subtitle_string(self, subtitle: str) -> str:
        """清理副标题字符串，处理数组格式"""
        if isinstance(subtitle, str):
            subtitle = subtitle.strip()
            # 检查是否是数组格式
            if subtitle.startswith('[') and (subtitle.endswith('],') or subtitle.endswith(']')):
                # 移除末尾逗号
                if subtitle.endswith('],'):
                    subtitle = subtitle[:-1]
                
                try:
                    # 尝试解析为列表
                    import json
                    items = json.loads(subtitle)
                    if isinstance(items, list):
                        # 转换为友好的副标题格式，最多取前3个
                        if len(items) > 3:
                            subtitle = ' | '.join(items[:3]) + ' ...'
                        else:
                            subtitle = ' | '.join(items)
                except:
                    # 如果解析失败，移除方括号
                    subtitle = subtitle[1:-1].replace('"', '')
            else:
                # 普通字符串清理
                subtitle = self._clean_title_string(subtitle)
        
        return subtitle if subtitle else '专业分析报告'

    def _extract_chapters_to_files(self, integration_data: Dict[str, Any]) -> List[str]:
        """提取章节内容到独立HTML文件（不整合）
        
        Args:
            integration_data: 整合数据
            
        Returns:
            生成的文件路径列表
        """
        chapters = integration_data.get('chapters', [])
        if not chapters:
            logger.warning("没有章节内容可提取", agent_name="ReportIntegrationAgent")
            return []
        
        # 创建输出目录
        import os
        workflow_id = integration_data.get('workflow_id', 'unknown')
        extract_dir = self._create_extraction_directory(workflow_id)
        
        output_paths = []
        page_counter = 1
        
        for chapter_idx, chapter in enumerate(chapters):
            content = chapter.get('content', '')
            step_id = chapter.get('step_id', f'chapter_{chapter_idx + 1}')
            section_title = chapter.get('section_title', f'章节 {chapter_idx + 1}')
            
            # 清理标题作为文件名
            safe_title = self._sanitize_filename(section_title)
            
            if chapter.get('is_multi_page', False) and 'PAGE_BREAK' in content:
                # 多页内容：按PAGE_BREAK分割
                pages = content.split('PAGE_BREAK')
                for page_idx, page_content in enumerate(pages):
                    if page_content.strip():
                        # 清理并完善HTML内容
                        clean_html = self._ensure_complete_html(page_content.strip(), page_counter)
                        
                        # 生成文件名
                        filename = f"page_{page_counter:03d}_{safe_title}_{page_idx + 1}.html"
                        file_path = os.path.join(extract_dir, filename)
                        
                        # 保存文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(clean_html)
                        
                        output_paths.append(file_path)
                        page_counter += 1
                        
                        logger.info(f"已提取页面: {filename}", agent_name="ReportIntegrationAgent")
            else:
                # 单页内容
                if content.strip():
                    # 清理并完善HTML内容
                    clean_html = self._ensure_complete_html(content.strip(), page_counter)
                    
                    # 生成文件名
                    filename = f"page_{page_counter:03d}_{safe_title}.html"
                    file_path = os.path.join(extract_dir, filename)
                    
                    # 保存文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(clean_html)
                    
                    output_paths.append(file_path)
                    page_counter += 1
                    
                    logger.info(f"已提取页面: {filename}", agent_name="ReportIntegrationAgent")
        
        # 创建索引文件
        if output_paths:
            index_path = self._create_extraction_index(extract_dir, output_paths, integration_data)
            output_paths.append(index_path)
        
        logger.info(f"提取完成，共生成 {len(output_paths)} 个文件", agent_name="ReportIntegrationAgent")
        return output_paths
    
    def _create_extraction_directory(self, workflow_id: str) -> str:
        """创建提取目录"""
        import os
        from datetime import datetime
        
        # 生成目录名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dir_name = f"extract_{workflow_id}_{timestamp}"
        
        # 确保在examples/sample_reports下
        base_dir = os.path.join(os.getcwd(), "examples", "sample_reports")
        os.makedirs(base_dir, exist_ok=True)
        
        extract_dir = os.path.join(base_dir, dir_name)
        os.makedirs(extract_dir, exist_ok=True)
        
        logger.info(f"创建提取目录: {extract_dir}", agent_name="ReportIntegrationAgent")
        return extract_dir
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名，移除非法字符"""
        import re
        # 移除或替换非法字符
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        safe_name = re.sub(r'\s+', '_', safe_name)
        # 限制长度
        if len(safe_name) > 50:
            safe_name = safe_name[:50]
        return safe_name.strip('_')
    
    def _ensure_complete_html(self, content: str, page_number: int) -> str:
        """确保HTML内容是完整的"""
        # 如果已经是完整的HTML文档，直接返回
        if '<!DOCTYPE html' in content or '<html' in content:
            return content
        
        # 否则包装成完整的HTML
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>页面 {page_number}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .content {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        h1 {{
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        .page-info {{
            text-align: center;
            color: #7f8c8d;
            margin-bottom: 30px;
            padding: 10px;
            background: #ecf0f1;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="content">
        <div class="page-info">页面 {page_number}</div>
        {content}
    </div>
</body>
</html>"""
    
    def _create_extraction_index(self, extract_dir: str, file_paths: List[str], integration_data: Dict[str, Any]) -> str:
        """创建提取文件的索引页面"""
        import os
        from datetime import datetime
        
        # 清理标题
        report_title = self._clean_title_string(integration_data.get('report_title', '提取内容'))
        
        # 生成文件列表HTML
        files_html = ""
        for i, file_path in enumerate(file_paths, 1):
            filename = os.path.basename(file_path)
            files_html += f"""
            <div class="file-item">
                <div class="file-number">{i}</div>
                <div class="file-info">
                    <h3><a href="{filename}" target="_blank">{filename}</a></h3>
                    <p>点击查看页面内容</p>
                </div>
            </div>
            """
        
        index_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title} - 提取文件索引</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: #f5f7fa;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .content {{
            padding: 40px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-item {{
            text-align: center;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}
        .stat-label {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        .files-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }}
        .file-item {{
            display: flex;
            align-items: center;
            padding: 20px;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            transition: all 0.3s ease;
        }}
        .file-item:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
            border-color: #667eea;
        }}
        .file-number {{
            width: 40px;
            height: 40px;
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            margin-right: 20px;
        }}
        .file-info h3 {{
            margin: 0 0 5px 0;
            color: #495057;
        }}
        .file-info p {{
            margin: 0;
            color: #6c757d;
            font-size: 0.9em;
        }}
        .file-info a {{
            color: #667eea;
            text-decoration: none;
        }}
        .file-info a:hover {{
            text-decoration: underline;
        }}
        .footer {{
            text-align: center;
            padding: 30px;
            background: #f8f9fa;
            color: #6c757d;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{report_title}</h1>
            <p>提取内容索引 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="content">
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-number">{len(file_paths)}</div>
                    <div class="stat-label">提取文件数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{integration_data.get('total_chapters', 0)}</div>
                    <div class="stat-label">原始章节数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">{datetime.now().strftime('%Y-%m-%d')}</div>
                    <div class="stat-label">提取日期</div>
                </div>
            </div>
            
            <h2>提取文件列表</h2>
            <div class="files-grid">
                {files_html}
            </div>
        </div>
        
        <div class="footer">
            <p>提取模式 - 每个页面保存为独立HTML文件</p>
        </div>
    </div>
</body>
</html>"""
        
        index_path = os.path.join(extract_dir, "index.html")
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_html)
        
        logger.info(f"创建索引文件: {index_path}", agent_name="ReportIntegrationAgent")
        return index_path

    def _generate_built_in_slide_template(self, slide_data: Dict[str, Any]) -> str:
        """生成内置幻灯片模板"""
        slide_type = slide_data.get('slide_type', 'content')
        slide_title = slide_data.get('slide_title', 'PPT标题')
        slide_number = slide_data.get('slide_number', 1)
        total_slides = slide_data.get('total_slides', 1)
        prev_file = slide_data.get('prev_slide_file', '')
        next_file = slide_data.get('next_slide_file', '')
        
        # 根据类型生成不同的内容
        if slide_type == 'cover':
            # 清理标题和副标题
            clean_report_title = self._clean_title_string(slide_data.get('report_title', slide_title))
            clean_report_subtitle = self._clean_subtitle_string(slide_data.get('report_subtitle', '专业分析报告'))
            
            content_body = f"""
            <h1 class="title">{clean_report_title}</h1>
            <p class="subtitle">{clean_report_subtitle}</p>
            <div class="metadata">
                <p>生成时间: {slide_data.get('generation_time', '2025-08-20')}</p>
                <p>工作流ID: {slide_data.get('workflow_id', 'workflow-001')}</p>
            </div>
            """
        elif slide_type == 'toc':
            chapters = slide_data.get('chapters', [])
            chapter_list = ""
            for i, chapter in enumerate(chapters, 1):
                raw_title = chapter.get('section_title', f'章节{i}')
                clean_title = self._extract_clean_title(raw_title)
                chapter_list += f"<li>{i}. {clean_title}</li>"
            
            content_body = f"""
            <h1>{slide_title}</h1>
            <div class="slide-content">
                <ul class="toc-list">
                    {chapter_list}
                </ul>
            </div>
            """
        else:
            # 内容页 - 智能处理和丰富化
            slide_content = slide_data.get('slide_content', '内容正在生成中...')
            processed_content = self._enrich_slide_content(slide_content, slide_title)
            
            content_body = f"""
            <h1>{slide_title}</h1>
            <div class="slide-content">
                {processed_content}
            </div>
            """
        
        # 导航按钮
        nav_buttons = []
        if prev_file:
            nav_buttons.append(f'<a href="{prev_file}" class="nav-button">上一页</a>')
        if next_file:
            nav_buttons.append(f'<a href="{next_file}" class="nav-button">下一页</a>')
        
        nav_html = '\n                '.join(nav_buttons)
        
        # 生成完整的HTML - Premium深蓝渐变模板
        html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{slide_title} - {slide_number}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background: #0a0a0a;
            overflow-x: hidden;
            margin: 0;
            padding: 0;
        }}
        
        /* Premium深蓝渐变背景 */
        .slide {{
            width: 100%;
            min-height: 100vh;
            background: linear-gradient(135deg, 
                #0a1426 0%, 
                #1e3c72 25%, 
                #2a5298 50%, 
                #1e3c72 75%, 
                #0a1426 100%
            );
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 80px 60px;
            color: white;
            overflow: hidden;
        }}
        
        /* 动态背景图案 */
        .slide::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 199, 255, 0.05) 0%, transparent 50%);
            z-index: 1;
        }}
        
        /* 网格背景图案 */
        .slide::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(rgba(120, 199, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(120, 199, 255, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            z-index: 1;
        }}
        
        /* 内容容器 */
        .slide-content {{
            position: relative;
            z-index: 10;
            max-width: 1000px;
            width: 100%;
            text-align: left;
        }}
        
        /* 封面幻灯片 */
        .slide.cover {{
            text-align: center;
        }}
        
        .cover .title {{
            font-size: 3.5em;
            font-weight: 300;
            margin-bottom: 30px;
            line-height: 1.2;
        }}
        
        .cover .subtitle {{
            font-size: 1.6em;
            font-weight: 300;
            opacity: 0.9;
            margin-bottom: 40px;
        }}
        
        .cover .metadata {{
            font-size: 1.1em;
            opacity: 0.8;
        }}
        
        /* 目录幻灯片 */
        .slide.toc {{
            justify-content: flex-start;
        }}
        
        .slide.toc h1 {{
            font-size: 2.5em;
            color: #1e3c72;
            margin-bottom: 40px;
            text-align: center;
            border-bottom: 3px solid #2a5298;
            padding-bottom: 20px;
        }}
        
        .toc-list {{
            list-style: none;
            padding: 0;
        }}
        
        .toc-list li {{
            font-size: 1.4em;
            line-height: 2;
            padding: 15px 0;
            border-bottom: 1px solid #e1e4e8;
            display: flex;
            align-items: center;
        }}
        
        .toc-list li::before {{
            content: '';
            width: 8px;
            height: 8px;
            background: #2a5298;
            border-radius: 50%;
            margin-right: 20px;
        }}
        
        /* 内容幻灯片 */
        .slide.content h1 {{
            font-size: 2.2em;
            color: #1e3c72;
            margin-bottom: 40px;
            padding-bottom: 15px;
            border-bottom: 3px solid #2a5298;
        }}
        
        .slide.content h2 {{
            font-size: 1.8em;
            color: #2a5298;
            margin: 30px 0 20px 0;
        }}
        
        .slide.content h3 {{
            font-size: 1.4em;
            color: #d1e7ff;
            margin: 25px 0 15px 0;
        }}
        
        .slide-content {{
            flex: 1;
            font-size: 1.1em;
            line-height: 1.8;
            color: #d1e7ff;
            max-height: calc(100vh - 200px);
            overflow: hidden;
        }}
        
        .slide-content p {{
            margin-bottom: 20px;
            text-align: justify;
        }}
        
        .slide-content ul, .slide-content ol {{
            margin: 20px 0;
            padding-left: 30px;
        }}
        
        .slide-content li {{
            margin-bottom: 12px;
            line-height: 1.7;
        }}
        
        /* 页码和导航 */
        .slide-footer {{
            position: absolute;
            bottom: 30px;
            left: 30px;
            right: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
        }}
        
        .slide-number {{
            font-size: 0.9em;
            color: rgba(255, 255, 255, 0.6);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            padding: 8px 16px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }}
        
        .slide.cover .slide-number {{
            color: rgba(255, 255, 255, 0.8);
            background: rgba(255, 255, 255, 0.1);
        }}
        
        .navigation {{
            display: flex;
            gap: 10px;
            z-index: 101;
            position: relative;
        }}
        
        .nav-button {{
            padding: 10px 20px;
            background: linear-gradient(45deg, #78c7ff, #4a9eff);
            color: #0a1426;
            text-decoration: none;
            border-radius: 25px;
            font-size: 0.9em;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
            position: relative;
            z-index: 102;
            cursor: pointer;
            display: inline-block;
        }}
        
        .nav-button:hover {{
            background: linear-gradient(45deg, #4a9eff, #2e7cff);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(120, 199, 255, 0.3);
        }}
        
        .nav-button.disabled {{
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.4);
            pointer-events: none;
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .slide {{
                padding: 30px 20px;
            }}
            
            .cover .title {{
                font-size: 2.5em;
            }}
            
            .slide.content h1 {{
                font-size: 1.8em;
            }}
            
            .toc-list li {{
                font-size: 1.2em;
            }}
            
            .slide-footer {{
                flex-direction: column;
                gap: 10px;
                align-items: stretch;
            }}
        }}
        
        /* 打印样式 */
        @media print {{
            body {{
                background: white;
            }}
            
            .slide {{
                box-shadow: none;
                page-break-after: always;
                page-break-inside: avoid;
            }}
            
            .slide-footer {{
                display: none;
            }}
        }}
        
        /* 动画效果 */
        .slide {{
            animation: slideIn 0.5s ease-in-out;
        }}
        
        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        /* 增强内容样式 - 深色主题优化 */
        .enhanced-list {{
            list-style: none;
            padding: 0;
        }}
        
        .enhanced-list li {{
            margin: 15px 0;
            padding: 12px 20px;
            border-left: 4px solid #78c7ff;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 0 8px 8px 0;
            transition: all 0.3s ease;
            color: #d1e7ff;
        }}
        
        .enhanced-list li:hover {{
            background: rgba(120, 199, 255, 0.15);
            border-left-color: #4a9eff;
            transform: translateX(5px);
        }}
        
        /* 指标项样式 - 深色主题 */
        .metric-item {{
            background: rgba(76, 175, 80, 0.12) !important;
            border-left-color: #4caf50 !important;
        }}
        
        .metric-value {{
            font-weight: 600;
            color: #a8d8ff;
        }}
        
        /* 成就项样式 - 深色主题 */
        .achievement-item {{
            background: rgba(255, 152, 0, 0.12) !important;
            border-left-color: #ff9800 !important;
        }}
        
        .icon-check::before {{
            content: "✓ ";
            color: #4caf50;
            font-weight: bold;
            margin-right: 8px;
        }}
        
        /* 风险项样式 - 深色主题 */
        .risk-item {{
            background: rgba(255, 87, 34, 0.12) !important;
            border-left-color: #ff5722 !important;
        }}
        
        .icon-warning::before {{
            content: "⚠ ";
            color: #ff5722;
            font-weight: bold;
            margin-right: 8px;
        }}
        
        /* 卡片布局 */
        .content-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        
        .content-card {{
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
            border-top: 4px solid #2a5298;
            transition: all 0.3s ease;
        }}
        
        .content-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
        }}
        
        .card-content {{
            font-size: 1.1em;
            line-height: 1.6;
            color: #d1e7ff;
        }}
        
        /* 大卡片布局 */
        .large-cards {{
            display: flex;
            flex-direction: column;
            gap: 25px;
            margin: 30px 0;
        }}
        
        .large-card {{
            display: flex;
            align-items: center;
            background: linear-gradient(135deg, #ffffff 0%, #f1f3f4 100%);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
        }}
        
        .large-card:hover {{
            transform: translateX(10px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
        }}
        
        .card-number {{
            font-size: 2em;
            font-weight: 300;
            color: #2a5298;
            margin-right: 25px;
            min-width: 60px;
            text-align: center;
            background: #e3f2fd;
            border-radius: 12px;
            padding: 10px;
        }}
        
        .card-content {{
            flex: 1;
            font-size: 1.2em;
            line-height: 1.6;
        }}
        
        /* 网格布局 */
        .grid-layout {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }}
        
        .grid-item {{
            display: flex;
            align-items: center;
            background: #ffffff;
            border: 2px solid #e1e4e8;
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
        }}
        
        .grid-item:hover {{
            border-color: #2a5298;
            box-shadow: 0 4px 12px rgba(42, 82, 152, 0.1);
        }}
        
        .item-icon {{
            font-size: 1.2em;
            color: #2a5298;
            margin-right: 15px;
            font-weight: bold;
        }}
        
        .item-text {{
            flex: 1;
            line-height: 1.5;
        }}
        
        /* 紧凑列表 */
        .compact-list {{
            list-style: none;
            padding: 0;
            columns: 2;
            column-gap: 40px;
        }}
        
        .compact-item {{
            break-inside: avoid;
            margin: 10px 0;
            padding: 8px 15px;
            background: #f8f9fa;
            border-radius: 6px;
            border-left: 3px solid #2a5298;
        }}
        
        /* 双栏布局 */
        .two-column-list {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            margin: 20px 0;
        }}
        
        /* 段落容器 */
        .paragraph-container {{
            margin: 20px 0;
        }}
        
        .enhanced-paragraph {{
            margin: 15px 0;
            line-height: 1.8;
            text-align: justify;
        }}
        
        .summary-box {{
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border-left: 6px solid #2196f3;
            border-radius: 0 12px 12px 0;
            padding: 20px 25px;
            margin: 25px 0;
        }}
        
        .summary-text {{
            font-size: 1.1em;
            line-height: 1.7;
            color: #1565c0;
            margin: 0;
            font-weight: 500;
        }}
        
        /* 丰富内容容器 */
        .rich-content-container, .rich-list-container {{
            margin: 20px 0;
            padding: 25px;
            background: #ffffff;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }}
        
        .section-title, .content-title {{
            color: #1e3c72;
            font-size: 1.4em;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e1e4e8;
        }}
        
        .highlight-paragraph {{
            background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
            border-left: 6px solid #ffc107;
            font-size: 1.1em;
            line-height: 1.7;
        }}
        
        .content-paragraph {{
            margin: 15px 0;
            line-height: 1.8;
            text-align: justify;
        }}
        
        /* 装饰性标题 */
        .heading-container {{
            margin: 30px 0;
        }}
        
        .decorated-heading {{
            position: relative;
            color: #1e3c72;
        }}
        
        .heading-decorator {{
            position: absolute;
            left: -20px;
            top: 50%;
            transform: translateY(-50%);
            width: 4px;
            height: 100%;
            background: linear-gradient(to bottom, #2a5298, #1e3c72);
            border-radius: 2px;
        }}
        
        /* 分栏布局 */
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            align-items: start;
        }}
        
        .three-column {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 25px;
            align-items: start;
        }}
        
        .column-center {{
            padding: 0 10px;
        }}
        
        .section-heading {{
            font-size: 1.2em;
            color: #2a5298;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #e3f2fd;
            font-weight: 600;
        }}
        
        .content-sections {{
            margin: 20px 0;
        }}
        
        .section-header {{
            text-align: center;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 3px solid #2a5298;
        }}
        
        .section-header h4 {{
            color: #1e3c72;
            font-size: 1.5em;
            font-weight: 500;
        }}
        
        .styled-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        
        .styled-list li {{
            margin: 10px 0;
            padding: 12px 18px;
            border-radius: 8px;
            position: relative;
            transition: all 0.3s ease;
        }}
        
        .metric-item {{
            background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
            border-left: 4px solid #4caf50;
        }}
        
        .achievement-item {{
            background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
            border-left: 4px solid #ff9800;
        }}
        
        .standard-item {{
            background: #f8f9fa;
            border-left: 4px solid #2a5298;
        }}
        
        .summary-box {{
            background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
            border: 1px solid #2196f3;
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        }}
        
        .summary-box p {{
            margin: 0;
            line-height: 1.6;
            color: #1565c0;
        }}
        
        /* 响应式调整 */
        @media (max-width: 768px) {{
            .three-column {{
                grid-template-columns: 1fr;
                gap: 20px;
            }}
            
            .two-column {{
                grid-template-columns: 1fr;
                gap: 20px;
            }}
        
        @media (max-width: 768px) {{
            .two-column-list {{
                grid-template-columns: 1fr;
                gap: 20px;
            }}
            
            .compact-list {{
                columns: 1;
            }}
            
            .grid-layout {{
                grid-template-columns: 1fr;
            }}
            
            .large-card {{
                flex-direction: column;
                text-align: center;
            }}
            
            .card-number {{
                margin-right: 0;
                margin-bottom: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="slide {slide_type}">
        {content_body}
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                {nav_html}
            </div>
        </div>
    </div>
</body>
</html>"""
        
        return html_template
    
    def _generate_default_integrated_report(self, data: Dict[str, Any]) -> str:
        """生成默认的整合报告"""
        html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{data['report_title']}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            line-height: 1.8;
            color: #d1e7ff;
            background: #0a1426;
            padding: 20px 0;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
            border-radius: 8px;
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 60px 40px;
            text-align: center;
            position: relative;
        }}
        
        .header::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #f39c12, #e74c3c, #9b59b6, #3498db);
        }}
        
        .title {{
            font-size: 3.2em;
            font-weight: 300;
            margin-bottom: 20px;
            letter-spacing: -1px;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        
        .subtitle {{
            font-size: 1.4em;
            font-weight: 300;
            opacity: 0.9;
            letter-spacing: 0.5px;
            max-width: 800px;
            margin: 0 auto;
        }}
        
        .metadata {{
            background: #fafbfc;
            padding: 30px 40px;
            border-bottom: 1px solid #e1e4e8;
            display: flex;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 30px;
        }}
        
        .metadata-item {{
            color: #586069;
            font-size: 0.95em;
        }}
        
        .metadata-item strong {{
            color: #24292e;
            margin-right: 8px;
        }}
        
        .content {{
            padding: 60px 50px;
        }}
        
        .chapter {{
            margin-bottom: 80px;
            animation: fadeIn 0.6s ease-in;
        }}
        
        .chapter:last-child {{
            margin-bottom: 0;
        }}
        
        @keyframes fadeIn {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        
        .chapter-title {{
            font-size: 2.2em;
            color: #1e3c72;
            margin-bottom: 30px;
            padding-bottom: 15px;
            border-bottom: 3px solid #e1e4e8;
            position: relative;
            font-weight: 400;
        }}
        
        .chapter-title::after {{
            content: '';
            position: absolute;
            bottom: -3px;
            left: 0;
            width: 80px;
            height: 3px;
            background: linear-gradient(90deg, #3498db 0%, #2a5298 100%);
            border-radius: 2px;
        }}
        
        .chapter-content {{
            color: #d1e7ff;
            font-size: 1.05em;
            line-height: 1.8;
        }}
        
        .chapter-content h3 {{
            color: #2a5298;
            font-size: 1.4em;
            margin: 35px 0 20px 0;
            font-weight: 500;
        }}
        
        .chapter-content h4 {{
            color: #ffffff;
            font-size: 1.2em;
            margin: 25px 0 15px 0;
            font-weight: 500;
        }}
        
        .chapter-content p {{
            margin-bottom: 20px;
            text-align: justify;
        }}
        
        .chapter-content ul, .chapter-content ol {{
            margin: 20px 0;
            padding-left: 35px;
        }}
        
        .chapter-content li {{
            margin-bottom: 12px;
            line-height: 1.7;
        }}
        
        .toc {{
            background: #f8f9fa;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 50px;
            border: 1px solid #e1e4e8;
        }}
        
        .toc h2 {{
            color: #1e3c72;
            margin-bottom: 20px;
            font-size: 1.5em;
        }}
        
        .toc ul {{
            list-style: none;
            padding: 0;
        }}
        
        .toc li {{
            margin-bottom: 10px;
        }}
        
        .toc a {{
            color: #2a5298;
            text-decoration: none;
            font-size: 1.1em;
            transition: color 0.3s ease;
        }}
        
        .toc a:hover {{
            color: #1e3c72;
            text-decoration: underline;
        }}
        
        .footer {{
            background: #fafbfc;
            padding: 40px;
            text-align: center;
            color: #586069;
            font-size: 0.95em;
            border-top: 1px solid #e1e4e8;
        }}
        
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            
            .container {{
                box-shadow: none;
                max-width: 100%;
            }}
            
            .header {{
                background: #1e3c72 !important;
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            
            .chapter {{
                page-break-inside: avoid;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">{self._clean_title_string(data.get('report_title', '专业分析报告'))}</h1>
            <p class="subtitle">{self._clean_subtitle_string(data.get('report_subtitle', '提供专业的分析和建议'))}</p>
        </div>
        
        <div class="metadata">
            <div class="metadata-item">
                <strong>生成时间:</strong> {data['generation_time']}
            </div>
            <div class="metadata-item">
                <strong>工作流ID:</strong> {data['workflow_id']}
            </div>
            <div class="metadata-item">
                <strong>章节数量:</strong> {data['total_chapters']}
            </div>
        </div>
        
        <div class="content">
            <div class="toc">
                <h2>目录</h2>
                <ul>
"""
        
        # 添加目录
        for i, chapter in enumerate(data['chapters'], 1):
            raw_title = chapter.get('section_title', f'章节 {i}')
            clean_title = self._extract_clean_title(raw_title)
            html_template += f'                    <li><a href="#chapter-{i}">{i}. {clean_title}</a></li>\n'
        
        html_template += """
                </ul>
            </div>
"""
        
        # 添加章节内容
        for i, chapter in enumerate(data['chapters'], 1):
            raw_title = chapter.get('section_title', f'章节 {i}')
            clean_title = self._extract_clean_title(raw_title)
            content = chapter.get('content', '')
            
            html_template += f"""
            <div class="chapter" id="chapter-{i}">
                <h2 class="chapter-title">{clean_title}</h2>
                <div class="chapter-content">
                    {content}
                </div>
            </div>
"""
        
        html_template += f"""
        </div>
        
        <div class="footer">
            <p>本报告由 Multi-Agent Report Generation System (MARGS) 自动生成</p>
            <p>生成时间: {data['generation_time']} | 工作流ID: {data['workflow_id']}</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html_template
    
    def _enrich_slide_content(self, content: str, slide_title: str) -> str:
        """智能丰富幻灯片内容，提升视觉效果和排版质量"""
        if not content or not content.strip():
            return '<p>内容正在生成中...</p>'
        
        # 分析内容类型
        content_type = self._analyze_content_type(content)
        
        # 根据内容类型选择增强策略
        if content_type == 'html_complete':
            # 已经是完整HTML，进行轻微优化
            return self._enhance_existing_html(content)
        elif content_type == 'html_fragment':
            # HTML片段，需要结构化包装
            return self._enhance_html_fragment(content)
        elif content_type == 'plain_text':
            # 纯文本，转换为丰富HTML
            return self._convert_text_to_rich_html(content, slide_title)
        else:
            # 混合内容，智能处理
            return self._enhance_mixed_content(content, slide_title)
    
    def _analyze_content_type(self, content: str) -> str:
        """分析内容类型以确定最佳增强策略"""
        content = content.strip()
        
        # 检查是否是完整HTML
        if (content.startswith('<!DOCTYPE') or 
            ('<html>' in content and '</html>' in content)):
            return 'html_complete'
        
        # 检查是否是HTML片段
        if (content.startswith('<') and 
            ('</div>' in content or '</p>' in content or '</li>' in content)):
            return 'html_fragment'
        
        # 检查是否包含HTML标签
        import re
        html_tags = re.findall(r'<[^>]+>', content)
        if len(html_tags) > 0:
            return 'mixed_content'
        
        # 纯文本内容
        return 'plain_text'
    
    def _enhance_existing_html(self, content: str) -> str:
        """增强已有的HTML内容"""
        import re
        
        # 添加现代化的CSS类到现有元素
        enhanced = content
        
        # 增强列表样式
        enhanced = re.sub(r'<ul>', '<ul class="enhanced-list">', enhanced)
        enhanced = re.sub(r'<ol>', '<ol class="enhanced-ordered-list">', enhanced)
        
        # 增强段落样式
        enhanced = re.sub(r'<p>(?!.*class)', '<p class="enhanced-paragraph">', enhanced)
        
        # 为标题添加增强样式
        enhanced = re.sub(r'<h([1-6])>(?!.*class)', r'<h\\1 class="enhanced-heading">', enhanced)
        
        return enhanced
    
    def _enhance_html_fragment(self, content: str) -> str:
        """增强HTML片段，添加现代化样式和结构"""
        import re
        
        # 检查是否有列表项
        if '<li>' in content:
            return self._enhance_list_content(content)
        
        # 检查是否有段落
        if '<p>' in content:
            return self._enhance_paragraph_content(content)
        
        # 检查是否有标题
        if re.search(r'<h[1-6]>', content):
            return self._enhance_heading_content(content)
        
        # 默认处理
        return f'<div class="content-wrapper">{content}</div>'
    
    def _enhance_list_content(self, content: str) -> str:
        """增强列表内容的视觉效果"""
        import re
        
        # 提取所有列表项
        list_items = re.findall(r'<li>(.*?)</li>', content, re.DOTALL)
        
        if len(list_items) == 0:
            return content
        
        # 分析列表项内容，创建丰富的布局
        enhanced_items = []
        for i, item in enumerate(list_items):
            # 清理内容
            cleaned_item = item.strip()
            
            # 检查是否包含关键指标
            if any(keyword in cleaned_item for keyword in ['%', '率', '数量', '金额', '时间', '次']):
                enhanced_items.append(f'<li class="metric-item"><span class="metric-value">{cleaned_item}</span></li>')
            elif any(keyword in cleaned_item for keyword in ['完成', '实现', '达成', '成功']):
                enhanced_items.append(f'<li class="achievement-item"><i class="icon-check"></i>{cleaned_item}</li>')
            elif any(keyword in cleaned_item for keyword in ['风险', '问题', '挑战', '威胁']):
                enhanced_items.append(f'<li class="risk-item"><i class="icon-warning"></i>{cleaned_item}</li>')
            else:
                enhanced_items.append(f'<li class="standard-item">{cleaned_item}</li>')
        
        # 根据项目数量选择布局
        if len(enhanced_items) <= 4:
            # 卡片式布局
            cards_html = '<div class="content-cards">'
            for item in enhanced_items:
                clean_text = re.sub(r'<[^>]+>', '', item)
                cards_html += f'''
                <div class="content-card">
                    <div class="card-content">{clean_text}</div>
                </div>'''
            cards_html += '</div>'
            return cards_html
        else:
            # 双栏列表布局
            mid_point = len(enhanced_items) // 2
            left_items = enhanced_items[:mid_point]
            right_items = enhanced_items[mid_point:]
            
            return f'''
            <div class="two-column-list">
                <div class="column-left">
                    <ul class="enhanced-list">
                        {"".join(left_items)}
                    </ul>
                </div>
                <div class="column-right">
                    <ul class="enhanced-list">
                        {"".join(right_items)}
                    </ul>
                </div>
            </div>'''
    
    def _enhance_paragraph_content(self, content: str) -> str:
        """增强段落内容"""
        import re
        
        # 提取段落
        paragraphs = re.findall(r'<p>(.*?)</p>', content, re.DOTALL)
        
        if not paragraphs:
            return f'<div class="content-wrapper">{content}</div>'
        
        enhanced_content = '<div class="paragraph-container">'
        for para in paragraphs:
            para = para.strip()
            if para:
                # 检查是否是摘要性段落
                if any(keyword in para for keyword in ['摘要', '总结', '概述', '综合']):
                    enhanced_content += f'<div class="summary-box"><p class="summary-text">{para}</p></div>'
                else:
                    enhanced_content += f'<p class="enhanced-paragraph">{para}</p>'
        enhanced_content += '</div>'
        
        return enhanced_content
    
    def _enhance_heading_content(self, content: str) -> str:
        """增强标题内容"""
        import re
        
        # 为标题添加装饰性元素
        enhanced = re.sub(
            r'<h([1-6])>(.*?)</h([1-6])>',
            r'<h\1 class="decorated-heading"><span class="heading-decorator"></span>\2</h\3>',
            content
        )
        
        return f'<div class="heading-container">{enhanced}</div>'
    
    def _convert_text_to_rich_html(self, text: str, slide_title: str) -> str:
        """将纯文本转换为丰富的HTML格式"""
        if not text.strip():
            return '<p class="empty-content">内容正在生成中...</p>'
        
        lines = text.strip().split('\n')
        
        # 检查文本结构
        has_bullet_points = any(line.strip().startswith(('•', '-', '*', '◆')) for line in lines)
        has_numbered_items = any(re.match(r'^\d+\.', line.strip()) for line in lines)
        
        if has_bullet_points or has_numbered_items:
            return self._convert_list_text_to_html(lines, slide_title)
        else:
            return self._convert_paragraph_text_to_html(lines, slide_title)
    
    def _convert_list_text_to_html(self, lines: List[str], slide_title: str) -> str:
        """将列表形式的文本转换为丰富HTML"""
        import re
        
        html_content = '<div class="rich-list-container">'
        
        # 添加装饰性标题
        if slide_title and slide_title != "页面":
            html_content += f'<h3 class="section-title">{slide_title}</h3>'
        
        current_items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 清理列表标记
            clean_line = re.sub(r'^[•\-*◆\d+\.]\s*', '', line)
            if clean_line:
                current_items.append(clean_line)
        
        # 创建视觉丰富的列表
        if current_items:
            if len(current_items) <= 3:
                # 大卡片布局
                html_content += '<div class="large-cards">'
                for i, item in enumerate(current_items, 1):
                    html_content += f'''
                    <div class="large-card">
                        <div class="card-number">{i:02d}</div>
                        <div class="card-content">{item}</div>
                    </div>'''
                html_content += '</div>'
            elif len(current_items) <= 6:
                # 网格布局
                html_content += '<div class="grid-layout">'
                for item in current_items:
                    html_content += f'''
                    <div class="grid-item">
                        <div class="item-icon">▶</div>
                        <div class="item-text">{item}</div>
                    </div>'''
                html_content += '</div>'
            else:
                # 紧凑列表布局
                html_content += '<ul class="compact-list">'
                for item in current_items:
                    html_content += f'<li class="compact-item">{item}</li>'
                html_content += '</ul>'
        
        html_content += '</div>'
        return html_content
    
    def _convert_paragraph_text_to_html(self, lines: List[str], slide_title: str) -> str:
        """将段落文本转换为丰富HTML"""
        html_content = '<div class="rich-content-container">'
        
        # 添加标题
        if slide_title and slide_title != "页面":
            html_content += f'<h3 class="content-title">{slide_title}</h3>'
        
        # 合并相关行成段落
        paragraphs = []
        current_para = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_para:
                    paragraphs.append(' '.join(current_para))
                    current_para = []
            else:
                current_para.append(line)
        
        if current_para:
            paragraphs.append(' '.join(current_para))
        
        # 生成丰富的段落HTML
        for i, para in enumerate(paragraphs):
            if i == 0 and len(paragraphs) > 1:
                # 第一段作为重点显示
                html_content += f'<div class="highlight-paragraph">{para}</div>'
            else:
                html_content += f'<p class="content-paragraph">{para}</p>'
        
        html_content += '</div>'
        return html_content
    
    def _enhance_mixed_content(self, content: str, slide_title: str) -> str:
        """增强混合内容"""
        import re
        
        # 检查内容中的HTML标签
        html_parts = re.findall(r'<[^>]+>.*?</[^>]+>', content, re.DOTALL)
        
        if html_parts:
            # 有HTML标签，进行增强
            enhanced = content
            for part in html_parts:
                if '<li>' in part:
                    enhanced_part = self._enhance_list_content(part)
                    enhanced = enhanced.replace(part, enhanced_part)
                elif '<p>' in part:
                    enhanced_part = self._enhance_paragraph_content(part)
                    enhanced = enhanced.replace(part, enhanced_part)
            return enhanced
        else:
            # 当作纯文本处理
            return self._convert_text_to_rich_html(content, slide_title)
    
    def _save_report_to_file(self, content: str, data: Dict[str, Any]) -> Path:
        """保存报告到文件"""
        # 创建输出目录
        output_dir = Path("examples/sample_reports")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"integrated_report_{timestamp}.html"
        output_path = output_dir / filename
        
        # 保存文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"报告已保存到: {output_path}", agent_name="ReportIntegrationAgent")
        return output_path
    
    def _generate_chapter_summary(self, confirmed_chapters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成章节摘要"""
        summary = []
        for step_id, chapter in confirmed_chapters.items():
            summary.append({
                "step_id": step_id,
                "title": self._extract_clean_title(chapter.get('section_title', '未知章节')),
                "word_count": len(chapter.get('content', '')),
                "confirmed_time": chapter.get('timestamp', datetime.now()).isoformat() if hasattr(chapter.get('timestamp', datetime.now()), 'isoformat') else str(chapter.get('timestamp', datetime.now()))
            })
        return summary