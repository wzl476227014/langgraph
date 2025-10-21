"""
Create Slide工具模块
专门用于生成PPT幻灯片的工具
"""

import json
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from ..utils.config import get_config, get_agent_prompt
from ..utils.logger import get_logger
from ..utils.llm_config import generate_system_response

logger = get_logger(__name__)


class CreateSlideTool:
    """幻灯片创建工具"""
    
    def __init__(self):
        """初始化幻灯片创建工具"""
        self.config = get_config().get_tool_config("content_generator")
        self.enabled = self.config.get("enabled", True)
        self.max_content_length = self.config.get("max_content_length", 5000)
        self.system_prompt = get_agent_prompt("create_slide_tool")
        
        # 幻灯片类型定义
        self.slide_types = {
            "cover": {
                "name": "封面页",
                "description": "PPT封面页，包含标题、公司名称、时间等",
                "template": "cover_slide.html"
            },
            "toc": {
                "name": "目录页", 
                "description": "目录页，列出PPT的主要章节",
                "template": "toc_slide.html"
            },
            "content": {
                "name": "内容页",
                "description": "内容页，展示具体内容和分析",
                "template": "content_slide.html"
            },
            "chart": {
                "name": "图表页",
                "description": "图表页，展示数据图表和分析",
                "template": "chart_slide.html"
            },
            "summary": {
                "name": "总结页",
                "description": "总结页，总结要点和结论",
                "template": "summary_slide.html"
            }
        }

        # 新增AI模板构建方法定义
        self.ai_template_constraints = """
### 核心硬性约束：
1. **页面尺寸**：必须固定为 1920x1080 像素，不可改变
2. **样式保持**：所有CSS样式、颜色、字体大小、页码位置、标题样式、底部条等必须与模板完全一致
3. **内容替换**：只允许替换内容部分（标题、副标题、段落、卡片内容、列表文字、图表等）
4. **页码格式**：<div class="page-number">X</div> 必须保留且位置不变，只替换数字
5. **布局结构**：单栏布局，垂直方向固定为三个容器（标题区、内容区、页码区）
6. **文字规范**：容器里的字号不小于25px，图表标签不小于14px

### 关键布局与空间控制：
1. **严格空间限制**：
   - 标题区域：约120px（h1 42px + h2 32px + 分割线）
   - 内容区域：最多780px可用空间，绝对不能超出
   - 页码区域：固定底部60px
   - 内容总高度≤900px
2. **内容精简原则**：
   - 如果材料过多，必须提炼关键信息
   - 数据项超过8个时，只选择4-6个最重要的展示
3. **可视化限制**：
   - 每页最多2-3个可视化元素
   - 每个图表容器最大高度200px，最小高度150px
   - 图表数据项最多4个，列表最多4个要点

### 禁止事项：
1. 禁止使用任何带自定义类名的标签，如<span class="highlight">
2. 禁止垂直堆叠超过3个大型图表
3. 禁止使用小于14px的字体
4. 禁止忽略页面高度限制
5. 禁止改变基础模板结构
"""

        self.base_template = """<!DOCTYPE html>
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
  .slide-container { width: 1920px; height: 1080px; background-color: white; position: relative; overflow: hidden; display: flex; flex-direction: column; }
  .content-section { flex: 1; padding: 40px 80px 60px 80px; display: flex; flex-direction: column; overflow: hidden; }
  .page-number { position: absolute; bottom: 30px; right: 50px; font-size: 14px; color: #666; }
  .primary-color { color: rgb(10, 66, 117); }
  .primary-bg { background-color: rgb(10, 66, 117); }
  .top-bar { height: 10px; width: 100%; background-color: rgb(10, 66, 117); }
  .data-card {
    border-left: 4px solid rgb(10, 66, 117);
    padding: 15px 20px;
    background-color: rgba(10, 66, 117, 0.03);
    border-radius: 8px;
    margin-bottom: 20px;
  }
  .chatainer {
    min-height: 180px;
    max-height: 200px;
    position: relative;
    overflow: visible;
  }
  .stat-card {
    background-color: rgba(10, 66, 117, 0.08);
    border-radius: 8px;
    padding: 15px 20px;
    border-left: 4px solid rgb(10, 66, 117);
    margin-bottom: 20px;
  }
  .progress-bar {
    height: 16px;
    border-radius: 8px;
    background-color: #e2e8f0;
    margin-bottom: 4px;
    overflow: visible;
  }
  .strategy-card {
    border-radius: 8px;
    padding: 15px 20px;
    background-color: rgba(10, 66, 117, 0.06);
    border-left: 4px solid rgb(10, 66, 117);
    margin-bottom: 20px;
  }
  .bullet-point {
    display: flex;
    align-items: center;
    margin-bottom: 8px;
    font-size: 20px;
  }
  .bullet-icon {
    color: rgb(10, 66, 117);
    margin-right: 10px;
    min-width: 20px;
  }
  .logo-space {
        position: absolute;
        top: 0;
        right: 0;
        width: 200px;
        height: 100px;
    }
  .visualization-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 30px;
        width: 100%;
        max-width: calc(1920px - 160px);
        overflow-wrap: break-word;
        word-wrap: break-word;
        overflow: visible;
    }
    .stats-container {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 20px;
        margin-bottom: 30px;
        overflow: visible;
    }
    .stat-box {
        max-height: 300px;
        min-height:200px;
        background-color: rgba(10, 66, 117, 0.06);
        border-radius: 10px;
        padding: 20px;
        display: flex;
        align-items: center;
        max-width: calc(1920px - 160px);
        overflow-wrap: break-word;
        word-wrap: break-word;
    }
    .stat-icon {
        font-size: 36px;
        margin-right: 20px;
        color: #3498db;
    }
    .stat-content {
        flex: 1;
    }
    .stat-title {
        font-size: 24px;
        margin-bottom: 5px;
        color: rgb(10, 66, 117);
    }
    .large-chart {
        grid-column: span 2;
        height: 270px;
    }
     .ip-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 20px 0;
    background-color: #ffffff;
    border-radius: 10px;
    overflow: visible;
    font-size: 24px;
   }
    .ip-table th, .ip-table td {
    padding: 12px 15px;
    text-align: left;
    border-bottom: 1px solid #eee;
    font-size: 24px;
   }
    .ip-table th {
    background-color: rgb(10, 66, 117);
    color: #ffffff;
    font-weight: 600;
   }
    .ip-table tr:last-child td {
    border-bottom: none;
   }
    .ip-table td:first-child {
    color: rgb(10, 66, 117);
    font-weight: 600;
   }
  h1 {
    font-size: 42px;
    font-weight: 700;
    color: rgb(10, 66, 117);
    margin-bottom: 10px;
  }
  p {
    font-size: 22px;
    color: #333;
    line-height: 1.5;
    margin-bottom: 8px;
  }
  h2 {
    font-size: 32px;
    font-weight: 600;
    color: rgb(10, 66, 117);
    margin-bottom: 15px;
  }
  h3 {
    font-size: 26px;
    font-weight: 600;
    color: rgb(10, 66, 117);
    margin-bottom: 10px;
  }
  .content-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 20px;
    overflow: hidden;
  }

  /* CSS图表样式 - 供LLM使用 */
  .css-chart-container {
    margin: 20px 0;
    padding: 20px;
    background: rgba(10, 66, 117, 0.03);
    border-radius: 8px;
    min-height: 200px;
    max-height: 300px;
    overflow: visible;
  }
  .bar-chart {
    display: flex;
    align-items: flex-end;
    height: 180px;
    gap: 15px;
    padding: 10px;
  }
  .bar-item {
    flex: 1;
    background: linear-gradient(0deg, rgb(10, 66, 117) 0%, rgba(10, 66, 117, 0.7) 100%);
    border-radius: 4px 4px 0 0;
    position: relative;
    transition: all 0.3s ease;
  }
  .bar-item:hover {
    opacity: 0.8;
  }
  .bar-label {
    position: absolute;
    bottom: -30px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 14px;
    color: #333;
    text-align: center;
    width: 100%;
  }
  .bar-value {
    position: absolute;
    top: -25px;
    left: 50%;
    transform: translateX(-50%);
    font-size: 14px;
    font-weight: 600;
    color: rgb(10, 66, 117);
  }
  .pie-chart {
    width: 200px;
    height: 200px;
    border-radius: 50%;
    margin: 0 auto;
    position: relative;
  }
  .pie-segment {
    position: absolute;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    clip-path: polygon(50% 50%, 50% 0%, 100% 0%);
  }
  .progress-chart {
    margin: 15px 0;
  }
  .progress-item {
    margin: 10px 0;
  }
  .progress-label {
    display: flex;
    justify-content: space-between;
    margin-bottom: 5px;
    font-size: 18px;
  }
  .progress-track {
    height: 20px;
    background: #e2e8f0;
    border-radius: 10px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, rgb(10, 66, 117) 0%, rgba(10, 66, 117, 0.8) 100%);
    border-radius: 10px;
    transition: width 0.3s ease;
  }
  .doughnut-chart {
    width: 180px;
    height: 180px;
    border-radius: 50%;
    margin: 0 auto;
    position: relative;
    background: conic-gradient(rgb(10, 66, 117) 0deg 120deg, #3498db 120deg 240deg, #95d5ff 240deg 360deg);
  }
  .doughnut-chart::after {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    width: 80px;
    height: 80px;
    background: white;
    border-radius: 50%;
    transform: translate(-50%, -50%);
  }

  /* 饼图样式 - 纯CSS实现 */
  .pie-chart-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 30px;
    margin: 20px 0;
  }
  .pie-chart-css {
    width: 180px;
    height: 180px;
    border-radius: 50%;
    position: relative;
    background: conic-gradient(
      rgb(10, 66, 117) 0deg,
      rgb(10, 66, 117) var(--slice1),
      #3498db var(--slice1),
      #3498db var(--slice2),
      #95d5ff var(--slice2),
      #95d5ff var(--slice3),
      #ffd700 var(--slice3),
      #ffd700 var(--slice4),
      #ff6b6b var(--slice4)
    );
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  }
  .pie-legend {
    display: flex;
    flex-direction: column;
    gap: 8px;
    font-size: 14px;
  }
  .pie-legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .pie-legend-color {
    width: 12px;
    height: 12px;
    border-radius: 2px;
  }

  /* 折线图样式 - 纯CSS实现 */
  .line-chart-container {
    margin: 20px 0;
    padding: 20px;
    background: rgba(10, 66, 117, 0.03);
    border-radius: 8px;
    position: relative;
    height: 250px;
  }
  .line-chart-grid {
    position: absolute;
    top: 20px;
    left: 40px;
    right: 20px;
    bottom: 40px;
    border-left: 2px solid #e0e0e0;
    border-bottom: 2px solid #e0e0e0;
  }
  .line-chart-line {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 100%;
  }
  .line-chart-path {
    fill: none;
    stroke: rgb(10, 66, 117);
    stroke-width: 3;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .line-chart-point {
    position: absolute;
    width: 8px;
    height: 8px;
    background: rgb(10, 66, 117);
    border: 2px solid white;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  }
  .line-chart-point:hover::after {
    content: attr(data-value);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.8);
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
    white-space: nowrap;
    margin-bottom: 4px;
  }
  .line-chart-labels {
    position: absolute;
    bottom: 0;
    left: 40px;
    right: 20px;
    display: flex;
    justify-content: space-between;
    font-size: 12px;
    color: #666;
  }
  .line-chart-values {
    position: absolute;
    top: 20px;
    left: 0;
    bottom: 40px;
    width: 35px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: flex-end;
    font-size: 11px;
    color: #666;
  }
  .chart-legend {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 15px;
    margin-top: 15px;
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
  }
  .legend-color {
    width: 16px;
    height: 16px;
    border-radius: 3px;
  }
  /* 其他样式可以自由设置，container和card最大高度不能超过300px，最小高度不能低于200px。所有容器overflow必须设置为visible，容器里的字号不小于25px。且不允许改变基础样式 */
</style>
</head>
<body>
<div class="slide-container">
  <div class="top-bar"></div>
  <div class="content-section">
    <!-- 标题区域，严格按照h1和h2样式，如果副标题h2没有可以去掉 -->
    <div class="mt-10">
      <h1>标题占位，必选</h1>
      <h2 class="mt-2">副标题占位，可选</h2>
      <div class="w-20 h-1 primary-bg mb-4"></div>
    </div>

    <!-- 内容区域：正文使用p标签，单栏布局，固定为3个容器 -->
    <div class="space-y-10">
      <p class="primary-color">内容区域占位</p>
    </div>
  </div>
  <div class="page-number">X</div>
</div>
</body>
</html>"""

        logger.info("幻灯片创建工具初始化完成", agent_name="CreateSlideTool")
    
    def _analyze_data_for_charts(self, content: str) -> Dict[str, Any]:
        """分析内容中的数据，识别适合图表化的部分"""
        chart_data = {
            "has_charts": False,
            "charts": [],
            "processed_content": content
        }
        
        # 安全运营特定数据模式 - 支持HTML标签包裹的数据
        # 1. 安全评分数据 (如：84.14分、75分等) - 支持HTML包裹格式
        security_score_pattern = r'(威胁管理|资产管理|脆弱性管理|事件管理|安全状态|安全评分)[：:→\s]*(?:<[^>]*>)?(\d+(?:\.\d+)?)(?:</[^>]*>)?[分]'
        security_scores = re.findall(security_score_pattern, content)
        
        # 2. 闭环率、修复率等百分比 - 支持HTML包裹格式
        rate_pattern = r'(闭环率|修复率|成功率|覆盖率|达成率|完成率|在线率|响应率)[：:→\s]*(?:<[^>]*>)?(\d+(?:\.\d+)?)(?:</[^>]*>)?%'
        rate_matches = re.findall(rate_pattern, content)
        
        # 3. 安全事件统计 (个、次、起、万次等) - 支持HTML包裹格式和更复杂的模式
        # 匹配 "存在456个漏洞" 或 "23个业务资产" 这样的模式
        incident_pattern = r'(?:存在|发现|监测到|识别)?.*?(?:<[^>]*>)?(\d+(?:\.\d+)?)(?:</[^>]*>)?.*?(漏洞|事件|攻击|威胁|资产|端口|业务系统)(?:个|次|起|台|万次?|千次?)?'
        incident_matches = re.findall(incident_pattern, content)
        
        # 额外模式：直接匹配数字+单位的模式
        direct_pattern = r'(?:<[^>]*>)?(\d+(?:\.\d+)?)(?:</[^>]*>)?\s*(个|次|起|台)(?:\s*(漏洞|事件|攻击|威胁|资产|端口|业务系统))?'
        direct_matches = re.findall(direct_pattern, content)
        
        # 合并incident_matches，调整顺序以匹配预期格式
        adjusted_incident_matches = []
        for count, category in incident_matches:
            if count and category:
                adjusted_incident_matches.append((category, count))
        
        # 处理direct_matches，提取有效的数据
        for count, unit, category in direct_matches:
            if count and unit and category:
                adjusted_incident_matches.append((category, count))
            elif count and unit and not category:
                # 如果没有具体类别，尝试从上下文推断
                adjusted_incident_matches.append(("安全项", count))
        
        # 用调整后的数据替换原始匹配结果
        incident_matches = adjusted_incident_matches
        
        # 4. 大数据量统计 (万次、千个等)
        large_num_pattern = r'(拦截|监测|处理|发现).*?(\d+(?:\.\d+)?)(?:万次|千个|百个)'
        large_num_matches = re.findall(large_num_pattern, content)
        
        # 5. 设备状态统计
        device_status_pattern = r'(在线|离线|已接入|未接入).*?(\d+)'
        device_matches = re.findall(device_status_pattern, content)
        
        # 处理安全评分数据
        if security_scores and len(security_scores) >= 2:
            labels = []
            values = []
            for name, score in security_scores:
                labels.append(name)
                values.append(float(score))
            
            if labels and values:
                chart_data["charts"].append({
                    "type": "bar",
                    "title": "安全评分对比",
                    "labels": labels,
                    "values": values,
                    "id": f"chart_security_score_{len(chart_data['charts'])}"
                })
                chart_data["has_charts"] = True
        
        # 处理闭环率等百分比数据 - 包括从文本中提取的百分比
        # 提取更多百分比数据，包括修复率等
        additional_rate_pattern = r'修复率.*?(?:<[^>]*>)?(\d+(?:\.\d+)?)(?:</[^>]*>)?%'
        additional_rates = re.findall(additional_rate_pattern, content)
        
        # 合并rate_matches和additional_rates
        all_rate_matches = rate_matches[:]
        for rate in additional_rates:
            all_rate_matches.append(("修复率", rate))
        
        # 添加行业平均水平数据（如果存在）
        industry_avg_pattern = r'行业平均水平.*?(?:<[^>]*>)?(\d+(?:\.\d+)?)(?:</[^>]*>)?%'
        industry_avgs = re.findall(industry_avg_pattern, content)
        for avg in industry_avgs:
            all_rate_matches.append(("行业平均", avg))
        
        if all_rate_matches and len(all_rate_matches) >= 2:
            # 去重逻辑
            seen_categories = set()
            unique_rates = []
            for name, rate in all_rate_matches:
                if name not in seen_categories:
                    unique_rates.append((name, rate))
                    seen_categories.add(name)
            
            labels = []
            values = []
            for name, rate in unique_rates[:5]:  # 限制最多5个数据点
                labels.append(name)
                values.append(float(rate))
            
            if labels and values and len(labels) >= 2:
                chart_data["charts"].append({
                    "type": "doughnut",
                    "title": "效率指标对比",
                    "labels": labels,
                    "values": values,
                    "id": f"chart_rates_{len(chart_data['charts'])}"
                })
                chart_data["has_charts"] = True
        
        # 处理安全事件统计 - 去重并限制数量
        if incident_matches and len(incident_matches) >= 3:
            # 去重逻辑：同一类别保留第一个数值
            seen_categories = set()
            unique_matches = []
            for name, count in incident_matches:
                if name not in seen_categories:
                    unique_matches.append((name, count))
                    seen_categories.add(name)
            
            # 限制图表数据点数量，避免过于复杂
            if len(unique_matches) > 6:
                unique_matches = unique_matches[:6]
                
            labels = []
            values = []
            for name, count in unique_matches:
                labels.append(name)
                # 处理浮点数（如151.8）
                try:
                    values.append(float(count))
                except ValueError:
                    values.append(0)
            
            if labels and values:
                chart_data["charts"].append({
                    "type": "bar",
                    "title": "安全事件统计",
                    "labels": labels,
                    "values": values,
                    "id": f"chart_incidents_{len(chart_data['charts'])}"
                })
                chart_data["has_charts"] = True
        
        # 处理设备状态统计
        if device_matches and len(device_matches) >= 2:
            labels = []
            values = []
            for status, count in device_matches:
                labels.append(status + "设备")
                # 处理浮点数
                try:
                    values.append(float(count))
                except ValueError:
                    values.append(0)
            
            if labels and values:
                chart_data["charts"].append({
                    "type": "pie",
                    "title": "设备状态分布",
                    "labels": labels,
                    "values": values,
                    "id": f"chart_device_status_{len(chart_data['charts'])}"
                })
                chart_data["has_charts"] = True
        
        # 处理大数据量统计（如：151.8万次）
        if large_num_matches and len(large_num_matches) >= 2:
            labels = []
            values = []
            for action, number in large_num_matches:
                labels.append(action)
                # 转换万/千/百到实际数值
                num = float(number)
                if '万' in content[content.find(number):content.find(number)+10]:
                    num = num * 10000
                elif '千' in content[content.find(number):content.find(number)+10]:
                    num = num * 1000
                elif '百' in content[content.find(number):content.find(number)+10]:
                    num = num * 100
                values.append(num)
            
            if labels and values and len(labels) >= 2:
                chart_data["charts"].append({
                    "type": "bar",
                    "title": "安全操作统计",
                    "labels": labels,
                    "values": values,
                    "id": f"chart_large_nums_{len(chart_data['charts'])}"
                })
                chart_data["has_charts"] = True
        
        return chart_data
    
    def _generate_slide_from_template_direct(self, slide_type: str, template_data: Dict[str, Any], 
                                           context: Dict[str, Any], style: str) -> str:
        """
        使用AI+模板直接生成HTML幻灯片，一步到位生成最终HTML
        
        Args:
            slide_type: 幻灯片类型
            template_data: 模板数据
            context: 上下文信息
            style: 样式风格
            
        Returns:
            完整的HTML幻灯片内容
        """
        try:
            # 检查content是否已经是完整的HTML
            content = template_data.get('content', '')
            
            # 如果内容已经是完整的HTML文档，直接使用Premium模板包装纯内容部分
            if content and ('<!DOCTYPE' in content or '<html' in content):
                logger.info("检测到内容已经是完整HTML，提取内容部分并应用Premium模板")
                
                # 提取实际内容（去除HTML结构）
                from bs4 import BeautifulSoup
                try:
                    soup = BeautifulSoup(content, 'html.parser')
                    # 查找主要内容区域
                    main_content = soup.find('body')
                    if main_content:
                        # 获取标题文本用于比较
                        title_text = template_data.get('title', '').strip()
                        
                        # 提取内容，但跳过标题
                        extracted_content = []
                        
                        # 查找所有相关元素
                        for elem in main_content.find_all(['h1', 'h2', 'h3', 'p', 'ul', 'ol', 'div', 'section']):
                            # 跳过与模板标题相同的h1
                            if elem.name == 'h1':
                                elem_text = elem.get_text(strip=True)
                                if elem_text == title_text or 'slide-title' in elem.get('class', []):
                                    logger.info(f"跳过重复标题: {elem_text}")
                                    continue
                            
                            # 跳过空元素和包装div
                            if elem.name == 'div':
                                # 如果是包含其他内容的容器div，提取子元素
                                if elem.get('class') and any(c in ['slide-container', 'content-area', 'slide'] for c in elem.get('class', [])):
                                    continue
                                # 如果div有实际内容，保留
                                if elem.get_text(strip=True):
                                    # 只保留有意义的div
                                    if not any(c in ['slide', 'container'] for c in elem.get('class', [])):
                                        extracted_content.append(str(elem))
                            else:
                                # 保留其他元素
                                extracted_content.append(str(elem))
                        
                        # 更新template_data中的content为纯内容
                        if extracted_content:
                            template_data['content'] = '\n'.join(extracted_content)
                            logger.info(f"提取了 {len(extracted_content)} 个内容元素")
                        else:
                            # 如果没有提取到内容，使用纯文本
                            template_data['content'] = main_content.get_text(strip=True)
                            logger.info("使用纯文本内容")
                    else:
                        # 如果没有body，尝试提取所有文本
                        template_data['content'] = soup.get_text(strip=True)
                        logger.info("没有找到body，使用纯文本")
                except Exception as e:
                    logger.warning(f"解析HTML内容失败: {e}")
                    # 保持原内容
            
            # 检查是否需要特殊处理（如已有HTML需要优化布局）
            content = template_data.get('content', '')
            
            # 只有当内容已经包含HTML结构需要优化时，才使用固定16:9模板
            if content and ('<!DOCTYPE' in content or '<html' in content or 
                          '<div class="two-column">' in content or '<div class="chart-section">' in content):
                logger.info("检测到需要优化的HTML内容，使用固定16:9样式模板")
                
                # 获取标题
                title = template_data.get('title', '未命名幻灯片')
                
                # 使用预定义的16:9样式模板处理已有HTML
                html_content = self._generate_fixed_16_9_template(title, content, slide_type, context)
                
                # 验证生成的HTML是否完整
                if self._validate_html_structure(html_content):
                    logger.info(f"固定16:9模板优化HTML成功，类型: {slide_type}", agent_name="CreateSlideTool")
                    return html_content
            
            # 正常情况：让AI生成内容
            logger.info("使用AI生成幻灯片内容")
            combined_context = {**context, **template_data}
            prompt = self._build_ai_template_prompt(slide_type, combined_context, style)
            logger.info(f"生成的prompt是：{prompt}", agent_name="CreateSlideTool")
            response = self._call_ai_service(prompt, max_tokens=3000)
            
            if response and response.get("choices"):
                html_content = response["choices"][0]["message"]["content"].strip()
                html_content = self._clean_html_output(html_content)
                #logger.info(f"生成的html_content是：{html_content}", agent_name="CreateSlideTool")
                if self._validate_html_structure(html_content):
                    logger.info(f"AI生成HTML成功，类型: {slide_type}", agent_name="CreateSlideTool")
                    return html_content
            
            # 如果AI生成失败，回退到纯模板方法
            logger.warning(f"AI生成失败，回退到纯模板方法", agent_name="CreateSlideTool")
            return self._fallback_template_generation(slide_type, combined_context, style)
                
        except Exception as e:
            logger.error(f"AI+模板生成失败: {str(e)}, 回退到纯模板方法", agent_name="CreateSlideTool")
            return self._fallback_template_generation(slide_type, combined_context, style)
    
    def _generate_fixed_16_9_template(self, title: str, content: str, slide_type: str, context: Dict[str, Any]) -> str:
        """生成固定16:9比例的HTML模板"""
        
        # 导航信息
        slide_number = context.get('slide_number', 1)
        total_slides = context.get('total_slides', 1)
        prev_slide_file = context.get('prev_slide_file', '')
        next_slide_file = context.get('next_slide_file', '')
        
        # 构建导航按钮
        nav_buttons = ""
        if prev_slide_file:
            nav_buttons += f'<a href="{prev_slide_file}" class="nav-button">上一页</a>'
        if next_slide_file:
            nav_buttons += f'<a href="{next_slide_file}" class="nav-button">下一页</a>'
        
        # 处理内容 - 限制内容长度避免超出16:9屏幕
        processed_content = self._optimize_content_for_16_9(content)
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Microsoft YaHei', sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 768px;
            margin: 0;
            padding: 0;
        }}
        
        .slide {{
            /* 严格16:9比例 - 1366x768 */
            width: 1366px;
            height: 768px;
            background: #ffffff;
            border-radius: 8px;
            padding: 40px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15);
            border: 1px solid #e2e8f0;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            color: #1e293b;
        }}
        
        .slide::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.05) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(6, 182, 212, 0.05) 0%, transparent 50%);
            pointer-events: none;
        }}
        
        h1 {{
            font-size: 28px;
            font-weight: bold;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #1e293b, #475569);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            z-index: 1;
            position: relative;
        }}
        
        .content-area {{
            flex: 1;
            overflow: hidden;
            z-index: 1;
            position: relative;
            font-size: 14px;
            line-height: 1.5;
            color: #475569;
        }}
        
        .content-area h2 {{
            font-size: 18px;
            color: #1e40af;
            margin-bottom: 10px;
        }}
        
        .content-area h3 {{
            font-size: 16px;
            color: #3b82f6;
            margin-bottom: 8px;
        }}
        
        .content-area p {{
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        
        .content-area ul, .content-area ol {{
            margin: 8px 0 8px 20px;
        }}
        
        .content-area li {{
            margin-bottom: 4px;
            font-size: 13px;
        }}
        
        .slide-footer {{
            position: absolute;
            bottom: 15px;
            left: 40px;
            right: 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
            font-size: 12px;
        }}
        
        .slide-number {{
            color: rgba(255, 255, 255, 0.6);
            background: rgba(255, 255, 255, 0.05);
            padding: 6px 12px;
            border-radius: 15px;
            border: 1px solid rgba(120, 199, 255, 0.2);
        }}
        
        .navigation {{
            display: flex;
            gap: 8px;
        }}
        
        .nav-button {{
            padding: 6px 12px;
            background: linear-gradient(45deg, #3b82f6, #1d4ed8);
            color: #ffffff;
            text-decoration: none;
            border-radius: 15px;
            font-size: 11px;
            font-weight: 500;
            transition: all 0.3s ease;
        }}
        
        .nav-button:hover {{
            background: linear-gradient(45deg, #1e40af, #1d4ed8);
            transform: translateY(-1px);
        }}
        
        /* 内容优化样式 */
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            height: 100%;
        }}
        
        .column-left, .column-right {{
            overflow: hidden;
        }}
        
        .stats-container {{
            background: rgba(120, 199, 255, 0.1);
            border-left: 2px solid #78c7ff;
            padding: 8px;
            margin: 8px 0;
            border-radius: 4px;
            font-size: 12px;
        }}
        
        .content-card {{
            background: rgba(120, 199, 255, 0.08);
            border: 1px solid rgba(120, 199, 255, 0.2);
            border-radius: 6px;
            padding: 10px;
            margin: 8px 0;
            font-size: 12px;
        }}
        
        .section-heading {{
            font-size: 14px;
            color: #78c7ff;
            margin: 10px 0 8px 0;
            font-weight: 600;
            border-bottom: 1px solid rgba(120, 199, 255, 0.3);
            padding-bottom: 4px;
        }}
        
        /* 图表优化样式 */
        .chart-container {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
            max-height: 250px;
            overflow: hidden;
        }}
        
        .chart-title {{
            font-size: 14px;
            color: #ffffff;
            text-align: center;
            margin-bottom: 10px;
            font-weight: 500;
        }}
        
        .optimized-chart {{
            max-height: 180px !important;
            height: 180px !important;
            width: 100% !important;
        }}
        
        /* 单栏布局样式 */
        .single-column {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
    </style>
</head>
<body>
    <div class="slide">
        <h1>{title}</h1>
        <div class="content-area">
            {processed_content}
        </div>
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                {nav_buttons}
            </div>
        </div>
    </div>
</body>
</html>"""
    
    def _optimize_content_for_16_9(self, content: str) -> str:
        """优化内容以适配16:9屏幕比例"""
        from bs4 import BeautifulSoup
        
        try:
            # 如果内容包含HTML标签，解析并优化
            if '<' in content and '>' in content:
                soup = BeautifulSoup(content, 'html.parser')
                
                # 处理两栏布局 - 确保内容不被截断
                if soup.find('div', class_='two-column'):
                    # 将两栏合并为单栏，避免内容被切断
                    two_col = soup.find('div', class_='two-column')
                    left_col = two_col.find('div', class_='column-left')
                    right_col = two_col.find('div', class_='column-right')
                    
                    # 创建新的单栏容器
                    new_container = soup.new_tag('div')
                    new_container['class'] = 'single-column'
                    
                    # 合并左右列内容
                    if left_col:
                        for elem in left_col.children:
                            if elem.name:  # 只处理标签元素
                                new_container.append(elem.extract())
                    
                    if right_col:
                        for elem in right_col.children:
                            if elem.name:  # 只处理标签元素
                                new_container.append(elem.extract())
                    
                    # 替换原来的两栏布局
                    two_col.replace_with(new_container)
                
                # 限制内容元素数量，避免内容过多
                content_elements = soup.find_all(['p', 'div', 'ul', 'ol', 'h2', 'h3', 'h4', 'h5', 'h6'])
                max_elements = 15  # 16:9屏幕最多显示15个主要元素
                
                if len(content_elements) > max_elements:
                    # 移除超出的元素
                    for elem in content_elements[max_elements:]:
                        elem.decompose()
                    
                    # 添加省略提示
                    ellipsis = soup.new_tag('p')
                    ellipsis.string = "..."
                    ellipsis['style'] = "text-align: center; color: #3b82f6; font-style: italic;"
                    soup.append(ellipsis)
                
                # 处理长段落 - 截断过长的文本
                for p in soup.find_all('p'):
                    if p.string and len(p.string) > 200:
                        p.string = p.string[:200] + "..."
                
                # 处理长列表 - 限制列表项数量
                for ul in soup.find_all(['ul', 'ol']):
                    items = ul.find_all('li')
                    if len(items) > 8:
                        for item in items[8:]:
                            item.decompose()
                        # 添加省略项
                        ellipsis_li = soup.new_tag('li')
                        ellipsis_li.string = "..."
                        ellipsis_li['style'] = "color: #3b82f6; font-style: italic;"
                        ul.append(ellipsis_li)
                
                # 处理图表部分 - 整合到主要内容中
                chart_sections = soup.find_all('div', class_='chart-section')
                text_sections = soup.find_all('div', class_='text-section')
                
                if chart_sections and text_sections:
                    # 将图表整合到文本内容中，而不是分离
                    for i, text_section in enumerate(text_sections):
                        if i < len(chart_sections):
                            # 在文本部分后面直接添加对应的图表
                            chart = chart_sections[i].extract()
                            text_section.append(chart)
                    
                    # 移除剩余的独立图表部分
                    for chart in chart_sections:
                        chart.decompose()
                
                # 优化图表容器样式，使其适合16:9布局
                for chart_container in soup.find_all('div', class_='chart-container'):
                    # 减小图表高度，适配16:9屏幕
                    canvas = chart_container.find('canvas')
                    if canvas:
                        canvas['class'] = canvas.get('class', []) + ['optimized-chart']
                        canvas['style'] = 'max-height: 200px; width: 100%;'
                
                return str(soup)
            
            else:
                # 纯文本内容，直接截断
                if len(content) > 800:
                    content = content[:800] + "..."
                
                # 转换为简单段落
                paragraphs = content.split('\n\n')
                if len(paragraphs) > 8:
                    paragraphs = paragraphs[:8] + ["..."]
                
                html_content = ""
                for para in paragraphs:
                    if para.strip():
                        html_content += f"<p>{para.strip()}</p>\n"
                
                return html_content
                
        except Exception as e:
            logger.warning(f"内容优化失败: {e}")
            # 回退到简单截断
            if len(content) > 1000:
                content = content[:1000] + "..."
            return f"<div>{content}</div>"
    
    def _detect_multi_section_content(self, content_desc: str, title: str) -> bool:
        """检测是否为多section内容页面"""
        if not content_desc:
            return False
        
        # 检查内容中是否包含多个section的指标
        section_indicators = [
            # 直接的section标识
            '1.', '2.', '3.', '4.', 
            '一、', '二、', '三、', '四、',
            '第一', '第二', '第三', '第四',
            'section', 'Section', '章节',
            # 内容结构指标（如果包含多个这样的词汇，可能是多section）
            '分析', '评估', '建议', '措施', '影响', '风险',
            '热点事件', '关联性分析', '潜在影响', '防御建议',
            '工作重点', '技术措施', '流程优化', '能力提升'
        ]
        
        # 统计匹配的指标数量
        matches = sum(1 for indicator in section_indicators if indicator in content_desc or indicator in title)
        
        # 如果匹配超过4个指标，或者明确包含数字编号，认为是多section
        has_numbered_sections = any(indicator in content_desc for indicator in ['1.', '2.', '3.', '一、', '二、', '三、', '第一', '第二'])
        has_multiple_topics = matches >= 4
        
        return has_numbered_sections or has_multiple_topics
    
    def _fallback_template_generation(self, slide_type: str, combined_context: Dict[str, Any], style: str) -> str:
        """回退到纯模板生成方法"""
        # 根据slide_type选择对应的模板生成方法
        if slide_type == "cover":
            return self._generate_cover_slide_template(combined_context, style)
        elif slide_type == "toc":
            return self._generate_toc_slide_template(combined_context, style)
        elif slide_type == "content":
            return self._generate_content_slide_template(combined_context, style)
        elif slide_type == "chart":
            return self._generate_chart_slide_template(combined_context, style)
        elif slide_type == "summary":
            return self._generate_summary_slide_template(combined_context, style)
        else:
            return self._generate_general_slide_template(combined_context, style)
    
    def _build_ai_template_prompt(self, slide_type: str, context: Dict[str, Any], style: str) -> str:
        """构建AI+模板的提示词，让AI直接生成完整的HTML幻灯片"""
        
        # 提取内容描述，如果有的话
        content_desc = context.get('content', '')
        title = context.get('title', '未命名幻灯片')
        
        # 检测是否为多section内容页面
        is_multi_section = self._detect_multi_section_content(content_desc, title)
        
        # 如果content是任务描述，需要明确告诉AI生成实际内容
        content_instruction = ""
        if content_desc and ('生成' in content_desc or '包含' in content_desc or '提供' in content_desc):
            content_instruction = f"""
重要：上面的'content'是任务描述，不是实际内容！
请根据描述生成真实、专业、有价值的内容，而不是重复显示任务描述。

例如：
- 如果描述要求"续费服务价值"，请生成实际的价值说明（如：提升安全防护等级、降低运营成本等）
- 如果描述要求"技术架构图"，请用文字描述架构组件和关系
- 如果描述要求"性能指标"，请生成具体的指标数据（如：响应时间<200ms等）
"""
        
        base_prompt = f"""
你是一个专业的HTML幻灯片生成专家。请根据以下要求直接生成一个完整的Premium高端HTML幻灯片：

幻灯片类型: {slide_type} ({self.slide_types.get(slide_type, {}).get('name', '内容页')})
样式风格: Premium高端设计（16:9 PPT标准比例）
幻灯片标题: {title}

任务要求:
{self._format_context_for_prompt(context)}

{content_instruction}

PREMIUM设计规范（强制约束）:
1. **绝对尺寸**：固定1366×768px（16:9），任何内容不得超出此范围，全局强制overflow:hidden
2. **高度硬约束**：
   - 总高=头部(50-60px)+内容区(708-718px)，合计严格768px
   - 容器内边距上下左右各15px（总占用30px），实际可用高度=768-30=738px
3. **内容量上限**：
   - 单区块最多4个要点，多区块（≤2个）每区最多3个要点
   - 每个要点仅限1行文字（≤25字），超则必须删减
4. **字体硬性限制**：
   - 标题最大28px（多卡片24px），高度≤60px
   - 正文最大16px（多卡片14px），行高1.3倍
   - 字体仅限'Microsoft YaHei', sans-serif
5. **视觉与布局**：
   - 纯白背景(#ffffff)，主色深灰(#1f2937)，强调色仅用#3b82f6
   - 单栏布局，内容区宽≤600px，主容器强制居中(margin:0 auto)
   - 所有元素间距（margin/padding）≤10px，多卡片(3x2)内边距≤8px
6. **图表强制尺寸**：
   - canvas严格≤250×250px
   - 饼图/环形图直径≤180px
   - 柱状图严格≤500×250px

技术强制要求:
1. 生成完整的HTML文档结构（包含<!DOCTYPE html>, <html>, <head>, <body>等）。
2. 用内嵌CSS样式，确保样式完整独立
3. 禁用任何可能导致溢出的属性（如min-height、百分比高度）
4. 布局仅用grid，且grid-template-rows必须设为固定值（头部+内容区=768px）
5. 内容溢出时，优先压缩边距至5px，仍超则删减文字（保留核心词）

内容生成要求:
- 必须生成实际、有价值的内容，不要重复任务描述
- 内容要专业、具体、可操作
- **重要**：生成前必须计算总高度：container.padding + header + content ≤ 768px
- **不要生成页码或页脚**：页面不需要显示页码、页数或任何footer元素
- 如果内容过多无法在一页展示，必须精简内容或建议分成多页
- 如果是技术内容，提供具体的技术细节
- 如果是业务内容，提供实际的业务价值
- 如果包含图表，严格控制图表大小：canvas不超过200x200px，图表应与文字内容协调配置

输出格式要求:
- 直接输出HTML代码，不要包含```html标记
- 不要添加任何解释文本或注释
- 确保输出是纯HTML格式，可直接在浏览器中打开
- 主容器必须居中：使用margin: 0 auto确保水平居中显示
- 不要生成进度条元素（不需要progress bar、进度指示器）
- 不要生成页面进度条或阅读进度显示
- 不要生成页码、页脚或任何类似"第X页/共X页"的元素
- 关键约束：确保所有内容在1366x768px容器内完整显示，绝对不能溢出或被截断
- **CSS必须设置**：
  - body {{ height: 768px; overflow: hidden; }}
  - .container {{ width: 1366px; height: 768px; overflow: hidden; }}"""

        # 添加特定于多section页面的CSS指导
        if is_multi_section and slide_type == "content":
            base_prompt += """
  - **多section页面特殊CSS**：不要在section上设置overflow: hidden，使用min-height和合理的高度分配
"""
        else:
            base_prompt += """
  - 单section页面：内容区域可以设置overflow: hidden防止溢出
"""

        base_prompt += """
请直接返回完整的HTML代码：
"""
        
        # 根据不同的幻灯片类型添加特定要求
        if slide_type == "cover":
            base_prompt += """
封面页PREMIUM设计要求:
- 中央放置大型圆形安全盾牌图标（蓝色渐变，带外圈）
- 主标题大号深灰色字体居中显示(#1f2937)
- 副标题使用蓝色字体，位于主标题下方(#3b82f6)
- 顶部添加行业标签：政府、医疗、教育、企业、金融（圆角矩形标签）
- 底部添加特性标签：通报应对、勒索防护、业务保护、攻防演练（带图标）
- 页面底部显示专业团队信息和时间
- 整体采用居中对称布局
- 背景使用纯白色(#ffffff)，营造专业简洁感
"""
        elif slide_type == "toc":
            # 检查是否有实际章节列表
            all_chapters = context.get('all_chapters', [])
            chapter_list = context.get('chapter_list', [])
            logger.info(f"TOC生成 - context包含: {list(context.keys())}", agent_name="CreateSlideTool")
            logger.info(f"TOC生成 - all_chapters: {all_chapters}", agent_name="CreateSlideTool")
            logger.info(f"TOC生成 - chapter_list: {chapter_list}", agent_name="CreateSlideTool")
            
            if all_chapters or chapter_list:
                chapters = all_chapters or chapter_list
                chapter_list_str = "\n".join([f"{i}. {ch}" for i, ch in enumerate(chapters, 1)])
                base_prompt += f"""
目录页PREMIUM设计要求:
- 顶部居中显示"目录"标题，使用深灰色大字体(#1f2937)
- 列出以下实际章节（不要使用通用模板内容）：
{chapter_list_str}
- 每个章节用圆形编号和优雅的连接线
- 章节标题使用清晰的字体(18-20px)
- 页码使用简洁的格式(P1, P2等)
- 整体布局居中对称，使用蓝色强调色(#3b82f6)
- 背景使用纯白色(#ffffff)
**重要**：必须使用上述提供的实际章节，不要生成通用的模板内容！
"""
            else:
                base_prompt += """
目录页PREMIUM设计要求:
- 顶部居中显示"目录"标题，使用深灰色大字体(#1f2937)
- 根据上下文信息生成相应的章节列表
- 每个章节用圆形编号和优雅的连接线
- 章节标题使用清晰的字体(18-20px)
- 页码使用简洁的格式(P1, P2等)
- 整体布局居中对称，使用蓝色强调色(#3b82f6)
- 背景使用纯白色(#ffffff)
"""
        elif slide_type == "content":
            if is_multi_section:
                base_prompt += """
内容页PREMIUM设计要求（多Section布局）:
- 顶部居中标题，使用深灰色大字体(#1f2937)，高度控制在40px内
- **多section页面特殊处理**：
  - 使用flexbox布局，设置flex-direction: column
  - 容器总高度限制在728px内（去除padding后的可用高度）
  - 标题区域：40px，内容区域：688px
  - **动态高度分配策略**：
    * 4个section: 每个约150px可用高度
    * 5个section: 每个约120px可用高度  
    * 6个或更多: 每个约100px可用高度
  - section之间间距：4-5个section用8px，6个以上用6px
  - section内部padding：4个section用12px，5个section用10px，6个以上用8px
  - 字体动态缩放：
    * 4个section: 标题16px，正文13px
    * 5个section: 标题15px，正文12px
    * 6个以上: 标题14px，正文11px
  - **重要**：不使用overflow: hidden，而是使用flex: 1和min-height
  - 每个section使用 flex: 1 自动分配空间，确保内容完整显示
  - 如果内容过多，自动调整：减少padding、缩小字体、压缩间距
- 每个section使用轻微圆角和浅色边框
- 配色方案：白色背景+深灰色文字(#1f2937)+蓝色强调(#3b82f6)
"""
            else:
                base_prompt += """
内容页PREMIUM设计要求:
- 顶部居中标题，使用深灰色大字体(#1f2937)，高度不超过50px
- 内容区域使用卡片式布局，带圆角和阴影
- 重要数据使用大号数字突出显示（但不超过24px）
- 使用现代化图标配合文本说明（图标大小不超过40px）
- 数据项采用三列或四列网格布局
- 每个数据卡片使用浅灰色背景(#f8fafc)或白色背景
- 配色方案：白色背景+深灰色文字(#1f2937)+蓝色强调(#3b82f6)
"""
        elif slide_type == "chart":
            base_prompt += """
图表页PREMIUM设计要求:
- 图表尺寸紧凑合理：canvas不超过200x200px，饼图直径不超过150px
- 使用现代化配色方案：蓝色系渐变(#3b82f6到#1e40af)
- 图表与数据说明并排布局，各占页面50%空间
- 右侧添加数据卡片展示关键指标，卡片使用白色背景
- 数据标签使用清晰的字体(12px-14px)和颜色
- 图例紧凑排列，避免占用过多空间
- 整体保持视觉平衡，图表不应占据页面主导地位
- 优先显示数据解释和关键洞察，图表作为辅助说明
"""
        elif slide_type == "summary":
            base_prompt += """
总结页PREMIUM设计要求:
- 居中显示核心成果数据（使用大号数字）
- 采用网格卡片布局展示关键要点，卡片使用白色背景
- 使用图标 + 标题 + 描述的组合
- 添加成功指标的可视化展示
- 使用蓝色系(#3b82f6)强调重要信息
- 底部添加建议或下一步计划
- 整体布局简洁、重点突出，保持白色背景主题
- 保持与整体风格的一致性
"""
        
        return base_prompt
    
    def _format_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """将上下文信息格式化为适合AI理解的文本"""
        formatted_lines = []
        
        for key, value in context.items():
            if isinstance(value, dict):
                formatted_lines.append(f"{key}:")
                for sub_key, sub_value in value.items():
                    formatted_lines.append(f"  - {sub_key}: {sub_value}")
            elif isinstance(value, list):
                formatted_lines.append(f"{key}:")
                for i, item in enumerate(value, 1):
                    formatted_lines.append(f"  {i}. {item}")
            else:
                formatted_lines.append(f"{key}: {value}")
        
        return "\n".join(formatted_lines)
    
    def _call_ai_service(self, prompt: str, max_tokens: int = 3000) -> Dict[str, Any]:
        """调用AI服务生成内容"""
        try:
            response = generate_system_response(
                self.system_prompt,
                prompt,
                temperature=0.7
            )
            
            # 返回类似OpenAI API的格式
            return {
                "choices": [
                    {
                        "message": {
                            "content": response
                        }
                    }
                ]
            }
        except Exception as e:
            logger.error(f"AI服务调用失败: {str(e)}", agent_name="CreateSlideTool")
            return None
    
    def _get_slide_styles(self, style: str = "professional") -> str:
        """获取幻灯片样式 - PPT 16:9标准尺寸"""
        # Premium风格样式
        if style == "premium" or style == "professional":
            return """
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Microsoft YaHei', sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 768px;
            margin: 0;
            padding: 0;
        }
        
        .slide {
            /* 标准PPT 16:9比例 - 1366x768 */
            width: 1366px;
            height: 768px;
            background: linear-gradient(135deg, #0a1628 0%, #1e3a8a 100%);
            border-radius: 8px;
            padding: 48px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        
        /* 添加背景纹理效果 */
        .slide::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                radial-gradient(circle at 20% 20%, rgba(59, 130, 246, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(6, 182, 212, 0.15) 0%, transparent 50%);
            pointer-events: none;
        }
        
        h1 {
            font-size: 36px;
            font-weight: bold;
            margin-bottom: 24px;
            background: linear-gradient(135deg, #ffffff, #e2e8f0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            z-index: 1;
        }
        
        h2 {
            font-size: 28px;
            color: #60a5fa;
            margin-bottom: 16px;
            text-align: center;
            z-index: 1;
        }
        
        h3 {
            font-size: 20px;
            color: #93c5fd;
            margin-bottom: 12px;
            z-index: 1;
        }
        
        p {
            font-size: 16px;
            line-height: 1.6;
            color: #cbd5e1;
            margin-bottom: 16px;
            z-index: 1;
        }
        
        ul, ol {
            margin-left: 24px;
            margin-bottom: 16px;
            z-index: 1;
        }
        
        li {
            font-size: 14px;
            line-height: 1.6;
            color: #cbd5e1;
            margin-bottom: 8px;
        }
        
        .chart-container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            z-index: 1;
        }
        
        .data-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin: 20px 0;
            z-index: 1;
        }
        
        .data-card {
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(6, 182, 212, 0.2));
            border: 1px solid rgba(59, 130, 246, 0.4);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
        }
        
        .data-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #3b82f6;
            margin-bottom: 8px;
        }
        
        .data-card .label {
            font-size: 12px;
            color: #94a3b8;
        }
        
        .slide-footer {
            position: absolute;
            bottom: 24px;
            left: 48px;
            right: 48px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            color: #94a3b8;
            font-size: 12px;
            z-index: 1;
        }
        
        /* 确保内容不会溢出 */
        .slide-content {
            max-height: calc(100% - 60px);
            overflow-y: auto;
            scrollbar-width: thin;
            scrollbar-color: rgba(255, 255, 255, 0.2) transparent;
            z-index: 1;
        }
        
        .slide-content::-webkit-scrollbar {
            width: 6px;
        }
        
        .slide-content::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .slide-content::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 3px;
        }
        
        /* 响应式适配 */
        @media (max-width: 1000px) {
            .slide {
                width: 100%;
                max-width: 1366px;
                height: auto;
                min-height: 768px;
                aspect-ratio: 16/9;
            }
        }
    </style>
            """
        else:
            # 默认样式
            return """
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 40px;
            background: #f3f4f6;
        }
        .slide {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 60px;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        h1 { color: #1f2937; margin-bottom: 30px; }
        h2 { color: #374151; margin-bottom: 20px; }
        h3 { color: #4b5563; margin-bottom: 15px; }
        p { color: #6b7280; line-height: 1.6; }
    </style>
            """
    
    def _clean_html_output(self, html_content: str) -> str:
        """清理AI生成的HTML内容，移除不需要的标记"""
        import re
        
        # 移除可能的markdown代码块标记
        html_content = re.sub(r'^```html\s*\n?', '', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'^```\s*\n?', '', html_content, flags=re.MULTILINE)
        html_content = re.sub(r'\n?```$', '', html_content, flags=re.MULTILINE)
        
        # 移除多余的空行
        html_content = re.sub(r'\n\s*\n\s*\n', '\n\n', html_content)
        
        # 确保HTML以<!DOCTYPE开始
        if not html_content.strip().startswith('<!DOCTYPE'):
            # 查找DOCTYPE的位置并从那里开始
            doctype_match = re.search(r'<!DOCTYPE[^>]*>', html_content)
            if doctype_match:
                html_content = html_content[doctype_match.start():]
        
        return html_content.strip()
    
    def _validate_html_structure(self, html_content: str) -> bool:
        """验证生成的HTML是否具有基本的完整结构"""
        if not html_content or len(html_content.strip()) < 100:
            return False
        
        # 检查必要的HTML标签
        required_tags = ['<!DOCTYPE html>', '<html', '<head', '<body', '</html>']
        content_lower = html_content.lower()
        
        for tag in required_tags:
            if tag.lower() not in content_lower:
                logger.warning(f"HTML验证失败：缺少标签 {tag}", agent_name="CreateSlideTool")
                return False
        
        # 检查是否包含实际内容（不只是模板框架）
        content_indicators = ['<h1', '<h2', '<h3', '<p', '<div', 'class=']
        content_found = any(indicator in content_lower for indicator in content_indicators)
        
        if not content_found:
            logger.warning("HTML验证失败：缺少实际内容", agent_name="CreateSlideTool")
            return False
        
        return True
    
    def _generate_cover_slide_template(self, data: Dict[str, Any], style: str) -> str:
        """生成Premium风格封面页模板"""
        title = data.get("title", "安全运营工作报告")
        subtitle = data.get("subtitle", "7*24H全时守护 安全效果护航业务稳定运行")
        metadata = data.get("metadata", {})
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Microsoft YaHei', sans-serif;
            background: #f5f5f5;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 768px;
            margin: 0;
            padding: 0;
        }}
        
        .slide {{
            /* 标准PPT 16:9比例 - 1366x768 */
            width: 1366px;
            height: 768px;
            background: linear-gradient(135deg, #0a1628 0%, #1e3a8a 100%);
            border-radius: 8px;
            padding: 48px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
        }}
        
        .slide::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                radial-gradient(circle at 25% 25%, rgba(59, 130, 246, 0.15) 0%, transparent 50%),
                radial-gradient(circle at 75% 75%, rgba(6, 182, 212, 0.15) 0%, transparent 50%);
            pointer-events: none;
        }}
        
        .security-icon {{
            width: 80px;
            height: 80px;
            margin: 0 auto 20px;
            background: linear-gradient(135deg, #3b82f6, #06b6d4);
            border-radius: 50%;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
            z-index: 1;
        }}
        
        .security-icon::before {{
            content: '🛡';
            font-size: 36px;
            color: white;
        }}
        
        .title {{
            font-size: 32px;
            font-weight: bold;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #ffffff, #e2e8f0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1.2;
            z-index: 1;
        }}
        
        .subtitle {{
            font-size: 18px;
            color: #3b82f6;
            margin-bottom: 24px;
            font-weight: 300;
            z-index: 1;
        }}
        
        .tags {{
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            z-index: 1;
        }}
        
        .tag {{
            background: rgba(59, 130, 246, 0.2);
            border: 1px solid rgba(59, 130, 246, 0.4);
            padding: 6px 12px;
            border-radius: 16px;
            font-size: 12px;
            color: #60a5fa;
        }}
        
        .features {{
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 0;
            flex-wrap: wrap;
            z-index: 1;
        }}
        
        .feature-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 14px;
            color: #cbd5e1;
        }}
        
        .feature-item::before {{
            content: '📋';
            font-size: 14px;
        }}
        
        .metadata-info {{
            position: absolute;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            text-align: center;
            z-index: 1;
        }}
        
        .metadata-item {{
            font-size: 12px;
            color: #94a3b8;
            margin: 3px 0;
        }}
        
        /* 响应式适配 */
        @media (max-width: 1000px) {{
            .slide {{
                width: 100%;
                max-width: 1366px;
                height: auto;
                min-height: 768px;
                aspect-ratio: 16/9;
                padding: 32px;
            }}
            .title {{
                font-size: 28px;
            }}
            .subtitle {{
                font-size: 16px;
            }}
            .features {{
                gap: 16px;
            }}
            .feature-item {{
                font-size: 12px;
            }}
        }}
    </style>
