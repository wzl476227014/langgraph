"""
Report Optimization Agent模块
负责读取现有报告并生成优化后的版本
"""

import re
import os
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from ..utils.config import get_agent_config, get_agent_prompt
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response


logger = get_logger(__name__)


class ReportOptimizationAgent:
    """Report Optimization Agent - 报告优化专家"""
    
    def __init__(self):
        """初始化Report Optimization Agent"""
        self.config = get_agent_config("report_optimization")
        self.system_prompt = self._get_optimization_prompt()
        
        logger.info("Report Optimization Agent初始化完成", agent_name="ReportOptimizationAgent")
    
    def _get_optimization_prompt(self) -> str:
        """获取优化系统提示"""
        return """你是一位专业的报告优化专家，擅长：
1. 分析现有报告的结构和内容
2. 识别报告中的不足和改进空间
3. 增强内容的专业性和深度
4. 补充数据、案例和最佳实践
5. 改进文字表达和逻辑结构
6. 提供可操作的建议和实施方案

你的任务是基于提供的原始报告内容，生成一份更加专业、完善和有价值的优化版本。
"""
    
    def analyze_existing_report(self, report_path: str) -> Dict[str, Any]:
        """
        分析现有报告
        
        Args:
            report_path: 报告文件路径
            
        Returns:
            分析结果字典
        """
        log_agent_start("ReportOptimizationAgent", f"分析报告: {report_path}")
        
        try:
            # 读取报告内容
            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取报告结构
            structure = self._extract_report_structure(content)
            
            # 分析内容质量
            quality_metrics = self._analyze_content_quality(content)
            
            # 识别改进点
            improvement_areas = self._identify_improvement_areas(structure, quality_metrics)
            
            analysis_result = {
                "file_path": report_path,
                "file_size": len(content),
                "structure": structure,
                "quality_metrics": quality_metrics,
                "improvement_areas": improvement_areas,
                "original_content": content
            }
            
            logger.info(f"报告分析完成，识别到 {len(improvement_areas)} 个改进点", 
                       agent_name="ReportOptimizationAgent")
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"报告分析失败: {str(e)}", agent_name="ReportOptimizationAgent")
            raise Exception(f"报告分析失败: {str(e)}")
    
    def _extract_report_structure(self, content: str) -> Dict[str, Any]:
        """提取报告结构"""
        structure = {
            "title": "",
            "subtitle": "",
            "chapters": [],
            "total_paragraphs": 0,
            "total_words": 0
        }
        
        # 提取标题
        title_match = re.search(r'<title>([^<]+)</title>', content)
        if title_match:
            structure["title"] = title_match.group(1)
        
        # 提取副标题
        subtitle_match = re.search(r'class="subtitle">([^<]+)</p>', content)
        if subtitle_match:
            structure["subtitle"] = subtitle_match.group(1)
        
        # 提取章节
        chapter_pattern = r'<div class="chapter"[^>]*>.*?<h2[^>]*>([^<]+)</h2>.*?<div class="chapter-content">(.*?)</div>'
        chapter_matches = re.findall(chapter_pattern, content, re.DOTALL)
        
        for title, chapter_content in chapter_matches:
            # 清理HTML标签
            clean_content = re.sub(r'<[^>]+>', ' ', chapter_content)
            clean_content = re.sub(r'\s+', ' ', clean_content).strip()
            
            structure["chapters"].append({
                "title": title.strip(),
                "content": clean_content,
                "word_count": len(clean_content.split()),
                "paragraph_count": chapter_content.count('<p>')
            })
            
            structure["total_paragraphs"] += chapter_content.count('<p>')
        
        # 计算总字数
        text_only = re.sub(r'<[^>]+>', ' ', content)
        structure["total_words"] = len(text_only.split())
        
        return structure
    
    def _analyze_content_quality(self, content: str) -> Dict[str, float]:
        """分析内容质量"""
        text_only = re.sub(r'<[^>]+>', '', content)
        
        # 专业术语密度
        professional_terms = [
            '分析', '优化', '策略', '架构', '方案', '评估', '指标', '框架',
            '实施', '监控', '性能', '安全', '效率', '质量', '流程', '标准'
        ]
        term_count = sum(text_only.count(term) for term in professional_terms)
        term_density = term_count / (len(text_only.split()) + 1)
        
        # 数据支撑度（检查数字、百分比等）
        numbers = re.findall(r'\d+', text_only)
        data_density = len(numbers) / (len(text_only.split()) + 1)
        
        # 结构化程度（列表、标题等）
        list_count = content.count('<ul>') + content.count('<ol>')
        heading_count = content.count('<h') 
        structure_score = min((list_count + heading_count) / 10, 1.0)
        
        # 内容丰富度
        avg_paragraph_length = len(text_only.split()) / (content.count('<p>') + 1)
        richness_score = min(avg_paragraph_length / 100, 1.0)
        
        return {
            "professional_term_density": term_density,
            "data_support_density": data_density,
            "structure_score": structure_score,
            "content_richness": richness_score,
            "overall_quality": (term_density + data_density + structure_score + richness_score) / 4
        }
    
    def _identify_improvement_areas(self, structure: Dict[str, Any], 
                                   quality_metrics: Dict[str, float]) -> List[str]:
        """识别改进点"""
        improvements = []
        
        # 检查内容长度
        if structure["total_words"] < 1000:
            improvements.append("内容过于简短，需要扩充详细内容")
        
        # 检查章节平衡
        if structure["chapters"]:
            word_counts = [ch["word_count"] for ch in structure["chapters"]]
            if max(word_counts) > min(word_counts) * 3:
                improvements.append("章节内容不平衡，需要调整各章节篇幅")
        
        # 检查专业性
        if quality_metrics["professional_term_density"] < 0.02:
            improvements.append("专业术语使用不足，需要增加行业术语")
        
        # 检查数据支撑
        if quality_metrics["data_support_density"] < 0.01:
            improvements.append("缺少数据支撑，需要添加具体数据和案例")
        
        # 检查结构化
        if quality_metrics["structure_score"] < 0.3:
            improvements.append("内容结构化不足，需要添加列表和子标题")
        
        # 检查内容丰富度
        if quality_metrics["content_richness"] < 0.5:
            improvements.append("段落内容单薄，需要丰富细节描述")
        
        return improvements
    
    def optimize_report(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化报告内容
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            优化后的报告内容
        """
        log_agent_start("ReportOptimizationAgent", "开始优化报告")
        
        try:
            structure = analysis_result["structure"]
            improvements = analysis_result["improvement_areas"]
            
            # 构建优化提示
            optimization_prompt = self._build_optimization_prompt(structure, improvements)
            
            # 调用LLM生成优化内容
            optimized_chapters = []
            for chapter in structure["chapters"]:
                optimized_content = self._optimize_chapter(chapter, improvements)
                optimized_chapters.append({
                    "section_title": chapter["title"],
                    "original_content": chapter["content"],
                    "optimized_content": optimized_content,
                    "improvement_notes": self._get_chapter_improvements(chapter)
                })
            
            # 生成新章节（如果需要）
            additional_chapters = self._generate_additional_chapters(structure, improvements)
            optimized_chapters.extend(additional_chapters)
            
            result = {
                "optimized_chapters": optimized_chapters,
                "optimization_summary": self._create_optimization_summary(
                    structure, optimized_chapters, improvements
                ),
                "quality_improvement": self._calculate_quality_improvement(
                    analysis_result, optimized_chapters
                )
            }
            
            log_agent_complete("ReportOptimizationAgent", "报告优化", 
                             f"优化了 {len(optimized_chapters)} 个章节")
            
            return result
            
        except Exception as e:
            logger.error(f"报告优化失败: {str(e)}", agent_name="ReportOptimizationAgent")
            raise Exception(f"报告优化失败: {str(e)}")
    
    def _build_optimization_prompt(self, structure: Dict[str, Any], 
                                  improvements: List[str]) -> str:
        """构建优化提示"""
        prompt = f"""
请优化以下报告，使其更加专业和完善：

报告标题：{structure['title']}
当前章节数：{len(structure['chapters'])}
总字数：{structure['total_words']}

需要改进的方面：
{chr(10).join(f"- {imp}" for imp in improvements)}

优化要求：
1. 保持原有主题和核心观点
2. 扩充每个章节的内容深度
3. 添加具体的数据、案例和最佳实践
4. 使用更专业的行业术语
5. 改进段落结构和逻辑流畅性
6. 增加可操作的建议和实施步骤
"""
        return prompt
    
    def _optimize_chapter(self, chapter: Dict[str, Any], 
                         improvements: List[str]) -> str:
        """优化单个章节"""
        # 这里应该调用LLM，但为了演示，我们生成模拟的优化内容
        original = chapter["content"]
        
        # 模拟优化：扩充内容
        optimized = f"""
<h3>概述</h3>
<p>{original}</p>

<h3>详细分析</h3>
<p>基于深入的行业研究和最佳实践分析，我们发现{chapter['title']}领域存在以下关键要素需要重点关注。
通过对标国际领先企业的实践经验，结合本地市场特点，我们识别出多个优化机会。</p>

<h3>核心要点</h3>
<ul>
    <li><strong>关键指标</strong>：根据行业基准数据，性能提升可达25-40%</li>
    <li><strong>实施路径</strong>：采用分阶段推进策略，确保平稳过渡</li>
    <li><strong>风险管控</strong>：建立完善的监控机制，及时识别和应对潜在风险</li>
    <li><strong>价值实现</strong>：预期投资回报率(ROI)可达150%以上</li>
</ul>

<h3>案例分析</h3>
<p>以某领先企业为例，通过实施类似的优化方案，在6个月内实现了显著的业务改善：
运营效率提升35%，客户满意度提高28%，成本降低22%。这些成果充分证明了该方案的可行性和有效性。</p>

<h3>实施建议</h3>
<ol>
    <li><strong>第一阶段（1-2月）</strong>：完成现状评估和详细规划</li>
    <li><strong>第二阶段（3-4月）</strong>：试点实施和效果验证</li>
    <li><strong>第三阶段（5-6月）</strong>：全面推广和持续优化</li>
</ol>

<h3>预期成果</h3>
<p>通过系统化的实施，预计可以实现以下成果：提升整体运营效率30%以上，
降低运营成本20%，提高服务质量评分至4.5分以上（满分5分），
并建立可持续的改进机制。</p>
"""
        return optimized
    
    def _get_chapter_improvements(self, chapter: Dict[str, Any]) -> List[str]:
        """获取章节具体改进点"""
        improvements = []
        
        if chapter["word_count"] < 200:
            improvements.append("扩充内容至少到500字")
        if chapter["paragraph_count"] < 3:
            improvements.append("增加段落结构")
        if "数据" not in chapter["content"] and "%" not in chapter["content"]:
            improvements.append("添加数据支撑")
        
        return improvements
    
    def _generate_additional_chapters(self, structure: Dict[str, Any], 
                                     improvements: List[str]) -> List[Dict[str, Any]]:
        """生成额外的章节"""
        additional = []
        
        # 如果原报告章节较少，添加新章节
        if len(structure["chapters"]) < 5:
            additional.append({
                "section_title": "实施路线图",
                "original_content": "",
                "optimized_content": """
<p>为确保项目成功实施，我们制定了详细的路线图，包括以下关键里程碑：</p>

<h3>短期目标（0-3个月）</h3>
<ul>
    <li>完成团队组建和培训</li>
    <li>建立基础设施和流程</li>
    <li>启动试点项目</li>
</ul>

<h3>中期目标（3-6个月）</h3>
<ul>
    <li>扩大实施范围</li>
    <li>优化流程和系统</li>
    <li>建立绩效监控体系</li>
</ul>

<h3>长期目标（6-12个月）</h3>
<ul>
    <li>实现全面部署</li>
    <li>持续改进和优化</li>
    <li>知识管理和最佳实践沉淀</li>
</ul>
""",
                "improvement_notes": ["新增章节：提供具体实施指导"]
            })
            
            additional.append({
                "section_title": "风险评估与应对",
                "original_content": "",
                "optimized_content": """
<p>任何变革都伴随着风险，我们识别了主要风险并制定了相应的应对策略：</p>

<table>
    <tr>
        <th>风险类型</th>
        <th>可能性</th>
        <th>影响程度</th>
        <th>应对措施</th>
    </tr>
    <tr>
        <td>技术风险</td>
        <td>中</td>
        <td>高</td>
        <td>建立技术储备，制定应急预案</td>
    </tr>
    <tr>
        <td>人员风险</td>
        <td>低</td>
        <td>中</td>
        <td>加强培训，建立激励机制</td>
    </tr>
    <tr>
        <td>市场风险</td>
        <td>中</td>
        <td>中</td>
        <td>灵活调整策略，保持敏捷性</td>
    </tr>
</table>
""",
                "improvement_notes": ["新增章节：完善风险管理"]
            })
        
        return additional
    
    def _create_optimization_summary(self, original_structure: Dict[str, Any],
                                    optimized_chapters: List[Dict[str, Any]],
                                    improvements: List[str]) -> Dict[str, Any]:
        """创建优化摘要"""
        return {
            "original_chapter_count": len(original_structure["chapters"]),
            "optimized_chapter_count": len(optimized_chapters),
            "applied_improvements": improvements,
            "content_expansion_ratio": 2.5,  # 模拟值
            "quality_score_improvement": 0.35,  # 模拟值
            "optimization_timestamp": datetime.now().isoformat()
        }
    
    def _calculate_quality_improvement(self, original_analysis: Dict[str, Any],
                                      optimized_chapters: List[Dict[str, Any]]) -> float:
        """计算质量改进度"""
        # 这里应该重新分析优化后的内容，但为了演示，返回模拟值
        original_quality = original_analysis["quality_metrics"]["overall_quality"]
        # 假设优化后质量提升30-50%
        improvement = original_quality * 0.4
        return min(improvement, 1.0 - original_quality)