"""
任务分析器模块
根据用户任务动态生成输出要求和样式设计
"""

import re
from typing import Dict, Any, List, Tuple
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TaskAnalyzer:
    """任务分析器 - 分析任务类型并生成相应的输出要求"""
    
    def __init__(self):
        """初始化任务分析器"""
        # 定义任务类型关键词
        self.task_patterns = {
            "technical_report": {
                "keywords": ["技术", "架构", "系统", "开发", "编程", "代码", "API", "框架", "算法"],
                "patterns": [r"技术.*报告", r"系统.*设计", r"架构.*方案", r"开发.*文档"]
            },
            "business_report": {
                "keywords": ["商业", "业务", "市场", "营销", "销售", "财务", "运营", "管理"],
                "patterns": [r"商业.*计划", r"市场.*分析", r"业务.*报告", r"财务.*报表"]
            },
            "research_paper": {
                "keywords": ["研究", "论文", "学术", "分析", "调研", "评估", "对比", "综述"],
                "patterns": [r"研究.*报告", r"学术.*论文", r".*分析报告", r".*调研"]
            },
            "security_assessment": {
                "keywords": ["安全", "漏洞", "威胁", "风险", "评估", "审计", "防护", "攻击"],
                "patterns": [r"安全.*评估", r"风险.*分析", r"漏洞.*扫描", r"安全.*审计"]
            },
            "data_analysis": {
                "keywords": ["数据", "统计", "分析", "指标", "KPI", "报表", "可视化", "趋势"],
                "patterns": [r"数据.*分析", r"统计.*报告", r"指标.*分析", r"趋势.*分析"]
            },
            "project_documentation": {
                "keywords": ["项目", "计划", "进度", "里程碑", "交付", "需求", "设计文档"],
                "patterns": [r"项目.*文档", r"需求.*文档", r"设计.*文档", r"项目.*计划"]
            },
            "user_manual": {
                "keywords": ["用户", "手册", "指南", "教程", "操作", "使用", "说明书", "帮助"],
                "patterns": [r"用户.*手册", r"操作.*指南", r"使用.*说明", r".*教程"]
            },
            "summary_report": {
                "keywords": ["总结", "汇总", "概要", "摘要", "简报", "要点", "概述"],
                "patterns": [r".*总结", r".*汇总", r".*摘要", r".*简报"]
            }
        }
        
        # 定义每种类型的输出要求模板
        self.output_requirements = {
            "technical_report": {
                "content_requirements": [
                    "包含详细的技术架构图和流程图",
                    "提供完整的技术实现细节和代码示例",
                    "包含性能指标和技术参数",
                    "添加技术栈说明和依赖关系",
                    "提供API文档和接口说明"
                ],
                "style_requirements": [
                    "使用技术术语和专业词汇",
                    "代码使用等宽字体和语法高亮",
                    "图表使用技术风格配色（蓝、灰、黑）",
                    "章节编号使用1.1.1多级格式",
                    "表格展示技术参数对比"
                ],
                "structure": ["概述", "技术架构", "核心模块", "实现细节", "性能分析", "部署方案", "附录"]
            },
            
            "business_report": {
                "content_requirements": [
                    "包含执行摘要和关键发现",
                    "提供市场数据和竞争分析",
                    "包含SWOT分析或波特五力分析",
                    "添加财务预测和ROI分析",
                    "提供可行性建议和行动计划"
                ],
                "style_requirements": [
                    "使用商业专业术语",
                    "数据可视化使用饼图、柱状图、趋势图",
                    "配色方案采用企业色（蓝、绿、橙）",
                    "重要数据使用醒目标注",
                    "结论部分突出关键建议"
                ],
                "structure": ["执行摘要", "市场分析", "竞争态势", "财务分析", "风险评估", "战略建议", "实施计划"]
            },
            
            "research_paper": {
                "content_requirements": [
                    "包含文献综述和理论基础",
                    "提供详细的研究方法论",
                    "包含实验数据和统计分析",
                    "添加对比分析和讨论",
                    "提供明确的研究结论"
                ],
                "style_requirements": [
                    "使用学术规范的引用格式",
                    "图表编号规范（图1、表1）",
                    "使用学术写作风格",
                    "避免主观表述，保持客观中立",
                    "数据呈现使用科学计数法"
                ],
                "structure": ["摘要", "引言", "文献综述", "研究方法", "结果分析", "讨论", "结论", "参考文献"]
            },
            
            "security_assessment": {
                "content_requirements": [
                    "包含威胁建模和风险矩阵",
                    "提供漏洞扫描结果和严重程度分级",
                    "包含渗透测试发现和复现步骤",
                    "添加安全加固建议和优先级",
                    "提供合规性检查清单"
                ],
                "style_requirements": [
                    "使用安全行业标准术语（CVE、CVSS）",
                    "风险使用红黄绿色标识",
                    "漏洞分级使用严重/高/中/低",
                    "使用表格展示漏洞清单",
                    "关键风险使用警告框突出"
                ],
                "structure": ["执行摘要", "评估范围", "威胁分析", "漏洞发现", "风险评估", "修复建议", "合规检查", "附录"]
            },
            
            "data_analysis": {
                "content_requirements": [
                    "包含数据来源和采集方法说明",
                    "提供描述性统计和探索性分析",
                    "包含相关性分析和趋势预测",
                    "添加数据质量评估",
                    "提供关键指标仪表板"
                ],
                "style_requirements": [
                    "大量使用数据可视化图表",
                    "数字使用千分位分隔符",
                    "百分比保留1-2位小数",
                    "使用热力图展示相关性",
                    "趋势图包含预测区间"
                ],
                "structure": ["数据概览", "描述统计", "趋势分析", "相关性分析", "预测模型", "关键发现", "建议"]
            },
            
            "project_documentation": {
                "content_requirements": [
                    "包含项目背景和目标",
                    "提供详细的需求规格说明",
                    "包含项目计划和里程碑",
                    "添加风险管理计划",
                    "提供交付物清单和验收标准"
                ],
                "style_requirements": [
                    "使用甘特图展示项目进度",
                    "需求使用用户故事格式",
                    "风险使用概率-影响矩阵",
                    "里程碑使用时间轴展示",
                    "任务分解使用WBS结构"
                ],
                "structure": ["项目概述", "需求分析", "技术方案", "项目计划", "资源安排", "风险管理", "质量保证"]
            },
            
            "user_manual": {
                "content_requirements": [
                    "包含快速入门指南",
                    "提供详细的功能说明",
                    "包含操作步骤和截图",
                    "添加常见问题解答",
                    "提供故障排除指南"
                ],
                "style_requirements": [
                    "使用编号列表描述操作步骤",
                    "重要提示使用信息框",
                    "截图添加标注和说明",
                    "使用简单易懂的语言",
                    "操作按钮使用特殊格式标记"
                ],
                "structure": ["简介", "安装配置", "快速入门", "功能详解", "高级功能", "故障排除", "FAQ", "附录"]
            },
            
            "summary_report": {
                "content_requirements": [
                    "包含核心要点提炼",
                    "提供关键数据汇总",
                    "包含主要发现和结论",
                    "添加行动建议",
                    "保持内容简洁精炼"
                ],
                "style_requirements": [
                    "使用要点列表",
                    "关键数据使用醒目展示",
                    "每段不超过3-4句话",
                    "使用信息图表",
                    "结论部分使用框架突出"
                ],
                "structure": ["概要", "关键发现", "数据亮点", "主要结论", "建议措施"]
            }
        }
        
        # 默认输出要求（当无法识别任务类型时使用）
        self.default_requirements = {
            "content_requirements": [
                "生成完整的章节内容",
                "内容应该专业、详细、有深度",
                "包含相关的背景信息和上下文",
                "提供充分的论据和支撑材料"
            ],
            "style_requirements": [
                "格式应该清晰易读",
                "包含适当的标题、段落、列表等结构",
                "使用专业的语言风格",
                "保持逻辑清晰、层次分明"
            ],
            "structure": ["引言", "主体内容", "分析讨论", "结论建议"]
        }
    
    def analyze_task(self, task_description: str) -> Tuple[str, float]:
        """
        分析任务描述，识别任务类型
        
        Args:
            task_description: 任务描述
            
        Returns:
            (task_type, confidence): 任务类型和置信度
        """
        task_description_lower = task_description.lower()
        scores = {}
        
        for task_type, config in self.task_patterns.items():
            score = 0.0
            
            # 关键词匹配
            for keyword in config["keywords"]:
                if keyword in task_description_lower:
                    score += 1.0
            
            # 正则模式匹配
            for pattern in config["patterns"]:
                if re.search(pattern, task_description_lower):
                    score += 2.0
            
            scores[task_type] = score
        
        # 找出得分最高的任务类型
        if scores:
            best_match = max(scores.items(), key=lambda x: x[1])
            if best_match[1] > 0:
                # 计算置信度（0-1之间）
                confidence = min(best_match[1] / 5.0, 1.0)
                return best_match[0], confidence
        
        return "general", 0.0
    
    def get_output_requirements(self, task_description: str) -> Dict[str, Any]:
        """
        根据任务描述获取输出要求
        
        Args:
            task_description: 任务描述
            
        Returns:
            输出要求字典
        """
        # 分析任务类型
        task_type, confidence = self.analyze_task(task_description)
        
        logger.info(f"识别任务类型: {task_type} (置信度: {confidence:.2f})", agent_name="TaskAnalyzer")
        
        # 获取对应的输出要求
        if task_type in self.output_requirements:
            requirements = self.output_requirements[task_type].copy()
        else:
            requirements = self.default_requirements.copy()
        
        # 添加任务类型和置信度信息
        requirements["task_type"] = task_type
        requirements["confidence"] = confidence
        
        # 根据置信度调整要求的严格程度
        if confidence < 0.5:
            # 低置信度时，添加通用要求
            requirements["content_requirements"].extend([
                "确保内容的完整性和准确性",
                "提供必要的解释和说明"
            ])
        
        return requirements
    
    def generate_style_guide(self, task_type: str) -> Dict[str, Any]:
        """
        生成样式指南
        
        Args:
            task_type: 任务类型
            
        Returns:
            样式指南字典
        """
        style_guides = {
            "technical_report": {
                "color_scheme": {
                    "primary": "#2E86C1",    # 技术蓝
                    "secondary": "#5D6D7E",  # 深灰
                    "accent": "#28B463",     # 成功绿
                    "warning": "#F39C12",    # 警告橙
                    "danger": "#E74C3C"      # 错误红
                },
                "typography": {
                    "heading_font": "Arial, sans-serif",
                    "body_font": "Helvetica, sans-serif",
                    "code_font": "Consolas, monospace",
                    "heading_sizes": {"h1": "2.5em", "h2": "2em", "h3": "1.5em"},
                    "line_height": "1.6"
                },
                "layout": {
                    "max_width": "1200px",
                    "margin": "20px",
                    "padding": "15px",
                    "code_block_bg": "#F8F9F9",
                    "border_radius": "4px"
                }
            },
            
            "business_report": {
                "color_scheme": {
                    "primary": "#1E3A8A",    # 商务蓝
                    "secondary": "#10B981",  # 成功绿
                    "accent": "#F59E0B",     # 金色
                    "warning": "#EF4444",    # 警告红
                    "neutral": "#6B7280"     # 中性灰
                },
                "typography": {
                    "heading_font": "Georgia, serif",
                    "body_font": "Arial, sans-serif",
                    "data_font": "Roboto, sans-serif",
                    "heading_sizes": {"h1": "2.8em", "h2": "2.2em", "h3": "1.8em"},
                    "line_height": "1.8"
                },
                "layout": {
                    "max_width": "1000px",
                    "margin": "30px",
                    "padding": "25px",
                    "chart_height": "400px",
                    "executive_summary_bg": "#F3F4F6"
                }
            },
            
            "research_paper": {
                "color_scheme": {
                    "primary": "#000000",    # 学术黑
                    "secondary": "#4B5563",  # 深灰
                    "accent": "#3B82F6",     # 链接蓝
                    "figure": "#059669",     # 图表绿
                    "table": "#7C3AED"       # 表格紫
                },
                "typography": {
                    "heading_font": "Times New Roman, serif",
                    "body_font": "Times New Roman, serif",
                    "math_font": "Computer Modern, serif",
                    "heading_sizes": {"h1": "1.8em", "h2": "1.5em", "h3": "1.2em"},
                    "line_height": "2.0"
                },
                "layout": {
                    "max_width": "800px",
                    "margin": "1in",
                    "padding": "0",
                    "two_column": False,
                    "figure_caption_style": "italic"
                }
            },
            
            "security_assessment": {
                "color_scheme": {
                    "critical": "#B91C1C",   # 严重红
                    "high": "#DC2626",       # 高危红
                    "medium": "#F59E0B",     # 中危橙
                    "low": "#10B981",        # 低危绿
                    "info": "#3B82F6"        # 信息蓝
                },
                "typography": {
                    "heading_font": "Roboto, sans-serif",
                    "body_font": "Open Sans, sans-serif",
                    "mono_font": "Source Code Pro, monospace",
                    "heading_sizes": {"h1": "2.2em", "h2": "1.8em", "h3": "1.4em"},
                    "line_height": "1.7"
                },
                "layout": {
                    "max_width": "1100px",
                    "margin": "15px",
                    "padding": "20px",
                    "alert_box_padding": "15px",
                    "risk_matrix_size": "500px"
                }
            },
            
            "data_analysis": {
                "color_scheme": {
                    "chart_colors": ["#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6"],
                    "background": "#FFFFFF",
                    "grid": "#E5E7EB",
                    "text": "#1F2937",
                    "highlight": "#FBBF24"
                },
                "typography": {
                    "heading_font": "Helvetica Neue, sans-serif",
                    "body_font": "Segoe UI, sans-serif",
                    "number_font": "Roboto Mono, monospace",
                    "heading_sizes": {"h1": "2.4em", "h2": "1.9em", "h3": "1.5em"},
                    "line_height": "1.65"
                },
                "layout": {
                    "max_width": "1400px",
                    "margin": "10px",
                    "padding": "15px",
                    "chart_default_height": "400px",
                    "dashboard_grid": "3-column"
                }
            }
        }
        
        # 返回对应类型的样式指南，如果没有则返回默认样式
        return style_guides.get(task_type, {
            "color_scheme": {
                "primary": "#2563EB",
                "secondary": "#64748B",
                "accent": "#10B981",
                "warning": "#F59E0B",
                "danger": "#EF4444"
            },
            "typography": {
                "heading_font": "Arial, sans-serif",
                "body_font": "Arial, sans-serif",
                "heading_sizes": {"h1": "2em", "h2": "1.7em", "h3": "1.4em"},
                "line_height": "1.6"
            },
            "layout": {
                "max_width": "1000px",
                "margin": "20px",
                "padding": "20px"
            }
        })
    
    def format_requirements_prompt(self, requirements: Dict[str, Any]) -> str:
        """
        将要求格式化为提示词
        
        Args:
            requirements: 输出要求字典
            
        Returns:
            格式化的提示词
        """
        prompt_parts = []
        
        # 添加任务类型说明
        task_type = requirements.get("task_type", "general")
        confidence = requirements.get("confidence", 0.0)
        
        if confidence > 0.7:
            prompt_parts.append(f"这是一份{self._get_task_type_name(task_type)}，请按照以下要求生成：")
        else:
            prompt_parts.append("请按照以下要求生成报告：")
        
        # 内容要求
        prompt_parts.append("\n内容要求：")
        for req in requirements.get("content_requirements", []):
            prompt_parts.append(f"- {req}")
        
        # 样式要求
        prompt_parts.append("\n样式要求：")
        for req in requirements.get("style_requirements", []):
            prompt_parts.append(f"- {req}")
        
        # 结构建议
        if "structure" in requirements:
            prompt_parts.append("\n建议的章节结构：")
            prompt_parts.append(", ".join(requirements["structure"]))
        
        return "\n".join(prompt_parts)
    
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
            "summary_report": "总结报告"
        }
        return type_names.get(task_type, "专业报告")


# 全局任务分析器实例
task_analyzer = TaskAnalyzer()


def analyze_and_get_requirements(task_description: str) -> Dict[str, Any]:
    """
    分析任务并获取输出要求的便捷函数
    
    Args:
        task_description: 任务描述
        
    Returns:
        输出要求和样式指南
    """
    requirements = task_analyzer.get_output_requirements(task_description)
    style_guide = task_analyzer.generate_style_guide(requirements["task_type"])
    
    return {
        "requirements": requirements,
        "style_guide": style_guide,
        "prompt": task_analyzer.format_requirements_prompt(requirements)
    }