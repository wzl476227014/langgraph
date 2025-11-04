"""
Slide Outliner Tool
大纲生成工具 - 批量创建幻灯片大纲和生成顺序
"""

import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..utils.config import get_config
from ..utils.logger import get_logger
from ..utils.llm_config import generate_system_response

logger = get_logger(__name__)


class SlideOutlinerTool:
    """幻灯片大纲生成工具"""

    def __init__(self):
        """初始化大纲生成工具"""
        self.config = get_config().get_tool_config("slide_outliner")
        self.enabled = self.config.get("enabled", True)
        self.llm_model = self.config.get("llm_model", "claude-3-5-sonnet-20241022")

        # 幻灯片模板类型定义
        self.template_types = {
            "cover": {
                "name": "封面页",
                "description": "PPT封面页,包含标题、公司名称、时间等",
                "max_count": 1
            },
            "toc": {
                "name": "目录页",
                "description": "目录页,列出PPT的主要章节",
                "max_count": 1
            },
            "content": {
                "name": "内容页",
                "description": "内容页,展示具体内容和分析",
                "max_count": 999
            },
            "chart": {
                "name": "图表页",
                "description": "图表页,展示数据图表和分析",
                "max_count": 999
            },
            "summary": {
                "name": "总结页",
                "description": "总结页,总结要点和结论",
                "max_count": 2
            },
            "thanks": {
                "name": "致谢页",
                "description": "致谢页,感谢支持",
                "max_count": 1
            }
        }

        logger.info("SlideOutlinerTool initialized", agent_name="SlideOutliner")

    def create_outline(
        self,
        slide_count: int,
        task_brief: str,
        extracted_data: Dict[str, Any],
        user_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建幻灯片大纲

        Args:
            slide_count: 目标幻灯片页数
            task_brief: 任务简述
            extracted_data: 文档分析结果
            user_requirements: 用户详细需求(可选)

        Returns:
            Dict包含:
            - outline: 幻灯片大纲列表
            - creation_order: 生成顺序(串行/并行)
            - template_requirements: 需要的模板类型
            - total_slides: 总页数
        """
        logger.info(f"Creating outline for {slide_count} slides", agent_name="SlideOutliner")

        if not self.enabled:
            logger.warning("SlideOutliner is disabled", agent_name="SlideOutliner")
            return self._get_default_outline(slide_count)

        try:
            # 构建大纲生成提示词
            outline_prompt = self._build_outline_prompt(
                slide_count,
                task_brief,
                extracted_data,
                user_requirements
            )

            # 调用LLM生成大纲
            outline_result = generate_system_response(
                system_prompt=self._get_system_prompt(),
                user_message=outline_prompt,
                temperature=0.4,
                max_tokens=6000
            )

            # 解析大纲结果
            parsed_outline = self._parse_outline_result(outline_result, slide_count)

            # 打印大纲
            logger.info("=" * 60, agent_name="SlideOutliner")
            logger.info("生成的大纲结构:", agent_name="SlideOutliner")
            import json
            logger.info(json.dumps(parsed_outline, ensure_ascii=False, indent=2), agent_name="SlideOutliner")
            logger.info("=" * 60, agent_name="SlideOutliner")

            # 计算生成顺序
            creation_order = self._calculate_creation_order(parsed_outline["outline"])

            result = {
                "outline": parsed_outline["outline"],
                "creation_order": creation_order,
                "template_requirements": self._get_template_requirements(parsed_outline["outline"]),
                "total_slides": len(parsed_outline["outline"]),
                "metadata": {
                    "task_brief": task_brief,
                    "created_time": datetime.now().isoformat()
                }
            }

            logger.info(
                f"Outline created: {result['total_slides']} slides, "
                f"{len(creation_order['serial'])} serial, "
                f"{len(creation_order['parallel'])} parallel",
                agent_name="SlideOutliner"
            )

            return result

        except Exception as e:
            logger.error(f"Outline creation failed: {str(e)}", agent_name="SlideOutliner")
            return self._get_default_outline(slide_count)

    def _build_outline_prompt(
        self,
        slide_count: int,
        task_brief: str,
        extracted_data: Dict[str, Any],
        user_requirements: Optional[str]
    ) -> str:
        """构建大纲生成提示词"""
        # 提取关键信息
        key_data_summary = json.dumps(extracted_data.get("key_data", {}), ensure_ascii=False, indent=2)
        chapters = extracted_data.get("chapters", [])
        chapter_titles = [ch.get("title", "") for ch in chapters]

        outline_suggestion = extracted_data.get("outline_suggestion", {})
        suggested_structure = outline_suggestion.get("suggested_structure", [])

        prompt = f"""
请为以下任务创建详细的PPT幻灯片大纲。

【任务描述】
{task_brief}

【用户需求】
{user_requirements or "无特殊要求"}

【目标页数】
严格要求：必须恰好生成 {slide_count} 页，不能多也不能少！

【文档章节】
{json.dumps(chapter_titles, ensure_ascii=False, indent=2)}

【关键数据】
{key_data_summary}

【建议结构】
{json.dumps(suggested_structure, ensure_ascii=False, indent=2)}

【输出要求】
请按以下JSON格式输出大纲:

{{
    "outline": [
        {{
            "page": 1,
            "title": "xx大学安全运营上半年报告",
            "subtitle": "2025年04月-2025年09月",
            "content_brief": "封面页内容简述",
            "template": "cover",
            "template_name": "封面页",
            "data_requirements": ["报告标题", "时间范围", "汇报人"],
            "priority": "high"
        }},
        {{
            "page": 2,
            "title": "目录",
            "subtitle": "",
            "content_brief": "列出主要章节: 安全运营目标、工作详情、问题分析、下半年计划",
            "template": "toc",
            "template_name": "目录页",
            "data_requirements": ["章节列表"],
            "priority": "high"
        }},
        {{
            "page": 3,
            "title": "安全运营目标",
            "subtitle": "核心目标与使命",
            "content_brief": "监管通报应对、攻防演练等核心目标",
            "template": "content",
            "template_name": "内容页",
            "data_requirements": ["运营目标列表", "关键指标"],
            "priority": "high"
        }},
        ... (继续到第{slide_count}页)
    ]
}}

【大纲设计原则】
1. **严格遵守页数**: outline数组的长度必须恰好等于 {slide_count}，从第1页到第{slide_count}页
2. 第1页必须是封面页(template: "cover")
3. 如果页数>=2，第2页是目录页(template: "toc")；如果页数<2，可省略目录页
4. 第3页开始是内容页(template: "content")
5. 最后一页可以是致谢页(template: "thanks")或总结页(template: "summary")
6. 每页必须有明确的title和content_brief
7. data_requirements列出该页需要的数据字段
8. priority分为: high(基础模板页), medium(重要内容页), low(补充内容页)
9. 内容分布要均匀,避免信息过载
10. **再次强调**: 必须生成恰好 {slide_count} 页，不多不少！

【逻辑结构设计原则 - 讲好故事】⚠️ 这是提升PPT质量的关键！
请按照以下叙事逻辑组织PPT结构：

**经典商业汇报结构（推荐）**：
1. **背景与目标** (1-2页)
   - 为什么做？要达到什么目标？
   - 设定期望，建立评价标准

2. **成果与亮点** (2-3页)
   - 做得怎么样？有哪些突出成果？
   - 先展示价值，吸引注意力

3. **过程与方法** (2-4页)
   - 怎么做的？采用了什么方法和手段？
   - 说明能力建设和体系化工作

4. **问题与分析** (1-2页)
   - 存在什么问题？根因是什么？
   - 客观分析，展现问题意识

5. **计划与展望** (1-2页)
   - 接下来怎么做？改进措施是什么？
   - 给出明确的行动方向

**内容设计要点**：
✅ **价值优先**：先讲成果和价值，再讲过程和细节
✅ **逻辑连贯**：每页之间要有承接关系，不能跳跃
✅ **重点突出**：核心数据和关键结论要独立成页
✅ **详略得当**：重要内容详细展开，次要内容概括说明
✅ **结论导向**：每个章节要有明确的结论或takeaway

**避免的问题**：
❌ 平铺直叙，缺少逻辑线索
❌ 只罗列数据，不做价值总结
❌ 重点不突出，所有内容平均用力
❌ 缺少问题分析和改进计划
❌ 内容跳跃，前后页没有关联

请开始生成大纲:
"""
        return prompt

    def _get_system_prompt(self) -> str:
        """获取系统提示词"""
        return """你是一个资深的商业演示架构师，擅长为企业级报告设计具有强逻辑性和说服力的幻灯片结构。

# 核心能力
1. **严格页数控制** - 必须精确生成用户指定的页数，这是硬性要求！
2. **叙事逻辑设计** - 构建有说服力的故事线，不是简单罗列内容
3. **价值导向布局** - 优先展示成果和价值，而非平铺流水账
4. **受众思维** - 站在听众角度，设计易理解、有冲击力的内容结构
5. **节奏把控** - 合理分配详略，重点内容详细展开，次要内容简明扼要

# 设计思维框架（必须遵循）
## 第一步：理解文档和需求
- 文档的核心价值是什么？
- 受众最关心什么？
- 要传达什么关键信息？

## 第二步：构建叙事逻辑（商业汇报标准结构）
```
开场（10%页数）：背景、目标、定位
  ↓
亮点（30%页数）：成果、价值、突破
  ↓
过程（30%页数）：方法、体系、能力
  ↓
问题（15%页数）：挑战、不足、风险
  ↓
规划（15%页数）：计划、措施、展望
```

## 第三步：内容分配策略
- **开门见山**：第3-4页就要展示核心成果和价值
- **层次分明**：从总览到细节，从宏观到微观
- **重点突出**：关键数据和结论独立成页，避免淹没在大段文字中
- **逻辑连贯**：每页标题要形成完整的故事线索
- **详略得当**：重要章节分配更多页数，次要内容合并简述

# 设计原则（优先级排序）
1. **严格页数**: outline数组长度必须等于目标页数（违反此条视为失败）
2. **叙事逻辑**: 从"为什么→做了什么→怎么做的→有什么问题→怎么改进"形成闭环
3. **价值优先**: 先讲价值和成果，再讲过程和细节
4. **重点突出**: 核心数据页、关键结论页要独立，标题要有冲击力
5. **节奏控制**: 避免前松后紧或前紧后松，保持均衡叙述
6. **易于理解**: 标题简洁有力（6-10字），副标题补充说明

# 页面布局技巧
✅ **封面页**：标题要有吸引力，体现价值或成果
✅ **目录页**：章节名称要体现逻辑递进关系
✅ **开篇页**：快速建立context，说明背景和目标
✅ **成果页**：用数据说话，突出亮点和突破
✅ **过程页**：展示方法论和能力建设
✅ **问题页**：客观分析，体现问题意识和改进决心
✅ **规划页**：给出明确的行动计划和时间表
✅ **总结页**：回顾关键结论，强化核心价值

# 输出格式要求
- 必须返回有效的JSON格式
- outline数组长度必须等于目标页数
- page字段从1开始连续编号
- template字段只能是: cover/toc/content/chart/summary/thanks
- priority字段标注页面优先级
- content_brief要体现该页的核心价值和逻辑定位

# 质量标准
✅ **完整的故事线**：读完所有标题，能理解整个报告的逻辑
✅ **清晰的价值主线**：成果、能力、问题、改进一目了然
✅ **合理的详略分配**：重点章节有充分展开空间
✅ **流畅的页面过渡**：每页之间有自然的承接关系

# 禁止事项
❌ 违反页数要求（增加或减少页数）
❌ 平铺直叙，缺少逻辑主线
❌ 把重要内容挤在一页，次要内容却占多页
❌ 页面标题没有信息量（如"数据统计""工作详情"）
❌ 缺少价值总结和问题分析环节

重要提醒: 如果用户要求生成3页，你就生成恰好3页；要求15页，就生成恰好15页。不要自作主张增加或减少页数！"""

    def _parse_outline_result(self, outline_result: str, expected_count: int) -> Dict[str, Any]:
        """解析LLM返回的大纲结果"""
        try:
            # 提取JSON
            json_match = re.search(r'\{[\s\S]*\}', outline_result)
            if json_match:
                result = json.loads(json_match.group())

                outline = result.get("outline", [])

                # 验证和修正
                if len(outline) != expected_count:
                    logger.warning(
                        f"Outline count mismatch: expected {expected_count}, got {len(outline)}",
                        agent_name="SlideOutliner"
                    )

                    # 强制修正：如果LLM生成的页数超过预期，截断到预期页数
                    if len(outline) > expected_count:
                        logger.info(
                            f"Truncating outline from {len(outline)} to {expected_count} pages",
                            agent_name="SlideOutliner"
                        )
                        outline = outline[:expected_count]
                    # 如果LLM生成的页数少于预期，补充默认页面
                    elif len(outline) < expected_count:
                        logger.info(
                            f"Padding outline from {len(outline)} to {expected_count} pages",
                            agent_name="SlideOutliner"
                        )
                        for i in range(len(outline) + 1, expected_count + 1):
                            outline.append({
                                "page": i,
                                "title": f"内容页 {i}",
                                "subtitle": "",
                                "content_brief": "补充内容页",
                                "template": "content",
                                "template_name": "内容页",
                                "data_requirements": [],
                                "priority": "low"
                            })

                # 确保page字段连续
                for i, slide in enumerate(outline, start=1):
                    slide["page"] = i

                return {"outline": outline}
            else:
                logger.warning("No JSON found in outline result", agent_name="SlideOutliner")
                return self._get_default_outline_structure(expected_count)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse outline result: {str(e)}", agent_name="SlideOutliner")
            return self._get_default_outline_structure(expected_count)

    def _calculate_creation_order(self, outline: List[Dict[str, Any]]) -> Dict[str, List[int]]:
        """
        计算幻灯片生成顺序

        规则:
        1. 封面、目录、第一个内容页必须串行生成(建立模板)
        2. 其余内容页可以并行生成
        """
        serial_pages = []
        parallel_pages = []

        template_first_occurrence = {}

        for slide in outline:
            page_num = slide["page"]
            template = slide["template"]

            # 记录每种模板的首次出现
            if template not in template_first_occurrence:
                template_first_occurrence[template] = page_num
                serial_pages.append(page_num)
            else:
                parallel_pages.append(page_num)

        return {
            "serial": sorted(serial_pages),
            "parallel": sorted(parallel_pages)
        }

    def _get_template_requirements(self, outline: List[Dict[str, Any]]) -> Dict[str, int]:
        """统计需要的模板类型"""
        template_count = {}

        for slide in outline:
            template = slide["template"]
            template_count[template] = template_count.get(template, 0) + 1

        return template_count

    def _get_default_outline(self, slide_count: int) -> Dict[str, Any]:
        """返回默认的大纲结构"""
        outline_structure = self._get_default_outline_structure(slide_count)

        return {
            "outline": outline_structure["outline"],
            "creation_order": self._calculate_creation_order(outline_structure["outline"]),
            "template_requirements": self._get_template_requirements(outline_structure["outline"]),
            "total_slides": len(outline_structure["outline"]),
            "metadata": {
                "task_brief": "默认大纲",
                "created_time": datetime.now().isoformat(),
                "status": "default"
            }
        }

    def _get_default_outline_structure(self, slide_count: int) -> Dict[str, Any]:
        """生成默认的大纲结构"""
        outline = []

        # 第1页: 封面
        outline.append({
            "page": 1,
            "title": "报告标题",
            "subtitle": "副标题",
            "content_brief": "封面页",
            "template": "cover",
            "template_name": "封面页",
            "data_requirements": ["标题", "时间", "汇报人"],
            "priority": "high"
        })

        # 第2页: 目录
        outline.append({
            "page": 2,
            "title": "目录",
            "subtitle": "",
            "content_brief": "目录页",
            "template": "toc",
            "template_name": "目录页",
            "data_requirements": ["章节列表"],
            "priority": "high"
        })

        # 第3到倒数第2页: 内容页
        for i in range(3, slide_count):
            outline.append({
                "page": i,
                "title": f"内容页 {i-2}",
                "subtitle": "",
                "content_brief": "内容详情",
                "template": "content",
                "template_name": "内容页",
                "data_requirements": ["内容"],
                "priority": "medium"
            })

        # 最后一页: 致谢
        outline.append({
            "page": slide_count,
            "title": "致谢",
            "subtitle": "",
            "content_brief": "致谢页",
            "template": "thanks",
            "template_name": "致谢页",
            "data_requirements": ["感谢语"],
            "priority": "low"
        })

        return {"outline": outline}

    def get_page_info(self, outline: Dict[str, Any], page_number: int) -> Optional[Dict[str, Any]]:
        """获取指定页面的信息"""
        for slide in outline.get("outline", []):
            if slide["page"] == page_number:
                return slide
        return None

    def get_pages_by_template(self, outline: Dict[str, Any], template: str) -> List[Dict[str, Any]]:
        """获取指定模板类型的所有页面"""
        return [
            slide for slide in outline.get("outline", [])
            if slide["template"] == template
        ]
