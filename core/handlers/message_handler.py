# filepath: e:\github desktop\AstrBot\data\plugins\astrbot_plugin_mcqq\core\handlers\message_handler.py
import uuid
from typing import Dict, Any, List, Callable, Awaitable
from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType
from astrbot.api.message_components import Plain
from astrbot import logger

from ..events.minecraft_event import MinecraftMessageEvent
from ..config.server_types import Vanilla, Spigot, Fabric, Forge, Neoforge
from ..utils.bot_filter import BotFilter
from ..commands.command_factory import CommandFactory


class MessageHandler:
    """Minecraft消息处理器 - 重构后版本，专注于消息路由和基础处理"""
    
    def __init__(self, 
                 server_name: str,
                 qq_message_prefix: str,
                 enable_join_quit: bool,
                 bot_filter: BotFilter):
        """
        初始化消息处理器
        
        Args:
            server_name: 服务器名称
            qq_message_prefix: QQ消息前缀
            enable_join_quit: 是否启用进入/退出消息
            bot_filter: 假人过滤器
        """
        self.server_name = server_name
        self.qq_message_prefix = qq_message_prefix
        self.enable_join_quit = enable_join_quit
        self.bot_filter = bot_filter
        
        # 使用命令工厂创建命令注册表
        self.command_registry = CommandFactory.setup_command_registry(self)
               
    def get_server_class(self, server_type: str):
        """根据服务器类型获取对应的服务器类型对象"""
        server_classes = {
            "vanilla": Vanilla(),
            "spigot": Spigot(),
            "fabric": Fabric(),
            "forge": Forge(),
            "neoforge": Neoforge()
        }
        return server_classes.get(server_type, Vanilla())
    
    async def handle_chat_message(self, 
                                data: Dict[str, Any], 
                                server_class,
                                bound_groups: List[str],
                                send_to_groups_callback: Callable[[List[str], str], Awaitable[None]],
                                send_mc_message_callback: Callable[[str], Awaitable[None]],
                                commit_event_callback: Callable[[MinecraftMessageEvent], None],
                                platform_meta,
                                adapter=None) -> bool:
        """
        处理聊天消息 - 简化版本，主要负责路由
        
        Args:
            data: 消息数据
            server_class: 服务器类型对象
            bound_groups: 绑定的群组列表
            send_to_groups_callback: 发送消息到群组的回调函数
            send_mc_message_callback: 发送消息到MC的回调函数
            commit_event_callback: 提交事件的回调函数
            platform_meta: 平台元数据
            adapter: 适配器实例
            
        Returns:
            bool: 是否处理了消息
        """
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        message_text = data.get("message", "")

        logger.info(f"{player_name}: {message_text}")

        # 如果不是以#开头的消息，直接返回False
        if not message_text.startswith("#"):
            return False

        # 委托给命令注册表处理
        return await self.command_registry.handle_command(
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
    
    async def create_astrbot_command_event(self, 
                                         command_text: str, 
                                         player_name: str, 
                                         platform_meta,
                                         send_mc_message_callback: Callable[[str], Awaitable[None]],
                                         adapter=None) -> MinecraftMessageEvent:
        """创建AstrBot命令事件"""
        # 创建一个虚拟的消息事件，用于执行指令
        abm = AstrBotMessage()
        abm.type = MessageType.FRIEND_MESSAGE
        abm.message_str = command_text
        abm.sender = MessageMember(
            user_id=f"minecraft_{player_name}",
            nickname=player_name
        )
        abm.message = [Plain(text=command_text)]
        abm.raw_message = {"content": command_text}
        abm.self_id = f"minecraft_{self.server_name}"
        abm.session_id = f"minecraft_{player_name}"
        abm.message_id = str(uuid.uuid4())

        # 创建消息事件
        message_event = MinecraftMessageEvent(
            message_str=command_text,
            message_obj=abm,
            platform_meta=platform_meta,
            session_id=f"minecraft_{player_name}",
            adapter=adapter
        )

        # 设置回调函数，将AstrBot的响应发送回Minecraft
        async def on_response(response_message):
            if response_message and response_message.strip():
                await send_mc_message_callback(response_message)

        message_event.on_response = on_response
        
        # 存储最后创建的事件，以便主适配器可以设置adapter引用
        self._last_event = message_event
        
        return message_event
    
    async def handle_player_join_quit(self, 
                                    data: Dict[str, Any], 
                                    event_name: str,
                                    server_class,
                                    bound_groups: List[str],
                                    send_to_groups_callback: Callable[[List[str], str], Awaitable[None]]) -> bool:
        """
        处理玩家进入/退出消息
        
        Args:
            data: 消息数据
            event_name: 事件名称
            server_class: 服务器类型对象
            bound_groups: 绑定的群组列表
            send_to_groups_callback: 发送消息到群组的回调函数
            
        Returns:
            bool: 是否处理了消息
        """
        if not self.enable_join_quit or not event_name:
            return False
            
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))

        # 过滤假人
        if self.bot_filter.is_bot_player(player_name):
            logger.debug(f"过滤假人 {player_name} 的进入/退出消息")
            return False

        # 构造进入/退出消息
        if event_name == "player_join":
            message = f"{self.qq_message_prefix} 🟢 {player_name} 加入了游戏"
        elif event_name == "player_quit":
            message = f"{self.qq_message_prefix} 🔴 {player_name} 离开了游戏"
        else:
            return False

        # 发送到绑定的QQ群
        if bound_groups:
            await send_to_groups_callback(bound_groups, message)
            logger.info(f"玩家 {player_name} {event_name} 消息已发送到QQ群")

        return True
    
    async def handle_player_death(self, 
                                data: Dict[str, Any], 
                                event_name: str,
                                server_class,
                                bound_groups: List[str],
                                send_to_groups_callback: Callable[[List[str], str], Awaitable[None]]) -> bool:
        """
        处理玩家死亡消息
        
        Args:
            data: 消息数据
            event_name: 事件名称
            server_class: 服务器类型对象
            bound_groups: 绑定的群组列表
            send_to_groups_callback: 发送消息到群组的回调函数
            
        Returns:
            bool: 是否处理了消息
        """
        if event_name != "player_death":
            return False
            
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        death_message = data.get("death_message", f"{player_name} 死了")

        # 过滤假人
        if self.bot_filter.is_bot_player(player_name):
            logger.debug(f"过滤假人 {player_name} 的死亡消息")
            return False

        # 构造死亡消息
        message = f"{self.qq_message_prefix} ☠️ {death_message}"

        # 发送到绑定的QQ群
        if bound_groups:
            await send_to_groups_callback(bound_groups, message)
            logger.info(f"玩家 {player_name} 死亡消息已发送到QQ群")

        return True
