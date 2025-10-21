"""
LLM配置模块
负责配置和管理语言模型
"""

from typing import Dict, Any, Optional, Iterator
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage, AIMessage
from ..utils.config import get_llm_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LLMConfig:
    """LLM配置管理器"""
    
    def __init__(self):
        """初始化LLM配置"""
        self.config = get_llm_config()
        self.llm = self._create_llm_instance()
    
    def _create_llm_instance(self) -> ChatOpenAI:
        """创建LLM实例"""
        try:
            llm_config = self.config
            
           # logger.info("正在初始化LLM实例...", agent_name="LLMConfig")
            
            llm = ChatOpenAI(
                model_name=llm_config.get('model', 'glm-4.5'),
                openai_api_key=llm_config.get('api_key'),
                openai_api_base=llm_config.get('base_url'),
                temperature=llm_config.get('temperature', 0.7),
                max_tokens=llm_config.get('max_tokens', 4000),
                top_p=llm_config.get('top_p', 0.7),
                frequency_penalty=llm_config.get('frequency_penalty', 0),
                presence_penalty=llm_config.get('presence_penalty', 0),
                extra_body={
                    "enable_thinking": llm_config.get('enable_thinking', False)
                }
            )
            
            logger.info("LLM实例初始化成功", agent_name="LLMConfig")
            return llm
            
        except Exception as e:
            logger.error(f"LLM实例初始化失败: {str(e)}", agent_name="LLMConfig")
            raise
    
    def get_llm(self) -> ChatOpenAI:
        """获取LLM实例"""
        return self.llm
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        更新LLM配置
        
        Args:
            new_config: 新的配置字典
        """
        try:
            self.config.update(new_config)
            self.llm = self._create_llm_instance()
            logger.info("LLM配置更新成功", agent_name="LLMConfig")
        except Exception as e:
            logger.error(f"LLM配置更新失败: {str(e)}", agent_name="LLMConfig")
            raise
    
    def generate_response(
        self, 
        messages: list, 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        生成LLM响应
        
        Args:
            messages: 消息列表
            temperature: 可选的温度参数
            max_tokens: 可选的最大token数
            
        Returns:
            生成的响应文本
        """
        try:
            # 临时调整参数
            original_temperature = self.llm.temperature
            original_max_tokens = self.llm.max_tokens
            
            if temperature is not None:
                self.llm.temperature = temperature
            if max_tokens is not None:
                self.llm.max_tokens = max_tokens
            
            # 生成响应
            response = self.llm.invoke(messages)
            
            # 恢复原始参数
            self.llm.temperature = original_temperature
            self.llm.max_tokens = original_max_tokens
            
            return response.content
            
        except Exception as e:
            logger.error(f"LLM响应生成失败: {str(e)}", agent_name="LLMConfig")
            raise
    
    def generate_response_stream(
        self, 
        messages: list, 
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> Iterator[str]:
        """
        生成LLM流式响应
        
        Args:
            messages: 消息列表
            temperature: 可选的温度参数
            max_tokens: 可选的最大token数
            
        Returns:
            流式响应的迭代器
        """
        try:
            # 临时调整参数
            original_temperature = self.llm.temperature
            original_max_tokens = self.llm.max_tokens
            
            if temperature is not None:
                self.llm.temperature = temperature
            if max_tokens is not None:
                self.llm.max_tokens = max_tokens
            
            # 创建流式LLM实例
            streaming_llm = ChatOpenAI(
                model_name=self.config.get('model', 'glm-4.5'),
                openai_api_key=self.config.get('api_key'),
                openai_api_base=self.config.get('base_url'),
                temperature=self.llm.temperature,
                max_tokens=self.llm.max_tokens,
                top_p=self.config.get('top_p', 0.7),
                frequency_penalty=self.config.get('frequency_penalty', 0),
                presence_penalty=self.config.get('presence_penalty', 0),
                streaming=True,
                extra_body={
                    "enable_thinking": self.config.get('enable_thinking', False)
                }
            )
            
            # 生成流式响应
            for chunk in streaming_llm.stream(messages):
                if chunk.content:
                    yield chunk.content
            
            # 恢复原始参数
            self.llm.temperature = original_temperature
            self.llm.max_tokens = original_max_tokens
            
        except Exception as e:
            logger.error(f"LLM流式响应生成失败: {str(e)}", agent_name="LLMConfig")
            raise
    
    def generate_system_response(
        self, 
        system_prompt: str, 
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        使用系统提示词和用户消息生成响应
        
        Args:
            system_prompt: 系统提示词
            user_message: 用户消息
            temperature: 可选的温度参数
            max_tokens: 可选的最大token数
            
        Returns:
            生成的响应文本
        """
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        
        return self.generate_response(messages, temperature, max_tokens)
    
    def generate_chat_response(
        self, 
        conversation_history: list,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        基于对话历史生成响应
        
        Args:
            conversation_history: 对话历史列表
            temperature: 可选的温度参数
            max_tokens: 可选的最大token数
            
        Returns:
            生成的响应文本
        """
        # 转换消息格式
        messages = []
        for msg in conversation_history:
            if msg['role'] == 'system':
                messages.append(SystemMessage(content=msg['content']))
            elif msg['role'] == 'user':
                messages.append(HumanMessage(content=msg['content']))
            elif msg['role'] == 'assistant':
                messages.append(AIMessage(content=msg['content']))
        
        return self.generate_response(messages, temperature, max_tokens)
    
    def get_config_info(self) -> Dict[str, Any]:
        """获取配置信息（隐藏敏感信息）"""
        config_info = self.config.copy()
        # 隐藏API密钥
        if 'api_key' in config_info:
            config_info['api_key'] = '***masked***'
        return config_info
    
    def test_connection(self) -> bool:
        """测试LLM连接"""
        try:
            test_messages = [
                SystemMessage(content="你是一个测试助手"),
                HumanMessage(content="请回复'连接测试成功'")
            ]
            
            response = self.generate_response(test_messages)
            
            if "连接测试成功" in response:
                logger.info("LLM连接测试成功", agent_name="LLMConfig")
                return True
            else:
                logger.warning("LLM连接测试响应异常", agent_name="LLMConfig")
                return False
                
        except Exception as e:
            logger.error(f"LLM连接测试失败: {str(e)}", agent_name="LLMConfig")
            return False


# 全局LLM配置实例
llm_config = LLMConfig()


def get_llm() -> ChatOpenAI:
    """获取全局LLM实例的便捷函数"""
    return llm_config.get_llm()


def generate_response(
    messages: list, 
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> str:
    """生成LLM响应的便捷函数"""
    return llm_config.generate_response(messages, temperature, max_tokens)


def generate_system_response(
    system_prompt: str, 
    user_message: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> str:
    """使用系统提示词生成响应的便捷函数"""
    return llm_config.generate_system_response(system_prompt, user_message, temperature, max_tokens)


def generate_system_response_stream(
    system_prompt: str, 
    user_message: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None
) -> Iterator[str]:
    """使用系统提示词生成流式响应的便捷函数"""
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message)
    ]
    return llm_config.generate_response_stream(messages, temperature, max_tokens)
