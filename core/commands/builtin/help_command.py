"""帮助命令处理器"""
from typing import Dict, Any, List, Callable, Awaitable
from astrbot import logger

from ..base_command import BaseCommand


class HelpCommand(BaseCommand):
    """处理命令指南请求"""
    
    def __init__(self, command_registry):
        super().__init__(prefix="命令指南", exact_match=True, priority=100)
        self.command_registry = command_registry
    
    async def execute(self, 
                     message_text: str,
                     data: Dict[str, Any],
                     server_class,
                     bound_groups: List[str],
                     send_to_groups_callback: Callable[[List[str], str], Awaitable[None]],
                     send_mc_message_callback: Callable[[str], Awaitable[None]],
                     commit_event_callback: Callable,
                     platform_meta,
                     adapter=None) -> bool:
        """执行帮助命令"""
        player_data = data.get("player", {})
        player_uuid = player_data.get("uuid")
        
        if not player_uuid:
            await send_mc_message_callback("无法获取玩家UUID，无法发送私聊消息")
            return True
        
        try:
            plugin_instance = getattr(adapter, 'plugin_instance', None)
            
            if plugin_instance and hasattr(plugin_instance, 'broadcast_config_manager'):
                adapter_id = getattr(adapter, 'adapter_id', None)
                broadcast_content = plugin_instance.broadcast_config_manager.get_broadcast_content(adapter_id)
                await adapter.send_private_message(player_uuid, broadcast_content)
            else:
                await send_mc_message_callback("无法获取广播管理器，请联系管理员")
        except Exception as e:
            logger.error(f"发送命令指南私聊时出错: {str(e)}")
        return True