</head>
<body>
    <div class="slide cover">
        <div class="security-icon"></div>
        <h1 class="title">{title}</h1>
        <p class="subtitle">{subtitle}</p>
        
        <div class="tags">
            <span class="tag">政府</span>
            <span class="tag">医疗</span>
            <span class="tag">教育</span>
            <span class="tag">企业</span>
            <span class="tag">金融</span>
        </div>
        
        <div class="features">
            <div class="feature-item">通报应对</div>
            <div class="feature-item">勒索防护</div>
            <div class="feature-item">业务保护</div>
            <div class="feature-item">攻防演练</div>
        </div>
        
        <div class="metadata-info">
            <div class="metadata-item">专业安全团队出品</div>
            <div class="metadata-item">{metadata.get('generation_time', self._get_current_time())}</div>
        </div>
    </div>
</body>
</html>"""
    
    def _generate_toc_slide_template(self, data: Dict[str, Any], style: str) -> str:
        """生成目录页模板"""
        title = data.get("title", "目录")
        toc_items = data.get("toc_items", [])
        slide_number = data.get('slide_number', 2)
        total_slides = data.get('total_slides', 10)
        prev_slide = data.get('prev_slide', '#')
        next_slide = data.get('next_slide', '#')
        
        # 生成目录项HTML
        toc_html = ""
        for i, item in enumerate(toc_items, 1):
            toc_html += f"""
            <div class="toc-item">
                <div class="number">{i}</div>
                <h3>{item.get('title', f'章节 {i}')}</h3>
                <p>{item.get('description', '相关内容描述')}</p>
            </div>
            """
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {self._get_slide_styles(style)}
</head>
<body>
    <div class="slide toc">
        <div class="slide-content">
            <h1>{title}</h1>
            <div class="toc-grid">
                {toc_html}
            </div>
        </div>
        
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                <a href="{prev_slide}" class="nav-button">上一页</a>
                <a href="{next_slide}" class="nav-button">下一页</a>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    def _generate_contextual_content(self, title: str) -> str:
        """根据标题生成上下文相关的示例内容"""
        title_lower = title.lower()
        
        # 根据标题关键词生成相应的示例内容
        if '工作目标' in title or '计划' in title:
            return """
            <h2>Q3-Q4工作规划</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number">3</div>
                    <div class="stat-label">重点项目</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">85%</div>
                    <div class="stat-label">目标完成率</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">12</div>
                    <div class="stat-label">关键里程碑</div>
                </div>
            </div>
            <h3>核心目标</h3>
            <ul>
                <li><strong>安全运营优化：</strong>提升监控覆盖率至98%，响应时间缩短至2小时内</li>
                <li><strong>技术能力建设：</strong>完成新一代安全平台部署，提升自动化处置能力</li>
                <li><strong>服务质量提升：</strong>建立7×24小时专业运营团队，确保业务连续性</li>
            </ul>
            """
        
        elif '续费' in title or '服务价值' in title:
            return """
            <h2>服务续费价值分析</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number">300万</div>
                    <div class="stat-label">年度投资回报</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">99.8%</div>
                    <div class="stat-label">服务可用性</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">2小时</div>
                    <div class="stat-label">平均响应时间</div>
                </div>
            </div>
            <h3>续费核心价值</h3>
            <ul>
                <li><strong>成本优势：</strong>相比自建团队节省60%运营成本</li>
                <li><strong>专业保障：</strong>7×24小时专业安全运营服务</li>
                <li><strong>技术升级：</strong>持续的安全技术更新和威胁情报支撑</li>
                <li><strong>合规支持：</strong>满足行业监管要求，降低合规风险</li>
            </ul>
            """
        
        elif '问题' in title or '风险' in title:
            return """
            <h2>关键问题识别</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number">156</div>
                    <div class="stat-label">安全事件</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">23</div>
                    <div class="stat-label">高危漏洞</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">4.2小时</div>
                    <div class="stat-label">平均处置时间</div>
                </div>
            </div>
            <h3>主要风险点</h3>
            <ul>
                <li><strong>系统漏洞：</strong>发现23个高危漏洞，需紧急修复</li>
                <li><strong>访问控制：</strong>部分系统存在权限过度分配问题</li>
                <li><strong>监控盲区：</strong>核心业务系统缺乏实时监控</li>
                <li><strong>应急响应：</strong>事件响应流程需要优化提升</li>
            </ul>
            """
        
        elif '解决方案' in title or '建议' in title:
            return """
            <h2>改进方案建议</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number">5</div>
                    <div class="stat-label">核心方案</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">3个月</div>
                    <div class="stat-label">实施周期</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number">80%</div>
                    <div class="stat-label">预期改善</div>
                </div>
            </div>
            <h3>重点改进措施</h3>
            <ul>
                <li><strong>技术升级：</strong>部署新一代安全监控平台，提升检测能力</li>
                <li><strong>流程优化：</strong>建立标准化事件响应流程，缩短处理时间</li>
                <li><strong>人员培训：</strong>加强安全意识培训，提升整体安全水平</li>
                <li><strong>制度完善：</strong>建立完善的安全管理制度和操作规范</li>
            </ul>
            """
        
        else:
            # 通用内容
            return f"""
            <h2>内容概述</h2>
            <p>本节将详细介绍{title}的相关内容，包括核心要点、技术方案和实施建议。</p>
            <h3>主要内容</h3>
            <ul>
                <li>核心要点分析与总结</li>
                <li>技术实现方案说明</li>
                <li>业务价值与效益评估</li>
                <li>具体实施步骤与建议</li>
            </ul>
            <div class="note" style="margin-top: 20px; padding: 15px; background: rgba(120, 199, 255, 0.1); border-left: 3px solid #78c7ff; border-radius: 4px;">
                <p><strong>说明：</strong>以上为示例内容，实际报告中将包含具体的业务数据和详细分析。</p>
            </div>
            """
    
    def _generate_content_slide_template(self, data: Dict[str, Any], style: str) -> str:
        """生成内容页模板"""
        title = data.get("title", "内容页面")
        raw_content = data.get("content", "这里是页面内容...")
        slide_number = data.get('slide_number', 3)
        total_slides = data.get('total_slides', 10)
        prev_slide = data.get('prev_slide', '#')
        next_slide = data.get('next_slide', '#')
        
        # 如果content是任务描述，生成占位符内容而不是直接显示
        if raw_content and ('生成' in raw_content or '包含' in raw_content or '提供' in raw_content or 
                           '重点突出' in raw_content or '样式要求' in raw_content):
            # 这是任务描述，生成基于标题的具体示例内容
            content = self._generate_contextual_content(title)
        else:
            content = raw_content
        
        charts = data.get("charts", [])
        
        # 生成图表HTML
        charts_html = ""
        chart_scripts = ""
        
        if charts:
            for chart in charts:
                chart_id = chart.get("id", f"chart_{len(charts_html)}")
                chart_title = chart.get("title", "数据图表")
                
                charts_html += f"""
                <div class="chart-container full-width-chart">
                    <h3 class="chart-title">{chart_title}</h3>
                    <canvas id="{chart_id}" class="chart-canvas"></canvas>
                </div>
                """
            
            chart_scripts = self._generate_chart_scripts(charts)
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    {self._get_slide_styles(style)}
</head>
<body>
    <div class="slide content">
        <div class="slide-content">
            <h1>{title}</h1>
            <div class="content-body">
                {self._format_content_for_html(content)}
                {charts_html}
            </div>
        </div>
        
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                <a href="{prev_slide}" class="nav-button">上一页</a>
                <a href="{next_slide}" class="nav-button">下一页</a>
            </div>
        </div>
    </div>
    
    {chart_scripts}
</body>
</html>"""
    
    def _generate_chart_slide_template(self, data: Dict[str, Any], style: str) -> str:
        """生成图表页模板"""
        return self._generate_content_slide_template(data, style)  # 复用内容页模板
    
    def _generate_summary_slide_template(self, data: Dict[str, Any], style: str) -> str:
        """生成总结页模板"""
        title = data.get("title", "总结")
        summary_points = data.get("summary_points", [])
        slide_number = data.get('slide_number', 10)
        total_slides = data.get('total_slides', 10)
        prev_slide = data.get('prev_slide', '#')
        
        # 生成总结点HTML
        points_html = ""
        for point in summary_points:
            points_html += f"""
            <div class="content-card">
                <h3>{point.get('title', '要点')}</h3>
                <p>{point.get('content', '内容描述')}</p>
            </div>
            """
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {self._get_slide_styles(style)}
</head>
<body>
    <div class="slide content">
        <div class="slide-content">
            <h1>{title}</h1>
            <div class="content-body">
                {points_html}
            </div>
        </div>
        
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                <a href="{prev_slide}" class="nav-button">上一页</a>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    def _generate_general_slide_template(self, data: Dict[str, Any], style: str) -> str:
        """生成通用页面模板"""
        return self._generate_content_slide_template(data, style)  # 复用内容页模板
    
    def _get_current_time(self) -> str:
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def generate_with_ai_template(self, task: str, context: Dict[str, Any],
                                 slide_number: int = 1, material_content: str = "") -> Dict[str, Any]:
        """
        基于AI构建模板的方法，严格遵循硬性约束，由LLM自主判断和生成可视化内容

        Args:
            task: 生成任务描述
            context: 上下文信息
            slide_number: 页码
            material_content: 基础材料内容

        Returns:
            生成结果字典
        """
        try:
            # 调试：检查task和material_content是否正确
            print(f"DEBUG: generate_with_ai_template - 构建prompt前:")
            print(f"  task: {task[:200] if len(task) > 200 else task}")
            print(f"  task长度: {len(task)}")
            print(f"  material_content前200字符: {material_content[:200] if len(material_content) > 200 else material_content}")
            print(f"  material_content长度: {len(material_content)}")

            # 构建AI生成Prompt - 让LLM自主判断是否需要图表和可视化
            prompt = f"""
按照下列要求基于材料生成PPT：

{self.ai_template_constraints}

### 模板：
{self.base_template}

### 任务要求：
{task}

### 材料内容：
{material_content}

### 页码：
{slide_number}

### 可视化选择指南：
请根据材料内容智能判断使用何种可视化方式：

**场景匹配**：
- 数值对比（评分、统计）→ 柱状图或数据卡片
- 百分比数据 → 进度条
- 结构化数据 → 表格
- 要点总结 → 要点列表
- 趋势变化 → 折线图
- 占比分布（整体构成、分类占比、层级占比）→ 饼图或环形图

### 可用的CSS样式类：
- **data-card / stat-card**：数据展示（高度≤200px）
- **stats-container + stat-box**：2列网格布局（每个≤180px）
- **ip-table**：表格（最多6行）
- **progress-chart**：进度条组
- **bullet-point**：要点列表（最多4项）
- **css-chart-container + bar-chart**：柱状图

### CSS图表生成指南（如需要）：
如果判断需要图表，请使用以下CSS图表样式：

**紧凑型柱状图示例（最多4项数据）**：
```html
<div class="css-chart-container" style="height: 180px; margin: 15px 0;">
    <h3 style="font-size: 24px; margin-bottom: 15px;">关键评分对比</h3>
    <div class="bar-chart" style="height: 120px;">
        <div class="bar-item" style="height: 85%;">
            <div class="bar-value">85分</div>
            <div class="bar-label">威胁管理</div>
        </div>
        <div class="bar-item" style="height: 92%;">
            <div class="bar-value">92分</div>
            <div class="bar-label">资产管理</div>
        </div>
    </div>
</div>
```

**紧凑型进度条图表示例（最多3项）**：
```html
<div class="progress-chart" style="margin: 15px 0;">
    <div class="progress-item" style="margin: 8px 0;">
        <div class="progress-label" style="font-size: 18px;">
            <span>闭环率</span>
            <span>95.2%</span>
        </div>
        <div class="progress-track" style="height: 16px;">
            <div class="progress-fill" style="width: 95.2%;"></div>
        </div>
    </div>
</div>
```

**双列数据卡片布局示例**：
```html
<div class="stats-container" style="margin: 20px 0; gap: 20px;">
    <div class="stat-box" style="height: 160px;">
        <div class="stat-content">
            <div class="stat-title" style="font-size: 36px;">456个</div>
            <p style="font-size: 18px;">发现漏洞</p>
        </div>
    </div>
    <div class="stat-box" style="height: 160px;">
        <div class="stat-content">
            <div class="stat-title" style="font-size: 36px;">23次</div>
            <p style="font-size: 18px;">安全攻击</p>
        </div>
    </div>
</div>
```

**饼图示例（适合展示比例关系）**：
```html
<div class="pie-chart-container">
    <div class="pie-chart-css" style="--slice1: 90deg; --slice2: 180deg; --slice3: 270deg; --slice4: 360deg;">
    </div>
    <div class="pie-legend">
        <div class="pie-legend-item">
            <div class="pie-legend-color" style="background: rgb(10, 66, 117);"></div>
            <span>威胁管理 25%</span>
        </div>
        <div class="pie-legend-item">
            <div class="pie-legend-color" style="background: #3498db;"></div>
            <span>资产管理 25%</span>
        </div>
        <div class="pie-legend-item">
            <div class="pie-legend-color" style="background: #95d5ff;"></div>
            <span>事件管理 25%</span>
        </div>
        <div class="pie-legend-item">
            <div class="pie-legend-color" style="background: #ffd700;"></div>
            <span>合规管理 25%</span>
        </div>
    </div>
</div>
```

**折线图示例（适合展示趋势变化）**：
```html
<div class="line-chart-container">
    <div class="line-chart-grid">
        <div class="line-chart-line">
            <!-- 使用SVG绘制折线 -->
            <svg width="100%" height="100%" viewBox="0 0 400 200" preserveAspectRatio="none">
                <polyline class="line-chart-path"
                    points="0,180 100,140 200,100 300,120 400,80" />
            </svg>
            <!-- 数据点 -->
            <div class="line-chart-point" style="left: 0%; bottom: 10%;" data-value="10"></div>
            <div class="line-chart-point" style="left: 25%; bottom: 30%;" data-value="30"></div>
            <div class="line-chart-point" style="left: 50%; bottom: 50%;" data-value="50"></div>
            <div class="line-chart-point" style="left: 75%; bottom: 40%;" data-value="40"></div>
            <div class="line-chart-point" style="left: 100%; bottom: 60%;" data-value="60"></div>
        </div>
        <div class="line-chart-labels">
            <span>1月</span>
            <span>2月</span>
            <span>3月</span>
            <span>4月</span>
            <span>5月</span>
        </div>
    </div>
    <div class="line-chart-values">
        <span>100</span>
        <span>75</span>
        <span>50</span>
        <span>25</span>
        <span>0</span>
    </div>
</div>
```

### 生成要求：
- 页码必须为{slide_number}
- 严格遵循上述所有硬性约束和布局控制要求（见ai_template_constraints）
- 根据内容智能选择合适的可视化方式
- 确保生成的HTML代码完整、有效、不超出页面范围

请生成完整的HTML代码。
"""

            # 使用AI生成内容
            logger.info(f"使用AI模板生成方法创建幻灯片: {task[:50]}...", agent_name="CreateSlideTool")
            logger.info(f"prompt是: {prompt}", agent_name="CreateSlideTool")

            # 分离系统提示和用户消息
            system_prompt = """你是一个专业的PPT设计助手，专门创建高质量的HTML格式幻灯片。

核心任务：
1. 严格遵循ai_template_constraints中的所有硬性约束
2. 智能判断内容类型，选择最适合的可视化方式
3. 确保内容不超出页面范围（总高度≤900px）
4. 精简内容，只展示最重要的信息

可视化决策原则：
- 数值对比 → 柱状图（最多4项）或数据卡片
- 百分比/占比 → 进度条（最多3项）或饼图（展示比例关系）
- 趋势变化 → 折线图（时间序列数据，最多5个数据点）
- 多指标 → 双列网格布局
- 要点 → 列表（最多4项）
- 组成分析 → 饼图（展示各部分占比，最多5个分类）
- 当文字描述更清晰时，保持文字形式

布局优化要点：
- 优先水平排列，充分利用1920px宽度
- 控制每个元素高度≤200px
- 精简内容，突出关键信息
- 合理使用空白增强可读性
"""

            response = generate_system_response(
                system_prompt=system_prompt,
                user_message=prompt,
                max_tokens=8000,
                temperature=0.1
            )

            if not response:
                raise Exception("AI生成响应为空")

            # 清理和验证生成的HTML
            html_content = self._clean_and_validate_html(response, slide_number)

            logger.info(f"AI模板生成成功，页码: {slide_number}，由LLM自主设计可视化内容", agent_name="CreateSlideTool")

            return {
                "success": True,
                "task": task,
                "slide_content": html_content,
                "slide_type": "ai_template",
                "metadata": {
                    "generated_at": self._get_current_time(),
                    "slide_number": slide_number,
                    "method": "ai_template",
                    "constraints_applied": True
                }
            }

        except Exception as e:
            logger.error(f"AI模板生成失败: {str(e)}", agent_name="CreateSlideTool")
            return {
                "success": False,
                "error": f"AI模板生成失败: {str(e)}",
                "slide_content": None
            }

    def _clean_and_validate_html(self, html_content: str, slide_number: int) -> str:
        """
        清理和验证生成的HTML内容

        Args:
            html_content: 原始HTML内容
            slide_number: 页码

        Returns:
            清理后的HTML内容
        """
        # 提取HTML部分
        if "```html" in html_content:
            start = html_content.find("```html") + 7
            end = html_content.find("```", start)
            if end != -1:
                html_content = html_content[start:end].strip()
        elif "<!DOCTYPE html>" in html_content:
            start = html_content.find("<!DOCTYPE html>")
            html_content = html_content[start:].strip()

        # 确保页码正确
        html_content = re.sub(
            r'<div class="page-number">.*?</div>',
            f'<div class="page-number">{slide_number}</div>',
            html_content
        )

        # 移除可能的自定义类名标签（违反约束7）
        html_content = re.sub(
            r'<span class="[^"]*">([^<]*)</span>',
            r'\1',
            html_content
        )

        # 确保尺寸约束
        if 'width: 1920px' not in html_content:
            html_content = html_content.replace(
                'class="slide-container"',
                'class="slide-container" style="width: 1920px; min-height: 1080px;"'
            )

        return html_content
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行幻灯片创建任务 - 仅使用AI模板模式

        Args:
            input_data: 输入数据，包含生成任务和参数

        Returns:
            生成结果字典
        """
        if not self.enabled:
            return {
                "success": False,
                "error": "幻灯片创建工具未启用",
                "slide_content": None
            }

        # 获取核心参数
        task = input_data.get("task", "")
        material_content = input_data.get("material_content", "")
        slide_number = input_data.get("slide_number", 1)

        # 调试日志
        print(f"DEBUG: CreateSlideTool.execute - 收到参数:")
        print(f"  task: {task[:100]}..." if len(task) > 100 else f"  task: {task}")
        print(f"  task长度: {len(task)}")
        print(f"  material_content长度: {len(material_content)}")
        print(f"  slide_number: {slide_number}")

        # 如果task过长，发出警告
        if task and len(task) > 200:
            print(f"WARNING: task参数异常长({len(task)}字符)，应该是简短的生成指令！")
        context = input_data.get("context", {})

        # 向后兼容处理
        # 1. 从旧参数构建task
        if not task:
            slide_type = input_data.get("slide_type", "content")
            title = input_data.get("title", "")
            if title:
                task = f"生成{slide_type}类型的幻灯片，标题为：{title}"
            else:
                task = f"生成{slide_type}类型的幻灯片"

        # 2. 从template_data构建material_content
        if not material_content and "template_data" in input_data:
            template_data = input_data.get("template_data", {})
            material_content = "\n".join([f"{k}: {v}" for k, v in template_data.items() if v])

        # 3. 检查use_ai_template标志（向后兼容）
        use_ai_template = input_data.get("use_ai_template", True)  # 默认为True

        # 4. 如果仍然没有task，返回错误
        if not task:
            return {
                "success": False,
                "error": "生成任务不能为空",
                "slide_content": None
            }

        try:
            logger.info(f"开始幻灯片创建任务 (AI模板模式): {task[:50]}..., 页码: {slide_number}", agent_name="CreateSlideTool")

            # 始终使用AI模板构建方法
            return self.generate_with_ai_template(task, context, slide_number, material_content)

        except Exception as e:
            error_msg = f"幻灯片创建失败: {str(e)}"
            logger.error(error_msg, agent_name="CreateSlideTool")

            return {
                "success": False,
                "error": error_msg,
                "task": task,
                "slide_content": None
            }
    
    def _generate_cover_slide(self, task: str, context: Dict[str, Any], 
                            style: str, max_length: int) -> str:
        """生成封面页内容"""
        prompt = self._build_cover_slide_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.8
        )
        
        content = self._post_process_content(response, style, max_length)
        return content
    
    def _generate_toc_slide(self, task: str, context: Dict[str, Any], 
                          style: str, max_length: int) -> str:
        """生成目录页内容"""
        prompt = self._build_toc_slide_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.6
        )
        
        content = self._post_process_content(response, style, max_length)
        return content
    
    def _generate_content_slide(self, task: str, context: Dict[str, Any], 
                              style: str, max_length: int) -> str:
        """生成内容页内容"""
        prompt = self._build_content_slide_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        return content
    
    def _generate_chart_slide(self, task: str, context: Dict[str, Any], 
                            style: str, max_length: int) -> str:
        """生成图表页内容"""
        prompt = self._build_chart_slide_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        return content
    
    def _generate_summary_slide(self, task: str, context: Dict[str, Any], 
                               style: str, max_length: int) -> str:
        """生成总结页内容"""
        prompt = self._build_summary_slide_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        return content
    
    def _generate_general_slide(self, task: str, context: Dict[str, Any], 
                               style: str, max_length: int) -> str:
        """生成通用幻灯片内容"""
        prompt = self._build_general_slide_prompt(task, context, style, max_length)
        
        response = generate_system_response(
            self.system_prompt,
            prompt,
            temperature=0.7
        )
        
        content = self._post_process_content(response, style, max_length)
        return content
    
    def _build_cover_slide_prompt(self, task: str, context: Dict[str, Any], 
                                 style: str, max_length: int) -> str:
        """构建封面页生成提示"""
        prompt = f"""
