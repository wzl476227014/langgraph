"""
Slide Analyzer Tool
文档分析工具 - 从PDF中提取幻灯片所需的关键信息
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..utils.config import get_config, get_agent_prompt
from ..utils.logger import get_logger
from ..utils.llm_config import generate_system_response

logger = get_logger(__name__)


class SlideAnalyzerTool:
    """文档分析工具 - 提取PDF中的关键数据用于幻灯片生成"""

    def __init__(self):
        """初始化文档分析工具"""
        self.config = get_config().get_tool_config("slide_analyzer")
        self.enabled = self.config.get("enabled", True)
        self.llm_model = self.config.get("llm_model", "claude-3-5-sonnet-20241022")

        logger.info("SlideAnalyzerTool initialized", agent_name="SlideAnalyzer")

    def analyze_document(
        self,
        document_content: str,
        user_requirements: str,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        分析文档内容,提取幻灯片生成所需的结构化信息

        Args:
            document_content: 文档原始内容(PDF提取后的文本)
            user_requirements: 用户需求描述
            file_path: 文档路径(可选)

        Returns:
            Dict包含:
            - key_data: 关键数据点(数字、指标等)
            - chapters: 章节结构
            - metrics: 统计指标
            - summary: 文档摘要
            - outline_suggestion: 建议的幻灯片大纲
        """
        logger.info("Starting document analysis", agent_name="SlideAnalyzer")

        if not self.enabled:
            logger.warning("SlideAnalyzer is disabled", agent_name="SlideAnalyzer")
            return self._get_default_analysis()

        try:
            # 构建分析提示词
            analysis_prompt = self._build_analysis_prompt(
                document_content,
                user_requirements
            )

            # 调用LLM分析
            analysis_result = generate_system_response(
                system_prompt=self._get_system_prompt(),
                user_message=analysis_prompt,
                temperature=1.0,
                max_tokens=4000
            )

            # 打印LLM原始输出
            logger.info("=" * 80, agent_name="SlideAnalyzer")
            logger.info("LLM原始输出 (analysis_result):", agent_name="SlideAnalyzer")
            logger.info(analysis_result, agent_name="SlideAnalyzer")
            logger.info("=" * 80, agent_name="SlideAnalyzer")

            # 解析分析结果
            parsed_result = self._parse_analysis_result(analysis_result)

            # 添加元数据
            parsed_result["metadata"] = {
                "file_path": file_path,
                "analysis_time": datetime.now().isoformat(),
                "user_requirements": user_requirements
            }

            logger.info(
                f"Document analysis completed. Found {len(parsed_result.get('key_data', {}))} key data points",
                agent_name="SlideAnalyzer"
            )

            # 打印完整的 parsed_result
            import json
            logger.info("=" * 80, agent_name="SlideAnalyzer")
            logger.info("文档分析结果 (parsed_result):", agent_name="SlideAnalyzer")
            logger.info(json.dumps(parsed_result, ensure_ascii=False, indent=2), agent_name="SlideAnalyzer")
            logger.info("=" * 80, agent_name="SlideAnalyzer")

            return parsed_result

        except Exception as e:
            logger.error(f"Document analysis failed: {str(e)}", agent_name="SlideAnalyzer")
            return self._get_default_analysis()

    def _build_analysis_prompt(self, document_content: str, user_requirements: str) -> str:
        """构建文档分析提示词"""
        # 截取文档内容(避免超过token限制)
        max_content_length = 15000
        if len(document_content) > max_content_length:
            document_content = document_content[:max_content_length] + "\n...(内容已截断)"

        prompt = f"""
请详细分析以下文档内容,提取用于生成PPT幻灯片的关键信息。

【用户需求】
{user_requirements}

【文档内容】
{document_content}

【分析要求】
请按以下JSON格式输出分析结果:

{{
    "key_data": {{
        "资产数量": "285个服务器IP资产",
        "监测日志": "589.39万条",
        "安全告警": "6.7万条",
        ... (提取所有关键数字和统计指标)
    }},
    "detailed_content": {{
        "一、[章节名称]": {{
            "小节标题": "完整段落内容，包含数据+描述..."
        }},
        "二、[章节名称]": {{ ... }}
        ... (按文档实际章节组织，每个value必须是完整段落，不只是关键词)
    }},
    "chapters": [
        {{
            "title": "安全运营目标",
            "content_summary": "监管通报应对、攻防演练等核心目标"
        }},
        ... (识别文档中的主要章节标题和摘要即可，完整段落存储在detailed_content中)
    ],
    "metrics": {{
        "total_assets": 285,
        "total_alerts": 67000,
        "closure_rate": 91.13,
        ... (纯数值型指标，用于图表展示)
    }},
    "summary": "文档核心内容的简短摘要(2-3句话)",
    "outline_suggestion": {{
        "recommended_page_count": 15,
        "reasoning": "文档包含4个主要章节和12个关键数据点，建议15页以充分展示内容",
        "page_types": {{
            "cover": 1,
            "toc": 1,
            "content": 11,
            "summary": 1,
            "thanks": 1
        }},
        "suggested_structure": [
            "第1页: 封面页",
            "第2页: 目录页",
            "第3页: 运营目标",
            ... (建议的完整结构)
        ]
    }}
}}

【注意事项】
1. **key_data**: 提取所有带数字的统计指标（如"285个服务器IP资产"、"闭环率91.13%"）

2. **detailed_content**: ⚠️⚠️⚠️ 最重要的部分！必须按照以下要求组织：
   - **结构化层次**：使用"一、二、三、四"等章节标题作为一级 key
   - **完整段落**：每个小节的 value 必须是完整的段落文本，包含数据和描述
   - **内容丰富**：不要只提取关键词，要提取完整的句子和段落
   - **参考示例格式**：
     ```
     "一、安全运营成果数据": {{
       "资产管理": "IT业务资产共285个服务器IP、60项服务资产纳入7×24小时监测，识别风险资产89个，闭环48个，41个因漏洞或弱口令未闭环。",
       "实时监测": "运营期间监测589.39万条安全日志，产生6.7万条告警..."
     }}
     ```
   - **必须包含**：工作方法、具体措施、问题分析、改进建议、业务流程等所有描述性内容
   - **按用户需求组织**：如果用户需求中指定了章节结构（如"第二页：目录页，包含【安全运营目标】..."），则按用户要求的章节组织

3. **chapters**: 只需章节标题和摘要，完整段落已存储在detailed_content中，避免重复

4. **metrics**: 只包含纯数值（如 "total_assets": 285），便于图表展示

5. **outline_suggestion**: ⚠️ 智能推荐页数
   - **recommended_page_count**: 根据文档内容量智能推荐页数
     * 考虑因素：章节数量、关键数据点数量、内容复杂度、用户需求
     * 推荐规则：
       - 简单文档（1-2章节，<5个数据点）：5-8页
       - 中等文档（3-4章节，5-15个数据点）：10-15页
       - 复杂文档（5+章节，15+个数据点）：15-25页
     * 如果用户明确要求页数（如"生成3页"），必须遵守用户要求
     * 如果用户未指定，根据文档内容智能推荐
   - **reasoning**: 简要说明推荐页数的理由（1句话）
   - **page_types**: 各类型页面的建议数量
   - **suggested_structure**: 建议的页面结构

6. **JSON格式要求**：
   - 必须返回严格的JSON格式
   - 字符串中的反斜杠必须转义为 \\\\ (例如: "7×24H" 不要写成 "7\×24H")
   - 特殊字符如引号、换行符等必须正确转义
   - 确保所有括号、引号正确配对

请开始分析:
"""
        return prompt

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个专业的文档分析专家,擅长从安全运营报告、业务分析报告等文档中提取关键信息。

