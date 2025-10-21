"""
主程序入口
提供命令行接口和程序启动功能
"""

import argparse
import sys
import logging
import os
import traceback
from pathlib import Path
from typing import List, Optional, Dict, Any

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from src.graph.workflow import MultiAgentWorkflow, get_workflow
from src.graph.workflow_with_intelligent_routing import get_intelligent_workflow
from src.utils.config import get_config
from src.utils.logger import setup_logging, get_logger
from src.tools.file_upload_tool import FileUploadTool

logger = get_logger(__name__)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Multi-Agent Report Generation System (MARGS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  python src/main.py --chat  # 对话式交互模式（推荐）
  python src/main.py --task "生成一份关于人工智能发展的报告"
  python src/main.py --task "分析市场趋势" --constraints "使用正式语言风格"
  python src/main.py --task "优化报告" --file "report.pdf" --extract-only  # 只提取HTML页面
  python src/main.py --interactive  # 菜单式交互模式
  python src/main.py --config config/custom_settings.yaml  # 使用自定义配置
        """
    )
    
    parser.add_argument(
        "--task",
        type=str,
        help="用户请求的任务描述"
    )
    
    parser.add_argument(
        "--constraints",
        type=str,
        nargs="*",
        help="用户约束条件，可以指定多个"
    )
    
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="启动交互模式（菜单式）"
    )
    
    parser.add_argument(
        "--chat",
        "-c",
        action="store_true",
        help="启动对话式交互模式（推荐）"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="examples/sample_reports",
        help="报告输出目录"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="启用详细日志输出"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="MARGS 1.0.0"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        nargs="*",
        help="要上传的文件路径（支持PDF和Excel文件）"
    )
    
    parser.add_argument(
        "--file-operation",
        type=str,
        choices=["upload", "process", "validate"],
        default="upload",
        help="文件操作类型"
    )
    
    parser.add_argument(
        "--extract-only",
        action="store_true",
        help="仅提取HTML页面，不整合成完整报告"
    )
    
    parser.add_argument(
        "--use-premium-template",
        action="store_true",
        help="使用Premium高端模板直接生成幻灯片（基于abc-居中版.pdf设计风格）"
    )
    
    return parser.parse_args()


def setup_configuration(args):
    """设置配置"""
    config_manager  = get_config()
    
    # 设置日志级别
    log_level_str = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level_str)

    # 设置输出目录
    if args.output_dir:
        output_config = config_manager.get_output_config()
        output_config["reports_directory"] = args.output_dir
    
    logger.info("配置设置完成", agent_name="Main")
    
    return config_manager


def run_chat_mode():
    """运行对话式交互模式"""
    try:
        from src.interactive_chat import InteractiveChatSystem
        chat_system = InteractiveChatSystem()
        chat_system.run_chat()
    except ImportError:
        print("ERROR: 对话模式模块未找到，请确认 interactive_chat.py 存在")
        logger.error("对话模式模块导入失败", agent_name="Main")
    except Exception as e:
        print(f"ERROR: 启动对话模式失败: {str(e)}")
        logger.error(f"启动对话模式失败: {str(e)}", agent_name="Main")


def run_interactive_mode():
    """运行交互模式"""
    print("=" * 60)
    print("Multi-Agent Report Generation System (MARGS)")
    print("交互模式")
    print("=" * 60)
    print()
    
    workflow = get_intelligent_workflow()  # 使用智能工作流
    
    while True:
        print("\n请选择操作:")
        print("1. 生成报告")
        print("2. 查看系统状态")
        print("3. 查看帮助")
        print("4. 退出")
        
        choice = input("\n请输入选项 (1-4): ").strip()
        
        if choice == "1":
            generate_report_interactive(workflow)
        elif choice == "2":
            show_system_status()
        elif choice == "3":
            show_help()
        elif choice == "4":
            print("感谢使用 MARGS，再见！")
            break
        else:
            print("无效选项，请重新输入。")


def generate_report_interactive(workflow):
    """交互式生成报告"""
    print("\n" + "=" * 40)
    print("报告生成")
    print("=" * 40)
    
    # 获取用户请求
    task = input("请输入您想要生成的报告主题或任务: ").strip()
    if not task:
        print("任务不能为空！")
        return
    
    # 获取约束条件
    print("\n请输入约束条件（可选，每行一个，输入空行结束）:")
    constraints = []
    while True:
        constraint = input().strip()
        if not constraint:
            break
        constraints.append(constraint)
    
    # 确认信息
    print(f"\n任务: {task}")
    if constraints:
        print("约束条件:")
        for i, constraint in enumerate(constraints, 1):
            print(f"  {i}. {constraint}")
    
    confirm = input("\n确认生成报告吗？(y/N): ").strip().lower()
    if confirm not in ['y', 'yes', '是']:
        print("已取消报告生成。")
        return
    
    # 执行工作流
    print("\n开始执行报告生成流程...")
    try:
        result = workflow.execute(task, constraints, None, False)
        
        # 显示结果
        print("\n" + "=" * 40)
        print("报告生成完成！")
        print("=" * 40)
        
        if result and hasattr(result, 'get_execution_result'):
            final_result = result.get_execution_result("step_final")
            if final_result and final_result.get("report_metadata"):
                metadata = final_result["report_metadata"]
                print(f"报告文件: {metadata['output_path']}")
                print(f"文件大小: {metadata['file_size']} 字符")
                print(f"生成时间: {metadata['generation_time']}")
            else:
                print("报告已生成，但无法获取详细信息。")
        else:
            print("报告生成完成，但结果格式异常。")
        
    except Exception as e:
        print(f"\n报告生成失败: {str(e)}")
        logger.error(f"交互模式报告生成失败: {str(e)}", agent_name="Main")


def show_system_status():
    """显示系统状态"""
    print("\n" + "=" * 40)
    print("系统状态")
    print("=" * 40)
    
    try:
        workflow = get_intelligent_workflow()  # 使用智能工作流
        from src.graph.state import create_workflow_state
        state = create_workflow_state("status_check", "检查系统状态")
        status = workflow.get_workflow_status(state)
        
        print(f"工作流状态: {status.get('workflow_status', '未知')}")
        print(f"Agent数量: {len(workflow.agents) if hasattr(workflow, 'agents') else '未知'}")
        print(f"工具数量: {len(workflow.tools) if hasattr(workflow, 'tools') else '未知'}")
        
    except Exception as e:
        print(f"获取系统状态失败: {str(e)}")


def show_help():
    """显示帮助信息"""
    print("\n" + "=" * 40)
    print("帮助信息")
    print("=" * 40)
    
    help_text = """
MARGS 使用指南:

1. 命令行模式:
   python src/main.py --task "您的任务描述"
   
   示例:
   python src/main.py --task "生成一份关于人工智能发展的报告"
   python src/main.py --task "分析市场趋势" --constraints "使用正式语言风格"

2. 对话式交互模式（推荐）:
   python src/main.py --chat
   与智能助手自然对话，支持打字机效果

3. 菜单式交互模式:
   python src/main.py --interactive
   按照提示输入任务和约束条件

4. 配置文件:
   可以使用 --config 参数指定自定义配置文件
   默认配置文件: config/settings.yaml

5. 输出目录:
   使用 --output-dir 参数指定报告输出目录
   默认输出目录: examples/sample_reports

6. 日志级别:
   使用 --verbose 参数启用详细日志输出

支持的Agent:
- Plan Agent: 规划专家，制定报告生成计划
- React Agent: 执行专家，逐步执行计划
- Reflect Agent: 质量评估专家，评估结果质量
- Memory Agent: 信息管理专家，管理流程信息
- Report Agent: 报告生成专家，生成最终报告

支持的工具:
- Web Search Tool: 网络搜索工具
- Data Processor Tool: 数据处理器工具
- Content Generator Tool: 内容生成器工具
- File Upload Tool: 文件上传工具

常见问题:
1. 如果遇到配置错误，请检查配置文件格式
2. 如果报告生成失败，请查看详细日志信息
3. 如果需要自定义输出格式，请修改模板文件

更多信息请参考项目文档。
    """
    
    print(help_text)


def run_single_task(args):
    """运行单个任务"""
    task = args.task
    constraints = args.constraints or []
    files = args.file or []
    
    if not task:
        print("错误: 必须指定任务描述")
        print("使用 --help 查看帮助信息")
        return
    
    print(f"任务: {task}")
    if constraints:
        print("约束条件:")
        for i, constraint in enumerate(constraints, 1):
            print(f"  {i}. {constraint}")
    
    # 处理文件上传
    if files:
        print(f"\n文件处理 ({len(files)} 个文件):")
        uploaded_files = process_files(files, args.file_operation, task)
        if uploaded_files:
            print(f"OK 成功处理 {len(uploaded_files)} 个文件")
        else:
            print("WARNING 文件处理失败，将不使用文件数据")
    
    print("\n开始执行报告生成流程...")
    
    try:
        workflow = get_intelligent_workflow()  # 使用智能工作流
        
        # 检查是否有文件处理结果需要传递
        file_processing_results = None
        if 'uploaded_files' in locals() and uploaded_files:
            file_processing_results = [{"success": True, "result": file_info} for file_info in uploaded_files]
        
        result = workflow.execute(task, constraints, file_processing_results, args.extract_only, use_premium_template=args.use_premium_template)
        
        # 显示结果摘要
        print("\n" + "=" * 50)
        print("报告生成完成！")
        print("=" * 50)
        
        if result:
            # result can be either a WorkflowState object or a dictionary
            # Handle both cases
            if hasattr(result, 'execution_steps'):
                # WorkflowState object
                execution_steps = result.execution_steps
                execution_results = result.execution_results
                quality_assessment = result.quality_assessment
            else:
                # Dictionary representation
                execution_steps = result.get('execution_steps', [])
                execution_results = result.get('execution_results', {})
                quality_assessment = result.get('quality_assessment')
            
            # 获取最终报告信息
            final_step = None
            for step in execution_steps:
                step_id = step.step_id if hasattr(step, 'step_id') else step.get('step_id')
                if step_id == "step_final":
                    final_step = step
                    break
            
            if final_step:
                step_status = final_step.status.value if hasattr(final_step, 'status') else final_step.get('status')
                if step_status == "completed":
                    # Access the execution_results dictionary directly
                    final_result_data = execution_results.get("step_final")
                    if final_result_data and final_result_data.get("report_metadata"):
                        metadata = final_result_data["report_metadata"]
                        print(f"OK 报告文件: {metadata['output_path']}")
                        print(f"OK 文件大小: {metadata['file_size']} 字符")
                        print(f"OK 生成时间: {metadata['generation_time']}")
                        print(f"OK 报告格式: {metadata['report_format']}")
                        
                        # 检查文件是否存在
                        if os.path.exists(metadata['output_path']):
                            print(f"OK 文件已成功保存")
                        else:
                            print(f"WARNING 文件保存路径可能有问题")
                    else:
                        print("OK 报告已生成，但无法获取元数据信息")
                else:
                    print("WARNING 报告生成可能未完全完成")
            else:
                print("WARNING 报告生成可能未完全完成")
            
            # 显示工作流统计
            completed_steps_list = []
            for step in execution_steps:
                step_status = step.status.value if hasattr(step, 'status') else step.get('status')
                if step_status == 'completed':
                    completed_steps_list.append(step)
            
            completed_steps = len(completed_steps_list)
            total_steps = len(execution_steps)
            
            print(f"\nSTATS 执行统计:")
            print(f"   总步骤数: {total_steps}")
            print(f"   完成步骤: {completed_steps}")
            if total_steps > 0:
                print(f"   成功率: {completed_steps/total_steps*100:.1f}%")
            else:
                print(f"   成功率: 0.0%")
            
            # 显示质量评估
            if quality_assessment:
                if hasattr(quality_assessment, 'overall_score'):
                    overall_score = quality_assessment.overall_score
                else:
                    overall_score = quality_assessment.get('overall_score', 0.0)
                print(f"\nQUALITY 质量评估:")
                print(f"   总体评分: {overall_score:.2f}/1.0")
                print(f"   评估结果: {'通过' if overall_score >= 0.8 else '需改进'}")
                
        else:
            print("ERROR 报告生成失败")
        
    except Exception as e:
        print(f"\nERROR 报告生成失败: {str(e)}")
        logger.error(f"单任务模式报告生成失败: {str(e)}", agent_name="Main")
        
        if args.verbose:
            traceback.print_exc()


def process_files(file_paths, operation, task):
    """处理文件上传"""
    uploaded_files = []
    
    try:
        file_tool = FileUploadTool()
        
        for file_path in file_paths:
            print(f"  FILE 处理文件: {file_path}")
            
            # 验证文件是否存在
            if not os.path.exists(file_path):
                print(f"    ERROR 文件不存在: {file_path}")
                continue
            
            # 执行文件操作
            input_data = {
                "task": task,
                "file_path": file_path,
                "operation": operation
            }
            
            result = file_tool.execute(input_data)
            
            if result.get("success"):
                file_info = result.get("result", {})
                uploaded_files.append(file_info)
                
                # 显示文件处理结果
                file_type = file_info.get("file_type", "unknown")
                file_size = file_info.get("file_size", 0)
                print(f"    OK 成功处理 {file_type} 文件 ({file_size} 字节)")
                
                # 如果是PDF文件，显示文本提取结果
                if file_type == "pdf" and "text_content" in file_info:
                    text_length = file_info.get("text_length", 0)
                    print(f"    TEXT 提取文本: {text_length} 字符")
                
                # 如果是Excel文件，显示工作表信息
                elif file_type == "excel" and "sheets" in file_info:
                    sheets = file_info.get("sheets", {})
                    print(f"    SHEETS 工作表数量: {len(sheets)}")
                    for sheet_name in sheets.keys():
                        print(f"      - {sheet_name}")
                
            else:
                error_msg = result.get("error", "未知错误")
                print(f"    ERROR 处理失败: {error_msg}")
        
    except Exception as e:
        print(f"  ERROR 文件处理工具初始化失败: {str(e)}")
        logger.error(f"文件处理工具初始化失败: {str(e)}", agent_name="Main")
    
    return uploaded_files


def main():
    """主函数"""
    try:
        # 解析命令行参数
        args = parse_arguments()
        # 设置配置
        config = setup_configuration(args)
        
        logger.info("MARGS 启动", agent_name="Main")
        
        # 根据参数选择运行模式
        if args.chat:
            run_chat_mode()
        elif args.interactive:
            run_interactive_mode()
        elif args.task:
            run_single_task(args)
        else:
            # 没有指定任务，显示帮助信息
            print("MARGS - Multi-Agent Report Generation System")
            print("请使用 --help 查看使用说明")
            print()
            print("快速开始:")
            print("  python src/main.py --chat          # 对话式交互模式（推荐）")
            print("  python src/main.py --interactive    # 菜单式交互模式")
            print("  python src/main.py --task \"您的任务\"  # 命令行模式")
    
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
        logger.info("程序被用户中断", agent_name="Main")
        sys.exit(1)
    except Exception as e:
        print(f"\n程序运行出错: {str(e)}")
        logger.error(f"程序运行出错: {str(e)}", agent_name="Main")
        
        # Always print traceback for debugging
        print("--- Full Traceback ---")
        traceback.print_exc()
        print("----------------------")
        
        sys.exit(1)


if __name__ == "__main__":
    main()
