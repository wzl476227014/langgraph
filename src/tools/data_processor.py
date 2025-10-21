"""
数据处理器工具模块
提供数据处理和分析功能
"""

import json
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class DataProcessorTool:
    """数据处理器工具"""
    
    def __init__(self):
        """初始化数据处理器工具"""
        self.config = get_config().get_tool_config("data_processor")
        self.enabled = self.config.get("enabled", True)
        self.max_text_length = self.config.get("max_text_length", 10000)
        
        logger.info("数据处理器工具初始化完成", agent_name="DataProcessorTool")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行数据处理任务
        
        Args:
            input_data: 输入数据，包含待处理的数据和处理类型
            
        Returns:
            处理结果字典
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "数据处理器工具未启用",
                "result": None
            }
        
        task = input_data.get("task", "")
        data = input_data.get("data", "")
        processing_type = input_data.get("processing_type", "analysis")
        
        if not task or not data:
            return {
                "success": False,
                "error": "任务和数据不能为空",
                "result": None
            }
        
        try:
            logger.info(f"开始数据处理任务: {task}", agent_name="DataProcessorTool")
            
            # 根据处理类型选择处理方法
            if processing_type == "analysis":
                result = self._analyze_data(data, task)
            elif processing_type == "extraction":
                result = self._extract_data(data, task)
            elif processing_type == "transformation":
                result = self._transform_data(data, task)
            elif processing_type == "validation":
                result = self._validate_data(data, task)
            elif processing_type == "summarization":
                result = self._summarize_data(data, task)
            else:
                result = self._default_processing(data, task, processing_type)
            
            processed_result = {
                "success": True,
                "task": task,
                "processing_type": processing_type,
                "result": result,
                "processed_at": datetime.now().isoformat(),
                "metadata": {
                    "input_size": len(str(data)),
                    "output_size": len(str(result)),
                    "processing_time": "processed"
                }
            }
            
            logger.info(f"数据处理任务完成: {task}", agent_name="DataProcessorTool")
            
            return processed_result
            
        except Exception as e:
            error_msg = f"数据处理失败: {str(e)}"
            logger.error(error_msg, agent_name="DataProcessorTool")
            
            return {
                "success": False,
                "error": error_msg,
                "task": task,
                "result": None
            }
    
    def _analyze_data(self, data: Any, task: str) -> Dict[str, Any]:
        """分析数据"""
        data_str = str(data)
        
        # 基本统计信息
        analysis_result = {
            "basic_stats": {
                "character_count": len(data_str),
                "word_count": len(data_str.split()),
                "line_count": len(data_str.split('\n')),
                "paragraph_count": len([p for p in data_str.split('\n\n') if p.strip()])
            },
            "content_analysis": {
                "language": self._detect_language(data_str),
                "sentiment": self._analyze_sentiment(data_str),
                "topics": self._extract_topics(data_str),
                "keywords": self._extract_keywords(data_str)
            },
            "structure_analysis": {
                "has_headings": bool(re.search(r'^#+\s', data_str, re.MULTILINE)),
                "has_lists": bool(re.search(r'^[\*\-\+]\s', data_str, re.MULTILINE)),
                "has_code": bool(re.search(r'```', data_str)),
                "has_links": bool(re.search(r'http[s]?://', data_str)),
                "format_type": self._detect_format(data_str)
            }
        }
        
        return analysis_result
    
    def _extract_data(self, data: Any, task: str) -> Dict[str, Any]:
        """提取数据"""
        data_str = str(data)
        
        extraction_result = {
            "extracted_entities": self._extract_entities(data_str),
            "extracted_dates": self._extract_dates(data_str),
            "extracted_numbers": self._extract_numbers(data_str),
            "extracted_emails": self._extract_emails(data_str),
            "extracted_urls": self._extract_urls(data_str),
            "extracted_phone_numbers": self._extract_phone_numbers(data_str)
        }
        
        return extraction_result
    
    def _transform_data(self, data: Any, task: str) -> Dict[str, Any]:
        """转换数据"""
        data_str = str(data)
        
        transformation_result = {
            "original_data": data_str,
            "transformed_data": {
                "normalized_text": self._normalize_text(data_str),
                "cleaned_text": self._clean_text(data_str),
                "formatted_text": self._format_text(data_str),
                "structured_data": self._structure_data(data_str)
            },
            "transformation_summary": {
                "changes_made": ["文本规范化", "清理特殊字符", "格式化输出"],
                "data_integrity": "preserved"
            }
        }
        
        return transformation_result
    
    def _validate_data(self, data: Any, task: str) -> Dict[str, Any]:
        """验证数据"""
        data_str = str(data)
        
        validation_result = {
            "validation_checks": {
                "is_empty": len(data_str.strip()) == 0,
                "is_too_long": len(data_str) > self.max_text_length,
                "has_valid_encoding": self._check_encoding(data_str),
                "has_special_characters": self._has_special_characters(data_str),
                "is_structured": self._is_structured(data_str)
            },
            "quality_metrics": {
                "readability_score": self._calculate_readability(data_str),
                "coherence_score": self._calculate_coherence(data_str),
                "completeness_score": self._calculate_completeness(data_str, task)
            },
            "recommendations": self._generate_validation_recommendations(data_str, task)
        }
        
        return validation_result
    
    def _summarize_data(self, data: Any, task: str) -> Dict[str, Any]:
        """总结数据"""
        data_str = str(data)
        
        summary_result = {
            "original_length": len(data_str),
            "summary_length": 0,
            "compression_ratio": 0.0,
            "summary": self._generate_summary(data_str),
            "key_points": self._extract_key_points(data_str),
            "summary_type": "extractive"
        }
        
        summary_result["summary_length"] = len(summary_result["summary"])
        if summary_result["original_length"] > 0:
            summary_result["compression_ratio"] = summary_result["summary_length"] / summary_result["original_length"]
        
        return summary_result
    
    def _default_processing(self, data: Any, task: str, processing_type: str) -> Dict[str, Any]:
        """默认处理方法"""
        data_str = str(data)
        
        return {
            "processing_type": processing_type,
            "task": task,
            "data_preview": data_str[:500] + "..." if len(data_str) > 500 else data_str,
            "basic_info": {
                "length": len(data_str),
                "type": type(data).__name__,
                "processing_completed": True
            },
            "message": f"使用默认处理方法处理数据，类型: {processing_type}"
        }
    
    def process_file_content(self, file_data: Dict[str, Any], task: str) -> Dict[str, Any]:
        """处理文件内容"""
        content_type = file_data.get("content_type", "unknown")
        processing_status = file_data.get("processing_status", "unknown")
        
        if processing_status != "completed":
            return {
                "success": False,
                "error": f"文件处理未完成: {processing_status}",
                "result": None
            }
        
        if content_type == "pdf":
            return self._process_pdf_content(file_data, task)
        elif content_type == "excel":
            return self._process_excel_content(file_data, task)
        else:
            return {
                "success": False,
                "error": f"不支持的文件内容类型: {content_type}",
                "result": None
            }
    
    def _process_pdf_content(self, file_data: Dict[str, Any], task: str) -> Dict[str, Any]:
        """处理PDF文件内容"""
        text_content = file_data.get("text_content", "")
        content_analysis = file_data.get("content_analysis", {})
        
        if not text_content:
            return {
                "success": False,
                "error": "PDF文件没有可提取的文本内容",
                "result": None
            }
        
        # 使用AI优化文本内容
        optimized_content = self._optimize_pdf_content(text_content, task)
        
        result = {
            "success": True,
            "content_type": "pdf",
            "original_content": text_content[:1000] + "..." if len(text_content) > 1000 else text_content,
            "optimized_content": optimized_content,
            "content_analysis": content_analysis,
            "optimization_summary": {
                "original_length": len(text_content),
                "optimized_length": len(optimized_content),
                "improvements_applied": ["结构优化", "语言润色", "逻辑整理"]
            }
        }
        
        return result
    
    def _process_excel_content(self, file_data: Dict[str, Any], task: str) -> Dict[str, Any]:
        """处理Excel文件内容"""
        sheets = file_data.get("sheets", {})
        
        if not sheets:
            return {
                "success": False,
                "error": "Excel文件没有可处理的数据",
                "result": None
            }
        
        # 分析Excel数据
        analysis_results = {}
        
        for sheet_name, sheet_info in sheets.items():
            sample_data = sheet_info.get("sample_data", [])
            summary_stats = sheet_info.get("summary_stats", {})
            columns = sheet_info.get("columns", [])
            
            sheet_analysis = {
                "sheet_name": sheet_name,
                "data_summary": self._analyze_excel_sheet(sample_data, columns, summary_stats),
                "insights": self._generate_excel_insights(sample_data, columns, summary_stats),
                "recommendations": self._generate_excel_recommendations(sample_data, columns, task)
            }
            
            analysis_results[sheet_name] = sheet_analysis
        
        result = {
            "success": True,
            "content_type": "excel",
            "analysis_results": analysis_results,
            "summary": {
                "total_sheets": len(sheets),
                "data_quality_score": self._calculate_data_quality_score(analysis_results),
                "key_findings": self._extract_key_findings(analysis_results)
            }
        }
        
        return result
    
    def _optimize_pdf_content(self, text_content: str, task: str) -> str:
        """优化PDF内容"""
        # 这里可以集成LLM来优化文本内容
        # 目前提供一个基础优化版本
        
        # 基础文本清理
        optimized = text_content
        
        # 移除多余的空白字符
        import re
        optimized = re.sub(r'\s+', ' ', optimized)
        
        # 修复段落结构
        optimized = re.sub(r'([.!?])\s*([A-Z\u4e00-\u9fff])', r'\1\n\n\2', optimized)
        
        # 根据任务进行针对性优化
        if "报告" in task or "report" in task.lower():
            optimized = self._optimize_for_report(optimized)
        elif "分析" in task or "analysis" in task.lower():
            optimized = self._optimize_for_analysis(optimized)
        
        return optimized
    
    def _optimize_for_report(self, text: str) -> str:
        """为报告优化文本"""
        # 添加报告结构
        if not text.startswith('#'):
            # 如果没有标题，尝试提取第一个有意义的句子作为标题
            sentences = text.split('。')
            for sentence in sentences:
                if len(sentence.strip()) > 10:
                    text = f"# {sentence.strip()}\n\n{text}"
                    break
        
        return text
    
    def _optimize_for_analysis(self, text: str) -> str:
        """为分析优化文本"""
        # 添加分析结构
        analysis_sections = [
            "## 数据概览",
            "## 主要发现",
            "## 详细分析",
            "## 结论建议"
        ]
        
        # 检查是否已经有这些结构
        for section in analysis_sections:
            if section not in text:
                # 在适当位置添加结构
                text = f"{section}\n{text}"
                break
        
        return text
    
    def _analyze_excel_sheet(self, sample_data: List[Dict], columns: List[str], summary_stats: Dict) -> Dict[str, Any]:
        """分析Excel工作表"""
        analysis = {
            "columns": columns,
            "row_count": len(sample_data),
            "column_count": len(columns),
            "data_types": {},
            "completeness": {},
            "basic_statistics": summary_stats
        }
        
        if sample_data:
            # 分析数据类型
            for col in columns:
                col_values = [row.get(col) for row in sample_data if row.get(col) is not None]
                if col_values:
                    # 简单的类型推断
                    if all(isinstance(v, (int, float)) for v in col_values):
                        analysis["data_types"][col] = "numeric"
                    elif all(isinstance(v, str) for v in col_values):
                        analysis["data_types"][col] = "text"
                    else:
                        analysis["data_types"][col] = "mixed"
                    
                    # 计算完整性
                    non_null_count = len([v for v in col_values if v is not None])
                    analysis["completeness"][col] = non_null_count / len(sample_data)
        
        return analysis
    
    def _generate_excel_insights(self, sample_data: List[Dict], columns: List[str], summary_stats: Dict) -> List[str]:
        """生成Excel数据洞察"""
        insights = []
        
        if not sample_data:
            return insights
        
        # 数据量洞察
        insights.append(f"数据集包含 {len(sample_data)} 行记录")
        
        # 列数洞察
        insights.append(f"数据集包含 {len(columns)} 个字段")
        
        # 数据类型洞察
        numeric_columns = [col for col in columns if any(isinstance(row.get(col), (int, float)) for row in sample_data)]
        text_columns = [col for col in columns if col not in numeric_columns]
        
        if numeric_columns:
            insights.append(f"包含 {len(numeric_columns)} 个数值型字段")
        if text_columns:
            insights.append(f"包含 {len(text_columns)} 个文本型字段")
        
        # 统计洞察
        for col, stats in summary_stats.items():
            if isinstance(stats, dict) and 'mean' in stats:
                mean_val = stats['mean']
                std_val = stats.get('std', 0)
                insights.append(f"字段 '{col}' 的平均值为 {mean_val:.2f}，标准差为 {std_val:.2f}")
        
        return insights
    
    def _generate_excel_recommendations(self, sample_data: List[Dict], columns: List[str], task: str) -> List[str]:
        """生成Excel数据处理建议"""
        recommendations = []
        
        if not sample_data:
            return recommendations
        
        # 数据质量建议
        for col in columns:
            col_values = [row.get(col) for row in sample_data]
            null_count = len([v for v in col_values if v is None])
            
            if null_count > len(sample_data) * 0.5:
                recommendations.append(f"字段 '{col}' 缺失值较多，建议检查数据来源")
        
        # 数据分析建议
        numeric_columns = [col for col in columns if any(isinstance(row.get(col), (int, float)) for row in sample_data)]
        if len(numeric_columns) > 1:
            recommendations.append("建议进行多变量相关性分析")
        
        if len(numeric_columns) > 0:
            recommendations.append("建议生成数据可视化图表")
        
        # 任务相关建议
        if "报告" in task or "report" in task.lower():
            recommendations.append("建议基于数据生成结构化报告")
        elif "分析" in task or "analysis" in task.lower():
            recommendations.append("建议进行深入的趋势分析")
        
        return recommendations
    
    def _calculate_data_quality_score(self, analysis_results: Dict) -> float:
        """计算数据质量评分"""
        if not analysis_results:
            return 0.0
        
        total_score = 0.0
        sheet_count = 0
        
        for sheet_analysis in analysis_results.values():
            data_summary = sheet_analysis.get("data_summary", {})
            completeness = data_summary.get("completeness", {})
            
            if completeness:
                # 基于完整性计算评分
                avg_completeness = sum(completeness.values()) / len(completeness)
                total_score += avg_completeness
                sheet_count += 1
        
        return total_score / sheet_count if sheet_count > 0 else 0.0
    
    def _extract_key_findings(self, analysis_results: Dict) -> List[str]:
        """提取关键发现"""
        findings = []
        
        for sheet_name, sheet_analysis in analysis_results.items():
            insights = sheet_analysis.get("insights", [])
            for insight in insights:
                findings.append(f"{sheet_name}: {insight}")
        
        return findings[:10]  # 返回前10个关键发现
    
    def _detect_language(self, text: str) -> str:
        """检测文本语言"""
        # 简单的语言检测
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if chinese_chars > english_chars:
            return "zh-CN"
        elif english_chars > 0:
            return "en"
        else:
            return "unknown"
    
    def _analyze_sentiment(self, text: str) -> str:
        """分析情感倾向"""
        # 简单的情感分析
        positive_words = ["好", "优秀", "成功", "喜欢", "满意", "棒", "赞", "good", "great", "excellent", "love", "like"]
        negative_words = ["坏", "差", "失败", "讨厌", "不满", "糟", "bad", "terrible", "hate", "dislike", "fail"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _extract_topics(self, text: str) -> List[str]:
        """提取主题"""
        # 简单的主题提取
        words = re.findall(r'\b[\w\u4e00-\u9fff]+\b', text)
        word_freq = {}
        
        for word in words:
            if len(word) > 1:  # 忽略单字符
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # 返回频率最高的词作为主题
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:5]]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 基于词频和位置提取关键词
        sentences = re.split(r'[。！？.!?]', text)
        keywords = []
        
        for sentence in sentences:
            if sentence.strip():
                # 提取句子中的名词和形容词
                words = re.findall(r'\b[\w\u4e00-\u9fff]{2,}\b', sentence)
                keywords.extend(words)
        
        # 统计词频
        keyword_freq = {}
        for keyword in keywords:
            keyword_freq[keyword] = keyword_freq.get(keyword, 0) + 1
        
        # 返回高频关键词
        sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)
        return [keyword for keyword, freq in sorted_keywords[:10]]
    
    def _detect_format(self, text: str) -> str:
        """检测文本格式"""
        if re.search(r'^#{1,6}\s', text, re.MULTILINE):
            return "markdown"
        elif re.search(r'<[^>]+>', text):
            return "html"
        elif re.search(r'^\s*"[^"]+":\s*{', text, re.MULTILINE):
            return "json"
        elif re.search(r'^\s*[A-Za-z_][A-Za-z0-9_]*:\s', text, re.MULTILINE):
            return "yaml"
        else:
            return "plain_text"
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """提取命名实体"""
        entities = []
        
        # 提取人名（简单模式）
        person_pattern = r'([A-Z][a-z]+ [A-Z][a-z]+)'
        persons = re.findall(person_pattern, text)
        for person in persons:
            entities.append({"type": "PERSON", "text": person})
        
        # 提取组织名（简单模式）
        org_pattern = r'([A-Z][a-z]+ (?:Inc|Corp|Company|Group|Organization))'
        orgs = re.findall(org_pattern, text)
        for org in orgs:
            entities.append({"type": "ORGANIZATION", "text": org})
        
        return entities
    
    def _extract_dates(self, text: str) -> List[str]:
        """提取日期"""
        date_patterns = [
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{4}年\d{2}月\d{2}日',  # 中文日期
            r'\d{1,2}月\d{1,2}日',  # 简化中文日期
        ]
        
        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, text))
        
        return list(set(dates))  # 去重
    
    def _extract_numbers(self, text: str) -> List[str]:
        """提取数字"""
        # 提取各种格式的数字
        number_patterns = [
            r'\d+\.?\d*',  # 小数
            r'\d{1,3}(?:,\d{3})*',  # 带逗号的数字
            r'\d+%',  # 百分比
            r'\d+\s*(?:万|亿|千|百万)',  # 中文数字单位
        ]
        
        numbers = []
        for pattern in number_patterns:
            numbers.extend(re.findall(pattern, text))
        
        return list(set(numbers))
    
    def _extract_emails(self, text: str) -> List[str]:
        """提取邮箱地址"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        return re.findall(email_pattern, text)
    
    def _extract_urls(self, text: str) -> List[str]:
        """提取URL"""
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        return re.findall(url_pattern, text)
    
    def _extract_phone_numbers(self, text: str) -> List[str]:
        """提取电话号码"""
        phone_patterns = [
            r'1[3-9]\d{9}',  # 中国手机号
            r'\d{3}-\d{4}-\d{4}',  # XXX-XXXX-XXXX
            r'\d{3}-\d{3}-\d{4}',  # XXX-XXX-XXXX
            r'\(\d{3}\)\s*\d{3}-\d{4}',  # (XXX) XXX-XXXX
        ]
        
        phone_numbers = []
        for pattern in phone_patterns:
            phone_numbers.extend(re.findall(pattern, text))
        
        return list(set(phone_numbers))
    
    def _normalize_text(self, text: str) -> str:
        """规范化文本"""
        # 转换为统一格式
        normalized = text
        
        # 统一换行符
        normalized = re.sub(r'\r\n|\r', '\n', normalized)
        
        # 统一空格
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # 统一标点符号
        normalized = re.sub(r'，', ',', normalized)
        normalized = re.sub(r'。', '.', normalized)
        normalized = re.sub(r'！', '!', normalized)
        normalized = re.sub(r'？', '?', normalized)
        
        return normalized.strip()
    
    def _clean_text(self, text: str) -> str:
        """清理文本"""
        cleaned = text
        
        # 移除特殊字符
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()\[\]{}"\'-]', '', cleaned)
        
        # 移除多余的空格
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # 移除空行
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
        
        return cleaned.strip()
    
    def _format_text(self, text: str) -> str:
        """格式化文本"""
        formatted = text
        
        # 确保段落之间有适当的间隔
        formatted = re.sub(r'\n\s*\n', '\n\n', formatted)
        
        # 确保句子结束有适当的标点
        formatted = re.sub(r'([a-zA-Z\u4e00-\u9fff])\s*([a-zA-Z\u4e00-\u9fff])', r'\1. \2', formatted)
        
        return formatted
    
    def _structure_data(self, text: str) -> Dict[str, Any]:
        """结构化数据"""
        lines = text.split('\n')
        structured = {
            "paragraphs": [],
            "headings": [],
            "lists": [],
            "code_blocks": []
        }
        
        current_paragraph = []
        in_code_block = False
        
        for line in lines:
            line = line.strip()
            
            if not line:
                if current_paragraph:
                    structured["paragraphs"].append(' '.join(current_paragraph))
                    current_paragraph = []
                continue
            
            # 检测标题
            if re.match(r'^#+\s', line):
                if current_paragraph:
                    structured["paragraphs"].append(' '.join(current_paragraph))
                    current_paragraph = []
                structured["headings"].append(line)
                continue
            
            # 检测代码块
            if line.startswith('```'):
                in_code_block = not in_code_block
                continue
            
            if in_code_block:
                if not structured["code_blocks"] or structured["code_blocks"][-1] != line:
                    structured["code_blocks"].append(line)
                continue
            
            # 检测列表项
            if re.match(r'^[\*\-\+]\s', line):
                if current_paragraph:
                    structured["paragraphs"].append(' '.join(current_paragraph))
                    current_paragraph = []
                structured["lists"].append(line)
                continue
            
            current_paragraph.append(line)
        
        # 处理最后一个段落
        if current_paragraph:
            structured["paragraphs"].append(' '.join(current_paragraph))
        
        return structured
    
    def _check_encoding(self, text: str) -> bool:
        """检查编码"""
        try:
            text.encode('utf-8')
            return True
        except UnicodeEncodeError:
            return False
    
    def _has_special_characters(self, text: str) -> bool:
        """检查是否包含特殊字符"""
        special_chars = re.findall(r'[^\w\s\u4e00-\u9fff.,!?;:()\[\]{}"\'-]', text)
        return len(special_chars) > 0
    
    def _is_structured(self, text: str) -> bool:
        """检查是否有结构"""
        return bool(re.search(r'^(#{1,6}\s|[\*\-\+]\s|\d+\.\s)', text, re.MULTILINE))
    
    def _calculate_readability(self, text: str) -> float:
        """计算可读性评分"""
        if not text:
            return 0.0
        
        # 简单的可读性计算
        sentences = len(re.split(r'[。！？.!?]', text))
        words = len(re.findall(r'\b[\w\u4e00-\u9fff]+\b', text))
        
        if sentences == 0:
            return 0.0
        
        avg_words_per_sentence = words / sentences
        
        # 简单评分：句子长度适中得分高
        if 10 <= avg_words_per_sentence <= 20:
            return 0.8
        elif 5 <= avg_words_per_sentence <= 30:
            return 0.6
        else:
            return 0.4
    
    def _calculate_coherence(self, text: str) -> float:
        """计算连贯性评分"""
        if not text:
            return 0.0
        
        # 简单的连贯性检查
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) < 2:
            return 0.5
        
        # 检查句子之间的连接词
        transition_words = ["但是", "因此", "所以", "然而", "另外", "而且", "同时", 
                           "but", "therefore", "so", "however", "also", "moreover", "while"]
        
        coherence_count = 0
        for i in range(len(sentences) - 1):
            for word in transition_words:
                if word in sentences[i] or word in sentences[i + 1]:
                    coherence_count += 1
                    break
        
        return min(coherence_count / (len(sentences) - 1), 1.0)
    
    def _calculate_completeness(self, text: str, task: str) -> float:
        """计算完整性评分"""
        if not text or not task:
            return 0.0
        
        # 基于任务关键词的完整性检查
        task_keywords = re.findall(r'\b[\w\u4e00-\u9fff]{2,}\b', task)
        text_keywords = re.findall(r'\b[\w\u4e00-\u9fff]{2,}\b', text)
        
        if not task_keywords:
            return 0.5
        
        matched_keywords = sum(1 for keyword in task_keywords if keyword in text_keywords)
        completeness = matched_keywords / len(task_keywords)
        
        return min(completeness, 1.0)
    
    def _generate_validation_recommendations(self, text: str, task: str) -> List[str]:
        """生成验证建议"""
        recommendations = []
        
        if len(text) > self.max_text_length:
            recommendations.append("文本过长，建议分段处理")
        
        if self._has_special_characters(text):
            recommendations.append("包含特殊字符，建议清理文本")
        
        readability = self._calculate_readability(text)
        if readability < 0.6:
            recommendations.append("可读性较低，建议优化句子结构")
        
        coherence = self._calculate_coherence(text)
        if coherence < 0.6:
            recommendations.append("连贯性不足，建议增加过渡词")
        
        completeness = self._calculate_completeness(text, task)
        if completeness < 0.6:
            recommendations.append("完整性不足，建议补充相关信息")
        
        if not recommendations:
            recommendations.append("数据质量良好，无需特别处理")
        
        return recommendations
    
    def _generate_summary(self, text: str) -> str:
        """生成摘要"""
        if not text:
            return ""
        
        # 简单的抽取式摘要
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) <= 3:
            return text
        
        # 选择前3个句子作为摘要
        summary = '。'.join(sentences[:3]) + '。'
        
        # 限制摘要长度
        if len(summary) > 300:
            summary = summary[:300] + "..."
        
        return summary
    
    def _extract_key_points(self, text: str) -> List[str]:
        """提取关键点"""
        if not text:
            return []
        
        # 简单的关键点提取
        sentences = re.split(r'[。！？.!?]', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        key_points = []
        
        # 寻找包含重要词汇的句子
        important_words = ["重要", "关键", "核心", "主要", "基本", "essential", "key", "important", "main", "core"]
        
        for sentence in sentences:
            for word in important_words:
                if word in sentence:
                    key_points.append(sentence)
                    break
        
        # 如果没有找到，选择前3个句子
        if not key_points:
            key_points = sentences[:3]
        
        return key_points[:5]  # 最多返回5个关键点
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "DataProcessorTool",
            "description": "数据处理器工具，提供数据处理和分析功能",
            "version": "1.0.0",
            "enabled": self.enabled,
            "max_text_length": self.max_text_length,
            "supported_types": ["analysis", "extraction", "transformation", "validation", "summarization"],
            "capabilities": [
                "文本分析",
                "数据提取",
                "格式转换",
                "质量验证",
                "自动摘要",
                "关键词提取",
                "情感分析",
                "语言检测"
            ]
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        if not isinstance(input_data, dict):
            return False
        
        task = input_data.get("task", "")
        data = input_data.get("data", "")
        processing_type = input_data.get("processing_type", "")
        
        if not task or not isinstance(task, str):
            return False
        
        if data is None:
            return False
        
        if not isinstance(processing_type, str):
            return False
        
        return True
    
    def enable_tool(self) -> None:
        """启用工具"""
        self.enabled = True
        logger.info("数据处理器工具已启用", agent_name="DataProcessorTool")
    
    def disable_tool(self) -> None:
        """禁用工具"""
        self.enabled = False
        logger.info("数据处理器工具已禁用", agent_name="DataProcessorTool")
    
    def set_max_text_length(self, max_length: int) -> None:
        """设置最大文本长度"""
        if max_length > 0:
            self.max_text_length = max_length
            logger.info(f"最大文本长度已设置为: {max_length}", agent_name="DataProcessorTool")
        else:
            raise ValueError("最大文本长度必须大于0")
