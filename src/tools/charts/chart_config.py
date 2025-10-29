"""
图表配置数据结构
定义LLM输出的图表配置格式
"""

from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


class ChartType(Enum):
    """图表类型枚举"""
    BAR = "bar"  # 柱状图
    LINE = "line"  # 折线图
    PIE = "pie"  # 饼图
    GAUGE = "gauge"  # 仪表盘
    RADAR = "radar"  # 雷达图
    SCATTER = "scatter"  # 散点图
    FUNNEL = "funnel"  # 漏斗图
    TABLE = "table"  # 表格（非图表，但归类到数据展示）


@dataclass
class ChartData:
    """图表数据结构"""
    # 标签（X轴或分类）
    labels: List[str] = field(default_factory=list)
    
    # 数据系列
    series: List[Dict[str, Any]] = field(default_factory=list)
    # series 格式: [{"name": "系列1", "data": [1, 2, 3]}, ...]
    
    # 单值数据（用于仪表盘等）
    value: Optional[float] = None
    
    # 最大值（用于仪表盘等）
    max_value: Optional[float] = None
    
    # 表格数据（用于table类型）
    table_rows: Optional[List[Dict[str, Any]]] = None
    table_headers: Optional[List[str]] = None


@dataclass
class ChartConfig:
    """图表完整配置"""
    # 图表类型
    chart_type: ChartType
    
    # 图表标题
    title: str
    
    # 图表数据
    data: ChartData
    
    # 容器ID（自动生成）
    container_id: str = ""
    
    # 高度（px）
    height: int = 400
    
    # 配置选项
    options: Dict[str, Any] = field(default_factory=dict)
    # options可包含：
    # - show_legend: bool (是否显示图例)
    # - legend_position: str (图例位置: "top", "right", "bottom", "left")
    # - show_data_labels: bool (是否显示数据标签)
    # - color_scheme: List[str] (自定义颜色方案)
    # - y_axis_name: str (Y轴名称)
    # - x_axis_name: str (X轴名称)
    # - unit: str (数据单位)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "chart_type": self.chart_type.value,
            "title": self.title,
            "data": {
                "labels": self.data.labels,
                "series": self.data.series,
                "value": self.data.value,
                "max_value": self.data.max_value,
                "table_rows": self.data.table_rows,
                "table_headers": self.data.table_headers
            },
            "container_id": self.container_id,
            "height": self.height,
            "options": self.options
        }
    
    @staticmethod
    def from_dict(config_dict: Dict[str, Any]) -> 'ChartConfig':
        """从字典创建配置对象"""
        chart_type = ChartType(config_dict["chart_type"])
        
        data_dict = config_dict["data"]
        data = ChartData(
            labels=data_dict.get("labels", []),
            series=data_dict.get("series", []),
            value=data_dict.get("value"),
            max_value=data_dict.get("max_value"),
            table_rows=data_dict.get("table_rows"),
            table_headers=data_dict.get("table_headers")
        )
        
        return ChartConfig(
            chart_type=chart_type,
            title=config_dict["title"],
            data=data,
            container_id=config_dict.get("container_id", ""),
            height=config_dict.get("height", 400),
            options=config_dict.get("options", {})
        )


def validate_chart_config(config: ChartConfig) -> bool:
    """验证图表配置的完整性"""
    # 基础验证
    if not config.title:
        return False
    
    # 根据图表类型验证数据
    if config.chart_type == ChartType.GAUGE:
        if config.data.value is None:
            return False
    elif config.chart_type == ChartType.TABLE:
        if not config.data.table_rows or not config.data.table_headers:
            return False
    else:
        # 其他图表类型需要labels和series
        if not config.data.labels or not config.data.series:
            return False
    
    return True
