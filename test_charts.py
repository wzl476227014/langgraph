#!/usr/bin/env python3
"""
图表系统测试脚本
验证图表配置、生成和占位符处理功能
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.tools.charts.chart_config import ChartConfig, ChartType, ChartData, validate_chart_config
from src.tools.charts.chart_generator import ChartCodeGenerator
from src.tools.charts.chart_processor import ChartProcessor


def test_chart_config():
    """测试图表配置"""
    print("=" * 60)
    print("测试1: 图表配置创建和验证")
    print("=" * 60)
    
    # 创建柱状图配置
    config = ChartConfig(
        chart_type=ChartType.BAR,
        title="测试柱状图",
        data=ChartData(
            labels=["Q1", "Q2", "Q3", "Q4"],
            series=[
                {"name": "2023年", "data": [120, 150, 180, 200]},
                {"name": "2024年", "data": [150, 180, 220, 250]}
            ]
        ),
        height=400,
        options={
            "show_legend": True,
            "unit": "万元"
        }
    )
    
    print(f"✅ 配置类型: {config.chart_type.value}")
    print(f"✅ 标题: {config.title}")
    print(f"✅ 高度: {config.height}px")
    print(f"✅ 数据系列数: {len(config.data.series)}")
    print(f"✅ 验证结果: {'通过' if validate_chart_config(config) else '失败'}")
    
    # 转换为字典
    config_dict = config.to_dict()
    print(f"✅ 可序列化: {len(str(config_dict))} 字符")
    
    # 从字典恢复
    restored_config = ChartConfig.from_dict(config_dict)
    print(f"✅ 反序列化: {restored_config.title}")
    
    print()


def test_chart_generator():
    """测试图表代码生成"""
    print("=" * 60)
    print("测试2: ECharts代码生成")
    print("=" * 60)
    
    generator = ChartCodeGenerator()
    
    # 测试柱状图
    bar_config = ChartConfig(
        chart_type=ChartType.BAR,
        title="销售额对比",
        data=ChartData(
            labels=["Q1", "Q2", "Q3"],
            series=[{"name": "销售额", "data": [100, 150, 200]}]
        ),
        height=400
    )
    
    bar_html = generator.generate_chart_html(bar_config)
    print(f"✅ 柱状图HTML: {len(bar_html)} 字符")
    print(f"   - 包含容器ID: {'id=' in bar_html}")
    print(f"   - 包含ECharts初始化: {'echarts.init' in bar_html}")
    print(f"   - 包含option配置: {'var option' in bar_html}")
    
    # 测试饼图
    pie_config = ChartConfig(
        chart_type=ChartType.PIE,
        title="市场份额",
        data=ChartData(
            labels=["产品A", "产品B", "产品C"],
            series=[{"name": "份额", "data": [35, 28, 22]}]
        ),
        height=350
    )
    
    pie_html = generator.generate_chart_html(pie_config)
    print(f"✅ 饼图HTML: {len(pie_html)} 字符")
    
    # 测试仪表盘
    gauge_config = ChartConfig(
        chart_type=ChartType.GAUGE,
        title="完成率",
        data=ChartData(value=75, max_value=100),
        height=350,
        options={"unit": "%"}
    )
    
    gauge_html = generator.generate_chart_html(gauge_config)
    print(f"✅ 仪表盘HTML: {len(gauge_html)} 字符")
    
    # 测试表格
    table_config = ChartConfig(
        chart_type=ChartType.TABLE,
        title="关键指标",
        data=ChartData(
            table_headers=["指标", "数值"],
            table_rows=[
                {"指标": "收入", "数值": "100万"},
                {"指标": "用户", "数值": "1000"}
            ]
        ),
        height=300
    )
    
    table_html = generator._generate_table_html(table_config)
    print(f"✅ 表格HTML: {len(table_html)} 字符")
    print(f"   - 包含表头: {'<thead>' in table_html}")
    print(f"   - 包含表体: {'<tbody>' in table_html}")
    
    print()


def test_chart_processor():
    """测试占位符处理"""
    print("=" * 60)
    print("测试3: 占位符处理器")
    print("=" * 60)
    
    processor = ChartProcessor()
    
    # 创建测试HTML
    test_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>测试页面</title>
</head>
<body>
    <div class="content">
        <h1>销售数据分析</h1>
        
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "bar",
          "title": "季度销售额",
          "height": 400,
          "data": {
            "labels": ["Q1", "Q2", "Q3", "Q4"],
            "series": [
              {"name": "2024年", "data": [120, 150, 180, 200]}
            ]
          },
          "options": {
            "show_legend": true,
            "unit": "万元"
          }
        } -->
        
        <p>分析说明文字</p>
        
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "pie",
          "title": "市场份额",
          "height": 350,
          "data": {
            "labels": ["产品A", "产品B", "产品C"],
            "series": [{"name": "份额", "data": [40, 35, 25]}]
          }
        } -->
    </div>
</body>
</html>"""
    
    # 验证占位符
    validation = processor.validate_placeholders(test_html)
    print(f"✅ 占位符验证:")
    print(f"   - 有效: {validation['valid']}")
    print(f"   - 数量: {validation['count']}")
    print(f"   - 错误: {validation['errors'] if validation['errors'] else '无'}")
    
    # 提取配置
    configs = processor.extract_chart_configs(test_html)
    print(f"✅ 提取配置: {len(configs)} 个")
    for i, config in enumerate(configs):
        print(f"   - 图表{i+1}: {config['chart_type']} - {config['title']}")
    
    # 处理HTML
    processed_html = processor.process_html(test_html)
    print(f"✅ HTML处理:")
    print(f"   - 原始长度: {len(test_html)} 字符")
    print(f"   - 处理后长度: {len(processed_html)} 字符")
    print(f"   - 包含ECharts库: {'echarts.min.js' in processed_html}")
    print(f"   - 占位符已替换: {'CHART_PLACEHOLDER' not in processed_html}")
    print(f"   - 包含图表容器: {'chart-container' in processed_html}")
    print(f"   - 包含ECharts实例: {'echarts.init' in processed_html}")
    
    # 保存处理后的HTML（可选）
    output_path = "test_output_chart.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(processed_html)
    print(f"✅ 测试文件已保存: {output_path}")
    print(f"   提示: 用浏览器打开此文件查看效果")
    
    print()