你的任务是:
1. 准确识别文档中的所有关键数据点(数字、指标、统计数据)
2. 理解文档的章节结构和逻辑关系
3. 提取适合用于PPT展示的核心内容
4. 建议合理的幻灯片大纲结构

输出要求:
- **必须返回严格有效的JSON格式**
- **所有字段值之间必须用逗号分隔**
- **所有字符串必须用双引号包围**
- **不要在JSON中添加注释**
- 数据提取要完整、准确
- 建议的大纲要符合PPT设计规范
- 关注数据的可视化潜力

JSON格式检查清单:
✓ 每个键值对后面有逗号（最后一个除外）
✓ 所有字符串用双引号
✓ 数组元素之间有逗号
✓ 对象成员之间有逗号
✓ 没有尾随逗号"""

    def _parse_analysis_result(self, analysis_result: str) -> Dict[str, Any]:
        """解析LLM返回的分析结果"""
        try:
            # 尝试提取JSON
            json_match = re.search(r'\{[\s\S]*\}', analysis_result)
            if json_match:
                json_str = json_match.group()

                # 尝试直接解析
                try:
                    result = json.loads(json_str)
                    return result
                except json.JSONDecodeError as e:
                    # 如果失败，尝试修复常见的JSON错误
                    logger.warning(f"First parse failed: {str(e)}, attempting to fix JSON", agent_name="SlideAnalyzer")

                    # 多步骤修复JSON
                    fixed_json = json_str

                    # 1. 修复未转义的反斜杠
                    fixed_json = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', fixed_json)

                    # 2. 修复缺失的逗号（对象内部）
                    # 匹配: "key": "value" "nextkey" -> "key": "value", "nextkey"
                    fixed_json = re.sub(r'("\s*:\s*"[^"]*")\s+(")', r'\1, \2', fixed_json)
                    # 匹配: "key": value } "nextkey" -> "key": value, "nextkey"
                    fixed_json = re.sub(r'("\s*:\s*[^,}\]]+)\s+(")', r'\1, \2', fixed_json)

                    # 3. 修复数组内缺失的逗号
                    # 匹配: } { -> }, {
                    fixed_json = re.sub(r'}\s*{', r'}, {', fixed_json)
                    # 匹配: ] [ -> ], [
                    fixed_json = re.sub(r']\s*\[', r'], [', fixed_json)

                    # 4. 移除尾部多余的逗号
                    fixed_json = re.sub(r',(\s*[}\]])', r'\1', fixed_json)

                    # 5. 修复未闭合的引号（简单处理）
                    # 统计每行的引号数量，如果是奇数则在行尾添加引号
                    lines = fixed_json.split('\n')
                    fixed_lines = []
                    for line in lines:
                        quote_count = line.count('"') - line.count('\\"')
                        if quote_count % 2 != 0 and not line.strip().endswith(','):
                            # 奇数引号，可能缺失闭合引号
                            line = line.rstrip() + '"'
                        fixed_lines.append(line)
                    fixed_json = '\n'.join(fixed_lines)

                    try:
                        result = json.loads(fixed_json)
                        logger.info("Successfully parsed JSON after fixing", agent_name="SlideAnalyzer")
                        return result
                    except json.JSONDecodeError as e2:
                        logger.error(f"Failed to parse even after fixing: {str(e2)}", agent_name="SlideAnalyzer")

                        # 尝试最后一次修复：在错误位置附近添加缺失的逗号
                        error_pos = getattr(e2, 'pos', 0)
                        error_msg = str(e2).lower()

                        if 'expecting' in error_msg and 'delimiter' in error_msg:
                            # 错误提示缺少分隔符，尝试在错误位置前插入逗号
                            logger.info(f"Attempting to add missing comma at position {error_pos}", agent_name="SlideAnalyzer")

                            # 查找错误位置前最近的引号或括号
                            search_start = max(0, error_pos - 50)
                            before_error = fixed_json[search_start:error_pos]

                            # 找到最后一个非空白字符的位置
                            insert_pos = error_pos
                            for i in range(error_pos - 1, search_start - 1, -1):
                                if fixed_json[i] not in [' ', '\n', '\t', '\r']:
                                    insert_pos = i + 1
                                    break

                            # 在该位置插入逗号
                            last_fix_json = fixed_json[:insert_pos] + ',' + fixed_json[insert_pos:]

                            try:
                                result = json.loads(last_fix_json)
                                logger.info("Successfully parsed JSON after adding missing comma", agent_name="SlideAnalyzer")
                                return result
                            except json.JSONDecodeError as e3:
                                logger.error(f"Final attempt failed: {str(e3)}", agent_name="SlideAnalyzer")

                        # 打印错误位置附近的内容
                        context_start = max(0, error_pos - 100)
                        context_end = min(len(fixed_json), error_pos + 100)
                        logger.error(f"Error context: ...{fixed_json[context_start:context_end]}...", agent_name="SlideAnalyzer")

                        # 保存失败的JSON到文件以便调试
                        try:
                            import tempfile
                            with tempfile.NamedTemporaryFile(mode='w', suffix='_failed.json', delete=False, encoding='utf-8') as f:
                                f.write(fixed_json)
                                logger.error(f"Failed JSON saved to: {f.name}", agent_name="SlideAnalyzer")
                        except:
                            pass

                        return self._get_default_analysis()
            else:
                logger.warning("No JSON found in analysis result", agent_name="SlideAnalyzer")
                return self._get_default_analysis()

        except Exception as e:
            logger.error(f"Unexpected error parsing analysis result: {str(e)}", agent_name="SlideAnalyzer")
            return self._get_default_analysis()

    def _get_default_analysis(self) -> Dict[str, Any]:
        """返回失败标记，不使用默认配置"""
        return {
            "key_data": {},
            "chapters": [],
            "metrics": {},
            "summary": "文档分析失败",
            "outline_suggestion": {},
            "metadata": {
                "analysis_time": datetime.now().isoformat(),
                "status": "failed",
                "error": "JSON解析失败，无法提取文档内容"
            },
            "parse_failed": True  # 添加失败标记
        }

    def extract_data_for_chart(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        从分析结果中提取适合图表展示的数据

        Returns:
            List of chart data dictionaries
        """
        chart_data = []

        metrics = analysis_result.get("metrics", {})
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                chart_data.append({
                    "label": key,
                    "value": value,
                    "type": "number"
                })

        return chart_data

    def get_chapter_outline(self, analysis_result: Dict[str, Any]) -> List[str]:
        """
        获取章节大纲列表

        Returns:
            List of chapter titles
        """
        chapters = analysis_result.get("chapters", [])
        return [chapter.get("title", "") for chapter in chapters]
