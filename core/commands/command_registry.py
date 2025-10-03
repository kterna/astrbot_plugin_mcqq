"""命令注册表，负责管理和分发命令"""
from typing import List, Dict, Any, Callable, Awaitable
from astrbot import logger

from .base_command import BaseCommand


class CommandRegistry:
    """统一的命令注册和分发机制"""
    
    def __init__(self):
        self.commands: List[BaseCommand] = []
        
    def register(self, command: BaseCommand):
        """
        注册命令处理器
        
        Args:
            command: 命令实例
        """
        self.commands.append(command)
        # 按优先级排序，优先级高的在前面
        self.commands.sort(key=lambda cmd: cmd.get_priority(), reverse=True)
        logger.debug(f"注册命令: {command.__class__.__name__}, 前缀: {command.prefix}, 优先级: {command.priority}")
    
    def register_multiple(self, commands: List[BaseCommand]):
        """
        批量注册命令
        
        Args:
            commands: 命令列表
        """
        for command in commands:
            self.register(command)
    
    async def handle_command(self, 
                           message_text: str,
                           data: Dict[str, Any],
                           server_class,
                           bound_groups: List[str],
                           send_to_groups_callback: Callable[[List[str], str], Awaitable[None]],
                           send_mc_message_callback: Callable[[str], Awaitable[None]],
                           commit_event_callback: Callable,
                           platform_meta,
                           adapter=None) -> bool:
        """
        分发命令到对应的处理器
        
        Args:
            message_text: 消息文本
            data: 消息数据
            server_class: 服务器类型对象
            bound_groups: 绑定的群组列表
            send_to_groups_callback: 发送消息到群组的回调函数
            send_mc_message_callback: 发送消息到MC的回调函数
            commit_event_callback: 提交事件的回调函数
            platform_meta: 平台元数据
            adapter: 适配器实例
            
        Returns:
            bool: 是否有命令处理了消息
        """
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        
        # 遍历所有注册的命令处理器
        for command in self.commands:
            if command.matches(message_text):
                logger.debug(f"{player_name} 执行命令: {message_text}")
                try:
                    result = await command.execute(
                        message_text=message_text,
                        data=data,
                        server_class=server_class,
                        bound_groups=bound_groups,
                        send_to_groups_callback=send_to_groups_callback,
                        send_mc_message_callback=send_mc_message_callback,
                        commit_event_callback=commit_event_callback,
                        platform_meta=platform_meta,
                        adapter=adapter
                    )
                    if result:
                        logger.debug(f"命令 {command.__class__.__name__} 处理了消息: {message_text}")
                        return True
                except Exception as e:
                    logger.error(f"执行命令 {command.__class__.__name__} 时发生错误: {e}")
                    continue
        
        logger.debug(f"没有命令处理器能够处理消息: {message_text}")
        return False
    
