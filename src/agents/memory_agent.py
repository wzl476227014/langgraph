"""
Memory Agent模块
负责管理整个流程中的信息和状态
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..utils.config import get_agent_config, get_agent_prompt
from ..utils.logger import get_logger, log_agent_start, log_agent_complete
from ..utils.llm_config import generate_system_response
from ..graph.state import MemoryEntry, create_memory_entry

logger = get_logger(__name__)


class MemoryAgent:
    """Memory Agent - 信息管理专家"""
    
    def __init__(self):
        """初始化Memory Agent"""
        self.config = get_agent_config("memory")
        self.system_prompt = get_agent_prompt("memory_agent")
        self.max_memory_size = self.config.get("max_memory_size", 1000)
        
        logger.info("Memory Agent初始化完成", agent_name="MemoryAgent")
    
    def execute(self, state) -> Dict[str, Any]:
        """
        执行信息管理任务
        
        Args:
            state: 工作流状态
            
        Returns:
            记忆管理结果字典
        """
        task_description = "管理流程中的信息和状态"
        log_agent_start("MemoryAgent", task_description)
        
        try:
            # 收集需要记忆的信息
            memory_data = self._collect_memory_data(state)
            
            # 创建记忆条目
            memory_entries = self._create_memory_entries(memory_data)
            
            # 整合现有记忆
            integrated_memories = self._integrate_memories(state.memory_entries, memory_entries)
            
            # 生成上下文摘要
            context_summary = self._generate_context_summary(integrated_memories, state)
            
            # 清理低价值记忆
            cleaned_memories = self._cleanup_memories(integrated_memories)
            
            # 构建结果
            result = {
                "memory_entries": cleaned_memories,
                "context_summary": context_summary,
                "memory_statistics": self._generate_memory_statistics(cleaned_memories),
                "memory_summary": self._generate_memory_summary(cleaned_memories),
                "total_entries": len(cleaned_memories)
            }
            
            logger.info(f"记忆管理完成，共处理 {len(cleaned_memories)} 个记忆条目", agent_name="MemoryAgent")
            log_agent_complete("MemoryAgent", task_description, f"处理 {len(cleaned_memories)} 个条目")
            
            return result
            
        except Exception as e:
            error_msg = f"记忆管理失败: {str(e)}"
            logger.error(error_msg, agent_name="MemoryAgent")
            raise Exception(error_msg)
    
    def _collect_memory_data(self, state) -> Dict[str, Any]:
        """收集需要记忆的信息"""
        memory_data = {
            "workflow_info": {
                "workflow_id": state.workflow_id,
                "user_request": state.user_request,
                "user_constraints": state.user_constraints,
                "start_time": state.start_time,
                "end_time": state.end_time,
                "workflow_status": state.workflow_status.value
            },
            "plan_info": state.plan,
            "execution_summary": {
                "total_steps": len(state.execution_steps),
                "completed_steps": len(state.get_completed_steps()),
                "failed_steps": len(state.get_failed_steps()),
                "pending_steps": len(state.get_pending_steps()),
                "execution_logs": state.execution_logs
            },
            "execution_results": state.execution_results,
            "quality_assessment": None,
            "user_interactions": {
                "user_inputs": state.user_inputs,
                "user_feedback": state.user_feedback
            },
            "error_info": {
                "error_count": state.error_count,
                "retry_count": state.retry_count,
                "last_error": state.last_error
            }
        }
        
        # 添加质量评估信息
        if state.quality_assessment:
            memory_data["quality_assessment"] = {
                "overall_score": state.quality_assessment.overall_score,
                "strengths": state.quality_assessment.strengths,
                "weaknesses": state.quality_assessment.weaknesses,
                "improvement_suggestions": state.quality_assessment.improvement_suggestions
            }
        
        return memory_data
    
    def _create_memory_entries(self, memory_data: Dict[str, Any]) -> List[MemoryEntry]:
        """创建记忆条目"""
        memory_entries = []
        
        # 工作流基本信息
        workflow_entry = create_memory_entry(
            entry_id=f"workflow_info_{memory_data['workflow_info']['workflow_id']}",
            entry_type="workflow_info",
            content=memory_data["workflow_info"],
            tags=["workflow", "info", "metadata"],
            importance=1.0
        )
        memory_entries.append(workflow_entry)
        
        # 计划信息
        if memory_data["plan_info"]:
            plan_entry = create_memory_entry(
                entry_id=f"plan_info_{memory_data['workflow_info']['workflow_id']}",
                entry_type="plan_info",
                content=memory_data["plan_info"],
                tags=["plan", "strategy", "workflow"],
                importance=0.9
            )
            memory_entries.append(plan_entry)
        
        # 执行摘要
        execution_entry = create_memory_entry(
            entry_id=f"execution_summary_{memory_data['workflow_info']['workflow_id']}",
            entry_type="execution_summary",
            content=memory_data["execution_summary"],
            tags=["execution", "summary", "progress"],
            importance=0.8
        )
        memory_entries.append(execution_entry)
        
        # 执行结果
        if memory_data["execution_results"]:
            results_entry = create_memory_entry(
                entry_id=f"execution_results_{memory_data['workflow_info']['workflow_id']}",
                entry_type="execution_results",
                content=memory_data["execution_results"],
                tags=["execution", "results", "data"],
                importance=0.7
            )
            memory_entries.append(results_entry)
        
        # 质量评估
        if memory_data["quality_assessment"]:
            quality_entry = create_memory_entry(
                entry_id=f"quality_assessment_{memory_data['workflow_info']['workflow_id']}",
                entry_type="quality_assessment",
                content=memory_data["quality_assessment"],
                tags=["quality", "assessment", "evaluation"],
                importance=0.8
            )
            memory_entries.append(quality_entry)
        
        # 用户交互
        user_interaction_entry = create_memory_entry(
            entry_id=f"user_interactions_{memory_data['workflow_info']['workflow_id']}",
            entry_type="user_interactions",
            content=memory_data["user_interactions"],
            tags=["user", "interaction", "feedback"],
            importance=0.6
        )
        memory_entries.append(user_interaction_entry)
        
        # 错误信息（如果有）
        if memory_data["error_info"]["error_count"] > 0:
            error_entry = create_memory_entry(
                entry_id=f"error_info_{memory_data['workflow_info']['workflow_id']}",
                entry_type="error_info",
                content=memory_data["error_info"],
                tags=["error", "issue", "debug"],
                importance=0.5
            )
            memory_entries.append(error_entry)
        
        return memory_entries
    
    def _integrate_memories(self, existing_memories: List[MemoryEntry], 
                           new_memories: List[MemoryEntry]) -> List[MemoryEntry]:
        """整合现有记忆和新记忆"""
        integrated = existing_memories.copy()
        
        # 检查重复并更新
        for new_memory in new_memories:
            is_duplicate = False
            
            for i, existing_memory in enumerate(integrated):
                if (existing_memory.entry_type == new_memory.entry_type and 
                    existing_memory.entry_id == new_memory.entry_id):
                    # 更新现有记忆
                    integrated[i] = new_memory
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                integrated.append(new_memory)
        
        return integrated
    
    def _generate_context_summary(self, memory_entries: List[MemoryEntry], state) -> str:
        """生成上下文摘要"""
        try:
            # 构建摘要输入
            summary_input = self._build_summary_input(memory_entries, state)
            
            # 生成摘要
            response = generate_system_response(
                self.system_prompt,
                summary_input,
                temperature=0.5
            )
            
            # 提取摘要内容
            summary = self._extract_summary_content(response)
            
            return summary
            
        except Exception as e:
            logger.warning(f"上下文摘要生成失败: {str(e)}", agent_name="MemoryAgent")
            return self._create_fallback_summary(memory_entries)
    
    def _build_summary_input(self, memory_entries: List[MemoryEntry], state) -> str:
        """构建摘要输入"""
        input_text = f"""
