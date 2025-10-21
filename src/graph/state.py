"""
工作流状态管理模块
定义和管理multi-agent工作流的状态
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class WorkflowStatus(str, Enum):
    """工作流状态枚举"""
    INITIALIZED = "initialized"
    PLANNING = "planning"
    PLAN_CONFIRMED = "plan_confirmed"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    MEMORIZING = "memorizing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    """Agent状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_INPUT = "waiting_input"


class ExecutionStep(BaseModel):
    """执行步骤模型"""
    step_id: str = Field(description="步骤ID")
    description: str = Field(description="步骤描述")
    expected_output: str = Field(description="预期输出")
    required_tools: List[str] = Field(default_factory=list, description="所需工具")
    dependencies: List[str] = Field(default_factory=list, description="依赖的步骤")
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="步骤状态")
    result: Optional[Dict[str, Any]] = Field(default=None, description="执行结果")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    execution_attempts: int = Field(default=0, description="执行尝试次数")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="步骤元数据")


class QualityAssessment(BaseModel):
    """质量评估模型"""
    overall_score: float = Field(ge=0.0, le=1.0, description="总体质量评分")
    accuracy_score: float = Field(ge=0.0, le=1.0, description="准确性评分")
    completeness_score: float = Field(ge=0.0, le=1.0, description="完整性评分")
    logical_score: float = Field(ge=0.0, le=1.0, description="逻辑性评分")
    readability_score: float = Field(ge=0.0, le=1.0, description="可读性评分")
    relevance_score: float = Field(ge=0.0, le=1.0, description="相关性评分")
    strengths: List[str] = Field(default_factory=list, description="优点")
    weaknesses: List[str] = Field(default_factory=list, description="不足")
    improvement_suggestions: List[str] = Field(default_factory=list, description="改进建议")
    assessment_notes: str = Field(default="", description="评估备注")


