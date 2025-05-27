"""重启QQ命令处理器"""
from typing import Dict, Any, List, Callable, Awaitable
from astrbot import logger

from ..base_command import BaseCommand


class RestartCommand(BaseCommand):
    """处理重启QQ指令"""
    
    def __init__(self, message_handler):
        super().__init__(prefix="重启qq", priority=100)
        self.message_handler = message_handler
    
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
        """执行重启QQ指令"""
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        
        logger.info(f"玩家 {player_name} 请求重启QQ连接")
        
        # 使用process_manager的restart_napcat方法
        result = await self.message_handler.process_manager.restart_napcat()
        await send_mc_message_callback(result["message"])
        
        return True
    
    def get_help_text(self) -> str:
        """获取帮助文本"""
        return "#重启qq - 重启QQ机器人连接"
