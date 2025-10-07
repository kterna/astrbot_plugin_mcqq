"""AstrBot指令代理命令处理器"""
import uuid
from typing import Dict, Any, List, Callable, Awaitable
from astrbot import logger
from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType
from astrbot.api.message_components import Plain

from ..base_command import BaseCommand
from ...events.minecraft_event import MinecraftMessageEvent


class AstrBotCommand(BaseCommand):
    """处理AstrBot指令代理，通用处理器"""
    
    def __init__(self, message_handler):
        super().__init__(prefix=None, priority=0)  # 通用处理器，优先级最低
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
        """执行AstrBot指令代理"""
        
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))

        logger.debug(f"玩家 {player_name} 执行AstrBot指令: {message_text}")
        
        try:
            # 创建AstrBot命令事件
            command_event = await self.message_handler.create_astrbot_command_event(
                command_text=message_text,
                player_name=player_name,
                platform_meta=platform_meta,
                send_mc_message_callback=send_mc_message_callback,
                adapter=adapter
            )
            
            # 提交事件到AstrBot
            commit_event_callback(command_event)
            
            return True
            
        except Exception as e:
            logger.error(f"处理AstrBot指令时发生错误: {e}")
            await send_mc_message_callback(f"❌ 指令执行失败: {str(e)}")
            return True
    
    def get_help_text(self) -> str:
        """获取帮助文本"""
        return "<唤醒词> + AstrBot指令 - 执行AstrBot系统指令"
