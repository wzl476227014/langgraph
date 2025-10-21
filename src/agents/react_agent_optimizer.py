"""
React Agent优化器扩展
支持单页优化和重新生成功能
"""

import logging
from typing import Dict, Any, Optional
from ..utils.logger import get_logger, log_agent_start, log_agent_complete

logger = get_logger(__name__)


class ReactAgentOptimizer:
    """React Agent的优化扩展"""
    
    def __init__(self, react_agent):
        """
        初始化优化器
        
        Args:
            react_agent: ReactAgent实例
        """
        self.react_agent = react_agent
        self.tools = react_agent.tools
    
    def optimize_single_page(self, state, page_number: int, optimization_request: str, regenerate: bool = False) -> Dict[str, Any]:
        """
        优化或重新生成单个页面
        
        Args:
            state: 工作流状态
            page_number: 页码
            optimization_request: 优化要求
            regenerate: 是否完全重新生成（True）还是优化（False）
            
        Returns:
            优化结果
        """
        operation = "重新生成" if regenerate else "优化"
        log_agent_start("ReactAgent", f"{operation}第{page_number}页")
        
        try:
            # 获取当前页面内容
            current_content = self._get_current_page_content(state, page_number)
            
            # 检查create_slide工具是否可用
            if "create_slide" not in self.tools:
                raise ValueError("create_slide工具不可用")
            
            tool = self.tools["create_slide"]
            
            # 构建工具输入
            tool_input = self._build_tool_input(
                page_number=page_number,
                optimization_request=optimization_request,
                current_content=current_content,
                regenerate=regenerate,
                state=state
            )
            
            # 执行工具
            logger.info(f"使用create_slide工具{operation}第{page_number}页", agent_name="ReactAgent")
            result = tool.execute(tool_input)
            
            # 更新页面内容
            self._update_page_content(state, page_number, result)
            
            log_agent_complete("ReactAgent", f"页面{page_number}{operation}完成")
            
            return {
                "success": True,
                "page_number": page_number,
                "operation": operation,
                "content": result.get("slide_content", ""),
                "message": f"第{page_number}页已成功{operation}"
            }
            
        except Exception as e:
            logger.error(f"页面{operation}失败: {str(e)}", agent_name="ReactAgent")
            log_agent_complete("ReactAgent", f"页面{page_number}{operation}失败")
            
            return {
                "success": False,
                "page_number": page_number,
                "operation": operation,
                "error": str(e),
                "message": f"第{page_number}页{operation}失败: {str(e)}"
            }
    
    def optimize_multiple_pages(self, state, page_numbers: list, optimization_request: str) -> Dict[str, Any]:
        """
        批量优化多个页面
        
        Args:
            state: 工作流状态
            page_numbers: 页码列表
            optimization_request: 优化要求
            
        Returns:
            批量优化结果
        """
        results = []
        success_count = 0
        
        for page_num in page_numbers:
            result = self.optimize_single_page(state, page_num, optimization_request)
            results.append(result)
            if result["success"]:
                success_count += 1
        
        return {
            "total_pages": len(page_numbers),
            "success_count": success_count,
            "failed_count": len(page_numbers) - success_count,
            "results": results,
            "message": f"批量优化完成: {success_count}/{len(page_numbers)}页成功"
        }
    
    def _get_current_page_content(self, state, page_number: int) -> Optional[str]:
        """获取当前页面内容"""
        if hasattr(state, 'slides_content') and state.slides_content:
            if 0 < page_number <= len(state.slides_content):
                return state.slides_content[page_number - 1]
        return None
    
    def _build_tool_input(self, page_number: int, optimization_request: str, 
                         current_content: Optional[str], regenerate: bool, state) -> Dict[str, Any]:
        """构建工具输入"""
        tool_input = {
            "slide_index": page_number,
            "section_title": f"页面 {page_number}",
            "user_request": optimization_request,
            "optimization_mode": not regenerate,
            "regenerate_mode": regenerate
        }
        
        # 如果是优化模式，提供当前内容
        if not regenerate and current_content:
            tool_input["previous_content"] = current_content
            tool_input["optimization_instructions"] = f"""
请基于以下要求优化这个页面:
{optimization_request}

当前内容:
{current_content[:500]}...

优化要点:
1. 保持原有结构的合理部分
2. 根据用户要求进行改进
3. 确保内容的连贯性和专业性
"""
        
        # 添加文件处理结果（如果有）
        if hasattr(state, 'file_processing_results'):
            tool_input["file_processing_results"] = state.file_processing_results
        
        # 添加上下文信息
        if hasattr(state, 'user_request'):
            tool_input["original_request"] = state.user_request
        
        return tool_input
    
    def _update_page_content(self, state, page_number: int, result: Dict[str, Any]):
        """更新页面内容到state"""
        if "slide_content" not in result:
            return
        
        # 确保slides_content存在
        if not hasattr(state, 'slides_content'):
            state.slides_content = []
        
        # 确保列表足够长
        while len(state.slides_content) < page_number:
            state.slides_content.append("")
        
        # 更新指定页面
        state.slides_content[page_number - 1] = result["slide_content"]
        
        # 记录更新
        if hasattr(state, 'optimization_history'):
            if not state.optimization_history:
                state.optimization_history = []
            state.optimization_history.append({
                "page_number": page_number,
                "timestamp": logger.get_timestamp(),
                "content_preview": result["slide_content"][:200] + "..."
            })


def extend_react_agent_with_optimization(react_agent):
    """
    为ReactAgent添加优化功能
    
    Args:
        react_agent: ReactAgent实例
    """
    optimizer = ReactAgentOptimizer(react_agent)
    
    # 添加方法到ReactAgent
    react_agent.optimize_single_page = optimizer.optimize_single_page
    react_agent.optimize_multiple_pages = optimizer.optimize_multiple_pages
    
    logger.info("ReactAgent已扩展优化功能", agent_name="ReactAgent")