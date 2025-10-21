"""
简化的意图分析器
"""

import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


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
    reasoning: str = ""


class TaskIntentAnalyzer:
    def analyze_intent(self, task: str, context: Optional[Dict[str, Any]] = None):
        # 检测页面优化
        page_match = re.search(r'第(\d+)页|(\d+)页', task)
        if page_match:
            page_num = int(page_match.group(1) or page_match.group(2))
            if '重新生成' in task or '重做' in task:
                intent = TaskIntent.REGENERATE_SINGLE_PAGE
            elif '优化' in task or '修改' in task:
                intent = TaskIntent.OPTIMIZE_SINGLE_PAGE
            else:
                intent = TaskIntent.OPTIMIZE_SINGLE_PAGE
            
            return IntentAnalysisResult(
                intent=intent,
                confidence=0.9,
                target_pages=[page_num],
                reasoning=f"检测到页面{page_num}任务"
            )
        
        return IntentAnalysisResult(
            intent=TaskIntent.UNCLEAR,
            confidence=0.3,
            reasoning="无法识别"
        )
