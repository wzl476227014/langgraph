"""
增强的意图分析器 - 支持中文数字和更多模式
"""

import re
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TaskIntent(Enum):
    OPTIMIZE_SINGLE_PAGE = "optimize_single_page"
    REGENERATE_SINGLE_PAGE = "regenerate_single_page"
    GENERATE_NEW_REPORT = "generate_new_report"
    UNCLEAR = "unclear"


@dataclass
class IntentAnalysisResult:
    intent: TaskIntent
    confidence: float
    target_pages: List[int] = None
    specific_requirements: Dict[str, Any] = None
    reasoning: str = ""


class TaskIntentAnalyzer:
    def __init__(self):
        # 中文数字映射
        self.chinese_nums = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
            '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15
        }
    
    def analyze_intent(self, task: str, context: Optional[Dict[str, Any]] = None):
        """分析任务意图"""
        logger.info(f"[意图分析] 输入: {task}")
        
        # 检测页面相关任务
        page_info = self._extract_page_number(task)
        if page_info:
            page_num, match_type = page_info
            logger.info(f"[意图分析] 检测到页面: {page_num} (匹配类型: {match_type})")
            
            # 判断操作类型
            if any(word in task for word in ['重新生成', '重做', '重写', '重新制作']):
                intent = TaskIntent.REGENERATE_SINGLE_PAGE
                operation = "重新生成"
            elif any(word in task for word in ['优化', '改进', '修改', '调整', '完善', '改善']):
                intent = TaskIntent.OPTIMIZE_SINGLE_PAGE
                operation = "优化"
            else:
                # 默认为优化
                intent = TaskIntent.OPTIMIZE_SINGLE_PAGE
                operation = "优化"
            
            logger.info(f"[意图分析] 识别结果: {intent.value} - {operation}第{page_num}页")
            
            return IntentAnalysisResult(
                intent=intent,
                confidence=0.95,
                target_pages=[page_num],
                reasoning=f"检测到页面{page_num}的{operation}任务"
            )
        
        # 检测其他任务类型
        if any(word in task for word in ['生成报告', '创建报告', '写报告', '制作报告']):
            logger.info("[意图分析] 识别为: 新报告生成")
            return IntentAnalysisResult(
                intent=TaskIntent.GENERATE_NEW_REPORT,
                confidence=0.85,
                reasoning="检测到新报告生成任务"
            )
        
        logger.info("[意图分析] 无法明确识别任务类型")
        return IntentAnalysisResult(
            intent=TaskIntent.UNCLEAR,
            confidence=0.3,
            reasoning="无法明确识别任务意图"
        )
    
    def _extract_page_number(self, text: str) -> Optional[tuple]:
        """提取页码信息
        
        Returns:
            (页码, 匹配类型) 或 None
        """
        # 定义各种页码模式
        patterns = [
            # 中文数字模式
            (r'第([一二三四五六七八九十]+)页', 'chinese'),
            (r'第([一二三四五六七八九十]+)张', 'chinese'),
            
            # 阿拉伯数字模式
            (r'第(\d+)页', 'digit'),
            (r'第(\d+)张', 'digit'),
            (r'页面(\d+)', 'digit'),
            (r'(\d+)页', 'digit'),
            
            # 英文模式
            (r'page\s*(\d+)', 'english'),
            (r'slide\s*(\d+)', 'english'),
            
            # 口语化模式
            (r'第([一二三四五六七八九十]+)个', 'chinese'),
            (r'第(\d+)个', 'digit'),
        ]
        
        for pattern, match_type in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                page_str = match.group(1)
                
                # 转换页码
                if match_type == 'chinese':
                    page_num = self._chinese_to_number(page_str)
                else:
                    try:
                        page_num = int(page_str)
                    except:
                        continue
                
                if page_num and page_num > 0:
                    return (page_num, match_type)
        
        return None
    
    def _chinese_to_number(self, chinese: str) -> Optional[int]:
        """中文数字转阿拉伯数字"""
        # 直接查找映射
        if chinese in self.chinese_nums:
            return self.chinese_nums[chinese]
        
        # 处理十几的情况
        if chinese.startswith('十'):
            if len(chinese) == 1:
                return 10
            elif len(chinese) == 2:
                unit = self.chinese_nums.get(chinese[1], 0)
                return 10 + unit
        
        # 处理二十、三十等
        if len(chinese) == 2 and chinese[1] == '十':
            tens = self.chinese_nums.get(chinese[0], 0)
            return tens * 10
        
        return None