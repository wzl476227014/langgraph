"""
图表代码生成器
将图表配置转换为ECharts代码
"""

import json
from typing import Dict, Any
from .chart_config import ChartConfig, ChartType


class ChartCodeGenerator:
    """图表代码生成器 - 生成ECharts HTML代码"""
    
    # 专业配色方案（与PPT主色调一致）
    DEFAULT_COLORS = [
        'rgb(10, 66, 117)',      # 主色
        'rgba(10, 66, 117, 0.8)',
        'rgba(10, 66, 117, 0.6)',
        'rgba(10, 66, 117, 0.4)',
        'rgba(10, 66, 117, 0.2)',
    ]
    
    def __init__(self):
        """初始化生成器"""
        self.echarts_version = "5.4.3"
    
    def generate_chart_html(self, config: ChartConfig) -> str:
        """
        生成完整的图表HTML代码
        
        Args:
            config: 图表配置
            
        Returns:
            包含ECharts初始化代码的HTML片段
        """
        # 生成唯一容器ID
        if not config.container_id:
            import uuid
            config.container_id = f"chart_{uuid.uuid4().hex[:8]}"
        
        # 根据图表类型生成对应的ECharts配置
        config.height = 200
        if config.chart_type == ChartType.BAR:
            echarts_option = self._generate_bar_option(config)
        elif config.chart_type == ChartType.LINE:
            echarts_option = self._generate_line_option(config)
        elif config.chart_type == ChartType.PIE:
            echarts_option = self._generate_pie_option(config)
        elif config.chart_type == ChartType.GAUGE:
            echarts_option = self._generate_gauge_option(config)
        elif config.chart_type == ChartType.RADAR:
            echarts_option = self._generate_radar_option(config)
        elif config.chart_type == ChartType.TABLE:
            # 表格使用HTML table，不是ECharts
            return self._generate_table_html(config)
        else:
            echarts_option = self._generate_bar_option(config)  # 默认柱状图
        
        # 生成HTML代码
        html = f"""
<div class="chart-container" style="margin-bottom: 20px;">
    <h3 style="font-size: 28px; color: rgb(10, 66, 117); margin-bottom: 15px;">{config.title}</h3>
    <div id="{config.container_id}" style="width: 100%; height: {config.height}px;"></div>
</div>
<script>
(function() {{
    var chartDom = document.getElementById('{config.container_id}');
    var myChart = echarts.init(chartDom);
    var option = {echarts_option};
    myChart.setOption(option);
    
    // 响应式调整
    window.addEventListener('resize', function() {{
        myChart.resize();
    }});
}})();
</script>
"""
        return html
    
    def _generate_bar_option(self, config: ChartConfig) -> str:
        """生成柱状图配置"""
        option = {
            "color": config.options.get("color_scheme", self.DEFAULT_COLORS),
            "title": {
                "show": False  # 标题已在外部显示
            },
            "tooltip": {
                "trigger": "axis",
                "axisPointer": {
                    "type": "shadow"
                },
                "textStyle": {
                    "fontSize": 14
                }
            },
            "legend": {
                "show": config.options.get("show_legend", True),
                "top": config.options.get("legend_position", "top"),
                "textStyle": {
                    "fontSize": 16
                }
            },
            "grid": {
                "left": "10%",
                "right": "5%",
                "bottom": "10%",
                "top": "15%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "data": config.data.labels,
                "axisLabel": {
                    "fontSize": 14,
                    "rotate": 0
                },
                "name": config.options.get("x_axis_name", ""),
                "nameTextStyle": {
                    "fontSize": 16
                }
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {
                    "fontSize": 14
                },
                "name": config.options.get("y_axis_name", ""),
                "nameTextStyle": {
                    "fontSize": 16
                },
                "splitLine": {
                    "lineStyle": {
                        "color": "#f0f0f0"
                    }
                }
            },
            "series": []
        }
        
        # 添加数据系列
        for series in config.data.series:
            series_config = {
                "name": series.get("name", ""),
                "type": "bar",
                "data": series.get("data", []),
                "barMaxWidth": 60,
                "label": {
                    "show": config.options.get("show_data_labels", True),
                    "position": "top",
                    "fontSize": 14,
                    "fontWeight": "bold",
                    "formatter": "{c}" + config.options.get("unit", "")
                }
            }
            option["series"].append(series_config)
        
        return json.dumps(option, ensure_ascii=False, indent=2)
    
    def _generate_line_option(self, config: ChartConfig) -> str:
        """生成折线图配置"""
        option = {
            "color": config.options.get("color_scheme", self.DEFAULT_COLORS),
            "tooltip": {
                "trigger": "axis",
                "textStyle": {
                    "fontSize": 14
                }
            },
            "legend": {
                "show": config.options.get("show_legend", True),
                "top": config.options.get("legend_position", "top"),
                "textStyle": {
                    "fontSize": 16
                }
            },
            "grid": {
                "left": "10%",
                "right": "5%",
                "bottom": "10%",
                "top": "15%",
                "containLabel": True
            },
            "xAxis": {
                "type": "category",
                "data": config.data.labels,
                "boundaryGap": False,
                "axisLabel": {
                    "fontSize": 14
                },
                "name": config.options.get("x_axis_name", ""),
                "nameTextStyle": {
                    "fontSize": 16
                }
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {
                    "fontSize": 14
                },
                "name": config.options.get("y_axis_name", ""),
                "nameTextStyle": {
                    "fontSize": 16
                },
                "splitLine": {
                    "lineStyle": {
                        "color": "#f0f0f0"
                    }
                }
            },
            "series": []
        }
        
        # 添加数据系列
        for series in config.data.series:
            series_config = {
                "name": series.get("name", ""),
                "type": "line",
                "data": series.get("data", []),
                "smooth": True,
                "lineStyle": {
                    "width": 3
                },
                "label": {
                    "show": config.options.get("show_data_labels", False),
                    "fontSize": 14
                }
            }
            option["series"].append(series_config)
        
        return json.dumps(option, ensure_ascii=False, indent=2)
    
    def _generate_pie_option(self, config: ChartConfig) -> str:
        """生成饼图配置"""
        # 将labels和series[0].data组合成饼图数据格式
        pie_data = []
        if config.data.series and len(config.data.series) > 0:
            values = config.data.series[0].get("data", [])
            for i, label in enumerate(config.data.labels):
                if i < len(values):
                    pie_data.append({
                        "name": label,
                        "value": values[i]
                    })
        
        option = {
            "color": config.options.get("color_scheme", self.DEFAULT_COLORS),
            "tooltip": {
                "trigger": "item",
                "formatter": "{b}: {c} ({d}%)",
                "textStyle": {
                    "fontSize": 14
                }
            },
            "legend": {
                "show": config.options.get("show_legend", True),
                "orient": "vertical",
                "left": "right",
                "top": "center",
                "textStyle": {
                    "fontSize": 16
                }
            },
            "series": [
                {
                    "name": config.data.series[0].get("name", "") if config.data.series else "",
                    "type": "pie",
                    "radius": ["40%", "70%"],
                    "center": ["40%", "50%"],
                    "avoidLabelOverlap": True,
                    "itemStyle": {
                        "borderRadius": 8,
                        "borderColor": "#fff",
                        "borderWidth": 2
                    },
                    "label": {
                        "show": config.options.get("show_data_labels", True),
                        "fontSize": 14,
                        "formatter": "{b}\n{d}%"
                    },
                    "emphasis": {
                        "label": {
                            "show": True,
                            "fontSize": 16,
                            "fontWeight": "bold"
                        }
                    },
                    "data": pie_data
                }
            ]
        }
        
        return json.dumps(option, ensure_ascii=False, indent=2)
    
    def _generate_gauge_option(self, config: ChartConfig) -> str:
        """生成仪表盘配置"""
        value = config.data.value or 0
        max_value = config.data.max_value or 100
        
        option = {
            "series": [
                {
                    "type": "gauge",
                    "startAngle": 180,
                    "endAngle": 0,
                    "center": ["50%", "70%"],
                    "radius": "90%",
                    "min": 0,
                    "max": max_value,
                    "splitNumber": 8,
                    "axisLine": {
                        "lineStyle": {
                            "width": 15,
                            "color": [
                                [0.3, "#91cc75"],
                                [0.7, "rgb(10, 66, 117)"],
                                [1, "#ee6666"]
                            ]
                        }
                    },
                    "pointer": {
                        "itemStyle": {
                            "color": "auto"
                        }
                    },
                    "axisTick": {
                        "distance": -15,
                        "length": 8,
                        "lineStyle": {
                            "color": "#fff",
                            "width": 2
                        }
                    },
                    "splitLine": {
                        "distance": -20,
                        "length": 15,
                        "lineStyle": {
                            "color": "#fff",
                            "width": 3
                        }
                    },
                    "axisLabel": {
                        "color": "auto",
                        "distance": 25,
                        "fontSize": 14
                    },
                    "detail": {
                        "valueAnimation": True,
                        "formatter": "{value}" + config.options.get("unit", ""),
                        "color": "rgb(10, 66, 117)",
                        "fontSize": 32,
                        "offsetCenter": [0, "0%"]
                    },
                    "data": [
                        {
                            "value": value,
                            "name": ""
                        }
                    ]
                }
            ]
        }
        
        return json.dumps(option, ensure_ascii=False, indent=2)
    
    def _generate_radar_option(self, config: ChartConfig) -> str:
        """生成雷达图配置"""
        # 构建雷达图指标
        indicator = [{"name": label, "max": 100} for label in config.data.labels]
        
        option = {
            "color": config.options.get("color_scheme", self.DEFAULT_COLORS),
            "tooltip": {
                "textStyle": {
                    "fontSize": 14
                }
            },
            "legend": {
                "show": config.options.get("show_legend", True),
                "top": "top",
                "textStyle": {
                    "fontSize": 16
                }
            },
            "radar": {
                "indicator": indicator,
                "axisName": {
                    "fontSize": 14
                }
            },
            "series": []
        }
        
        for series in config.data.series:
            series_config = {
                "name": series.get("name", ""),
                "type": "radar",
                "data": [
                    {
                        "value": series.get("data", []),
                        "name": series.get("name", "")
                    }
                ]
            }
            option["series"].append(series_config)
        
        return json.dumps(option, ensure_ascii=False, indent=2)
    
    def _generate_table_html(self, config: ChartConfig) -> str:
        """生成HTML表格"""
        if not config.data.table_rows or not config.data.table_headers:
            return "<p>表格数据不完整</p>"
        
        html = f"""
<div class="table-container" style="margin-bottom: 20px;">
    <h3 style="font-size: 28px; color: rgb(10, 66, 117); margin-bottom: 15px;">{config.title}</h3>
    <table style="width: 100%; border-collapse: collapse; font-size: 18px;">
        <thead>
            <tr style="background-color: rgb(10, 66, 117); color: white;">
"""
        
        # 表头
        for header in config.data.table_headers:
            html += f'                <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">{header}</th>\n'
        
        html += """            </tr>
        </thead>
        <tbody>
"""
        
        # 表格行
        for i, row in enumerate(config.data.table_rows):
            bg_color = "#f9f9f9" if i % 2 == 0 else "white"
            html += f'            <tr style="background-color: {bg_color};">\n'
            for header in config.data.table_headers:
                value = row.get(header, "")
                html += f'                <td style="padding: 10px; border: 1px solid #ddd;">{value}</td>\n'
            html += '            </tr>\n'
        
        html += """        </tbody>
    </table>
</div>
"""
        return html
