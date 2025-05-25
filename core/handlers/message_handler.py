import uuid
from typing import Dict, Any, List, Callable, Awaitable
from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType
from astrbot.api.message_components import Plain
from astrbot import logger

from ..events.minecraft_event import MinecraftMessageEvent
from ..config.server_types import Vanilla, Spigot, Fabric, Forge, Neoforge
from ..utils.bot_filter import BotFilter
from ..utils.wiki_utils import WikiUtils


class MessageHandler:
    """Minecraft消息处理器"""
    
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
                                platform_meta) -> bool:
        """
        处理聊天消息
        
        Args:
            data: 消息数据
            server_class: 服务器类型对象
            bound_groups: 绑定的群组列表
            send_to_groups_callback: 发送消息到群组的回调函数
            send_mc_message_callback: 发送消息到MC的回调函数
            commit_event_callback: 提交事件的回调函数
            platform_meta: 平台元数据
            
        Returns:
            bool: 是否处理了消息
        """
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        message_text = data.get("message", "")

        # 处理以"#qq"开头的消息，转发到QQ群
        if message_text.startswith("#qq"):
            message_text = message_text[3:].strip()
            qq_message = f"{self.qq_message_prefix} {player_name}: {message_text}"

            if bound_groups:
                await send_to_groups_callback(bound_groups, qq_message)
            else:
                logger.warning(f"没有找到绑定的群聊，无法转发消息: {qq_message}")
                await send_mc_message_callback("没有找到绑定的群聊，无法转发消息。请先使用/mcbind命令绑定群聊。")
            return True

        # 处理以"#astr"开头的消息，作为AstrBot指令处理
        elif message_text.startswith("#astr"):
            command_text = message_text[5:].strip()
            if not command_text:
                help_message = """请输入要执行的AstrBot指令，例如：
#astr help - 显示AstrBot帮助
#qq 消息内容 - 发送消息到QQ群
#wiki 词条名称 - 查询Minecraft Wiki"""
                await send_mc_message_callback(help_message)
                return True

            try:
                # 创建消息事件
                message_event = await self.create_astrbot_command_event(
                    command_text, player_name, platform_meta, send_mc_message_callback
                )
                
                # 提交事件到AstrBot处理
                commit_event_callback(message_event)
            except Exception as e:
                logger.error(f"执行AstrBot指令时出错: {str(e)}")
                await send_mc_message_callback(f"执行指令时出错: {str(e)}")
            return True

        # 处理Wiki查询命令
        elif message_text.startswith("#wiki"):
            wiki_title = message_text[5:].strip()
            if not wiki_title:
                help_message = """请输入要查询的Wiki词条，例如：
#wiki 玻璃 - 查询玻璃的相关信息
#wiki 钻石 - 查询钻石的相关信息"""
                await send_mc_message_callback(help_message)
                return True
            
            try:
                wiki_content = await WikiUtils.get_wiki_content_by_title(wiki_title)
                if wiki_content:
                    await send_mc_message_callback(wiki_content)
                else:
                    await send_mc_message_callback(f"无法获取词条 {wiki_title} 的信息，请检查词条名称是否正确")
            except Exception as e:
                logger.error(f"处理Wiki查询时出错: {str(e)}")
                await send_mc_message_callback(f"Wiki查询出错: {str(e)}")
            return True

        return False
    
    async def create_astrbot_command_event(self, 
                                         command_text: str, 
                                         player_name: str, 
                                         platform_meta,
                                         send_mc_message_callback: Callable[[str], Awaitable[None]]) -> MinecraftMessageEvent:
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
            adapter=None  # 这里需要在调用方设置
        )

        # 设置回调函数，将AstrBot的响应发送回Minecraft
        async def on_response(response_message):
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
        
        # 检查是否为假人
        if self.bot_filter.is_bot_player(player_name):
            return False
        
        if event_name == server_class.join:
            join_message = f"{self.qq_message_prefix} 玩家 {player_name} 加入了服务器"
            await send_to_groups_callback(bound_groups, join_message)
            return True
        elif event_name == server_class.quit:
            quit_message = f"{self.qq_message_prefix} 玩家 {player_name} 离开了服务器"
            await send_to_groups_callback(bound_groups, quit_message)
            return True
            
        return False
    
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
        if not hasattr(server_class, 'death') or event_name != server_class.death:
            return False
            
        player_data = data.get("player", {})
        player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
        
        # 检查是否为假人
        if self.bot_filter.is_bot_player(player_name):
            return False
            
        death_reason = data.get("message", "未知原因")

        # 构建死亡位置信息（如果服务器类型支持位置信息）
        death_location = ""
        if ("block_x" in server_class.player and 
            "block_y" in server_class.player and 
            "block_z" in server_class.player):
            death_location = (f"位置：x:{player_data.get('block_x')},"
                            f"y:{player_data.get('block_y')},"
                            f"z:{player_data.get('block_z')}")

        death_message = f"{self.qq_message_prefix} 玩家 {player_name} 死亡了，原因：{death_reason}"
        if death_location:
            death_message += f"，{death_location}"

        await send_to_groups_callback(bound_groups, death_message)
        return True 