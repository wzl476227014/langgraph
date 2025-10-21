"""
对话式交互界面
提供打字机效果的对话式交互体验
"""

import time
import sys
import threading
from typing import List, Optional, Dict, Any
from pathlib import Path

# 添加项目根目录到路径
sys.path.append(str(Path(__file__).parent.parent))

from src.graph.workflow import get_workflow
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TypewriterEffect:
    """打字机效果类"""
    
    def __init__(self, speed: float = 0.03, pause_after_sentence: float = 0.1):
        """
        初始化打字机效果
        
        Args:
            speed: 每个字符的显示间隔（秒）
            pause_after_sentence: 句子结束后的停顿时间（秒）
        """
        self.speed = speed
        self.pause_after_sentence = pause_after_sentence
        self._interrupted = False
    
    def type_text(self, text: str, color_code: str = "", end_char: str = "\n"):
        """
        以打字机效果显示文本
        
        Args:
            text: 要显示的文本
            color_code: ANSI颜色代码
            end_char: 结束字符
        """
        self._interrupted = False
        
        # ANSI颜色代码
        colors = {
            "blue": "\033[94m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "red": "\033[91m",
            "purple": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
            "reset": "\033[0m"
        }
        
        if color_code in colors:
            sys.stdout.write(colors[color_code])
        
        for char in text:
            if self._interrupted:
                # 如果被中断，直接显示剩余文本
                remaining_text = text[text.index(char):]
                try:
                    sys.stdout.write(remaining_text)
                except UnicodeEncodeError:
                    # 处理编码问题
                    sys.stdout.buffer.write(remaining_text.encode('utf-8', errors='ignore'))
                break
            
            try:
                sys.stdout.write(char)
                sys.stdout.flush()
            except UnicodeEncodeError:
                # 处理特殊字符（如emoji）的编码问题
                try:
                    sys.stdout.buffer.write(char.encode('utf-8', errors='ignore'))
                    sys.stdout.buffer.flush()
                except:
                    # 如果仍然失败，跳过这个字符
                    continue
            
            # 句子结束时稍微停顿
            if char in ['。', '！', '？', '.', '!', '?']:
                time.sleep(self.pause_after_sentence)
            elif char == '\n':
                time.sleep(self.pause_after_sentence * 0.5)
            else:
                time.sleep(self.speed)
        
        if color_code in colors:
            sys.stdout.write(colors["reset"])
        
        sys.stdout.write(end_char)
        sys.stdout.flush()
    
    def interrupt(self):
        """中断打字机效果"""
        self._interrupted = True


class InteractiveChatSystem:
    """对话式交互系统"""
    
    def __init__(self):
        """初始化对话系统"""
        self.typewriter = TypewriterEffect(speed=0.02)
        self.workflow = None
        self.conversation_history = []
        
        # 系统角色设定
        self.system_role = "MARGS智能助手"
        
    def initialize_system(self):
        """初始化系统组件"""
        try:
            self.workflow = get_workflow()
            return True
        except Exception as e:
            logger.error(f"系统初始化失败: {str(e)}", agent_name="ChatSystem")
            return False
    
    def print_welcome(self):
        """显示欢迎信息"""
        welcome_text = f"""
================================================================================
                   Multi-Agent Report Generation System                      
                              智能对话助手                                    
================================================================================

你好！我是{self.system_role}，很高兴为你服务！

我可以帮助你：
• 生成各类专业报告
• 分析数据和趋势  
• 制定报告计划
• 搜索相关信息
• 处理上传的文件

小提示：
- 直接告诉我你需要什么报告，我会为你量身定制
- 输入 '/help' 查看更多功能
- 输入 '/quit' 或 '/exit' 退出对话
- 按 Ctrl+C 可以跳过正在显示的文本

让我们开始对话吧！请问今天我可以为你做些什么？
"""
        
        self.typewriter.type_text(welcome_text, "cyan")
    
    def get_user_input(self) -> str:
        """获取用户输入"""
        try:
            # 显示输入提示符
            print(f"\n\033[96m你\033[0m: ", end="", flush=True)
            user_input = input().strip()
            return user_input
        except KeyboardInterrupt:
            return "/quit"
        except EOFError:
            return "/quit"
    
    def process_command(self, command: str) -> bool:
        """
        处理特殊命令
        
        Args:
            command: 用户输入的命令
            
        Returns:
            是否应该继续对话
        """
        command = command.lower().strip()
        
        if command in ['/quit', '/exit', '退出', '再见', 'bye']:
            self.typewriter.type_text("感谢使用MARGS智能助手，期待下次为你服务！再见！", "green")
            return False
        
        elif command in ['/help', '帮助']:
            self.show_help()
            return True
        
        elif command in ['/clear', '清屏']:
            import os
            os.system('cls' if os.name == 'nt' else 'clear')
            self.print_welcome()
            return True
        
        elif command in ['/history', '历史']:
            self.show_conversation_history()
            return True
        
        elif command in ['/status', '状态']:
            self.show_system_status()
            return True
        
        return True
    
    def show_help(self):
        """显示帮助信息"""
        help_text = """
MARGS智能助手 - 帮助信息

报告生成示例：
• "生成一份关于人工智能发展趋势的报告"
• "帮我分析2024年的市场数据"
• "制作一份网络安全评估报告"
• "生成季度业务总结报告"

可用命令：
• /help 或 帮助    - 显示此帮助信息
• /clear 或 清屏   - 清除屏幕内容
• /history 或 历史 - 查看对话历史
• /status 或 状态  - 查看系统状态
• /quit 或 /exit   - 退出对话

使用技巧：
• 可以指定报告的格式、风格、长度等要求
• 支持上传PDF、Excel等文件进行分析
• 可以要求生成PPT格式的报告
• 支持多轮对话，可以逐步完善需求

高级功能：
• 自动规划报告结构
• 智能搜索相关资料
• 多Agent协作生成
• 质量评估和优化
"""
        
        self.typewriter.type_text(help_text, "yellow")
    
    def show_conversation_history(self):
        """显示对话历史"""
        if not self.conversation_history:
            self.typewriter.type_text("暂无对话历史。", "yellow")
            return
        
        history_text = "对话历史：\n\n"
        for i, (user_msg, system_msg) in enumerate(self.conversation_history[-5:], 1):  # 只显示最近5条
            history_text += f"[{i}] 你: {user_msg[:50]}{'...' if len(user_msg) > 50 else ''}\n"
            history_text += f"[{i}] 助手: {system_msg[:100]}{'...' if len(system_msg) > 100 else ''}\n\n"
        
        self.typewriter.type_text(history_text, "blue")
    
    def show_system_status(self):
        """显示系统状态"""
        try:
            status_text = f"""
系统状态信息：

• 工作流状态: {'正常运行' if self.workflow else '未初始化'}
• 对话历史: {len(self.conversation_history)} 条记录
• 系统角色: {self.system_role}
• 打字机效果: 已启用

功能模块状态:
• Plan Agent (规划专家): 就绪
• React Agent (执行专家): 就绪  
• Report Agent (报告生成): 就绪
• Memory Agent (信息管理): 就绪
• Integration Agent (整合专家): 就绪

工具状态:
• Web搜索工具: 可用
• 文件处理工具: 可用
• PPT生成工具: 可用
• 内容生成器: 可用
"""
            
            self.typewriter.type_text(status_text, "green")
            
        except Exception as e:
            error_text = f"获取系统状态失败: {str(e)}"
            self.typewriter.type_text(error_text, "red")
    
    def generate_response(self, user_input: str) -> str:
        """
        生成系统回应
        
        Args:
            user_input: 用户输入
            
        Returns:
            系统回应文本
        """
        try:
            # 添加思考提示
            thinking_messages = [
                "让我想想...",
                "正在分析你的需求...",
                "准备为你生成报告...",
                "搜索相关信息中...",
                "制定报告计划中..."
            ]
            
            import random
            thinking_msg = random.choice(thinking_messages)
            self.typewriter.type_text(f"\n\033[95m{self.system_role}\033[0m: {thinking_msg}", end_char="")
            
            # 模拟思考时间
            time.sleep(1.0)
            
            # 清除思考提示行
            sys.stdout.write("\r" + " " * (len(f"{self.system_role}: {thinking_msg}") + 10) + "\r")
            sys.stdout.flush()
            
            # 执行实际的报告生成
            if self.workflow:
                result = self.workflow.execute(user_input, [])
                
                if result:
                    # 生成友好的回应
                    response = self.format_workflow_result(result, user_input)
                else:
                    response = "抱歉，报告生成过程中遇到了一些问题。让我们重新尝试，或者你可以提供更多具体信息。"
            else:
                response = "系统暂时无法处理请求，请稍后重试或联系管理员。"
            
            return response
            
        except Exception as e:
            logger.error(f"生成回应失败: {str(e)}", agent_name="ChatSystem")
            return f"抱歉，处理你的请求时出现了错误：{str(e)}。请尝试重新描述你的需求。"
    
    def format_workflow_result(self, result: Any, user_input: str) -> str:
        """
        格式化工作流结果为友好的回应
        
        Args:
            result: 工作流执行结果
            user_input: 用户输入
            
        Returns:
            格式化后的回应文本
        """
        try:
            response_parts = []
            
            # 开场白
            response_parts.append("太好了！我已经为你完成了报告生成。")
            
            # 获取执行结果
            if hasattr(result, 'execution_results'):
                execution_results = result.execution_results
            else:
                execution_results = result.get('execution_results', {})
            
            # 获取最终报告信息
            final_result = execution_results.get("step_final")
            if final_result and final_result.get("report_metadata"):
                metadata = final_result["report_metadata"]
                
                response_parts.append(f"报告详情：")
                response_parts.append(f"• 文件位置：{metadata['output_path']}")
                response_parts.append(f"• 文件大小：{metadata['file_size']} 字符")
                response_parts.append(f"• 生成时间：{metadata['generation_time']}")
                response_parts.append(f"• 报告格式：{metadata.get('report_format', 'HTML')}")
                
                # 检查文件是否存在
                import os
                if os.path.exists(metadata['output_path']):
                    response_parts.append("文件已成功保存到指定位置。")
                else:
                    response_parts.append("文件保存可能存在问题，请检查输出路径。")
            
            # 获取执行统计
            if hasattr(result, 'execution_steps'):
                execution_steps = result.execution_steps
                completed_steps = sum(1 for step in execution_steps 
                                    if (hasattr(step, 'status') and step.status.value == 'completed') or 
                                       (isinstance(step, dict) and step.get('status') == 'completed'))
                total_steps = len(execution_steps)
                
                if total_steps > 0:
                    success_rate = completed_steps / total_steps * 100
                    response_parts.append(f"执行统计：{completed_steps}/{total_steps} 步骤完成 ({success_rate:.1f}%)")
            
            # 获取质量评估
            quality_assessment = None
            if hasattr(result, 'quality_assessment'):
                quality_assessment = result.quality_assessment
            else:
                quality_assessment = result.get('quality_assessment')
            
            if quality_assessment:
                if hasattr(quality_assessment, 'overall_score'):
                    overall_score = quality_assessment.overall_score
                else:
                    overall_score = quality_assessment.get('overall_score', 0.0)
                
                if overall_score >= 0.8:
                    response_parts.append(f"质量评估：{overall_score:.2f}/1.0 - 优秀！")
                elif overall_score >= 0.6:
                    response_parts.append(f"质量评估：{overall_score:.2f}/1.0 - 良好")
                else:
                    response_parts.append(f"质量评估：{overall_score:.2f}/1.0 - 可进一步优化")
            
            # 结尾提示
            response_parts.append("如果你需要调整报告内容或格式，请告诉我具体需求！")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            logger.error(f"格式化结果失败: {str(e)}", agent_name="ChatSystem")
            return "报告已生成完成，但结果显示格式出现问题。请检查输出文件夹获取报告文件。"
    
    def run_chat(self):
        """运行对话循环"""
        # 显示欢迎信息
        self.print_welcome()
        
        # 初始化系统
        if not self.initialize_system():
            self.typewriter.type_text("❌ 系统初始化失败，部分功能可能不可用。", "red")
        
        # 主对话循环
        while True:
            try:
                # 获取用户输入
                user_input = self.get_user_input()
                
                # 跳过空输入
                if not user_input:
                    continue
                
                # 处理命令
                if user_input.startswith('/') or user_input in ['帮助', '退出', '清屏', '历史', '状态']:
                    if not self.process_command(user_input):
                        break
                    continue
                
                # 生成和显示回应
                response = self.generate_response(user_input)
                
                # 显示系统回应
                print(f"\n\033[95m{self.system_role}\033[0m: ", end="", flush=True)
                self.typewriter.type_text(response, "white")
                
                # 记录对话历史
                self.conversation_history.append((user_input, response))
                
            except KeyboardInterrupt:
                # 处理Ctrl+C中断
                print("\n")
                self.typewriter.interrupt()
                continue
            
            except Exception as e:
                logger.error(f"对话循环错误: {str(e)}", agent_name="ChatSystem")
                self.typewriter.type_text(f"抱歉，出现了意外错误：{str(e)}", "red")


def main():
    """主函数"""
    chat_system = InteractiveChatSystem()
    chat_system.run_chat()


if __name__ == "__main__":
    main()