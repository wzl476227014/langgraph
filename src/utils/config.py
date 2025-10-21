"""
配置管理模块
负责加载和管理应用配置
"""

import os
import yaml
from typing import Dict, Any
from pathlib import Path


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径，默认为项目根目录下的config目录
        """
        if config_path is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            config_path = project_root / "config"
        
        self.config_path = Path(config_path)
        self.settings = self._load_settings()
        self.prompts = self._load_prompts()
    
    def _load_settings(self) -> Dict[str, Any]:
        """加载应用设置"""
        settings_file = self.config_path / "settings.yaml"
        if not settings_file.exists():
            raise FileNotFoundError(f"Settings file not found: {settings_file}")
        
        with open(settings_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def _load_prompts(self) -> Dict[str, Any]:
        """加载Agent提示词"""
        prompts_file = self.config_path / "agent_prompts.yaml"
        if not prompts_file.exists():
            raise FileNotFoundError(f"Prompts file not found: {prompts_file}")
        
        with open(prompts_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self.settings.get('llm', {})
    
    def get_agent_config(self, agent_name: str) -> Dict[str, Any]:
        """获取指定Agent的配置"""
        return self.settings.get('agents', {}).get(agent_name, {})
    
    def get_agent_prompt(self, agent_name: str) -> str:
        """获取指定Agent的系统提示词"""
        return self.prompts.get(f"{agent_name}_system_prompt", "")
    
    def get_workflow_config(self) -> Dict[str, Any]:
        """获取工作流配置"""
        return self.settings.get('workflow', {})
    
    def get_output_config(self) -> Dict[str, Any]:
        """获取输出配置"""
        return self.settings.get('output', {})
    
    def get_tool_config(self, tool_name: str) -> Dict[str, Any]:
        """获取指定工具的配置"""
        return self.settings.get('tools', {}).get(tool_name, {})
    
    def get_all_tools_config(self) -> Dict[str, Any]:
        """获取所有工具的配置"""
        return self.settings.get('tools', {})
    
    def update_setting(self, key_path: str, value: Any) -> None:
        """
        更新设置
        
        Args:
            key_path: 配置键路径，如 'llm.temperature'
            value: 新的值
        """
        keys = key_path.split('.')
        config = self.settings
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def save_settings(self) -> None:
        """保存设置到文件"""
        settings_file = self.config_path / "settings.yaml"
        with open(settings_file, 'w', encoding='utf-8') as f:
            yaml.dump(self.settings, f, default_flow_style=False, allow_unicode=True)


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    return config_manager


def get_llm_config() -> Dict[str, Any]:
    """获取LLM配置的便捷函数"""
    return config_manager.get_llm_config()


def get_agent_config(agent_name: str) -> Dict[str, Any]:
    """获取Agent配置的便捷函数"""
    return config_manager.get_agent_config(agent_name)


def get_agent_prompt(agent_name: str) -> str:
    """获取Agent提示词的便捷函数"""
    return config_manager.get_agent_prompt(agent_name)