请为以下工作流信息生成一个简洁的上下文摘要:

工作流ID: {state.workflow_id}
用户请求: {state.user_request}

记忆条目概览:
"""
        
        # 按类型分组记忆条目
        memories_by_type = {}
        for entry in memory_entries:
            if entry.entry_type not in memories_by_type:
                memories_by_type[entry.entry_type] = []
            memories_by_type[entry.entry_type].append(entry)
        
        # 为每种类型生成摘要
        for entry_type, entries in memories_by_type.items():
            input_text += f"\n{entry_type} ({len(entries)} 条):\n"
            
            # 选择最重要的条目
            important_entries = sorted(entries, key=lambda x: x.importance, reverse=True)[:3]
            
            for entry in important_entries:
                content_str = str(entry.content)
                if len(content_str) > 200:
                    content_str = content_str[:200] + "..."
                input_text += f"- {content_str}\n"
        
        input_text += """
请生成一个简洁的上下文摘要，包含:
1. 工作流的主要目标和进展
2. 关键的执行结果和质量评估
3. 重要的用户交互和反馈
4. 当前状态和下一步建议

摘要应该简洁明了，重点突出，便于后续Agent快速了解上下文。
"""
        
        return input_text
    
    def _extract_summary_content(self, response: str) -> str:
        """提取摘要内容"""
        # 清理响应文本
        summary = response.strip()
        
        # 移除可能的格式标记
        summary = summary.replace("```", "").replace("摘要:", "").replace("上下文摘要:", "")
        
        # 分段并选择最相关的部分
        paragraphs = [p.strip() for p in summary.split('\n\n') if p.strip()]
        
        if paragraphs:
            # 选择第一个非空段落作为主要摘要
            main_summary = paragraphs[0]
            
            # 限制长度
            if len(main_summary) > 500:
                main_summary = main_summary[:500] + "..."
            
            return main_summary
        
        return response[:500] + "..." if len(response) > 500 else response
    
    def _create_fallback_summary(self, memory_entries: List[MemoryEntry]) -> str:
        """创建备用摘要"""
        total_entries = len(memory_entries)
        types = list(set(entry.entry_type for entry in memory_entries))
        
        summary = f"工作流包含 {total_entries} 个记忆条目，涵盖类型: {', '.join(types)}"
        
        return summary
    
    def _cleanup_memories(self, memory_entries: List[MemoryEntry]) -> List[MemoryEntry]:
        """清理低价值记忆"""
        if len(memory_entries) <= self.max_memory_size:
            return memory_entries
        
        # 按重要性排序
        sorted_memories = sorted(memory_entries, key=lambda x: x.importance, reverse=True)
        
        # 保留最重要的记忆
        cleaned_memories = sorted_memories[:self.max_memory_size]
        
        logger.info(f"记忆清理完成，从 {len(memory_entries)} 个条目减少到 {len(cleaned_memories)} 个", 
                   agent_name="MemoryAgent")
        
        return cleaned_memories
    
    def _generate_memory_statistics(self, memory_entries: List[MemoryEntry]) -> Dict[str, Any]:
        """生成记忆统计信息"""
        if not memory_entries:
            return {"total_entries": 0}
        
        # 按类型统计
        type_counts = {}
        importance_scores = []
        
        for entry in memory_entries:
            entry_type = entry.entry_type
            type_counts[entry_type] = type_counts.get(entry_type, 0) + 1
            importance_scores.append(entry.importance)
        
        # 计算统计信息
        stats = {
            "total_entries": len(memory_entries),
            "type_distribution": type_counts,
            "average_importance": sum(importance_scores) / len(importance_scores) if importance_scores else 0,
            "max_importance": max(importance_scores) if importance_scores else 0,
            "min_importance": min(importance_scores) if importance_scores else 0,
            "memory_size_ratio": len(memory_entries) / self.max_memory_size
        }
        
        return stats
    
    def _generate_memory_summary(self, memory_entries: List[MemoryEntry]) -> str:
        """生成记忆摘要"""
        if not memory_entries:
            return "无记忆条目"
        
        summary_parts = []
        
        # 按类型分组
        memories_by_type = {}
        for entry in memory_entries:
            entry_type = entry.entry_type
            if entry_type not in memories_by_type:
                memories_by_type[entry_type] = []
            memories_by_type[entry_type].append(entry)
        
        # 为每种类型生成摘要
        for entry_type, entries in memories_by_type.items():
            count = len(entries)
            avg_importance = sum(entry.importance for entry in entries) / count
            summary_parts.append(f"{entry_type}: {count} 条 (平均重要性: {avg_importance:.2f})")
        
        return " | ".join(summary_parts)
    
    def search_memory(self, memory_entries: List[MemoryEntry], 
                     query: str, limit: int = 5) -> List[MemoryEntry]:
        """搜索记忆条目"""
        results = []
        query_lower = query.lower()
        
        for entry in memory_entries:
            score = 0
            
            # 在内容中搜索
            content_str = str(entry.content).lower()
            if query_lower in content_str:
                score += 2
            
            # 在标签中搜索
            for tag in entry.tags:
                if query_lower in tag.lower():
                    score += 3
            
            # 在类型中搜索
            if query_lower in entry.entry_type.lower():
                score += 1
            
            if score > 0:
                # 添加搜索分数
                entry_with_score = entry
                entry_with_score.search_score = score
                results.append(entry_with_score)
        
        # 按分数排序并限制结果数量
        results.sort(key=lambda x: getattr(x, 'search_score', 0), reverse=True)
        return results[:limit]
    
    def get_memory_by_importance(self, memory_entries: List[MemoryEntry], 
                                 min_importance: float = 0.5) -> List[MemoryEntry]:
        """根据重要性获取记忆条目"""
        return [entry for entry in memory_entries if entry.importance >= min_importance]
    
    def get_recent_memories(self, memory_entries: List[MemoryEntry], 
                           hours: int = 24) -> List[MemoryEntry]:
        """获取最近的记忆条目"""
        cutoff_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        return [entry for entry in memory_entries 
                if entry.timestamp >= cutoff_time]
    
    def export_memory(self, memory_entries: List[MemoryEntry], 
                     format_type: str = "json") -> str:
        """导出记忆数据"""
        if format_type == "json":
            memory_data = []
            for entry in memory_entries:
                memory_data.append({
                    "entry_id": entry.entry_id,
                    "entry_type": entry.entry_type,
                    "content": entry.content,
                    "timestamp": entry.timestamp.isoformat(),
                    "tags": entry.tags,
                    "importance": entry.importance
                })
            
            return json.dumps(memory_data, ensure_ascii=False, indent=2)
        
        elif format_type == "summary":
            return self._generate_memory_summary(memory_entries)
        
        else:
            raise ValueError(f"不支持的导出格式: {format_type}")
