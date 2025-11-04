"""
Slide Generator Tool
内容生成工具 - 生成单个幻灯片的HTML内容
"""

import json
import re
import math
from typing import Dict, Any, Optional
from datetime import datetime
from ..utils.config import get_config
from ..utils.logger import get_logger
from ..utils.llm_config import generate_system_response
from .charts.chart_processor import ChartProcessor

logger = get_logger(__name__)


class SlideGeneratorTool:
    """幻灯片内容生成工具"""

    def __init__(self):
        """初始化内容生成工具"""
        self.config = get_config().get_tool_config("content_generator")
        self.enabled = self.config.get("enabled", True)
        self.llm_model = self.config.get("llm_model", "claude-3-5-sonnet-20241022")
        self.max_retries = self.config.get("max_retries", 2)

        # 基础模板
        self.base_template = self._load_base_template()

        # 模板约束
        self.template_constraints = self._load_template_constraints()
        
        # 图表处理器
        self.chart_processor = ChartProcessor()

        logger.info("SlideGeneratorTool initialized", agent_name="SlideGenerator")

    def generate_slide(
        self,
        page_info: Dict[str, Any],
        template_cache: Optional[Dict[str, str]],
        extracted_data: Dict[str, Any],
        user_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        生成单个幻灯片的HTML内容

        Args:
            page_info: 页面信息(来自outline)
            template_cache: 已生成的模板缓存(用于参考)
            extracted_data: 提取的文档数据
            user_requirements: 用户的特殊要求或优化需求（可选）

        Returns:
            Dict包含:
            - html_content: 生成的HTML
            - page_number: 页码
            - template: 模板类型
            - measured_height: 测量高度
            - generation_time: 生成时间
        """
        page_num = page_info["page"]
        template_type = page_info["template"]

        logger.info(
            f"Generating slide {page_num} with template '{template_type}'",
            agent_name="SlideGenerator"
        )

        if not self.enabled:
            logger.warning("SlideGenerator is disabled", agent_name="SlideGenerator")
            return self._get_default_slide(page_info)

        try:
            # 预处理数据：进行内容密度控制
            controlled_data = self._control_content_density(
                page_info,
                extracted_data,
                template_type
            )
            
            # 构建生成提示词
            generation_prompt = self._build_generation_prompt(
                page_info,
                template_cache,
                controlled_data,
                user_requirements
            )

            logger.info(f"generation_prompt length: {len(generation_prompt)} chars", agent_name="SlideGenerator")

            # 调用LLM生成HTML - 优化参数以提高质量和稳定性
            html_result = generate_system_response(
                system_prompt=self._get_system_prompt(template_type),
                user_message=generation_prompt,
                temperature=0.5,  # 降低温度到0.5，提高一致性和质量
                max_tokens=10000  # 增加token限制，确保完整输出
            )

            # 提取HTML内容
            html_content = self._extract_html(html_result)

            # 验证HTML
            if not self._validate_html(html_content):
                logger.warning(f"Generated HTML for page {page_num} failed validation", agent_name="SlideGenerator")
                html_content = self._fix_html(html_content)

            # 新功能：处理图表占位符
            if template_type == "chart":
                logger.info(f"Processing chart placeholders for page {page_num}", agent_name="SlideGenerator")
                
                # 验证占位符格式
                validation_result = self.chart_processor.validate_placeholders(html_content)
                if not validation_result["valid"]:
                    logger.warning(
                        f"Chart placeholder validation issues: {validation_result['errors']}", 
                        agent_name="SlideGenerator"
                    )
                
                # 替换占位符为实际图表代码
                html_content = self.chart_processor.process_html(html_content)
                logger.info(f"Replaced {validation_result['count']} chart placeholder(s)", agent_name="SlideGenerator")

            result = {
                "html_content": html_content,
                "page_number": page_num,
                "template": template_type,
                "template_name": page_info.get("template_name", "未知"),
                "title": page_info.get("title", ""),
                "measured_height": 1080,  # 固定高度
                "generation_time": datetime.now().isoformat(),
                "status": "success"
            }

            logger.info(f"Slide {page_num} generated successfully", agent_name="SlideGenerator")

            return result

        except Exception as e:
            logger.error(f"Slide {page_num} generation failed: {str(e)}", agent_name="SlideGenerator")
            return self._get_default_slide(page_info)

    async def generate_slide_async(
        self,
        page_info: Dict[str, Any],
        template_cache: Optional[Dict[str, str]],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        异步生成幻灯片(用于并行生成)

        注: 当前使用同步实现,未来可改为真正的异步调用
        """
        return self.generate_slide(page_info, template_cache, extracted_data)

    def _build_generation_prompt(
        self,
        page_info: Dict[str, Any],
        template_cache: Optional[Dict[str, str]],
        extracted_data: Dict[str, Any],
        user_requirements: Optional[str] = None
    ) -> str:
        """构建内容生成提示词"""
        page_num = page_info["page"]
        title = page_info.get("title", "")
        subtitle = page_info.get("subtitle", "")
        content_brief = page_info.get("content_brief", "")
        data_requirements = page_info.get("data_requirements", [])
        template_type = page_info["template"]

        # 根据模板类型决定需要提取的数据
        detailed_content = extracted_data.get("detailed_content", {})

        # 特殊页面类型的数据提取规则
        if template_type == "toc":
            # 目录页：只需要章节列表（从outline中提取，不需要detailed_content和统计数据）
            relevant_descriptions = {}
            relevant_statistics = {}
        elif template_type in ["cover", "thanks"]:
            # 封面页/致谢页：只需要元数据（标题、时间等），不需要detailed_content
            relevant_descriptions = {}
            relevant_statistics = self._extract_relevant_data(data_requirements, extracted_data)
        else:
            # 内容页/图表页：需要完整的描述性内容和统计数据
            relevant_descriptions = self._extract_relevant_descriptions(data_requirements, detailed_content)
            relevant_statistics = self._extract_relevant_data(data_requirements, extracted_data)

        # 查找同类型模板作为参考（优先使用参考模板，避免重复提供基础模板）
        reference_template_section = ""
        has_reference = False

        template_cache = False
        if template_cache:
            # 查找同类型的已生成模板
            for key, cached_result in template_cache.items():
                if isinstance(cached_result, dict) and cached_result.get('template') == template_type:
                    # 找到同类型模板，使用它作为参考
                    cached_html = cached_result.get('html_content', '')
                    if cached_html:
                        reference_template_section = f"""
【参考模板（同类型：{template_type}）】
{cached_html}

⚠️ 请参考上述模板的HTML结构和CSS样式，保持一致性。只需替换内容部分。
"""
                        has_reference = True
                        break

        # 如果没有参考模板，使用基础模板
        base_template_section = ""
        if not has_reference:
            base_template_section = f"""
【基础模板】
{self.base_template}

【约束条件】
这些规则必须被严格遵守，不得有任何例外：

*   **页面尺寸**: 固定为 `1920px` x `1080px`。
*   **布局结构**: 保持单栏布局，垂直方向为三个固定区域：顶部条(`.top-bar`)、内容区(`.content-section`)、页码(`.page-number`)。
    *   **内容区限制**: `.content-section` 内部必须是单栏布局，最多包含3个容器，避免内容过于复杂。
*   **样式一致性**: 所有CSS样式、颜色（如 `primary-color`）、字体大小（如 `h1`为48px）必须与模板完全一致。
*   **页码**: 必须保留 `<div class="page-number">X</div>` 结构，并将 `X` 替换为正确的页码。
*   **禁止项**:
    *   禁止创建或使用任何自定义的CSS类名。
    *   禁止使用 `<span>` 标签。
    *   禁止内容溢出容器。
    *   禁止使用小于 `14px` 的字体。
"""

        # 添加用户特殊要求
        user_requirements_section = ""
        if user_requirements:
            user_requirements_section = f"""
【用户特殊要求】
{user_requirements}
⚠️ 请务必在生成内容时满足上述用户要求！
"""

        # 图表指导（使用新的占位符方式）
        chart_guidance = ""
        if page_info["template"] == "chart":
            chart_guidance = self._get_chart_placeholder_guidance()

        prompt = f"""
# 任务：生成第{page_num}页HTML幻灯片

## 基本信息
- 页码：{page_num}
- 标题：{title}
- 副标题：{subtitle}
- 简述：{content_brief}
- 模板：{template_type}

## 可用数据

### 描述性内容
{json.dumps(relevant_descriptions, ensure_ascii=False, indent=2) if relevant_descriptions else "无可用描述性内容"}

### 统计数据
{json.dumps(relevant_statistics, ensure_ascii=False, indent=2) if relevant_statistics else "无可用统计数据"}
{chart_guidance}
{user_requirements_section}
{reference_template_section}
{base_template_section}

## 生成要求

### 核心约束（必须遵守）
1. **页面密度**：内容必须在单页内完整展示（1920x1080px）
   - 要点数：4-6个
   - 文字量：150-200字
   - 图表：0-1个（高≤400px）

2. **内容质量**：每个要点包含
   - 结论性小标题
   - 具体数据（精确数字）
   - 趋势分析（环比/同比）
   - 价值说明（业务意义）

3. **技术规范**
   - 完整HTML结构（DOCTYPE, html, head, body）
   - 单栏垂直布局
   - 使用模板CSS类（.data-card, .bullet-point）
   - 主色rgb(10,66,117)
   - 固定尺寸1920x1080px

### 内容示例
```
【监控效能持续提升】
• 日均处理日志589万条，同比增长35%
• 告警准确率85%，较上月提升20个百分点
• 误报下降显著，节省人工筛查时间40%
• 体现监控系统优化成效显著
```

### 数据选择原则
- 从上述数据中选择最关键的4-6项
- 优先选择有对比、有趋势、有价值的数据
- 每个数据都要配上分析说明

⚠️ 重要：直接输出完整HTML代码，不要markdown标记或额外说明
"""
        return prompt

    def _get_system_prompt(self, template_type: str) -> str:
        """获取智能化的系统提示词 - 平衡创造力与一致性"""
        base_prompt = self._get_base_system_prompt()
        specific_prompt = self._get_template_specific_prompt(template_type)
        
        return f"{base_prompt}\n\n{specific_prompt}"
    

    def _get_base_system_prompt(self) -> str:
        """获取基础系统提示词 - 精简版，聚焦核心要求"""
        return """# 角色
你是专业的商业PPT内容专家，专注于生成高质量、专业的幻灯片内容。

# 核心要求（按优先级）

## 1. 内容质量（最重要）
- 数据驱动：每个观点必须有具体数据支撑
- 深度分析：不仅展示数据，更要分析趋势、对比和价值
- 逻辑清晰：结论→数据→分析的完整链条
- 语言专业：使用精确数字和专业术语

## 2. 页面密度（关键）
⚠️ 必须确保内容在单页完整展示（1920x1080px）
- 核心要点：4-6个（最多）
- 正文字数：150-200字以内
- 图表数量：最多1-2个
- 数据项：选择最重要的6-8项展示

## 3. 技术规范
- 尺寸：1920x1080px
- 布局：单栏垂直，三段式（顶栏+内容+页码）
- 字体：h1=48px, h2/h3=28-36px, p=20-24px
- 主色：rgb(10,66,117)
- 结构：使用模板中的CSS类（.data-card, .bullet-point等）

## 4. 质量标准
✅ 有明确结论
✅ 数据完整准确
✅ 分析深入到位
✅ 布局清晰合理
✅ 内容适量不超页

❌ 避免：数据堆砌、内容过载、多列布局、缺少分析"""

    def _get_template_specific_prompt(self, template_type: str) -> str:
        """获取特定模板类型的提示词"""
        prompts = {
            "cover": self._get_cover_prompt(),
            "toc": self._get_toc_prompt(),
            "content": self._get_content_prompt(),
            "chart": self._get_content_prompt(),
            "summary": self._get_content_prompt(),
            "thanks": self._get_content_prompt()
        }
        
        return prompts.get(template_type, prompts["content"])
    
    def _get_cover_prompt(self) -> str:
        """封面页专用提示词 - 简化版"""
        return """## 📋 封面页设计要点

### 三段布局
- 顶部(200px): Logo/装饰元素
- 中心(600px): 主标题+副标题
- 底部(280px): 汇报人/日期

### 内容要求
- 主标题: 48-64px，8-15字
- 副标题: 28-36px，15-30字
- 信息: 汇报人、部门、日期

### 示例结构
```html
<div class="hero-area">
  <h1>主标题</h1>
  <h2>副标题</h2>
</div>
<div class="info-area">
  <div>汇报人</div>
  <div>2024年1月</div>
</div>
```"""

    def _get_toc_prompt(self) -> str:
        """目录页专用提示词 - 简化版"""
        return """## 📑 目录页设计要点

### 布局模式
纵向列表（推荐，3-8个章节）：
```
01 章节一
02 章节二
03 章节三
```

### 样式要求
- 编号: 28-32px, 主色调
- 标题: 28-32px, 加粗
- 间距: 章节间充分留白

### 示例结构
```html
<div class="toc-item">
  <div class="toc-number">01</div>
  <h3>章节标题</h3>
</div>
```

### 内容限制
- 章节数: 3-8个
- 章节名: 4-8字"""

    def _get_content_prompt(self) -> str:
        """内容页专用提示词 - 优化版"""
        return """## 📄 内容页要点

### 密度控制
- 要点数：4-6个
- 文字量：150-200字
- 图表：0-1个（高≤400px）
- 高度：内容区≤900px

### 内容结构
每个要点应包含：
1. 结论性小标题
2. 核心数据（具体数字）
3. 趋势分析（环比/同比/对比）
4. 价值说明（业务意义）

### 示例
```
【监控能力显著提升】
• 日均处理日志589万条，同比增长35%
• 告警精准率85%，较上月提升20%
• 有效节省40%人工筛查时间
• 反映监控系统持续优化见效
```

### 技术要求
- 使用.data-card或.bullet-point类
- h1标题 + h3小标题 + p正文
- 单栏垂直布局
- 保持主色调rgb(10,66,117)

✅ 确保：结论清晰、数据准确、分析到位、不超页"""

    def _get_system_prompt_bak(self, template_type: str) -> str:
        """获取智能化的系统提示词 - 平衡创造力与一致性"""
        
        role_definitions = {
            "cover": """
# 🎨 角色：企业品牌设计师
你是专业的企业品牌设计师，专精于使用我们确认的设计系统创建高端PPT封面。
**严格遵循设计规范**：单栏布局、主色调rgb(10, 66, 117)、固定尺寸1920x1080。
**禁止事项**：绝对禁止使用hover效果、动画、自定义颜色。
""",
            "toc": """
# 📋 角色：信息架构师
你是信息架构专家，使用我们确认的设计系统创建清晰的目录页面。
**设计原则**：保持单栏垂直布局，使用.toc-item类，字体28px，主色调突出。
**严格禁止**：禁止添加hover效果、动画、交互元素，保持静态专业。
""",
            "content": """
# 📝 角色：内容呈现专家
你是内容呈现专家，擅长在我们确认的设计框架内优化信息展示。
**核心约束**：单栏垂直布局、.data-card组件、25px正文字体、主色调rgb(10, 66, 117)。
**内容密度控制**：每页严格限制4-6个要点，禁止信息过载。
""",
            "chart": """
# 📊 角色：专业数据分析师 + 图表配置专家
你是专业的数据分析师，擅长分析数据特征并生成结构化的图表配置。

## 核心能力
- **数据理解**：准确理解数据含义和关系
- **图表选择**：根据数据特征选择最适合的图表类型
- **配置生成**：生成结构化的JSON配置，而非手动编写SVG代码

## 工作流程
1. **分析数据**：理解数据的维度、数量、关系
2. **选择图表类型**：
   - 分类对比 → 柱状图(bar)
   - 趋势变化 → 折线图(line)
   - 占比关系 → 饼图(pie)
   - 单一指标 → 仪表盘(gauge)
   - 多维对比 → 雷达图(radar)
   - 精确数值 → 表格(table)
3. **生成占位符**：使用 `<!-- CHART_PLACEHOLDER: {...} -->` 格式

## 关键要求
⚠️ **禁止手动编写SVG或ECharts代码**
✅ **只需生成图表占位符，系统会自动渲染专业图表**
✅ **确保data中的数值与原始数据100%匹配**
✅ **每页最多1-2个图表，避免信息过载**

## 图表高度标准
- 仪表盘：350px
- 柱状图：400px
- 饼图：350px
- 折线图：400px
- 表格：根据行数调整（约300-400px）
""",
            "summary": """
# 🎯 角色：战略总结专家
你是战略总结专家，在我们确认的设计框架内创建有力的总结页面。
**设计要求**：使用大号字体强调要点，保持主色调统一，单栏垂直布局。
**重点控制**：每页不超过4个核心要点，突出关键结论。
""",
            "thanks": """
# 🤝 角色：品牌形象专家
你是品牌形象专家，使用我们确认的设计系统创建专业的致谢页面。
**设计准则**：简洁优雅，保持主色调和单栏布局的一致性。
**保持简洁**：禁止添加过多装饰元素，保持专业清爽。
"""
        }
        
        # 设计系统约束（适度放宽）
        design_principles = """
# 🎨 设计系统 - 平衡一致性与灵活性

## 基础约束（必须遵守）
- **页面尺寸**: 1920×1080px
- **主色调**: rgb(10, 66, 117)
- **布局结构**: 三段式（顶部条+内容区+页码）
- **字体规范**: h1(48px), h2(36px), p(25px)

## 灵活原则（允许适度调整）
- **组件样式**: 可适度调整padding、margin以适应内容
- **图表类型**: 根据数据特点选择最适合的图表
- **信息密度**: 每页4-8个要点，图表页可适当减少
- **装饰元素**: 允许适度的边框、阴影效果

## 图表质量标准
- **数据准确性**: 100%，必须与原始数据一致
- **可读性**: 包含坐标轴、图例、标签
- **专业性**: 符合商业图表标准
- **简洁性**: 避免过度复杂的视觉效果

## 禁止事项（精简版）
- ❌ 使用外部CDN依赖
- ❌ 多列布局（grid、flex水平）
- ❌ hover效果和动画
- ❌ 自定义颜色（除主色调外）
"""
        
        # 针对目录页添加特殊说明
        toc_instruction = ""
        if template_type == "toc":
            toc_instruction = """

## 目录页特殊要求
- 使用 .toc-item 类展示每个目录项
- 使用 .toc-number 类显示章节序号  
- 使用 .toc-title 类显示章节标题
- 确保目录项字体大小不小于28px
- 所有目录项垂直排列，保持单栏布局
- 章节序号使用主色调rgb(10, 66, 117)
"""
        
        return f"{role_definitions.get(template_type, role_definitions['content'])}\n{design_principles}{toc_instruction}"

    def _control_content_density(
        self,
        page_info: Dict[str, Any],
        extracted_data: Dict[str, Any],
        template_type: str
    ) -> Dict[str, Any]:
        """
        内容密度控制 - 根据模板类型限制数据量
        
        目的：防止生成过多内容导致单页无法完整展示
        """
        controlled_data = extracted_data.copy()
        
        # 根据模板类型设置数据上限
        data_limits = {
            "cover": {"key_data": 0, "detailed_content": 0},  # 封面页不需要详细数据
            "toc": {"key_data": 0, "detailed_content": 0},     # 目录页不需要详细数据
            "content": {"key_data": 6, "detailed_content": 4}, # 内容页限制数据
            "chart": {"key_data": 8, "detailed_content": 2},   # 图表页留空间给图表
            "summary": {"key_data": 4, "detailed_content": 3}, # 总结页精简
            "thanks": {"key_data": 0, "detailed_content": 0}   # 致谢页不需要详细数据
        }
        
        limits = data_limits.get(template_type, {"key_data": 6, "detailed_content": 4})
        
        # 限制key_data数量
        if "key_data" in controlled_data and isinstance(controlled_data["key_data"], dict):
            key_data = controlled_data["key_data"]
            if len(key_data) > limits["key_data"]:
                # 只保留前N项
                controlled_data["key_data"] = dict(list(key_data.items())[:limits["key_data"]])
                logger.info(
                    f"Limited key_data from {len(key_data)} to {limits['key_data']} items",
                    agent_name="SlideGenerator"
                )
        
        # 限制detailed_content数量
        if "detailed_content" in controlled_data and isinstance(controlled_data["detailed_content"], dict):
            detailed = controlled_data["detailed_content"]
            if len(detailed) > limits["detailed_content"]:
                controlled_data["detailed_content"] = dict(list(detailed.items())[:limits["detailed_content"]])
                logger.info(
                    f"Limited detailed_content from {len(detailed)} to {limits['detailed_content']} items",
                    agent_name="SlideGenerator"
                )
        
        return controlled_data

    def _extract_relevant_descriptions(
        self,
        data_requirements: list,
        detailed_content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """从 detailed_content 中提取相关的描述性内容"""
        if not detailed_content:
            return {}

        # 如果没有 data_requirements，返回前5项（限制数量）
        if not data_requirements:
            logger.info("No data_requirements, returning limited detailed_content", agent_name="SlideGenerator")
            return dict(list(detailed_content.items())[:5])

        relevant = {}

        # 递归搜索 detailed_content（因为它可能包含嵌套字典）
        def search_nested_dict(d: dict, prefix: str = ""):
            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key

                # 检查是否匹配 data_requirements（使用更宽松的匹配）
                matched = False
                for req in data_requirements:
                    req_lower = req.lower()
                    key_lower = key.lower()

                    # 尝试多种匹配方式
                    if (req_lower in key_lower or
                        key_lower in req_lower or
                        any(word in key_lower for word in req_lower.split()) or
                        any(word in req_lower for word in key_lower.split())):
                        matched = True
                        break

                if matched:
                    if isinstance(value, dict):
                        # 如果是嵌套字典，继续展开
                        search_nested_dict(value, full_key)
                    else:
                        relevant[key] = value

        search_nested_dict(detailed_content)

        # 如果没有匹配到任何内容，返回前5项作为兜底
        if not relevant:
            logger.warning(
                f"No descriptions matched for requirements: {data_requirements}, returning limited detailed_content",
                agent_name="SlideGenerator"
            )
            return dict(list(detailed_content.items())[:5])

        # 即使匹配到了，也要限制数量，最多返回8项
        if len(relevant) > 8:
            relevant = dict(list(relevant.items())[:8])
            logger.info(f"Limited relevant descriptions to 8 items", agent_name="SlideGenerator")

        return relevant

    def _extract_relevant_data(
        self,
        data_requirements: list,
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """提取相关的统计数据（key_data 和 metrics）"""
        relevant = {}

        key_data = extracted_data.get("key_data", {})
        metrics = extracted_data.get("metrics", {})

        # 如果没有数据要求，返回前10项 key_data
        if not data_requirements:
            return dict(list(key_data.items())[:10])

        # 根据data_requirements提取数据
        for req in data_requirements:
            req_lower = req.lower()

            # 1. 搜索 key_data（数字统计）
            for key, value in key_data.items():
                if req_lower in key.lower() or key.lower() in req_lower:
                    relevant[key] = value

            # 2. 搜索 metrics（纯数值）
            for key, value in metrics.items():
                if req_lower in key.lower() or key.lower() in req_lower:
                    relevant[key] = value

        # 如果没找到相关数据：
        # - 对于元数据类需求（标题、时间、人员等），返回空字典，避免提供无关数据
        # - 对于统计数据类需求，返回部分 key_data 作为兜底
        if not relevant:
            metadata_keywords = ['标题', '时间', '日期', '汇报', '单位', '作者', '联系', '邮箱']
            is_metadata_request = any(keyword in ''.join(data_requirements) for keyword in metadata_keywords)

            if is_metadata_request:
                # 元数据类需求，找不到就返回空，不要用无关数据填充
                return {}
            else:
                # 统计数据类需求，返回前10项作为兜底
                return dict(list(key_data.items())[:10])

        return relevant

    def _extract_html(self, llm_output: str) -> str:
        """从LLM输出中提取HTML代码"""
        # 移除markdown代码块标记
        html = re.sub(r'```html\s*', '', llm_output)
        html = re.sub(r'```\s*$', '', html)

        # 提取<!DOCTYPE html>到</html>之间的内容
        match = re.search(r'<!DOCTYPE html>.*?</html>', html, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group()

        # 如果没有DOCTYPE,尝试提取<html>到</html>
        match = re.search(r'<html.*?</html>', html, re.DOTALL | re.IGNORECASE)
        if match:
            return '<!DOCTYPE html>\n' + match.group()

        # 返回原始内容
        return html.strip()

    def _validate_html(self, html_content: str) -> bool:
        """验证HTML内容"""
        required_elements = [
            '<!DOCTYPE html>',
            '<html',
            '</html>',
            '<head>',
            '</head>',
            '<body>',
            '</body>',
            'slide-container',
            'page-number'
        ]

        for element in required_elements:
            if element not in html_content:
                logger.warning(f"HTML validation failed: missing '{element}'", agent_name="SlideGenerator")
                return False

        return True

    def _fix_html(self, html_content: str) -> str:
        """修复HTML内容"""
        # 确保有DOCTYPE
        if '<!DOCTYPE html>' not in html_content:
            html_content = '<!DOCTYPE html>\n' + html_content

        # 其他修复逻辑...

        return html_content

    def _load_base_template(self) -> str:
        """加载基础模板 - 使用本地资源，优化内容显示"""
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta content="width=device-width, initial-scale=1.0" name="viewport"/>
<title>模板PPT</title>
<link href="https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css" rel="stylesheet"/>
<link href="https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.4.0/css/all.min.css" rel="stylesheet"/>
<style>
  /* 基础样式定义 - 必须遵守 */
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body, html { margin: 0; padding: 0; width: 1920px; height: 1080px; overflow: hidden; }
  .slide-container { width: 1920px; height: 1080px; background-color: white; position: relative; display: flex; flex-direction: column; overflow: hidden; }
  .content-section { 
    flex: 1; 
    padding: 40px 80px 60px 80px; 
    display: flex; 
    flex-direction: column;
    max-height: calc(1080px - 10px - 60px);  /* 减去顶部条和底部空间 */
    overflow: hidden;  /* 防止内容溢出 */
  }
  .page-number { position: absolute; bottom: 30px; right: 50px; font-size: 14px; color: #666; z-index: 100; }
  .primary-color { color: rgb(10, 66, 117); }
  .primary-bg { background-color: rgb(10, 66, 117); }
  .top-bar { height: 10px; width: 100%; background-color: rgb(10, 66, 117); flex-shrink: 0; }
  h1 { font-size: 48px; font-weight: 700; color: rgb(10, 66, 117); margin-bottom: 16px; line-height: 1.2; }
  h2 { font-size: 36px; font-weight: 600; color: rgb(10, 66, 117); margin-bottom: 12px; line-height: 1.3; }
  h3 { font-size: 28px; font-weight: 600; color: rgb(10, 66, 117); margin-bottom: 12px; line-height: 1.3; }
  p { font-size: 22px; color: #333; line-height: 1.5; margin-bottom: 10px; }
  .data-card { 
    border-left: 4px solid rgb(10, 66, 117); 
    padding: 12px 16px; 
    background-color: rgba(10, 66, 117, 0.03); 
    border-radius: 6px; 
    margin-bottom: 14px; 
  }
  .stat-card { 
    background-color: rgba(10, 66, 117, 0.08); 
    border-radius: 6px; 
    padding: 12px 16px; 
    border-left: 4px solid rgb(10, 66, 117); 
    margin-bottom: 14px; 
  }
  .bullet-point { display: flex; align-items: flex-start; margin-bottom: 8px; font-size: 22px; line-height: 1.5; }
  .bullet-icon { color: rgb(10, 66, 117); margin-right: 10px; min-width: 20px; margin-top: 2px; }
  .toc-item { display: flex; align-items: center; margin-bottom: 16px; font-size: 28px; color: #333; }
  .toc-number { color: rgb(10, 66, 117); font-weight: 600; margin-right: 15px; min-width: 40px; }
  .toc-title { flex: 1; }
  
  /* 图表容器优化 */
  .chart-container { margin-bottom: 16px; position: relative; max-height: 400px; }
  .chart-container h3 { font-size: 28px; color: rgb(10, 66, 117); margin-bottom: 8px; }
  
  /* 内容区域优化 - 确保不会溢出 */
  .content-section > * { flex-shrink: 0; }
  .mb-4 { margin-bottom: 16px; }
  .mb-6 { margin-bottom: 20px; }
</style>
</head>
<body>
<div class="slide-container">
  <div class="top-bar"></div>
  <div class="content-section">
    <!-- 标题区域 -->
    <div class="mb-4">
      <h1>标题占位</h1>
      <h2 class="text-gray-600">副标题占位，可选</h2>
      <div class="w-20 h-1 primary-bg"></div>
    </div>

    <!-- 内容区域：正文使用p标签，单栏布局 -->
    <div>
      <p>内容占位</p>
    </div>
  </div>
  <div class="page-number">1</div>
</div>
</body>
</html>"""

    def _load_template_constraints(self) -> str:
        """加载模板约束"""
        return """### 核心硬性约束:
1. **页面尺寸**: 必须固定为1920x1080像素
2. **内容区高度**: 最多1010px（1080-10顶部-60底部）
3. **样式保持**: 所有CSS样式、颜色、字体大小必须与模板一致
4. **页码格式**: <div class="page-number">X</div>必须保留
5. **布局结构**: 单栏布局,垂直方向为：顶部条+内容区+页码
6. **字体规范**: 标题48px, 副标题28-36px, 正文22px, 最小14px

### 内容密度控制（关键）:
1. **核心要点**: 每页最多4-6个
2. **总文字量**: 正文不超过200字
3. **数据项**: 不超过8个关键数据
4. **图表**: 最多1-2个，单个高度≤400px
5. **列表项**: 最多6个

### 高度预估（确保不超页）:
- 标题区: 约120px (h1+h2+分隔线)
- 每个要点: 约60-80px
- 每个图表: 指定高度+标题(约420px)
- 安全边距: 留60px底部空间

### 禁止事项:
1. 禁止内容超出内容区高度
2. 禁止多列布局
3. 禁止使用小于14px的字体
4. 禁止堆叠过多元素"""

    def _get_default_slide(self, page_info: Dict[str, Any]) -> Dict[str, Any]:
        """返回默认幻灯片"""
        page_num = page_info["page"]
        title = page_info.get("title", "标题")

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
  body, html {{ margin: 0; padding: 0; width: 1920px; height: 1080px; }}
  .slide-container {{ width: 1920px; height: 1080px; background-color: white; display: flex; align-items: center; justify-content: center; }}
  .page-number {{ position: absolute; bottom: 30px; right: 50px; font-size: 14px; color: #666; }}
  h1 {{ font-size: 48px; color: rgb(10, 66, 117); }}
</style>
</head>
<body>
<div class="slide-container">
  <h1>{title}</h1>
  <div class="page-number">{page_num}</div>
</div>
</body>
</html>"""

        return {
            "html_content": html_content,
            "page_number": page_num,
            "template": page_info["template"],
            "template_name": page_info.get("template_name", ""),
            "title": title,
            "measured_height": 1080,
            "generation_time": datetime.now().isoformat(),
            "status": "default"
        }

    def _get_chart_placeholder_guidance(self) -> str:
        """获取图表占位符使用指导 - 精简版"""
        return """

# 📊 图表生成指南

⚠️ **重要**：使用图表占位符，系统自动生成专业ECharts图表，禁止手写SVG！

## 占位符格式
```html
<!-- CHART_PLACEHOLDER: {"chart_type": "类型", "title": "标题", "height": 高度, "data": {...}} -->
```

## 常用图表类型

### 柱状图 (bar) - 用于对比
```html
<!-- CHART_PLACEHOLDER: {
  "chart_type": "bar",
  "title": "季度销售对比",
  "height": 400,
  "data": {
    "labels": ["Q1", "Q2", "Q3", "Q4"],
    "series": [{"name": "销售额", "data": [120, 150, 180, 200]}]
  },
  "options": {"y_axis_name": "销售额", "unit": "万元"}
} -->
```

### 饼图 (pie) - 用于占比
```html
<!-- CHART_PLACEHOLDER: {
  "chart_type": "pie",
  "title": "市场份额",
  "height": 350,
  "data": {
    "labels": ["产品A", "产品B", "产品C"],
    "series": [{"name": "份额", "data": [35, 28, 22]}]
  }
} -->
```

### 折线图 (line) - 用于趋势
```html
<!-- CHART_PLACEHOLDER: {
  "chart_type": "line",
  "title": "增长趋势",
  "height": 400,
  "data": {
    "labels": ["1月", "2月", "3月", "4月", "5月"],
    "series": [{"name": "用户数", "data": [100, 120, 150, 180, 220]}]
  }
} -->
```

### 仪表盘 (gauge) - 用于单一指标
```html
<!-- CHART_PLACEHOLDER: {
  "chart_type": "gauge",
  "title": "完成率",
  "height": 350,
  "data": {"value": 75, "max_value": 100},
  "options": {"unit": "%"}
} -->
```

## 关键要求
1. 数据必须与原始数据100%一致
2. 每页最多1-2个图表
3. 图表高度：350-400px
4. 在合适位置插入占位符注释

## 示例结构
```html
<div class="content-section">
  <h1>数据分析</h1>
  <p>核心观点...</p>
  <!-- CHART_PLACEHOLDER: {...} -->
  <p>结论说明...</p>
</div>
```
"""

    def _analyze_chart_data(self, extracted_data: Dict[str, Any], page_info: Dict[str, Any]) -> str:
        """分析图表数据，提供专业建议"""
        if page_info["template"] != "chart":
            return ""
        
        # 提取数值数据
        numeric_data = self._extract_numeric_data(extracted_data)
        
        # 数据特征分析
        data_characteristics = self._analyze_data_characteristics(numeric_data)
        
        # 推荐图表类型
        recommended_charts = self._recommend_chart_types(data_characteristics)
        
        return f"""
# 📈 图表数据分析
## 数据特征
{data_characteristics}

## 推荐图表类型
{recommended_charts}

## 数据准确性要求
- 所有百分比必须精确计算
- 图表角度/比例必须与数据严格匹配
- 数值标签必须与原始数据一致
"""

    def _provide_chart_design_guidance(self, page_info: Dict[str, Any], chart_analysis: str) -> str:
        """提供图表设计指导"""
        if page_info["template"] != "chart":
            return ""
        
        return f"""
# 🎨 图表设计指导

## 仪表盘设计（如有百分比数据）
```html
<!-- 使用精确的弧线计算，高度350px -->
<svg width="100%" height="350" viewBox="0 0 400 350">
  <g transform="translate(200, 175)">
    <!-- 背景弧线 -->
    <path d="M -80 0 A 80 80 0 0 1 80 0" stroke="#e5e7eb" stroke-width="15" fill="none"/>
    <!-- 进度弧线：角度 = (百分比/100) * 180 -->
    <path d="M -80 0 A 80 80 0 0 1 [计算坐标]" stroke="rgb(10, 66, 117)" stroke-width="15" fill="none"/>
    <!-- 刻度线 -->
    <text x="-80" y="20" text-anchor="middle" font-size="12" fill="#666">0%</text>
    <text x="0" y="-90" text-anchor="middle" font-size="12" fill="#666">100%</text>
    <text x="80" y="20" text-anchor="middle" font-size="12" fill="#666">50%</text>
    <!-- 数值显示 -->
    <text x="0" y="40" text-anchor="middle" font-size="32" font-weight="bold" fill="rgb(10, 66, 117)">[百分比]</text>
  </g>
</svg>
```

## 柱状图设计（如有分类数据）
```html
<!-- 包含坐标轴和网格线，高度400px -->
<svg width="100%" height="400" viewBox="0 0 600 400">
  <!-- Y轴 -->
  <line x1="80" y1="30" x2="80" y2="350" stroke="#ccc" stroke-width="1"/>
  <!-- X轴 -->
  <line x1="80" y1="350" x2="550" y2="350" stroke="#ccc" stroke-width="1"/>
  <!-- 网格线 -->
  <line x1="80" y1="30" x2="550" y2="30" stroke="#f0f0f0" stroke-width="1"/>
  <line x1="80" y1="102.5" x2="550" y2="102.5" stroke="#f0f0f0" stroke-width="1"/>
  <line x1="80" y1="175" x2="550" y2="175" stroke="#f0f0f0" stroke-width="1"/>
  <line x1="80" y1="247.5" x2="550" y2="247.5" stroke="#f0f0f0" stroke-width="1"/>
  
  <!-- Y轴刻度标签 -->
  <text x="70" y="35" text-anchor="end" font-size="12" fill="#666">最大值</text>
  <text x="70" y="107" text-anchor="end" font-size="12" fill="#666">75%</text>
  <text x="70" y="180" text-anchor="end" font-size="12" fill="#666">50%</text>
  <text x="70" y="252" text-anchor="end" font-size="12" fill="#666">25%</text>
  <text x="70" y="355" text-anchor="end" font-size="12" fill="#666">0%</text>
  
  <!-- 柱状图 -->
  <rect x="[x]" y="[y]" width="[width]" height="[height]" fill="rgb(10, 66, 117)"/>
  <!-- 数值标签 -->
  <text x="[center]" y="[y-5]" text-anchor="middle" font-size="14" font-weight="bold" fill="#333">[数值]</text>
  <!-- X轴标签 -->
  <text x="[x_center]" y="370" text-anchor="middle" font-size="12" fill="#666">[标签]</text>
</svg>
```

## 布局要求
- **单栏垂直布局**：图表从上到下排列
- **紧凑间距**：使用mb-4或mb-6，避免过多空白
- **信息密度控制**：每页最多2个图表，充分利用空间
- **标题清晰**：每个图表都有明确的标题和说明
- **空间利用**：图表应该占据足够的视觉空间，避免页面空旷
"""

    def _extract_numeric_data(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取数值数据用于图表分析"""
        numeric_data = {}
        
        # 从key_data中提取数值
        key_data = extracted_data.get("key_data", {})
        for key, value in key_data.items():
            if isinstance(value, (int, float)):
                numeric_data[key] = value
        
        # 从metrics中提取数值
        metrics = extracted_data.get("metrics", {})
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                numeric_data[key] = value
        
        return numeric_data

    def _analyze_data_characteristics(self, numeric_data: Dict[str, Any]) -> str:
        """分析数据特征"""
        if not numeric_data:
            return "无数值数据"
        
        characteristics = []
        
        # 数据量分析
        data_count = len(numeric_data)
        if data_count <= 3:
            characteristics.append(f"数据量少（{data_count}个），适合饼图或仪表盘")
        elif data_count <= 8:
            characteristics.append(f"数据量适中（{data_count}个），适合柱状图或折线图")
        else:
            characteristics.append(f"数据量较多（{data_count}个），建议筛选关键数据展示")
        
        # 数值范围分析
        values = list(numeric_data.values())
        if values:
            min_val, max_val = min(values), max(values)
            if max_val > 1000:
                characteristics.append(f"数值范围较大（{min_val}-{max_val}），需要合理缩放")
            elif max_val < 100:
                characteristics.append(f"数值为百分比值（{min_val}-{max_val}%），适合仪表盘展示")
        
        return "\n".join(f"- {char}" for char in characteristics)

    def _recommend_chart_types(self, data_characteristics: str) -> str:
        """推荐图表类型"""
        recommendations = []
        
        if "数据量少" in data_characteristics:
            recommendations.append("- **饼图**：适合展示占比关系")
            recommendations.append("- **仪表盘**：适合展示单一指标")
        
        if "数据量适中" in data_characteristics:
            recommendations.append("- **柱状图**：适合分类数据对比")
            recommendations.append("- **折线图**：适合趋势展示")
        
        if "百分比值" in data_characteristics:
            recommendations.append("- **仪表盘**：直观展示完成率或占比")
        
        if not recommendations:
            recommendations.append("- **柱状图**：通用图表类型")
            recommendations.append("- **数据卡片**：简洁展示关键指标")
        
        return "\n".join(recommendations)

    def _calculate_gauge_coordinates(self, percentage: float) -> str:
        """计算仪表盘弧线坐标"""
        # 将百分比转换为弧度（0-180度）
        angle = (percentage / 100) * math.pi
        # 计算终点坐标
        x = 80 * math.cos(angle)
        y = 80 * math.sin(angle)
        return f"M -80 0 A 80 80 0 0 1 {x:.2f} {y:.2f}"

    def _calculate_bar_chart_dimensions(self, data_list: list, max_width: int = 60, max_height: int = 150) -> list:
        """计算柱状图尺寸"""
        if not data_list:
            return []
        
        # 提取数值并过滤非数字
        values = []
        for item in data_list:
            if isinstance(item, (int, float)):
                values.append(item)
            elif isinstance(item, str) and item.replace('.', '').replace('-', '').isdigit():
                values.append(float(item))
        
        if not values:
            return []
        
        max_value = max(values)
        if max_value == 0:
            max_value = 1  # 避免除零
        
        return [
            {
                'height': int((value / max_value) * max_height),
                'y': 200 - int((value / max_value) * max_height),
                'value': value
            }
            for value in values
        ]

    def _calculate_pie_chart_angles(self, data_dict: dict) -> list:
        """计算饼图角度"""
        if not data_dict:
            return []
        
        # 计算总和
        total = sum(data_dict.values())
        if total == 0:
            return []
        
        angles = []
        current_angle = 0
        
        for label, value in data_dict.items():
            percentage = (value / total) * 100
            # 计算扇形角度（0-360度）
            start_angle = current_angle
            end_angle = current_angle + (percentage / 100) * 360
            
            # 转换为弧度
            start_rad = (start_angle * math.pi) / 180
            end_rad = (end_angle * math.pi) / 180
            
            # 计算路径
            x1 = 80 * math.cos(start_rad)
            y1 = 80 * math.sin(start_rad)
            x2 = 80 * math.cos(end_rad)
            y2 = 80 * math.sin(end_rad)
            
            # 判断是否为大弧
            large_arc = 1 if (end_angle - start_angle) > 180 else 0
            
            path = f"M 0 0 L {x1:.2f} {y1:.2f} A 80 80 0 {large_arc} 1 {x2:.2f} {y2:.2f} Z"
            
            angles.append({
                'path': path,
                'percentage': percentage,
                'label': label,
                'value': value
            })
            
            current_angle = end_angle
        
        return angles

    # 阶段2.2: 数据准确性验证功能
    def _validate_chart_accuracy(self, html_content: str, original_data: Dict[str, Any]) -> bool:
        """验证图表数据准确性"""
        try:
            # 提取SVG中的数值
            svg_values = self._extract_svg_values(html_content)
            
            # 与原始数据对比
            accuracy_score = self._calculate_data_accuracy(svg_values, original_data)
            
            if accuracy_score < 0.95:  # 95%准确率要求
                logger.warning(f"Chart accuracy warning: {accuracy_score:.2%}", agent_name="SlideGenerator")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Chart accuracy validation failed: {str(e)}", agent_name="SlideGenerator")
            return True  # 验证失败时不阻止生成

    def _extract_svg_values(self, html_content: str) -> Dict[str, Any]:
        """从SVG中提取数值"""
        svg_values = {}
        
        # 提取text标签中的数值
        text_matches = re.findall(r'<text[^>]*>([^<]+)</text>', html_content)
        for text in text_matches:
            # 提取数字（包括小数和百分比）
            number_match = re.search(r'(\d+(?:\.\d+)?)%?', text.strip())
            if number_match:
                value = float(number_match.group(1))
                if '%' in text:
                    svg_values[f"percentage_{len(svg_values)}"] = value
                else:
                    svg_values[f"value_{len(svg_values)}"] = value
        
        # 提取rect的高度值（柱状图）
        rect_matches = re.findall(r'<rect[^>]*height="(\d+(?:\.\d+)?)"', html_content)
        for i, height in enumerate(rect_matches):
            svg_values[f"bar_height_{i}"] = float(height)
        
        return svg_values

    def _calculate_data_accuracy(self, svg_values: Dict[str, Any], original_data: Dict[str, Any]) -> float:
        """计算数据准确率"""
        if not svg_values or not original_data:
            return 1.0  # 没有数据时返回满分
        
        # 提取原始数值数据
        original_numeric = self._extract_numeric_data(original_data)
        
        if not original_numeric:
            return 1.0
        
        # 简单的数值匹配验证
        matches = 0
        total_comparisons = 0
        
        for svg_key, svg_value in svg_values.items():
            for orig_key, orig_value in original_numeric.items():
                total_comparisons += 1
                # 允许小的误差（±5%）
                if isinstance(svg_value, (int, float)) and isinstance(orig_value, (int, float)):
                    if abs(svg_value - orig_value) / max(abs(orig_value), 1) <= 0.05:
                        matches += 1
                        break
        
        return matches / total_comparisons if total_comparisons > 0 else 1.0

    def _optimize_chart_layout(self, html_content: str, template_type: str) -> str:
        """优化图表布局，确保充分利用空间"""
        if template_type != "chart":
            return html_content
        
        # 优化SVG尺寸
        html_content = re.sub(
            r'<svg width="100%" height="200"',
            '<svg width="100%" height="350"',
            html_content
        )
        
        html_content = re.sub(
            r'<svg width="100%" height="250"',
            '<svg width="100%" height="400"',
            html_content
        )
        
        # 优化间距
        html_content = re.sub(
            r'class="mb-8"',
            'class="mb-4"',
            html_content
        )
        
        html_content = re.sub(
            r'class="mb-6"',
            'class="mb-4"',
            html_content
        )
        
        return html_content
