"""命令工厂，负责创建和配置命令"""
from typing import List
from astrbot import logger

from .base_command import BaseCommand
from .command_registry import CommandRegistry
from .builtin import (
    QQCommand,
    HelpCommand,
    WikiCommand,
    AstrBotCommand,
    LandmarkCommand
)


class CommandFactory:
    """命令工厂，负责创建和配置命令"""
    
    @staticmethod
    def create_builtin_commands(message_handler) -> List[BaseCommand]:
        """
        创建所有内置命令
        
        Args:
            message_handler: 消息处理器实例
            
        Returns:
            List[BaseCommand]: 创建的命令列表
        """
        commands = []
        
        try:
            # 创建QQ转发命令
            qq_cmd = QQCommand(message_handler)
            commands.append(qq_cmd)
            logger.debug("创建QQ转发命令")
            
            # 创建Wiki查询命令
            wiki_cmd = WikiCommand(message_handler)
            commands.append(wiki_cmd)
            logger.debug("创建Wiki查询命令")
            
            # 创建AstrBot指令代理命令（通用处理器）
            astrbot_cmd = AstrBotCommand(message_handler)
            commands.append(astrbot_cmd)
            logger.debug("创建AstrBot指令代理命令")
            
            # 创建Landmark路标命令
            landmark_cmd = LandmarkCommand(message_handler)
            commands.append(landmark_cmd)
            logger.debug("创建Landmark路标命令")
            
        except Exception as e:
            logger.error(f"创建内置命令时发生错误: {e}")
        
        return commands
    
    @staticmethod
    def setup_command_registry(message_handler) -> CommandRegistry:
        """
        设置并配置命令注册表
        
        Args:
            message_handler: 消息处理器实例
            
        Returns:
            CommandRegistry: 配置好的命令注册表
        """
        registry = CommandRegistry()
        
        # 创建内置命令
        builtin_commands = CommandFactory.create_builtin_commands(message_handler)
        
        # 批量注册内置命令
        registry.register_multiple(builtin_commands)
        
        # 创建帮助命令（需要注册表引用）
        help_cmd = HelpCommand(registry)
        registry.register(help_cmd)
        logger.debug("创建并注册帮助命令")
        
        return registry
    
    @staticmethod
    def create_plugin_commands(message_handler, plugin_dir: str = None) -> List[BaseCommand]:
        """
        创建插件命令（预留扩展点）
        
        Args:
            message_handler: 消息处理器实例
            plugin_dir: 插件目录路径
            
        Returns:
            List[BaseCommand]: 插件命令列表
        """
        # TODO: 实现插件命令加载机制
        # 可以从指定目录动态加载插件命令
        return []