def test_all_chart_types():
    """测试所有图表类型"""
    print("=" * 60)
    print("测试4: 所有图表类型完整示例")
    print("=" * 60)
    
    processor = ChartProcessor()
    
    # 创建包含所有图表类型的HTML
    all_charts_html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>图表测试 - 所有类型</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: rgb(10, 66, 117);
            text-align: center;
            margin-bottom: 40px;
        }
        .section {
            background: white;
            padding: 30px;
            margin-bottom: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <h1>📊 图表生成系统测试 - 所有类型展示</h1>
    
    <div class="section">
        <h2>1. 柱状图 (Bar Chart)</h2>
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "bar",
          "title": "季度销售额对比",
          "height": 400,
          "data": {
            "labels": ["Q1", "Q2", "Q3", "Q4"],
            "series": [
              {"name": "2023年", "data": [120, 150, 180, 200]},
              {"name": "2024年", "data": [150, 180, 220, 250]}
            ]
          },
          "options": {
            "show_legend": true,
            "legend_position": "top",
            "show_data_labels": true,
            "y_axis_name": "销售额",
            "x_axis_name": "季度",
            "unit": "万元"
          }
        } -->
    </div>
    
    <div class="section">
        <h2>2. 折线图 (Line Chart)</h2>
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "line",
          "title": "用户增长趋势",
          "height": 400,
          "data": {
            "labels": ["1月", "2月", "3月", "4月", "5月", "6月"],
            "series": [
              {"name": "活跃用户", "data": [1000, 1200, 1500, 1800, 2200, 2500]},
              {"name": "新增用户", "data": [200, 250, 300, 350, 400, 450]}
            ]
          },
          "options": {
            "show_legend": true,
            "y_axis_name": "用户数",
            "unit": "人"
          }
        } -->
    </div>
    
    <div class="section">
        <h2>3. 饼图 (Pie Chart)</h2>
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "pie",
          "title": "市场份额分布",
          "height": 350,
          "data": {
            "labels": ["产品A", "产品B", "产品C", "产品D", "其他"],
            "series": [
              {"name": "市场份额", "data": [35, 28, 22, 10, 5]}
            ]
          },
          "options": {
            "show_legend": true,
            "show_data_labels": true
          }
        } -->
    </div>
    
    <div class="section">
        <h2>4. 仪表盘 (Gauge)</h2>
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "gauge",
          "title": "目标完成率",
          "height": 350,
          "data": {
            "value": 75.5,
            "max_value": 100
          },
          "options": {
            "unit": "%"
          }
        } -->
    </div>
    
    <div class="section">
        <h2>5. 雷达图 (Radar Chart)</h2>
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "radar",
          "title": "综合能力评估",
          "height": 400,
          "data": {
            "labels": ["技术能力", "沟通能力", "领导力", "创新力", "执行力"],
            "series": [
              {"name": "员工A", "data": [85, 75, 70, 90, 80]},
              {"name": "员工B", "data": [70, 85, 80, 75, 85]}
            ]
          },
          "options": {
            "show_legend": true
          }
        } -->
    </div>
    
    <div class="section">
        <h2>6. 表格 (Table)</h2>
        <!-- CHART_PLACEHOLDER: {
          "chart_type": "table",
          "title": "关键指标汇总",
          "height": 300,
          "data": {
            "table_headers": ["指标名称", "2023年", "2024年", "增长率", "目标值"],
            "table_rows": [
              {"指标名称": "营业收入", "2023年": "100万", "2024年": "150万", "增长率": "+50%", "目标值": "200万"},
              {"指标名称": "用户数", "2023年": "10000", "2024年": "15000", "增长率": "+50%", "目标值": "20000"},
              {"指标名称": "客户满意度", "2023年": "85%", "2024年": "90%", "增长率": "+5%", "目标值": "95%"},
              {"指标名称": "市场份额", "2023年": "15%", "2024年": "18%", "增长率": "+3%", "目标值": "25%"}
            ]
          }
        } -->
    </div>
    
    <div style="text-align: center; padding: 40px; color: #666;">
        <p>✅ 图表生成系统测试完成</p>
        <p>所有图表类型均已成功渲染</p>
    </div>
</body>
</html>"""
    
    # 处理HTML
    processed = processor.process_html(all_charts_html)
    
    # 保存完整示例
    output_file = "test_all_charts.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(processed)
    
    print(f"✅ 完整示例已生成: {output_file}")
    print(f"   - 包含6种图表类型")
    print(f"   - 文件大小: {len(processed)} 字符")
    print(f"   - 用浏览器打开查看所有图表效果")
    print()


def main():
    """运行所有测试"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "图表系统测试套件" + " " * 15 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        test_chart_config()
        test_chart_generator()
        test_chart_processor()
        test_all_chart_types()
        
        print("╔" + "=" * 58 + "╗")
        print("║" + " " * 10 + "✅ 所有测试通过！" + " " * 10 + "║")
        print("╚" + "=" * 58 + "╝")
        print()
        print("📝 查看生成的测试文件:")
        print("   - test_output_chart.html (基础测试)")
        print("   - test_all_charts.html (完整示例)")
        print()
        print("🌐 在浏览器中打开这些文件，查看图表渲染效果")
        print()
        
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