class MemoryEntry(BaseModel):
    """记忆条目模型"""
    entry_id: str = Field(description="条目ID")
    entry_type: str = Field(description="条目类型")
    content: Dict[str, Any] = Field(description="内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    tags: List[str] = Field(default_factory=list, description="标签")
    importance: float = Field(default=1.0, ge=0.0, le=1.0, description="重要性")


class WorkflowState(BaseModel):
    """工作流状态模型"""
    
    # 基础信息
    workflow_id: str = Field(description="工作流ID")
    user_request: str = Field(description="用户请求")
    user_constraints: List[str] = Field(default_factory=list, description="用户约束")
    extract_only: bool = Field(default=False, description="是否只提取HTML页面，不整合")
    use_premium_template: bool = Field(default=False, description="是否使用Premium高端模板直接生成")
    
    # 状态信息
    workflow_status: WorkflowStatus = Field(default=WorkflowStatus.INITIALIZED, description="工作流状态")
    current_agent: Optional[str] = Field(default=None, description="当前执行的Agent")
    current_step: Optional[str] = Field(default=None, description="当前执行的步骤")
    
    # 时间信息
    start_time: datetime = Field(default_factory=datetime.now, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")
    
    # Plan相关
    plan: Optional[Dict[str, Any]] = Field(default=None, description="执行计划")
    execution_steps: List[ExecutionStep] = Field(default_factory=list, description="执行步骤列表")
    plan_confirmed: bool = Field(default=False, description="计划是否已确认")
    
    # Chapter设计相关
    chapter_design: Optional[Dict[str, Any]] = Field(default=None, description="章节设计方案")
    chapter_execution_steps: List[ExecutionStep] = Field(default_factory=list, description="章节执行步骤列表")
    chapter_confirmed: bool = Field(default=False, description="章节设计是否已确认")
    
    # 最终确认相关
    final_confirmed: bool = Field(default=False, description="最终内容是否已确认")
    
    # React相关
    execution_results: Dict[str, Any] = Field(default_factory=dict, description="执行结果")
    execution_logs: List[str] = Field(default_factory=list, description="执行日志")
    
    # Reflect相关
    quality_assessment: Optional[QualityAssessment] = Field(default=None, description="质量评估")
    reflection_notes: str = Field(default="", description="反思备注")
    
    # Memory相关
    memory_entries: List[MemoryEntry] = Field(default_factory=list, description="记忆条目")
    context_summary: str = Field(default="", description="上下文摘要")
    
    # Report相关
    report_content: Optional[str] = Field(default=None, description="报告内容")
    report_metadata: Dict[str, Any] = Field(default_factory=dict, description="报告元数据")
    
    # 用户交互
    user_inputs: Dict[str, Any] = Field(default_factory=dict, description="用户输入")
    user_feedback: List[str] = Field(default_factory=list, description="用户反馈")
    
    # 任务分析相关
    task_requirements: Optional[Dict[str, Any]] = Field(default=None, description="任务类型特定要求")
    task_style_guide: Optional[Dict[str, Any]] = Field(default=None, description="任务类型样式指南")
    
    # 错误和重试
    error_count: int = Field(default=0, description="错误计数")
    retry_count: int = Field(default=0, description="重试计数")
    last_error: Optional[str] = Field(default=None, description="最后错误信息")
    
    # 配置和参数
    config_overrides: Dict[str, Any] = Field(default_factory=dict, description="配置覆盖")
    
    # 文件上传相关
    uploaded_files: List[Dict[str, Any]] = Field(default_factory=list, description="上传的文件信息")
    file_processing_results: Dict[str, Any] = Field(default_factory=dict, description="文件处理结果")
    file_metadata: Dict[str, Any] = Field(default_factory=dict, description="文件元数据")
    
    # 幻灯片内容相关
    slides_content: Optional[Dict[str, str]] = Field(default=None, description="生成的幻灯片内容")

    # 优化后的幻灯片生成流程状态
    slide_data: Optional[Dict[str, Any]] = Field(default=None, description="文档分析提取的数据")
    slide_outline: Optional[Dict[str, Any]] = Field(default=None, description="幻灯片大纲")
    slide_templates: Optional[Dict[str, Dict[str, Any]]] = Field(default=None, description="基础模板缓存")
    generated_slides: Optional[List[Dict[str, Any]]] = Field(default=None, description="生成的幻灯片列表")
    slide_generation_status: Optional[Dict[str, Any]] = Field(default=None, description="幻灯片生成状态追踪")

    # 输出文件
    output_file: Optional[str] = Field(default=None, description="生成的输出文件路径")
    
    def add_execution_step(self, step: ExecutionStep) -> None:
        """添加执行步骤"""
        self.execution_steps.append(step)
    
    def update_step_status(self, step_id: str, status: AgentStatus) -> None:
        """更新步骤状态"""
        for step in self.execution_steps:
            if step.step_id == step_id:
                step.status = status
                if status == AgentStatus.RUNNING:
                    step.start_time = datetime.now()
                elif status in [AgentStatus.COMPLETED, AgentStatus.FAILED]:
                    step.end_time = datetime.now()
                break
    
    def get_step_by_id(self, step_id: str) -> Optional[ExecutionStep]:
        """根据ID获取步骤"""
        for step in self.execution_steps:
            if step.step_id == step_id:
                return step
        return None
    
    def get_pending_steps(self) -> List[ExecutionStep]:
        """获取待执行的步骤"""
        return [step for step in self.execution_steps if step.status == AgentStatus.IDLE]
    
    def get_completed_steps(self) -> List[ExecutionStep]:
        """获取已完成的步骤"""
        return [step for step in self.execution_steps if step.status == AgentStatus.COMPLETED]
    
    def get_failed_steps(self) -> List[ExecutionStep]:
        """获取失败的步骤"""
        return [step for step in self.execution_steps if step.status == AgentStatus.FAILED]
    
    def add_memory_entry(self, entry: MemoryEntry) -> None:
        """添加记忆条目"""
        self.memory_entries.append(entry)
    
    def get_memory_by_type(self, entry_type: str) -> List[MemoryEntry]:
        """根据类型获取记忆条目"""
        return [entry for entry in self.memory_entries if entry.entry_type == entry_type]
    
    def get_memory_by_tags(self, tags: List[str]) -> List[MemoryEntry]:
        """根据标签获取记忆条目"""
        return [entry for entry in self.memory_entries 
                if any(tag in entry.tags for tag in tags)]
    
    def add_execution_result(self, step_id: str, result: Dict[str, Any]) -> None:
        """添加执行结果"""
        self.execution_results[step_id] = result
    
    def get_execution_result(self, step_id: str) -> Optional[Dict[str, Any]]:
        """获取执行结果"""
        return self.execution_results.get(step_id)
    
    def add_user_input(self, input_type: str, content: Any) -> None:
        """添加用户输入"""
        self.user_inputs[input_type] = content
    
    def get_user_input(self, input_type: str) -> Optional[Any]:
        """获取用户输入"""
        return self.user_inputs.get(input_type)
    
    def add_user_feedback(self, feedback: str) -> None:
        """添加用户反馈"""
        self.user_feedback.append(feedback)
    
    def increment_error_count(self) -> None:
        """增加错误计数"""
        self.error_count += 1
    
    def increment_retry_count(self) -> None:
        """增加重试计数"""
        self.retry_count += 1
    
    def set_last_error(self, error_message: str) -> None:
        """设置最后错误信息"""
        self.last_error = error_message
    
    def add_uploaded_file(self, file_info: Dict[str, Any]) -> None:
        """添加上传的文件信息"""
        self.uploaded_files.append(file_info)
    
    def get_uploaded_files(self) -> List[Dict[str, Any]]:
        """获取上传的文件列表"""
        return self.uploaded_files
    
    def get_file_by_id(self, file_id: str) -> Optional[Dict[str, Any]]:
        """根据ID获取文件信息"""
        for file_info in self.uploaded_files:
            if file_info.get("file_id") == file_id:
                return file_info
        return None
    
    def add_file_processing_result(self, file_id: str, result: Dict[str, Any]) -> None:
        """添加文件处理结果"""
        self.file_processing_results[file_id] = result
    
    def get_file_processing_result(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取文件处理结果"""
        return self.file_processing_results.get(file_id)
    
    def add_file_metadata(self, file_id: str, metadata: Dict[str, Any]) -> None:
        """添加文件元数据"""
        self.file_metadata[file_id] = metadata
    
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """获取文件元数据"""
        return self.file_metadata.get(file_id)
    
    def get_files_by_type(self, file_type: str) -> List[Dict[str, Any]]:
        """根据类型获取文件"""
        return [file_info for file_info in self.uploaded_files if file_info.get("file_type") == file_type]
    
    def get_processing_summary(self) -> Dict[str, Any]:
        """获取文件处理摘要"""
        total_files = len(self.uploaded_files)
        processed_files = len(self.file_processing_results)
        pdf_files = len(self.get_files_by_type("pdf"))
        excel_files = len(self.get_files_by_type("xlsx")) + len(self.get_files_by_type("xls"))
        
        return {
            "total_files": total_files,
            "processed_files": processed_files,
            "pending_files": total_files - processed_files,
            "pdf_files": pdf_files,
            "excel_files": excel_files,
            "processing_progress": round(processed_files / total_files * 100, 2) if total_files > 0 else 0
        }
    
    def get_progress_summary(self) -> Dict[str, Any]:
        """获取进度摘要"""
        total_steps = len(self.execution_steps)
        completed_steps = len(self.get_completed_steps())
        failed_steps = len(self.get_failed_steps())
        pending_steps = len(self.get_pending_steps())
        
        progress_percentage = (completed_steps / total_steps * 100) if total_steps > 0 else 0
        
        return {
            "total_steps": total_steps,
            "completed_steps": completed_steps,
            "failed_steps": failed_steps,
            "pending_steps": pending_steps,
            "progress_percentage": round(progress_percentage, 2),
            "workflow_status": self.workflow_status.value,
            "current_agent": self.current_agent,
            "current_step": self.current_step
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowState':
        """从字典创建实例"""
        return cls(**data)


def create_workflow_state(workflow_id: str, user_request: str) -> WorkflowState:
    """创建工作流状态实例"""
    return WorkflowState(
        workflow_id=workflow_id,
        user_request=user_request
    )


def create_execution_step(
    step_id: str,
    description: str,
    expected_output: str,
    required_tools: List[str] = None,
    dependencies: List[str] = None
) -> ExecutionStep:
    """创建执行步骤实例"""
    # Ensure dependencies is a list of strings
    processed_dependencies = []
    if dependencies:
        if isinstance(dependencies, list):
            for dep in dependencies:
                if dep is not None: # Ensure dependency is not None
                    processed_dependencies.append(str(dep))
        else:
            # If dependencies is a single item (e.g., int or str), convert it to a string in a list
            if dependencies is not None:
                processed_dependencies.append(str(dependencies))
    
    return ExecutionStep(
        step_id=step_id,
        description=description,
        expected_output=expected_output,
        required_tools=required_tools or [],
        dependencies=processed_dependencies
    )


def create_memory_entry(
    entry_id: str,
    entry_type: str,
    content: Dict[str, Any],
    tags: List[str] = None,
    importance: float = 1.0
) -> MemoryEntry:
    """创建记忆条目实例"""
    return MemoryEntry(
        entry_id=entry_id,
        entry_type=entry_type,
        content=content,
        tags=tags or [],
        importance=importance
    )


def create_quality_assessment(
    overall_score: float,
    accuracy_score: float,
    completeness_score: float,
    logical_score: float,
    readability_score: float,
    relevance_score: float,
    strengths: List[str] = None,
    weaknesses: List[str] = None,
    improvement_suggestions: List[str] = None,
    assessment_notes: str = ""
) -> QualityAssessment:
    """创建质量评估实例"""
    return QualityAssessment(
        overall_score=overall_score,
        accuracy_score=accuracy_score,
        completeness_score=completeness_score,
        logical_score=logical_score,
        readability_score=readability_score,
        relevance_score=relevance_score,
        strengths=strengths or [],
        weaknesses=weaknesses or [],
        improvement_suggestions=improvement_suggestions or [],
        assessment_notes=assessment_notes
    )
