"""
图表处理器
解析HTML中的图表占位符，并替换为实际的ECharts代码
"""

import re
import json
from typing import List, Dict, Any
from .chart_config import ChartConfig
from .chart_generator import ChartCodeGenerator


class ChartProcessor:
    """图表处理器 - 解析并替换HTML中的图表占位符"""
    
    # 图表占位符格式：<!-- CHART_PLACEHOLDER: {...} -->
    CHART_PLACEHOLDER_PATTERN = r'<!-- CHART_PLACEHOLDER:\s*(\{.*?\})\s*-->'
    
    def __init__(self):
        """初始化处理器"""
        self.generator = ChartCodeGenerator()
    
    def process_html(self, html_content: str) -> str:
        """
        处理HTML内容，查找并替换所有图表占位符
        
        Args:
            html_content: 包含占位符的HTML内容
            
        Returns:
            替换后的HTML内容
        """
        # 确保引入ECharts库
        html_content = self._inject_echarts_library(html_content)
        
        # 查找所有图表占位符
        matches = list(re.finditer(self.CHART_PLACEHOLDER_PATTERN, html_content, re.DOTALL))
        
        if not matches:
            # 没有占位符，直接返回
            return html_content
        
        # 从后向前替换（避免位置偏移问题）
        for match in reversed(matches):
            placeholder = match.group(0)
            config_json = match.group(1)
            
            try:
                # 解析配置
                config_dict = json.loads(config_json)
                config = ChartConfig.from_dict(config_dict)
                
                # 生成图表代码
                chart_html = self.generator.generate_chart_html(config)
                
                # 替换占位符
                html_content = html_content[:match.start()] + chart_html + html_content[match.end():]
                
            except Exception as e:
                # 解析或生成失败，保留占位符或替换为错误信息
                error_html = f'<div class="chart-error" style="padding: 20px; background: #fee; border: 1px solid #fcc; border-radius: 4px;">图表生成失败: {str(e)}</div>'
                html_content = html_content[:match.start()] + error_html + html_content[match.end():]
        
        return html_content
    
    def _inject_echarts_library(self, html_content: str) -> str:
        """在HTML中注入ECharts库"""
        # 检查是否已经引入
        if 'echarts.min.js' in html_content:
            return html_content
        
        # 在</head>之前插入
        echarts_script = '<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>'
        
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', f'{echarts_script}\n</head>')
        elif '<head>' in html_content:
            # 如果没有</head>，在<head>后插入
            html_content = html_content.replace('<head>', f'<head>\n{echarts_script}')
        else:
            # 如果没有head标签，在开头插入
            html_content = echarts_script + '\n' + html_content
        
        return html_content
    
    def extract_chart_configs(self, html_content: str) -> List[Dict[str, Any]]:
        """
        提取HTML中的所有图表配置（不替换）
        
        Args:
            html_content: HTML内容
            
        Returns:
            图表配置列表
        """
        configs = []
        matches = re.finditer(self.CHART_PLACEHOLDER_PATTERN, html_content, re.DOTALL)
        
        for match in matches:
            config_json = match.group(1)
            try:
                config_dict = json.loads(config_json)
                configs.append(config_dict)
            except:
                pass
        
        return configs
    
    def validate_placeholders(self, html_content: str) -> Dict[str, Any]:
        """
        验证HTML中的图表占位符格式
        
        Returns:
            验证结果 {"valid": bool, "count": int, "errors": List[str]}
        """
        result = {
            "valid": True,
            "count": 0,
            "errors": []
        }
        
        matches = re.finditer(self.CHART_PLACEHOLDER_PATTERN, html_content, re.DOTALL)
        
        for i, match in enumerate(matches):
            result["count"] += 1
            config_json = match.group(1)
            
            try:
                config_dict = json.loads(config_json)
                config = ChartConfig.from_dict(config_dict)
                
                # 验证配置完整性
                from .chart_config import validate_chart_config
                if not validate_chart_config(config):
                    result["valid"] = False
                    result["errors"].append(f"占位符 #{i+1}: 配置不完整")
                    
            except json.JSONDecodeError as e:
                result["valid"] = False
                result["errors"].append(f"占位符 #{i+1}: JSON解析失败 - {str(e)}")
            except Exception as e:
                result["valid"] = False
                result["errors"].append(f"占位符 #{i+1}: 配置无效 - {str(e)}")
        
        return result


def create_chart_placeholder(config: ChartConfig) -> str:
    """
    创建图表占位符（用于LLM生成时插入）
    
    Args:
        config: 图表配置
        
    Returns:
        占位符字符串
    """
    config_json = json.dumps(config.to_dict(), ensure_ascii=False)
    return f"<!-- CHART_PLACEHOLDER: {config_json} -->"