请为以下任务生成PPT封面页内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 生成专业的封面页内容
2. 包含主标题、副标题（如果需要）
3. 包含公司/组织名称
4. 包含时间信息
5. 包含汇报人信息（如果有）
6. 使用{style}的写作风格
7. 内容简洁有力，突出重点
8. 内容长度控制在{max_length}字符以内

请直接生成封面页内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_toc_slide_prompt(self, task: str, context: Dict[str, Any], 
                               style: str, max_length: int) -> str:
        """构建目录页生成提示"""
        prompt = f"""
请为以下任务生成PPT目录页内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 生成清晰的目录页内容
2. 列出PPT的主要章节和子章节
3. 使用层次分明的结构
4. 使用{style}的写作风格
5. 内容长度控制在{max_length}字符以内
6. 便于导航和查找

请直接生成目录页内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_content_slide_prompt(self, task: str, context: Dict[str, Any], 
                                  style: str, max_length: int) -> str:
        """构建内容页生成提示"""
        prompt = f"""
请为以下任务生成PPT内容页内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:300]}..."
        
        # 添加文件内容
        if context.get('file_content') and context['file_content'] != "未找到上传的文件内容":
            prompt += f"""
上传的文件内容：
{context['file_content']}
"""
        
        prompt += f"""
PPT单页内容生成要求：

重要提示：这是一页标准PPT，内容量必须适合在一个16:9的屏幕内完整显示，无需滚动。

**内容格式要求**：
请使用多样化、自然的表达方式，避免机械化的"要点1**："格式。推荐使用以下多种格式：

✓ 推荐格式（选择最适合的1-2种）：
- 自然描述：直接用动词开头，如"发现了XX个漏洞"、"拦截了XX万次攻击"
- 关键词突出：用【】强调重点，如"【威胁检测】成功率达98.5%"
- 结果导向：用"实现了"、"达到了"、"提升了"等，如"实现了100%事件闭环"
- 数据展示：用"→"或"："分隔，如"安全评分 → 84.14分"、"修复进度：14.25%"

✗ 避免格式：
- 不要使用"要点1**："、"要点2**："等机械化编号
- 不要重复相同的句式结构
- 不要使用过于正式的公文格式

**内容结构**（选择最适合的部分）：
### 核心发现（3-4个要点）
用自然语言描述最重要的发现或成果

### 关键指标（2-3个数据）
展示最重要的数字和比率

### 总体评价（1句话）
简洁概括整体情况

**内容丰富度要求**：
1. **单页容量**：生成丰富实质的内容，充分利用PPT页面空间（800-1200字符）
2. **要点数量**：核心发现4-6个，关键指标3-4个，深入分析2-3个
3. **每条长度**：每个要点包含具体数据、背景说明和影响分析，25-40个中文字
4. **格式多样性**：使用不同的表达方式，包含具体数据和详细说明
5. **内容深度**：不仅展示结果，更要说明原因、影响和改进建议
6. **数据可视化**：必须包含可图表化的数据，格式如下：
   - 百分比数据："闭环率达到95.5%"、"修复率为14.25%"
   - 评分数据："威胁管理85分"、"资产管理78分"、"事件管理92分"
   - 统计数据："发现漏洞456个"、"处理事件63起"、"拦截攻击151万次"
   - 对比数据：包含多个同类指标便于生成对比图表

**详细内容结构**：
### 核心发现与成就（4-6个要点）
- 每个发现包含：具体数据 + 业务影响 + 对比分析
- 示例："【威胁防护】本月成功拦截外部攻击151.8万次，相比上月增长15%，其中高危攻击占比12.3%，通过AI引擎识别准确率达98.7%，有效保障了业务系统零中断运行"

### 关键指标分析（3-4个数据）
- 每个指标包含：当前值 + 环比变化 + 行业对比 + 改进空间
- 示例："安全评分达84.14分，较上月提升2.3分，在同行业中处于中上水平，主要提升空间集中在漏洞修复速度和资产管理规范化"

### 深度分析与建议（2-3个方面）
- 包含根因分析、趋势预测、改进方案
- 示例："漏洞修复率14.25%偏低的主要原因是部分历史遗留系统升级困难，建议建立分级修复机制，优先处理高危漏洞，制定长期技术债务清理计划"

风格：{style}
字符限制：{max_length}（实际生成800-1200字符的丰富内容）

请基于提供的内容直接生成详实、专业的格式化内容，包含数据分析、影响评估和改进建议。
"""
        
        return prompt
    
    def _build_chart_slide_prompt(self, task: str, context: Dict[str, Any], 
                                 style: str, max_length: int) -> str:
        """构建图表页生成提示"""
        prompt = f"""
请为以下任务生成PPT图表页内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:300]}..."
        
        prompt += f"""
