"""
章节设计代理模块
负责根据确认的计划设计详细的章节结构和PPT页面规划
"""

import json
import uuid
from typing import Dict, Any, List
from ..utils.config import get_agent_config, get_agent_prompt
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response, generate_system_response_stream
from typing import Iterator
from ..graph.state import ExecutionStep, create_execution_step

logger = get_logger(__name__)


class ChapterDesignAgent:
    """章节设计代理 - 章节设计专家"""
    
    def __init__(self):
        """初始化章节设计代理"""
        self.config = get_agent_config("chapter_design")
        self.system_prompt = get_agent_prompt("chapter_design_agent")
        self.max_chapters = self.config.get("max_chapters", 20)
        self.max_slides_per_chapter = self.config.get("max_slides_per_chapter", 10)
        
        logger.info("章节设计代理初始化完成", agent_name="ChapterDesignAgent")
    
    def execute(self, state) -> Dict[str, Any]:
        """
        执行章节设计任务
        
        Args:
            state: 工作流状态
            
        Returns:
            章节设计结果字典
        """
        task_description = f"为用户请求设计详细章节结构: {state.user_request}"
        log_agent_start("ChapterDesignAgent", task_description)
        
        try:
            # 构建用户输入
            user_input = self._build_user_input(state)
            
            # 生成章节设计（使用流式输出）
            design_response = ""
            logger.info("开始生成章节设计（流式输出）...", agent_name="ChapterDesignAgent")
            
            for chunk in generate_system_response_stream(
                self.system_prompt,
                user_input,
                temperature=0.3  # 降低温度以获得更稳定的输出
            ):
                design_response += chunk
                # 可以在这里添加实时处理逻辑
                # 例如：logger.debug(f"收到流式响应块: {chunk}")
            
            logger.info("章节设计生成完成，开始解析...", agent_name="ChapterDesignAgent")
            
            # 解析章节设计响应
            design_data = self._parse_design_response(design_response)
            
            # 创建章节执行步骤
            chapter_execution_steps = self._create_chapter_execution_steps(design_data)
            
            # 构建结果
            result = {
                "chapter_design": design_data,
                "chapter_execution_steps": chapter_execution_steps,
                "design_summary": self._generate_design_summary(design_data),
                "total_chapters": len(design_data.get("chapters", [])),
                "total_slides": self._calculate_total_slides(design_data)
            }
            
            logger.info(f"章节设计完成，共生成 {len(design_data.get('chapters', []))} 个章节", agent_name="ChapterDesignAgent")
            log_agent_complete("ChapterDesignAgent", task_description, f"生成 {len(chapter_execution_steps)} 个执行步骤")
            
            return result
            
        except Exception as e:
            error_msg = f"章节设计失败: {str(e)}"
            logger.error(error_msg, agent_name="ChapterDesignAgent")
            raise Exception(error_msg)
    
    def _build_user_input(self, state) -> str:
        """构建用户输入"""
        user_input = f"""
用户请求: {state.user_request}

用户约束条件:
"""
        
        if state.user_constraints:
            for constraint in state.user_constraints:
                user_input += f"- {constraint}\n"
        else:
            user_input += "- 无特殊约束\n"
        
        user_input += f"""
已确认的计划信息:
- 报告标题: {state.plan.get('report_title', '未指定') if state.plan else '未指定'}
- 报告目标: {state.plan.get('report_objective', '未指定') if state.plan else '未指定'}

要求:
1. 基于已确认的计划，设计详细的章节结构
2. 每个章节根据复杂度可以生成多张HTML样式的PPT
3. 确定每个章节的PPT页数（1-{self.max_slides_per_chapter}页）
4. 为每个PPT页面设计具体内容
5. 最多生成 {self.max_chapters} 个章节
6. 章节之间要有逻辑性和连贯性

输出格式要求:
请以JSON格式输出章节设计，包含以下字段:
- design_title: 设计标题
- design_objective: 设计目标
- chapters: 章节列表（每个章节包含PPT页面设计）
- total_estimated_slides: 总预估幻灯片数
- design_notes: 设计备注

其中chapters字段应该是一个数组，每个元素包含：
- chapter_id: 章节ID，格式为 "chapter_001", "chapter_002" 等
- chapter_title: 章节标题
- chapter_objective: 章节目标
- slide_count: 该章节的PPT页数
- slides: PPT页面列表，每个页面包含：
  - slide_id: 页面ID，格式为 "slide_001_1", "slide_001_2" 等
  - slide_title: 页面标题
  - slide_content: 页面内容描述
  - content_type: 内容类型（标题页/内容页/图表页/总结页等）
  - estimated_duration: 预估展示时间（分钟）

重要提示：
1. 章节ID必须使用 "chapter_XXX" 格式，其中XXX是三位数字
2. 页面ID必须使用 "slide_XXX_Y" 格式，其中XXX是章节号，Y是页号
3. 根据章节复杂度合理分配PPT页数
4. 确保每个章节的内容完整且有价值
5. PPT页面设计要符合演示逻辑

请确保输出是有效的JSON格式。
"""
        
        return user_input
    
    def _parse_design_response(self, response: str) -> Dict[str, Any]:
        """解析设计响应"""
        try:
            # 尝试直接解析JSON
            design_data = json.loads(response)
            return design_data
            
        except json.JSONDecodeError:
            # 如果直接解析失败，尝试提取JSON部分
            try:
                # 查找JSON开始和结束位置
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = response[start_idx:end_idx]
                    design_data = json.loads(json_str)
                    return design_data
                else:
                    raise ValueError("响应中未找到有效的JSON格式")
                    
            except Exception as e:
                logger.warning(f"JSON解析失败，尝试文本解析: {str(e)}", agent_name="ChapterDesignAgent")
                # 如果JSON解析完全失败，使用文本解析作为备选
                return self._parse_text_response(response)
    
    def _parse_text_response(self, response: str) -> Dict[str, Any]:
        """解析文本响应（备选方案）"""
        lines = response.split('\n')
        design_data = {
            "design_title": "章节设计方案",
            "design_objective": "基于用户需求设计章节结构",
            "chapters": [],
            "total_estimated_slides": 0,
            "design_notes": "从文本响应解析生成"
        }
        
        current_chapter = None
        chapter_counter = 1
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 简单的文本解析逻辑
            if "章节" in line or "chapter" in line.lower():
                if current_chapter:
                    design_data["chapters"].append(current_chapter)
                
                current_chapter = {
                    "chapter_id": f"chapter_{chapter_counter:03d}",
                    "chapter_title": line.replace("章节", "").replace("Chapter", "").strip(),
                    "chapter_objective": f"完成{line}的相关内容",
                    "slide_count": 1,
                    "slides": [{
                        "slide_id": f"slide_{chapter_counter:03d}_1",
                        "slide_title": line.replace("章节", "").replace("Chapter", "").strip(),
                        "slide_content": "相关内容页面",
                        "content_type": "内容页",
                        "estimated_duration": 2
                    }]
                }
                chapter_counter += 1
                
            elif current_chapter and ("页" in line or "slide" in line.lower()):
                # 处理页面信息
                current_chapter["slide_count"] += 1
                slide_num = current_chapter["slide_count"]
                current_chapter["slides"].append({
                    "slide_id": f"slide_{chapter_counter-1:03d}_{slide_num}",
                    "slide_title": f"{current_chapter['chapter_title']} - 第{slide_num}页",
                    "slide_content": line,
                    "content_type": "内容页",
                    "estimated_duration": 2
                })
        
        # 添加最后一个章节
        if current_chapter:
            design_data["chapters"].append(current_chapter)
        
        # 计算总页数
        design_data["total_estimated_slides"] = sum(chapter["slide_count"] for chapter in design_data["chapters"])
        
        return design_data
    
    def _create_chapter_execution_steps(self, design_data: Dict[str, Any]) -> List[ExecutionStep]:
        """创建章节执行步骤"""
        execution_steps = []
        
        # 从设计数据中提取章节信息
        chapters = design_data.get("chapters", [])
        
        if not chapters:
            # 如果没有章节信息，创建默认步骤
            default_step = create_execution_step(
                step_id="chapter_default",
                description="生成默认章节内容",
                expected_output="默认章节的完整内容",
                required_tools=["content_generator"],
                dependencies=[]
            )
            execution_steps.append(default_step)
            return execution_steps
        
        # 为每个章节的每个页面创建执行步骤
        step_counter = 1
        for chapter in chapters:
            chapter_id = chapter.get("chapter_id", f"chapter_{step_counter:03d}")
            chapter_title = chapter.get("chapter_title", f"章节 {step_counter}")
            slides = chapter.get("slides", [])
            
            for slide in slides:
                slide_id = slide.get("slide_id", f"slide_{step_counter:03d}_1")
                slide_title = slide.get("slide_title", f"{chapter_title} - 页面 1")
                slide_content = slide.get("slide_content", "页面内容")
                content_type = slide.get("content_type", "内容页")
                
                # 创建执行步骤
                step = create_execution_step(
                    step_id=slide_id,
                    description=f"生成 {slide_title} 的HTML幻灯片",
                    expected_output=f"{slide_title} 的完整HTML幻灯片内容",
                    required_tools=["content_generator"],
                    dependencies=[f"slide_{step_counter:03d}_{slide_counter-1}"] if slide_counter > 1 else []
                )
                
                # 添加额外的属性
                setattr(step, 'chapter_id', chapter_id)
                setattr(step, 'chapter_title', chapter_title)
                setattr(step, 'slide_title', slide_title)
                setattr(step, 'content_type', content_type)
                setattr(step, 'slide_content', slide_content)
                
                execution_steps.append(step)
            
            step_counter += 1
        
        # 添加整合步骤
        if execution_steps:
            integration_step = create_execution_step(
                step_id="slide_integration",
                description="整合所有幻灯片并生成完整演示文稿",
                expected_output="完整的HTML幻灯片演示文稿",
                required_tools=["content_generator"],
                dependencies=[step.step_id for step in execution_steps]
            )
            execution_steps.append(integration_step)
        
        return execution_steps
    
    def _generate_design_summary(self, design_data: Dict[str, Any]) -> str:
        """生成设计摘要"""
        summary = f"""
章节设计方案: {design_data.get('design_title', '未指定')}
设计目标: {design_data.get('design_objective', '未指定')}

章节详情:
"""
        
        for chapter in design_data.get("chapters", []):
            chapter_title = chapter.get("chapter_title", "未命名章节")
            slide_count = chapter.get("slide_count", 1)
            chapter_objective = chapter.get("chapter_objective", "未指定目标")
            
            summary += f"- {chapter_title} ({slide_count}页PPT)\n"
            summary += f"  目标: {chapter_objective}\n"
            
            slides = chapter.get("slides", [])
            for slide in slides:
                slide_title = slide.get("slide_title", "未命名页面")
                content_type = slide.get("content_type", "内容页")
                estimated_duration = slide.get("estimated_duration", 2)
                summary += f"  • {slide_title} ({content_type}, {estimated_duration}分钟)\n"
            
            summary += "\n"
        
        summary += f"总预估页数: {design_data.get('total_estimated_slides', 0)}\n"
        summary += f"设计备注: {design_data.get('design_notes', '无')}\n"
        
        return summary
    
    def _calculate_total_slides(self, design_data: Dict[str, Any]) -> int:
        """计算总幻灯片数"""
        total_slides = 0
        for chapter in design_data.get("chapters", []):
            total_slides += chapter.get("slide_count", 1)
        return total_slides
    
    def validate_design(self, design_data: Dict[str, Any]) -> bool:
        """验证设计的有效性"""
        required_fields = ["design_title", "design_objective", "chapters"]
        
        for field in required_fields:
            if not design_data.get(field):
                logger.warning(f"设计缺少必要字段: {field}", agent_name="ChapterDesignAgent")
                return False
        
        chapters = design_data.get("chapters", [])
        if not chapters:
            logger.warning("设计没有章节", agent_name="ChapterDesignAgent")
            return False
        
        if len(chapters) > self.max_chapters:
            logger.warning(f"章节数量超过限制: {len(chapters)} > {self.max_chapters}", agent_name="ChapterDesignAgent")
            return False
        
        # 验证每个章节的结构
        for chapter in chapters:
            if not chapter.get("chapter_title"):
                logger.warning("章节缺少标题", agent_name="ChapterDesignAgent")
                return False
            
            slides = chapter.get("slides", [])
            if len(slides) > self.max_slides_per_chapter:
                logger.warning(f"章节页数超过限制: {len(slides)} > {self.max_slides_per_chapter}", agent_name="ChapterDesignAgent")
                return False
        
        return True
    
    def refine_design(self, design_data: Dict[str, Any], feedback: str) -> Dict[str, Any]:
        """根据反馈优化设计"""
        refinement_prompt = f"""
基于以下反馈优化现有的章节设计:

原始设计:
{json.dumps(design_data, ensure_ascii=False, indent=2)}

用户反馈:
{feedback}

请优化设计，保持JSON格式不变，仅修改需要调整的部分。
注意保持章节ID和页面ID的格式规范。
"""
        
        try:
            refined_response = generate_system_response(
                self.system_prompt,
                refinement_prompt,
                temperature=0.3
            )
            
            refined_design = self._parse_design_response(refined_response)
            return refined_design
            
        except Exception as e:
            logger.error(f"设计优化失败: {str(e)}", agent_name="ChapterDesignAgent")
            return design_data  # 返回原始设计
