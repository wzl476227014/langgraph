"""
Web搜索工具模块
提供网络搜索功能以获取外部信息
"""

import json
import time
from typing import Dict, Any, List, Optional
from ..utils.config import get_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class WebSearchTool:
    """Web搜索工具"""
    
    def __init__(self):
        """初始化Web搜索工具"""
        self.config = get_config().get_tool_config("web_search")
        self.enabled = self.config.get("enabled", True)
        self.max_results = self.config.get("max_results", 5)
        self.search_delay = self.config.get("search_delay", 1.0)  # 搜索延迟，避免过于频繁的请求
        
        logger.info("Web搜索工具初始化完成", agent_name="WebSearchTool")
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行Web搜索
        
        Args:
            input_data: 输入数据，包含查询等信息
            
        Returns:
            搜索结果字典
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "Web搜索工具未启用",
                "results": []
            }
        
        query = input_data.get("query", "")
        max_results = input_data.get("max_results", self.max_results)
        
        if not query:
            return {
                "success": False,
                "error": "搜索查询不能为空",
                "results": []
            }
        
        try:
            logger.info(f"开始Web搜索: {query}", agent_name="WebSearchTool")
            
            # 执行搜索
            search_results = self._perform_search(query, max_results)
            
            # 处理结果
            processed_results = self._process_results(search_results)
            
            result = {
                "success": True,
                "query": query,
                "results": processed_results,
                "total_results": len(processed_results),
                "search_time": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            logger.info(f"Web搜索完成，返回 {len(processed_results)} 个结果", agent_name="WebSearchTool")
            
            return result
            
        except Exception as e:
            error_msg = f"Web搜索失败: {str(e)}"
            logger.error(error_msg, agent_name="WebSearchTool")
            
            return {
                "success": False,
                "error": error_msg,
                "query": query,
                "results": []
            }
    
    def _perform_search(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """执行实际搜索"""
        try:
            # 这里使用模拟搜索，实际应用中可以集成真实的搜索API
            # 如Google搜索API、Bing搜索API、DuckDuckGo等
            
            # 模拟搜索结果
            mock_results = self._generate_mock_results(query, max_results)
            
            # 添加搜索延迟
            time.sleep(self.search_delay)
            
            return mock_results
            
        except Exception as e:
            logger.error(f"搜索执行失败: {str(e)}", agent_name="WebSearchTool")
            raise
    
    def _generate_mock_results(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """生成模拟搜索结果"""
        # 基于查询生成相关的模拟结果
        mock_results = []
        
        # 根据查询关键词生成不同类型的结果
        query_lower = query.lower()
        
        # 通用结果模板
        result_templates = [
            {
                "title": f"关于{query}的综合信息",
                "url": f"https://example.com/search?q={query.replace(' ', '+')}",
                "snippet": f"这是一个关于{query}的综合信息页面，包含了相关的背景知识、最新动态和深度分析。",
                "content_type": "article",
                "source": "综合信息平台",
                "published_date": "2024-01-15",
                "relevance_score": 0.9
            },
            {
                "title": f"{query}的最新研究进展",
                "url": f"https://research.example.com/topic/{query.replace(' ', '-')}",
                "snippet": f"最新的研究显示，{query}领域取得了重要进展。本文详细介绍了相关的研究成果和未来发展方向。",
                "content_type": "research",
                "source": "学术研究平台",
                "published_date": "2024-01-10",
                "relevance_score": 0.85
            },
            {
                "title": f"如何理解和应用{query}",
                "url": f"https://tutorial.example.com/{query.replace(' ', '-')}-guide",
                "snippet": f"本教程提供了关于{query}的详细指南，包括基本概念、实践方法和应用案例。",
                "content_type": "tutorial",
                "source": "在线学习平台",
                "published_date": "2024-01-08",
                "relevance_score": 0.8
            },
            {
                "title": f"{query}的市场分析报告",
                "url": f"https://market.example.com/analysis/{query.replace(' ', '-')}",
                "snippet": f"最新的市场分析报告显示，{query}相关市场呈现出稳定增长的趋势，预计未来几年将继续保持良好发展。",
                "content_type": "report",
                "source": "市场分析机构",
                "published_date": "2024-01-05",
                "relevance_score": 0.75
            },
            {
                "title": f"{query}的技术实现方案",
                "url": f"https://tech.example.com/solutions/{query.replace(' ', '-')}",
                "snippet": f"本文介绍了{query}的多种技术实现方案，包括架构设计、技术选型和最佳实践建议。",
                "content_type": "technical",
                "source": "技术社区",
                "published_date": "2024-01-03",
                "relevance_score": 0.7
            }
        ]
        
        # 根据查询内容调整结果
        if any(keyword in query_lower for keyword in ["报告", "分析", "研究"]):
            # 优先返回研究相关结果
            priority_types = ["research", "report", "article"]
        elif any(keyword in query_lower for keyword in ["教程", "指南", "如何"]):
            # 优先返回教程相关结果
            priority_types = ["tutorial", "guide", "article"]
        elif any(keyword in query_lower for keyword in ["技术", "实现", "方案"]):
            # 优先返回技术相关结果
            priority_types = ["technical", "tutorial", "article"]
        else:
            # 默认优先级
            priority_types = ["article", "research", "tutorial"]
        
        # 按优先级排序结果
        sorted_templates = sorted(
            result_templates,
            key=lambda x: (priority_types.index(x["content_type"]) if x["content_type"] in priority_types else len(priority_types)),
            reverse=False
        )
        
        # 返回指定数量的结果
        for i, template in enumerate(sorted_templates[:max_results]):
            result = template.copy()
            result["position"] = i + 1
            mock_results.append(result)
        
        return mock_results
    
    def _process_results(self, raw_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理搜索结果"""
        processed_results = []
        
        for result in raw_results:
            processed_result = {
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", ""),
                "content_type": result.get("content_type", "unknown"),
                "source": result.get("source", "未知来源"),
                "published_date": result.get("published_date", ""),
                "relevance_score": result.get("relevance_score", 0.0),
                "position": result.get("position", 0),
                "metadata": {
                    "word_count": len(result.get("snippet", "").split()),
                    "has_https": result.get("url", "").startswith("https://"),
                    "domain": self._extract_domain(result.get("url", ""))
                }
            }
            
            processed_results.append(processed_result)
        
        return processed_results
    
    def _extract_domain(self, url: str) -> str:
        """从URL中提取域名"""
        try:
            if url.startswith("http://"):
                url = url[7:]
            elif url.startswith("https://"):
                url = url[8:]
            
            domain_parts = url.split("/")
            if domain_parts:
                return domain_parts[0]
            return "未知域名"
            
        except Exception:
            return "未知域名"
    
    def search_by_keywords(self, keywords: List[str], max_results: int = 5) -> Dict[str, Any]:
        """根据关键词列表搜索"""
        query = " ".join(keywords)
        return self.execute({
            "query": query,
            "max_results": max_results
        })
    
    def search_recent(self, query: str, days: int = 7, max_results: int = 5) -> Dict[str, Any]:
        """搜索最近的内容"""
        # 在实际实现中，这里可以使用搜索API的时间过滤功能
        # 目前返回所有结果，但在结果中会包含时间信息
        return self.execute({
            "query": query,
            "max_results": max_results
        })
    
    def search_by_type(self, query: str, content_type: str, max_results: int = 5) -> Dict[str, Any]:
        """按内容类型搜索"""
        input_data = {
            "query": query,
            "max_results": max_results * 2  # 获取更多结果以便筛选
        }
        
        # 执行搜索
        search_result = self.execute(input_data)
        
        if not search_result["success"]:
            return search_result
        
        # 按内容类型筛选结果
        filtered_results = [
            result for result in search_result["results"]
            if result.get("content_type", "").lower() == content_type.lower()
        ]
        
        # 返回筛选后的结果
        search_result["results"] = filtered_results[:max_results]
        search_result["total_results"] = len(filtered_results[:max_results])
        
        return search_result
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "WebSearchTool",
            "description": "Web搜索工具，用于获取外部信息",
            "version": "1.0.0",
            "enabled": self.enabled,
            "max_results": self.max_results,
            "search_delay": self.search_delay,
            "supported_types": ["article", "research", "tutorial", "report", "technical"],
            "capabilities": [
                "关键词搜索",
                "按内容类型筛选",
                "时间范围过滤",
                "域名提取",
                "相关性评分"
            ]
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        if not isinstance(input_data, dict):
            return False
        
        query = input_data.get("query", "")
        if not query or not isinstance(query, str):
            return False
        
        max_results = input_data.get("max_results", self.max_results)
        if not isinstance(max_results, int) or max_results <= 0:
            return False
        
        return True
    
    def format_results_summary(self, results: Dict[str, Any]) -> str:
        """格式化结果摘要"""
        if not results["success"]:
            return f"搜索失败: {results.get('error', '未知错误')}"
        
        summary = f"搜索 '{results['query']}' 返回 {results['total_results']} 个结果:\n\n"
        
        for i, result in enumerate(results["results"][:3], 1):  # 只显示前3个结果
            summary += f"{i}. {result['title']}\n"
            summary += f"   来源: {result['source']}\n"
            summary += f"   摘要: {result['snippet'][:100]}...\n"
            summary += f"   相关性: {result['relevance_score']:.2f}\n\n"
        
        if results['total_results'] > 3:
            summary += f"... 还有 {results['total_results'] - 3} 个结果"
        
        return summary
    
    def enable_tool(self) -> None:
        """启用工具"""
        self.enabled = True
        logger.info("Web搜索工具已启用", agent_name="WebSearchTool")
    
    def disable_tool(self) -> None:
        """禁用工具"""
        self.enabled = False
        logger.info("Web搜索工具已禁用", agent_name="WebSearchTool")
    
    def set_max_results(self, max_results: int) -> None:
        """设置最大结果数量"""
        if max_results > 0:
            self.max_results = max_results
            logger.info(f"最大搜索结果数已设置为: {max_results}", agent_name="WebSearchTool")
        else:
            raise ValueError("最大结果数必须大于0")
    
    def set_search_delay(self, delay: float) -> None:
        """设置搜索延迟"""
        if delay >= 0:
            self.search_delay = delay
            logger.info(f"搜索延迟已设置为: {delay}秒", agent_name="WebSearchTool")
        else:
            raise ValueError("搜索延迟不能为负数")