要求：
1. 生成专业的图表页内容
2. 包含图表标题和说明
3. 提供数据分析和解读
4. 使用{style}的写作风格
5. 内容长度控制在{max_length}字符以内
6. 适合配合图表展示

请直接生成图表页内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_summary_slide_prompt(self, task: str, context: Dict[str, Any], 
                                  style: str, max_length: int) -> str:
        """构建总结页生成提示"""
        prompt = f"""
请为以下任务生成PPT总结页内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 生成专业的总结页内容
2. 总结主要观点和发现
3. 强调关键结论
4. 提供下一步建议或展望
5. 使用{style}的写作风格
6. 内容长度控制在{max_length}字符以内
7. 给观众留下深刻印象

请直接生成总结页内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _build_general_slide_prompt(self, task: str, context: Dict[str, Any], 
                                   style: str, max_length: int) -> str:
        """构建通用幻灯片生成提示"""
        prompt = f"""
请为以下任务生成PPT幻灯片内容：

任务：{task}

写作风格：{style}
最大长度：{max_length} 字符

上下文信息：
"""
        
        # 添加上下文信息
        if context:
            for key, value in context.items():
                prompt += f"\n{key}: {str(value)[:200]}..."
        
        prompt += f"""
要求：
1. 生成专业的幻灯片内容
2. 内容符合任务要求，质量高
3. 使用{style}的写作风格
4. 结构清晰，表达流畅
5. 内容长度控制在{max_length}字符以内
6. 适合在幻灯片上展示

