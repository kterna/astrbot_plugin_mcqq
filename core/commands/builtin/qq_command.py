"""QQ转发命令处理器"""
from typing import Dict, Any, List, Callable, Awaitable
from astrbot import logger

from ..base_command import BaseCommand


class QQCommand(BaseCommand):
    """处理QQ转发指令"""
    
    def __init__(self, message_handler):
        super().__init__(prefix="qq", priority=100)
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
        """执行QQ转发指令"""
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        
        # 获取要转发的消息内容
        qq_message = self.remove_prefix(message_text)
        if not qq_message:
            await send_mc_message_callback("❌ 请提供要转发到QQ的消息内容")
            return True
        
        # 过滤假人
        if self.message_handler.bot_filter.is_bot_player(player_name):
            logger.debug(f"过滤假人 {player_name} 的QQ转发消息")
            return True
        
        # 构造转发消息
        formatted_message = f"{self.message_handler.qq_message_prefix} {player_name}: {qq_message}"
        
        # 发送到绑定的QQ群
        if bound_groups:
            await send_to_groups_callback(bound_groups, formatted_message)
            logger.info(f"玩家 {player_name} 通过QQ指令发送消息到群聊: {qq_message}")
        else:
            await send_mc_message_callback("❌ 当前没有绑定的QQ群")
        
        return True
    
    def get_help_text(self) -> str:
        """获取帮助文本"""
        return "<唤醒词>qq <消息> - 将消息转发到绑定的QQ群"