请直接生成幻灯片内容，不要包含额外的说明。
"""
        
        return prompt
    
    def _post_process_content(self, content: str, style: str, max_length: int) -> str:
        """后处理生成的内容"""
        # 清理内容
        content = content.strip()
        
        # 移除可能的格式标记
        content = re.sub(r'^```[\w\s]*\n', '', content, flags=re.MULTILINE)
        content = re.sub(r'\n```$', '', content)
        
        # 根据风格调整内容
        content = self._adjust_content_by_style(content, style)
        
        # 确保长度限制
        if len(content) > max_length:
            content = self._truncate_content(content, max_length)
        
        # 确保内容完整性
        content = self._ensure_content_completeness(content)
        
        return content
    
    def _adjust_content_by_style(self, content: str, style: str) -> str:
        """根据风格调整内容"""
        if style == "professional":
            # 专业风格：使用更正式的表达
            content = re.sub(r'\b我觉得\b', '分析表明', content)
            content = re.sub(r'\b可能\b', '预计', content)
            content = re.sub(r'\b很\b', '非常', content)
        elif style == "casual":
            # 随意风格：使用更轻松的表达
            content = re.sub(r'\b分析表明\b', '我觉得', content)
            content = re.sub(r'\b预计\b', '可能', content)
            content = re.sub(r'\b非常\b', '很', content)
        elif style == "academic":
            # 学术风格：使用更专业的表达
            content = re.sub(r'\b我觉得\b', '研究表明', content)
            content = re.sub(r'\b可能\b', '有可能', content)
            content = re.sub(r'\b很\b', '相当', content)
        
        return content
    
    def _truncate_content(self, content: str, max_length: int) -> str:
        """截断内容"""
        if len(content) <= max_length:
            return content
        
        # 尝试在句子边界截断
        sentences = re.split(r'[。！？.!?]', content)
        truncated = ""
        
        for sentence in sentences:
            if len(truncated + sentence + "。") <= max_length:
                truncated += sentence + "。"
            else:
                break
        
        # 如果还是太长，在单词边界截断
        if len(truncated) > max_length:
            words = truncated.split()
            truncated = ""
            
            for word in words:
                if len(truncated + word + " ") <= max_length:
                    truncated += word + " "
                else:
                    break
        
        # 添加省略号
        if truncated and len(truncated) < len(content):
            truncated += "..."
        
        return truncated.strip()
    
    def _ensure_content_completeness(self, content: str) -> str:
        """确保内容完整性"""
        if not content:
            return "内容生成失败，请重试。"
        
        # 确保以适当的标点符号结束
        if not content[-1] in ['。', '！', '？', '.', '!', '?']:
            content += '。'
        
        return content
    
    def _generate_html_slide(self, content: str, slide_type: str, context: Dict[str, Any]) -> str:
        """生成HTML格式的幻灯片 - 使用高端Premium模板"""
        
        # 获取幻灯片标题
        title = context.get("slide_title", "幻灯片标题")
        report_title = context.get("report_title", title)
        report_subtitle = context.get("report_subtitle", "7*24H全时守护 安全效果护航业务稳定运行")
        chapter_title = context.get("chapter_title", "")
        slide_number = context.get("slide_number", 1)
        total_slides = context.get("total_slides", 1)
        prev_file = context.get("prev_slide_file", "")
        next_file = context.get("next_slide_file", "")
        generation_time = context.get("generation_time", "")
        
        # 生成导航按钮
        nav_buttons = []
        if prev_file:
            nav_buttons.append(f'<a href="{prev_file}" class="nav-button">上一页</a>')
        if next_file:
            nav_buttons.append(f'<a href="{next_file}" class="nav-button">下一页</a>')
        
        nav_html = '\n                '.join(nav_buttons)
        
        # 生成图表脚本
        chart_scripts = self._generate_chart_scripts(context.get("charts", []))
        
        # 格式化内容
        formatted_content = self._format_content_with_charts(content, context)
        
        # 使用高端Premium模板 - 参考abc-居中版.pdf的视觉设计
        if slide_type == "cover":
            # 封面页使用专门的模板
            html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {slide_number}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background: #0a0a0a;
            overflow-x: hidden;
            margin: 0;
            padding: 0;
        }}
        
        /* 高级深蓝渐变背景 - 参考PDF样式 */
        .slide {{
            width: 1366px;
            height: 768px;
            background: #ffffff;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 80px 60px;
            color: white;
            overflow: hidden;
        }}
        
        /* 动态背景图案 */
        .slide::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 199, 255, 0.05) 0%, transparent 50%);
            z-index: 1;
        }}
        
        /* 网格背景图案 */
        .slide::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(rgba(120, 199, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(120, 199, 255, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            z-index: 1;
        }}
        
        /* 内容容器 */
        .slide-content {{
            position: relative;
            z-index: 10;
            max-width: 1000px;
            width: 100%;
            text-align: center;
        }}
        
        .security-icon {{
            width: 120px;
            height: 120px;
            margin: 0 auto 40px;
            background: rgba(120, 199, 255, 0.1);
            border: 3px solid rgba(120, 199, 255, 0.3);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
        }}
        
        .security-icon::before {{
            content: '🛡️';
            font-size: 60px;
        }}
        
        .security-icon::after {{
            content: '';
            position: absolute;
            top: -10px;
            left: -10px;
            right: -10px;
            bottom: -10px;
            border: 1px solid rgba(120, 199, 255, 0.2);
            border-radius: 50%;
            animation: pulse 3s infinite;
        }}
        
        @keyframes pulse {{
            0%, 100% {{ transform: scale(1); opacity: 0.5; }}
            50% {{ transform: scale(1.05); opacity: 0.8; }}
        }}
        
        .title {{
            font-size: 3.2em;
            font-weight: 300;
            margin-bottom: 30px;
            line-height: 1.2;
            background: linear-gradient(135deg, #ffffff 0%, #a8d8ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        
        .subtitle {{
            font-size: 1.4em;
            font-weight: 300;
            opacity: 0.85;
            margin-bottom: 50px;
            color: #a8d8ff;
            letter-spacing: 0.5px;
        }}
        
        /* 标签样式 */
        .tags {{
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 15px;
            margin-bottom: 40px;
        }}
        
        .tag {{
            padding: 8px 20px;
            background: rgba(120, 199, 255, 0.1);
            border: 1px solid rgba(120, 199, 255, 0.3);
            border-radius: 20px;
            font-size: 0.9em;
            color: #a8d8ff;
        }}
        
        /* 功能特色区域 */
        .features {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 40px;
        }}
        
        .feature-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 0.95em;
            color: #a8d8ff;
        }}
        
        .feature-item::before {{
            content: '';
            width: 8px;
            height: 8px;
            background: linear-gradient(45deg, #78c7ff, #4a9eff);
            border-radius: 50%;
        }}
        
        /* 元数据信息 */
        .metadata-info {{
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-top: 30px;
            font-size: 0.95em;
            color: rgba(255, 255, 255, 0.7);
        }}
        
        .metadata-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .metadata-item::before {{
            content: '';
            width: 6px;
            height: 6px;
            background: #78c7ff;
            border-radius: 50%;
        }}
        
        /* 页码和导航 */
        .slide-footer {{
            position: absolute;
            bottom: 40px;
            left: 60px;
            right: 60px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
        }}
        
        .slide-number {{
            font-size: 0.9em;
            color: rgba(255, 255, 255, 0.6);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            padding: 8px 16px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }}
        
        .navigation {{
            display: flex;
            gap: 10px;
            z-index: 101;
            position: relative;
        }}
        
        .nav-button {{
            padding: 10px 20px;
            background: linear-gradient(45deg, #78c7ff, #4a9eff);
            color: #0a1426;
            text-decoration: none;
            border-radius: 25px;
            font-size: 0.9em;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
            position: relative;
            z-index: 102;
            cursor: pointer;
            display: inline-block;
        }}
        
        .nav-button:hover {{
            background: linear-gradient(45deg, #4a9eff, #2e7cff);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(120, 199, 255, 0.3);
        }}
        
        .nav-button.disabled {{
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.4);
            pointer-events: none;
        }}
        
        /* 响应式设计 */
        @media (max-width: 768px) {{
            .slide {{
                padding: 40px 25px;
            }}
            
            .title {{
                font-size: 2.5em;
            }}
            
            .features {{
                flex-direction: column;
                gap: 20px;
            }}
            
            .slide-footer {{
                flex-direction: column;
                gap: 15px;
                bottom: 20px;
            }}
        }}
        
        /* 动画效果 */
        .slide {{
            animation: slideIn 0.8s ease-out;
        }}
        
        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>
    <div class="slide cover">
        <div class="slide-content">
            <div class="security-icon"></div>
            <h1 class="title">{report_title}</h1>
            <p class="subtitle">{report_subtitle}</p>
            
            <div class="tags">
                <span class="tag">政府</span>
                <span class="tag">医疗</span>
                <span class="tag">教育</span>
                <span class="tag">企业</span>
                <span class="tag">金融</span>
            </div>
            
            <div class="features">
                <div class="feature-item">通报应对</div>
                <div class="feature-item">勒索防护</div>
                <div class="feature-item">业务保护</div>
                <div class="feature-item">攻防演练</div>
            </div>
            
            <div class="metadata-info">
                <div class="metadata-item">专业安全团队出品</div>
                <div class="metadata-item">{generation_time if generation_time else "2025年08月"}</div>
            </div>
        </div>
        
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                {nav_html}
            </div>
        </div>
    </div>
    {chart_scripts}
</body>
</html>"""
        else:
            # 内容页使用现代化模板
            html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - {slide_number}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background: #0a0a0a;
            overflow-x: hidden;
            margin: 0;
            padding: 0;
        }}
        
        /* 高级深蓝渐变背景 */
        .slide {{
            width: 1366px;
            height: 768px;
            background: #ffffff;
            position: relative;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            text-align: center;
            padding: 80px 60px;
            color: white;
            overflow: hidden;
        }}
        
        /* 动态背景图案 */
        .slide::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(120, 199, 255, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(120, 199, 255, 0.05) 0%, transparent 50%);
            z-index: 1;
        }}
        
        /* 网格背景图案 */
        .slide::after {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-image: 
                linear-gradient(rgba(120, 199, 255, 0.03) 1px, transparent 1px),
                linear-gradient(90deg, rgba(120, 199, 255, 0.03) 1px, transparent 1px);
            background-size: 50px 50px;
            z-index: 1;
        }}
        
        /* 内容容器 */
        .slide-content {{
            position: relative;
            z-index: 10;
            max-width: 1000px;
            width: 100%;
        }}
        
        /* 内容页样式 */
        .slide.content h1, .slide.toc h1 {{
            font-size: 2.5em;
            margin-bottom: 50px;
            background: linear-gradient(135deg, #ffffff 0%, #a8d8ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            position: relative;
        }}
        
        .slide.content h1::after, .slide.toc h1::after {{
            content: '';
            position: absolute;
            bottom: -15px;
            left: 50%;
            transform: translateX(-50%);
            width: 80px;
            height: 3px;
            background: linear-gradient(90deg, #78c7ff, #4a9eff);
            border-radius: 2px;
        }}
        
        .content-body {{
            max-width: 900px;
            margin: 0 auto;
            text-align: left;
            font-size: 1.1em;
            line-height: 1.8;
            color: #d1e7ff;
        }}
        
        .content-body h2 {{
            font-size: 1.6em;
            color: #a8d8ff;
            margin: 30px 0 20px 0;
            font-weight: 500;
        }}
        
        .content-body h3 {{
            font-size: 1.3em;
            color: #ffffff;
            margin: 25px 0 15px 0;
            font-weight: 500;
        }}
        
        .content-body p {{
            margin-bottom: 18px;
            text-align: justify;
        }}
        
        .content-body ul, .content-body ol {{
            margin: 20px 0;
            padding-left: 30px;
        }}
        
        .content-body li {{
            margin-bottom: 10px;
            line-height: 1.7;
        }}
        
        /* 单栏内容容器 */
        .single-column-content {{
            display: flex;
            flex-direction: column;
            gap: 15px;
            max-height: calc(100vh - 200px);
            overflow: hidden;
        }}
        
        .single-column-content p,
        .single-column-content .stats-container,
        .single-column-content .content-card {{
            margin-bottom: 12px;
        }}
        
        /* 统计数据展示 */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 25px;
            margin: 40px 0;
        }}
        
        .stat-item {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
        }}
        
        .stat-number {{
            font-size: 2.5em;
            font-weight: 300;
            color: #78c7ff;
            margin-bottom: 10px;
        }}
        
        .stat-label {{
            font-size: 0.95em;
            color: #a8d8ff;
            opacity: 0.9;
        }}
        
        .stat-description {{
            font-size: 0.8em;
            color: #d1e7ff;
            margin-top: 8px;
            opacity: 0.8;
        }}
        
        /* 目录样式 */
        .toc-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 30px;
            max-width: 900px;
            margin: 0 auto;
        }}
        
        .toc-item {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            border-radius: 15px;
            padding: 30px;
            text-align: left;
            transition: all 0.3s ease;
            position: relative;
        }}
        
        .toc-item:hover {{
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(120, 199, 255, 0.4);
            transform: translateY(-5px);
        }}
        
        .toc-item .number {{
            position: absolute;
            top: -15px;
            left: 25px;
            background: linear-gradient(45deg, #78c7ff, #4a9eff);
            color: #0a1426;
            width: 30px;
            height: 30px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.9em;
        }}
        
        .toc-item h3 {{
            font-size: 1.3em;
            margin-bottom: 12px;
            color: #ffffff;
        }}
        
        .toc-item p {{
            font-size: 0.95em;
            color: #a8d8ff;
            line-height: 1.6;
            opacity: 0.9;
        }}
        
        /* 页码和导航 */
        .slide-footer {{
            position: absolute;
            bottom: 40px;
            left: 60px;
            right: 60px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
        }}
        
        .slide-number {{
            font-size: 0.9em;
            color: rgba(255, 255, 255, 0.6);
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            padding: 8px 16px;
            border-radius: 20px;
            backdrop-filter: blur(10px);
        }}
        
        .navigation {{
            display: flex;
            gap: 10px;
            z-index: 101;
            position: relative;
        }}
        
        .nav-button {{
            padding: 10px 20px;
            background: linear-gradient(45deg, #78c7ff, #4a9eff);
            color: #0a1426;
            text-decoration: none;
            border-radius: 25px;
            font-size: 0.9em;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
            position: relative;
            z-index: 102;
            cursor: pointer;
            display: inline-block;
        }}
        
        .nav-button:hover {{
            background: linear-gradient(45deg, #4a9eff, #2e7cff);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(120, 199, 255, 0.3);
        }}
        
        .nav-button.disabled {{
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.4);
            pointer-events: none;
        }}
        
        /* 图表容器样式 */
        .chart-container {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(120, 199, 255, 0.2);
            border-radius: 15px;
            padding: 25px;
            margin: 30px 0;
            backdrop-filter: blur(10px);
        }}

        .chart-container.full-width-chart {{
            width: 100%;
            max-width: 800px;
            margin: 30px auto;
        }}

        .chart-title {{
            font-size: 1.4em;
            color: #ffffff;
            text-align: center;
            margin-bottom: 20px;
            font-weight: 500;
            background: linear-gradient(135deg, #ffffff 0%, #a8d8ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .chart-canvas {{
            max-width: 100% !important;
            height: 400px !important;
            margin: 0 auto;
            display: block;
        }}

        /* 文本与图表布局优化 */
        .text-section {{
            margin-bottom: 40px;
        }}

        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 40px;
        }}

        .column-left, .column-right {{
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(120, 199, 255, 0.1);
            border-radius: 12px;
            padding: 25px;
        }}

        .section-heading {{
            font-size: 1.3em;
            color: #78c7ff;
            margin-bottom: 20px;
            font-weight: 600;
            text-align: center;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(120, 199, 255, 0.3);
        }}

        .stats-container {{
            background: rgba(120, 199, 255, 0.05);
            border-left: 3px solid #78c7ff;
            margin: 15px 0;
            padding: 15px;
            border-radius: 8px;
        }}

        .stats-container p {{
            margin: 0;
            line-height: 1.6;
            color: #d1e7ff;
        }}

        .tag {{
            background: #2ecc71;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }}

        .tag.success {{
            background: linear-gradient(45deg, #2ecc71, #27ae60);
        }}

        .stat-number {{
            color: #78c7ff;
            font-weight: bold;
            font-size: 1.1em;
        }}

        .content-card {{
            background: rgba(120, 199, 255, 0.08);
            border: 1px solid rgba(120, 199, 255, 0.2);
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
        }}

        .content-card p {{
            margin: 0;
            color: #ffffff;
            line-height: 1.7;
            text-align: justify;
        }}

        /* 响应式设计 */
        @media (max-width: 1024px) {{
            .slide {{
                padding: 60px 40px;
            }}
            
            .toc-grid {{
                grid-template-columns: 1fr;
            }}
            
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}

            .two-column {{
                grid-template-columns: 1fr;
                gap: 20px;
            }}

            .chart-canvas {{
                height: 350px !important;
            }}
        }}
        
        @media (max-width: 768px) {{
            .slide {{
                padding: 40px 25px;
            }}
            
            .slide.content h1, .slide.toc h1 {{
                font-size: 2em;
            }}
            
            .stats-grid {{
                grid-template-columns: 1fr;
            }}
            
            .slide-footer {{
                flex-direction: column;
                gap: 15px;
                bottom: 20px;
            }}

            .chart-canvas {{
                height: 300px !important;
            }}

            .chart-container.full-width-chart {{
                max-width: 100%;
                padding: 15px;
                margin: 20px 0;
            }}

            .section-heading {{
                font-size: 1.1em;
            }}
        }}
        
        /* 动画效果 */
        .slide {{
            animation: slideIn 0.8s ease-out;
        }}
        
        @keyframes slideIn {{
            from {{
                opacity: 0;
                transform: translateY(30px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>
    <div class="slide {slide_type}">
        <div class="slide-content">
            <h1>{title}</h1>
            <div class="content-body">
                {formatted_content}
            </div>
        </div>
        
        <div class="slide-footer">
            <div class="slide-number">{slide_number} / {total_slides}</div>
            <div class="navigation">
                {nav_html}
            </div>
        </div>
    </div>
    {chart_scripts}
</body>
</html>"""
        
        return html_template
    
    def _format_content_with_charts(self, content: str, context: Dict[str, Any]) -> str:
        """将内容格式化为HTML格式，包含图表"""
        has_charts = context.get("has_charts", False)
        charts = context.get("charts", [])
        
        if not has_charts or not charts:
            return self._format_content_for_html(content)
        
        # 如果有图表，使用混合布局
        formatted_content = self._format_content_for_html(content)
        
        # 决定布局方式
        if len(charts) == 1:
            # 单个图表，使用左右分栏布局
            chart = charts[0]
            chart_html = f"""
            <div class="chart-container">
                <div class="chart-title">{chart['title']}</div>
                <canvas id="{chart['id']}" class="chart-canvas"></canvas>
            </div>
            """
            
            return f"""
            <div class="content-with-charts">
                <div class="text-section">
                    {formatted_content}
                </div>
                <div class="chart-section">
                    {chart_html}
                </div>
            </div>
            """
        else:
            # 多个图表，使用垂直布局
            charts_html = ""
            for chart in charts:
                charts_html += f"""
                <div class="chart-container full-width-chart">
                    <div class="chart-title">{chart['title']}</div>
                    <canvas id="{chart['id']}" class="chart-canvas"></canvas>
                </div>
                """
            
            return f"""
            <div class="text-section">
                {formatted_content}
            </div>
            {charts_html}
            """
    
    def _generate_chart_scripts(self, charts: List[Dict[str, Any]]) -> str:
        """生成图表的JavaScript代码"""
        if not charts:
            return ""
        
        scripts = "<script>"
        scripts += """
        document.addEventListener('DOMContentLoaded', function() {
        """
        
        for chart in charts:
            chart_id = chart['id']
            chart_type = chart['type']
            labels = chart['labels']
            values = chart['values']
            title = chart['title']
            
            # 生成优化的图表配置
            if 'security_score' in chart_id:
                # 安全评分图表 - 使用蓝色系并优化配置
                colors = ["#78c7ff", "#4a9eff", "#2e7cff"][:len(values)]
                border_colors = ["rgba(120, 199, 255, 0.8)", "rgba(74, 158, 255, 0.8)", "rgba(46, 124, 255, 0.8)"][:len(values)]
                
                scripts += f"""
            var ctx_{chart_id} = document.getElementById('{chart_id}');
            if (ctx_{chart_id}) {{
                new Chart(ctx_{chart_id}, {{
                    type: 'bar',
                    data: {{
                        labels: {json.dumps(labels, ensure_ascii=False)},
                        datasets: [{{
                            data: {json.dumps(values)},
                            backgroundColor: {json.dumps(colors)},
                            borderColor: {json.dumps(border_colors)},
                            borderWidth: 1,
                            borderRadius: 8,
                            borderSkipped: false
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: false
                            }},
                            tooltip: {{
                                backgroundColor: 'rgba(10, 20, 38, 0.95)',
                                titleColor: '#78c7ff',
                                bodyColor: '#d1e7ff',
                                borderColor: '#78c7ff',
                                borderWidth: 1,
                                cornerRadius: 8,
                                displayColors: true,
                                callbacks: {{
                                    label: function(context) {{
                                        return context.label + ': ' + context.parsed + '分';
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                max: 100,
                                grid: {{
                                    color: 'rgba(120, 199, 255, 0.1)',
                                    borderColor: 'rgba(120, 199, 255, 0.3)'
                                }},
                                ticks: {{
                                    color: '#a8d8ff',
                                    font: {{
                                        size: 11
                                    }}
                                }}
                            }},
                            x: {{
                                grid: {{
                                    display: false
                                }},
                                ticks: {{
                                    color: '#d1e7ff',
                                    font: {{
                                        size: 11
                                    }}
                                }}
                            }}
                        }},
                        layout: {{
                            padding: {{
                                top: 10,
                                bottom: 10,
                                left: 10,
                                right: 10
                            }}
                        }}
                    }}
                }});
            }}
            """
            elif 'rates' in chart_id:
                # 效率指标图表 - 使用环形图并优化配置
                # 确保有对比数据
                if len(labels) < 2:
                    labels = ["我司修复率", "行业平均"]
                    values = values + [89.0] if len(values) < 2 else values
                
                colors = ["#ff6b6b", "#78c7ff"][:len(values)]
                border_colors = ["rgba(255, 107, 107, 0.8)", "rgba(120, 199, 255, 0.8)"][:len(values)]
                
                scripts += f"""
            var ctx_{chart_id} = document.getElementById('{chart_id}');
            if (ctx_{chart_id}) {{
                new Chart(ctx_{chart_id}, {{
                    type: 'doughnut',
                    data: {{
                        labels: {json.dumps(labels, ensure_ascii=False)},
                        datasets: [{{
                            data: {json.dumps(values)},
                            backgroundColor: {json.dumps(colors)},
                            borderColor: {json.dumps(border_colors)},
                            borderWidth: 2,
                            cutout: '60%'
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                position: 'bottom',
                                labels: {{
                                    padding: 20,
                                    usePointStyle: true,
                                    font: {{
                                        size: 12
                                    }},
                                    color: '#d1e7ff'
                                }}
                            }},
                            tooltip: {{
                                backgroundColor: 'rgba(10, 20, 38, 0.95)',
                                titleColor: '#78c7ff',
                                bodyColor: '#d1e7ff',
                                borderColor: '#78c7ff',
                                borderWidth: 1,
                                cornerRadius: 8,
                                displayColors: true,
                                callbacks: {{
                                    label: function(context) {{
                                        return context.label + ': ' + context.parsed + '%';
                                    }}
                                }}
                            }}
                        }},
                        layout: {{
                            padding: {{
                                top: 10,
                                bottom: 20,
                                left: 10,
                                right: 10
                            }}
                        }}
                    }}
                }});
            }}
            """
            elif 'incidents' in chart_id:
                # 安全事件图表 - 使用多彩柱状图并优化配置
                colors = [
                    "#ff6b6b", "#4ecdc4", "#45b7d1", 
                    "#96ceb4", "#ffeaa7", "#dda0dd"
                ][:len(values)]
                border_colors = [
                    "rgba(255, 107, 107, 0.8)", "rgba(78, 205, 196, 0.8)", 
                    "rgba(69, 183, 209, 0.8)", "rgba(150, 206, 180, 0.8)", 
                    "rgba(255, 234, 167, 0.8)", "rgba(221, 160, 221, 0.8)"
                ][:len(values)]
                
                # 优化标签名称
                optimized_labels = []
                for label in labels:
                    if label == "攻击":
                        optimized_labels.append("外部攻击")
                    elif label == "业务系统":
                        optimized_labels.append("业务系统")
                    elif label == "事件":
                        optimized_labels.append("安全事件")
                    elif label == "漏洞":
                        optimized_labels.append("系统漏洞")
                    elif label == "资产":
                        optimized_labels.append("安全资产")
                    else:
                        optimized_labels.append("安全项目")
                
                scripts += f"""
            var ctx_{chart_id} = document.getElementById('{chart_id}');
            if (ctx_{chart_id}) {{
                new Chart(ctx_{chart_id}, {{
                    type: 'bar',
                    data: {{
                        labels: {json.dumps(optimized_labels, ensure_ascii=False)},
                        datasets: [{{
                            data: {json.dumps(values)},
                            backgroundColor: {json.dumps(colors)},
                            borderColor: {json.dumps(border_colors)},
                            borderWidth: 1,
                            borderRadius: 6,
                            borderSkipped: false
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                display: false
                            }},
                            tooltip: {{
                                backgroundColor: 'rgba(10, 20, 38, 0.95)',
                                titleColor: '#78c7ff',
                                bodyColor: '#d1e7ff',
                                borderColor: '#78c7ff',
                                borderWidth: 1,
                                cornerRadius: 8,
                                displayColors: true,
                                callbacks: {{
                                    label: function(context) {{
                                        return context.label + ': ' + context.parsed + '项';
                                    }}
                                }}
                            }}
                        }},
                        scales: {{
                            y: {{
                                beginAtZero: true,
                                grid: {{
                                    color: 'rgba(120, 199, 255, 0.1)',
                                    borderColor: 'rgba(120, 199, 255, 0.3)'
                                }},
                                ticks: {{
                                    color: '#a8d8ff',
                                    font: {{
                                        size: 11
                                    }}
                                }}
                            }},
                            x: {{
                                grid: {{
                                    display: false
                                }},
                                ticks: {{
                                    color: '#d1e7ff',
                                    font: {{
                                        size: 10
                                    }},
                                    maxRotation: 45
                                }}
                            }}
                        }},
                        layout: {{
                            padding: {{
                                top: 10,
                                bottom: 10,
                                left: 10,
                                right: 10
                            }}
                        }}
                    }}
                }});
            }}
            """
            else:
                # 通用图表配置
                if chart_type == 'pie' or chart_type == 'doughnut':
                    colors = [
                        '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', 
                        '#9966FF', '#FF9F40', '#8BC34A', '#FF5722'
                    ][:len(values)]
                else:
                    colors = ['#2a5298', '#34495e', '#7f8c8d', '#95a5a6'][:len(values)]
                
                scripts += f"""
            var ctx_{chart_id} = document.getElementById('{chart_id}');
            if (ctx_{chart_id}) {{
                new Chart(ctx_{chart_id}, {{
                    type: '{chart_type}',
                    data: {{
                        labels: {json.dumps(labels, ensure_ascii=False)},
                        datasets: [{{
                            data: {json.dumps(values)},
                            backgroundColor: {json.dumps(colors)},
                            borderColor: {json.dumps(['rgba(255, 255, 255, 0.8)'] * len(values))},
                            borderWidth: 1
                        }}]
                    }},
                    options: {{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {{
                            legend: {{
                                position: 'bottom',
                                labels: {{
                                    padding: 20,
                                    usePointStyle: true,
                                    font: {{
                                        size: 12
                                    }},
                                    color: '#d1e7ff'
                                }}
                            }},
                            tooltip: {{
                                backgroundColor: 'rgba(10, 20, 38, 0.95)',
                                titleColor: '#78c7ff',
                                bodyColor: '#d1e7ff',
                                borderColor: '#78c7ff',
                                borderWidth: 1,
                                cornerRadius: 8,
                                callbacks: {{
                                    label: function(context) {{
                                        if ('{chart_type}' === 'pie' || '{chart_type}' === 'doughnut') {{
                                            return context.label + ': ' + context.parsed + '%';
                                        }} else {{
                                            return context.label + ': ' + context.parsed;
                                        }}
                                    }}
                                }}
                            }}
                        }},
                        {'layout: { padding: { top: 10, bottom: 10, left: 10, right: 10 } }' if chart_type in ['pie', 'doughnut'] else '''scales: {
                            y: {
                                beginAtZero: true,
                                grid: {
                                    color: 'rgba(120, 199, 255, 0.1)',
                                    borderColor: 'rgba(120, 199, 255, 0.3)'
                                },
                                ticks: {
                                    color: '#a8d8ff'
                                }
                            },
                            x: {
                                grid: {
                                    display: false
                                },
                                ticks: {
                                    color: '#d1e7ff'
                                }
                            }
                        },
                        layout: {
                            padding: {
                                top: 10,
                                bottom: 10,
                                left: 10,
                                right: 10
                            }
                        }'''}
                    }}
                }});
            }}
            """
        
        scripts += """
        });
        </script>"""
        
        return scripts
    
    def _format_content_for_html(self, content: str) -> str:
        """将内容格式化为HTML格式，应用现代化样式"""
        
        # 检测并分离不同类型的内容
        sections = self._parse_content_sections(content)
        formatted_sections = []
        
        for section in sections:
            section_type = section['type']
            section_content = section.get('content', '')
            
            if section_type == 'heading':
                level = section.get('level', 3)
                formatted_sections.append(f'<h{level} class="section-heading">{section_content}</h{level}>')
                
            elif section_type == 'list':
                list_html = '<ul class="styled-list">'
                for item in section['items']:
                    list_html += f'<li>{item}</li>'
                list_html += '</ul>'
                formatted_sections.append(list_html)
                
            elif section_type == 'highlight':
                formatted_sections.append(f'<div class="highlight-box"><h3>{section["title"]}</h3><p>{section_content}</p></div>')
                
            elif section_type == 'paragraph':
                # 检查段落是否包含关键信息
                if any(keyword in section_content for keyword in ['目的', '目标', '重要', '关键', '核心']):
                    formatted_sections.append(f'<div class="content-card"><p>{section_content}</p></div>')
                # 检查是否包含数字统计
                elif self._contains_statistics(section_content):
                    enhanced_content = self._enhance_statistics(section_content)
                    formatted_sections.append(f'<div class="stats-container">{enhanced_content}</div>')
                else:
                    formatted_sections.append(f'<p>{section_content}</p>')
        
        # 对于16:9比例，使用单栏布局避免内容被截断
        # 如果内容过多，进行适当精简
        if len(formatted_sections) > 8:
            # 限制内容数量，确保适合单页显示
            formatted_sections = formatted_sections[:8]
            formatted_sections.append('<p style="text-align: center; font-style: italic; color: #78c7ff;">... 更多内容请参阅完整报告</p>')
        
        # 使用单栏容器包装，确保内容完整性
        return f'''
        <div class="single-column-content">
            {chr(10).join(formatted_sections)}
        </div>
        '''
        
        return '\n'.join(formatted_sections)
    
    def _parse_content_sections(self, content: str) -> List[Dict[str, Any]]:
        """解析内容为不同的段落类型"""
        import re
        sections = []
        lines = content.split('\n')
        current_list_items = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检测标题
            if line.startswith('#'):
                if current_list_items:
                    sections.append({'type': 'list', 'items': current_list_items})
                    current_list_items = []
                    
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('# ').strip()
                sections.append({'type': 'heading', 'level': level + 2, 'content': title})
                
            # 检测列表项
            elif line.startswith(('•', '-', '*', '<li>')):
                item_text = line.lstrip('•-*<li> ').rstrip('</li>')
                # 修复HTML标签问题：确保strong标签正确闭合
                item_text = self._fix_html_tags(item_text)
                current_list_items.append(item_text)
                
            # 检测HTML标题
            elif line.startswith('<h') and line.endswith('>'):
                if current_list_items:
                    sections.append({'type': 'list', 'items': current_list_items})
                    current_list_items = []
                    
                # 提取标题内容
                match = re.search(r'<h[1-6].*?>(.*?)</h[1-6]>', line)
                if match:
                    title = match.group(1)
                    sections.append({'type': 'heading', 'level': 3, 'content': title})
                    
            # 普通段落
            else:
                if current_list_items:
                    sections.append({'type': 'list', 'items': current_list_items})
                    current_list_items = []
                    
                # 保留有用的HTML标签，如strong, em等
                # 先修复可能损坏的标签
                fixed_line = self._fix_html_tags(line)
                if fixed_line:
                    sections.append({'type': 'paragraph', 'content': fixed_line})
        
        # 处理剩余的列表项
        if current_list_items:
            sections.append({'type': 'list', 'items': current_list_items})
        
        return sections
    
    def _fix_html_tags(self, text: str) -> str:
        """修复损坏的HTML标签"""
        import re
        
        # 修复常见的标签问题
        # 1. 修复损坏的strong标签
        text = re.sub(r'strong>([^<]*)</strong>', r'<strong>\1</strong>', text)
        text = re.sub(r'strong>([^<]*)', r'<strong>\1</strong>', text)
        
        # 2. 修复损坏的em标签
        text = re.sub(r'em>([^<]*)</em>', r'<em>\1</em>', text)
        text = re.sub(r'em>([^<]*)', r'<em>\1</em>', text)
        
        # 3. 修复未闭合的标签
        text = re.sub(r'<strong>([^<]*?)(?=<strong>|$)', r'<strong>\1</strong>', text)
        text = re.sub(r'<em>([^<]*?)(?=<em>|$)', r'<em>\1</em>', text)
        
        # 4. 清理多余的闭合标签
        text = re.sub(r'</strong>+', '</strong>', text)
        text = re.sub(r'</em>+', '</em>', text)
        
        # 5. 修复**包围的文本为strong标签
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        
        # 6. 修复*包围的文本为em标签
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
        
        return text
    
    def _contains_statistics(self, text: str) -> bool:
        """检查文本是否包含统计数据"""
        import re
        # 匹配数字模式
        patterns = [
            r'\d+(?:\.\d+)?%',  # 百分比
            r'\d+(?:\.\d+)?分',  # 分数
            r'\d+个',           # 个数
            r'\d+次',           # 次数
            r'\d+起',           # 起数
            r'\d+万',           # 万级数字
            r'\d+千',           # 千级数字
        ]
        
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def _enhance_statistics(self, text: str) -> str:
        """增强统计数据的显示效果"""
        import re
        
        # 先修复可能存在的HTML标签问题
        text = self._fix_html_tags(text)
        
        # 保护已存在的HTML标签，避免被替换破坏
        # 临时替换strong和em标签
        text = text.replace('<strong>', '[[STRONG_START]]')
        text = text.replace('</strong>', '[[STRONG_END]]')
        text = text.replace('<em>', '[[EM_START]]')
        text = text.replace('</em>', '[[EM_END]]')
        
        # 增强百分比显示
        text = re.sub(r'(\d+(?:\.\d+)?)%', r'<span class="stat-number">\1%</span>', text)
        
        # 增强分数显示
        text = re.sub(r'(\d+(?:\.\d+)?)分', r'<span class="stat-number">\1分</span>', text)
        
        # 增强数量显示
        text = re.sub(r'(\d+)个', r'<span class="stat-number">\1</span>个', text)
        text = re.sub(r'(\d+)次', r'<span class="stat-number">\1</span>次', text)
        text = re.sub(r'(\d+)起', r'<span class="stat-number">\1</span>起', text)
        
        # 增强大数字显示
        text = re.sub(r'(\d+(?:\.\d+)?)万', r'<span class="stat-number">\1万</span>', text)
        text = re.sub(r'(\d+)千', r'<span class="stat-number">\1千</span>', text)
        
        # 添加状态标签（避免替换HTML标签内的文字）
        if '成功' in text or '完成' in text or '达成' in text:
            text = re.sub(r'(?<!>)(成功|完成|达成)(?!<)', r'<span class="tag success">\1</span>', text)
        
        if '警告' in text or '注意' in text or '待改进' in text:
            text = re.sub(r'(?<!>)(警告|注意|待改进)(?!<)', r'<span class="tag warning">\1</span>', text)
        
        if '失败' in text or '错误' in text or '风险' in text:
            text = re.sub(r'(?<!>)(失败|错误|风险)(?!<)', r'<span class="tag danger">\1</span>', text)
        
        # 恢复strong和em标签
        text = text.replace('[[STRONG_START]]', '<strong>')
        text = text.replace('[[STRONG_END]]', '</strong>')
        text = text.replace('[[EM_START]]', '<em>')
        text = text.replace('[[EM_END]]', '</em>')
        
        return f'<p>{text}</p>'
    
    def get_tool_info(self) -> Dict[str, Any]:
        """获取工具信息"""
        return {
            "name": "CreateSlideTool",
            "description": "幻灯片创建工具，专门用于生成PPT幻灯片",
            "version": "1.0.0",
            "enabled": self.enabled,
            "max_content_length": self.max_content_length,
            "supported_slide_types": list(self.slide_types.keys()),
            "supported_styles": ["professional", "casual", "academic", "business"],
            "capabilities": [
                "专业幻灯片生成",
                "多种幻灯片类型支持",
                "HTML格式输出",
                "风格自适应",
                "内容长度控制",
                "上下文感知生成",
                "模板化生成",
                "专业样式设计"
            ]
        }
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """验证输入数据"""
        if not isinstance(input_data, dict):
            return False
        
        task = input_data.get("task", "")
        slide_type = input_data.get("slide_type", "")
        style = input_data.get("style", "")
        max_length = input_data.get("max_length", 0)
        
        if not task or not isinstance(task, str):
            return False
        
        if not isinstance(slide_type, str):
            return False
        
        if not isinstance(style, str):
            return False
        
        if not isinstance(max_length, int) or max_length <= 0:
            return False
        
        return True
    
    def enable_tool(self) -> None:
        """启用工具"""
        self.enabled = True
        logger.info("幻灯片创建工具已启用", agent_name="CreateSlideTool")
    
    def disable_tool(self) -> None:
        """禁用工具"""
        self.enabled = False
        logger.info("幻灯片创建工具已禁用", agent_name="CreateSlideTool")
    
    def set_max_content_length(self, max_length: int) -> None:
        """设置最大内容长度"""
        if max_length > 0:
            self.max_content_length = max_length
            logger.info(f"最大内容长度已设置为: {max_length}", agent_name="CreateSlideTool")
        else:
            raise ValueError("最大内容长度必须大于0")
