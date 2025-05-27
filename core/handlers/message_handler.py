import json
import uuid
from typing import Dict, Any, List, Callable, Awaitable, Optional
from astrbot.api.platform import AstrBotMessage, MessageMember, MessageType
from astrbot.api.message_components import Plain
from astrbot import logger

from ..events.minecraft_event import MinecraftMessageEvent
from ..config.server_types import Vanilla, Spigot, Fabric, Forge, Neoforge
from ..utils.bot_filter import BotFilter
from ..managers.process_manager import ProcessManager
from ..utils.wiki_utils import WikiUtils


class CommandHandler:
    """指令处理器基类"""
    def __init__(self, message_handler):
        self.message_handler = message_handler

    async def handle(self, 
                    message_text: str,
                    data: Dict[str, Any],
                    server_class,
                    bound_groups: List[str],
                    send_to_groups_callback: Callable[[List[str], str], Awaitable[None]],
                    send_mc_message_callback: Callable[[str], Awaitable[None]],
                    commit_event_callback: Callable[[MinecraftMessageEvent], None],
                    platform_meta,
                    adapter=None) -> bool:
        """处理指令，返回True表示已处理"""
        raise NotImplementedError


class DecoratorCommandHandler(CommandHandler):
    """装饰器指令处理器"""
    def __init__(self, message_handler, func, prefix: Optional[str], exact_match: bool, priority: int):
        super().__init__(message_handler)
        self.func = func
        self.prefix = prefix
        self.exact_match = exact_match
        self.priority = priority

    def matches(self, message_text: str) -> bool:
        """检查消息是否匹配此处理器"""
        if not message_text.startswith("#"):
            return False
            
        if self.prefix is None:
            # 通用处理器，匹配所有#开头的消息
            return True
            
        command_part = message_text[1:]  # 去掉#
        
        if self.exact_match:
            return command_part == self.prefix
        else:
            return command_part.startswith(self.prefix)

    async def handle(self, 
                    message_text: str,
                    data: Dict[str, Any],
                    server_class,
                    bound_groups: List[str],
                    send_to_groups_callback: Callable[[List[str], str], Awaitable[None]],
                    send_mc_message_callback: Callable[[str], Awaitable[None]],
                    commit_event_callback: Callable[[MinecraftMessageEvent], None],
                    platform_meta,
                    adapter=None) -> bool:
        """处理指令"""
        if not self.matches(message_text):
            return False
            
        # 调用装饰的函数
        kwargs = {
            'server_class': server_class,
            'bound_groups': bound_groups,
            'send_to_groups_callback': send_to_groups_callback,
            'send_mc_message_callback': send_mc_message_callback,
            'commit_event_callback': commit_event_callback,
            'platform_meta': platform_meta,
            'adapter': adapter
        }
        
        result = await self.func(message_text, data, **kwargs)
        return result if result is not None else True


class MessageHandler:
    """Minecraft消息处理器"""
    
    def __init__(self, 
                 server_name: str,
                 qq_message_prefix: str,
                 enable_join_quit: bool,
                 bot_filter: BotFilter,
                 process_manager: ProcessManager):
        """
        初始化消息处理器
        
        Args:
            server_name: 服务器名称
            qq_message_prefix: QQ消息前缀
            enable_join_quit: 是否启用进入/退出消息
            bot_filter: 假人过滤器
            process_manager: 进程管理器
        """
        self.server_name = server_name
        self.qq_message_prefix = qq_message_prefix
        self.enable_join_quit = enable_join_quit
        self.bot_filter = bot_filter
        self.process_manager = process_manager
        
        # 指令处理器注册表
        self.command_handlers: List[CommandHandler] = []
        
        # 注册默认指令处理器
        self._register_default_handlers()
        
    def register_command_handler(self, handler: CommandHandler):
        """
        注册指令处理器
        
        Args:
            handler: 指令处理器实例
        """
        self.command_handlers.append(handler)
        # 按优先级排序，优先级高的在前面
        self.command_handlers.sort(key=lambda h: getattr(h, 'priority', 0), reverse=True)
        
    def command_handler(self, prefix: str = None, exact_match: bool = False, priority: int = 0):
        """
        指令处理器装饰器
        
        Args:
            prefix: 指令前缀，None表示匹配所有以#开头的指令
            exact_match: 是否精确匹配
            priority: 优先级，数字越大优先级越高
        """
        def decorator(func):
            handler = DecoratorCommandHandler(
                self, func, prefix, exact_match, priority
            )
            self.command_handlers.append(handler)
            # 按优先级排序，优先级高的在前面
            self.command_handlers.sort(key=lambda h: h.priority, reverse=True)
            return func
        return decorator
        
    def _register_default_handlers(self):
        """注册默认的指令处理器"""
        
        @self.command_handler(prefix="qq", priority=100)
        async def handle_qq_command(message_text: str, data: Dict[str, Any], **kwargs):
            """处理QQ转发指令"""
            player_data = data.get("player", {})
            player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
            
            content = message_text[3:].strip()
            qq_message = f"{self.qq_message_prefix} {player_name}: {content}"

            bound_groups = kwargs.get('bound_groups', [])
            send_to_groups_callback = kwargs.get('send_to_groups_callback')
            send_mc_message_callback = kwargs.get('send_mc_message_callback')

            if bound_groups:
                await send_to_groups_callback(bound_groups, qq_message)
            else:
                logger.warning(f"没有找到绑定的群聊，无法转发消息: {qq_message}")
                await send_mc_message_callback("没有找到绑定的群聊，无法转发消息。请先使用/mcbind命令绑定群聊。")
            return True

        @self.command_handler(prefix="命令指南", exact_match=True, priority=100)
        async def handle_command_guide(message_text: str, data: Dict[str, Any], **kwargs):
            """处理命令指南指令"""
            player_data = data.get("player", {})
            player_uuid = player_data.get("uuid")
            adapter = kwargs.get('adapter')
            send_mc_message_callback = kwargs.get('send_mc_message_callback')
            
            if not player_uuid:
                await send_mc_message_callback("无法获取玩家UUID，无法发送私聊消息")
                return True
            
            if adapter and hasattr(adapter, 'send_private_message'):
                try:
                    plugin_instance = getattr(adapter, 'plugin_instance', None)
                    
                    if plugin_instance and hasattr(plugin_instance, 'broadcast_manager'):
                        broadcast_content = plugin_instance.broadcast_manager.get_broadcast_content_for_private_message()
                        await adapter.send_private_message(player_uuid, broadcast_content)
                    else:
                        await send_mc_message_callback("无法获取广播管理器，请联系管理员")
                except Exception as e:
                    logger.error(f"发送命令指南私聊时出错: {str(e)}")
                    await send_mc_message_callback(f"发送命令指南时出错: {str(e)}")
            else:
                await send_mc_message_callback("当前不支持私聊功能")
            return True

        @self.command_handler(prefix="重启qq", priority=100)
        async def handle_restart_qq(message_text: str, data: Dict[str, Any], **kwargs):
            """处理重启QQ指令"""
            send_mc_message_callback = kwargs.get('send_mc_message_callback')
            result = await self.process_manager.restart_napcat()
            await send_mc_message_callback(result["message"])
            return True

        @self.command_handler(prefix="wiki", priority=100)
        async def handle_wiki_command(message_text: str, data: Dict[str, Any], **kwargs):
            """处理Wiki查询指令"""
            wiki_title = message_text[5:].strip()
            send_mc_message_callback = kwargs.get('send_mc_message_callback')
            adapter = kwargs.get('adapter')
            
            try:
                if not wiki_title:
                    wiki_data = await WikiUtils.get_random_wiki_content()
                else:
                    wiki_data = await WikiUtils.get_wiki_content_by_title(wiki_title)
                
                if wiki_data:
                    title = wiki_data["title"]
                    content = wiki_data["content"]
                    wiki_url = f"https://zh.minecraft.wiki/w/{title}"
                    
                    if not wiki_title:
                        display_text = f"你知道吗：{title} - {content}"
                    else:
                        display_text = f"📖 {title}: {content}"
                    
                    hover_text = f"🎓 点击查看 {title} 的完整Wiki页面"
                    
                    if adapter and hasattr(adapter, 'send_mc_rich_message'):
                        await adapter.send_mc_rich_message(display_text, wiki_url, hover_text)
                    else:
                        fallback_message = f"{display_text}\n🔗 查看完整页面: {wiki_url}"
                        await send_mc_message_callback(fallback_message)
                else:
                    if not wiki_title:
                        await send_mc_message_callback("无法获取随机Wiki内容，请稍后重试")
                    else:
                        await send_mc_message_callback(f"无法获取词条 {wiki_title} 的信息，请检查词条名称是否正确")
            except Exception as e:
                logger.error(f"处理Wiki查询时出错: {str(e)}")
                await send_mc_message_callback(f"Wiki查询出错: {str(e)}")
            return True

        @self.command_handler(prefix=None, priority=0)  # 最低优先级，处理所有其他#开头的指令
        async def handle_astrbot_command(message_text: str, data: Dict[str, Any], **kwargs):
            """处理AstrBot通用指令"""
            command_text = message_text[1:].strip()
            player_data = data.get("player", {})
            player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
            
            send_mc_message_callback = kwargs.get('send_mc_message_callback')
            commit_event_callback = kwargs.get('commit_event_callback')
            platform_meta = kwargs.get('platform_meta')
            adapter = kwargs.get('adapter')
            
            if not command_text:
                help_message = """请输入要执行的AstrBot指令，例如：
#help - 显示AstrBot帮助
#qq 消息内容 - 发送消息到QQ群
#wiki 词条名称 - 查询Minecraft Wiki
#重启qq - 重启QQ"""
                await send_mc_message_callback(help_message)
                return True

            try:
                message_event = await self.create_astrbot_command_event(
                    command_text, player_name, platform_meta, send_mc_message_callback, adapter
                )
                commit_event_callback(message_event)
            except Exception as e:
                logger.error(f"执行AstrBot指令时出错: {str(e)}")
                await send_mc_message_callback(f"执行指令时出错: {str(e)}")
            return True
    
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
        处理聊天消息
        
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

        # 遍历所有注册的指令处理器
        for handler in self.command_handlers:
            try:
                if await handler.handle(
                    message_text, data, server_class, bound_groups,
                    send_to_groups_callback, send_mc_message_callback,
                    commit_event_callback, platform_meta, adapter
                ):
                    return True
            except Exception as e:
                logger.error(f"指令处理器 {handler.__class__.__name__} 处理消息时出错: {str(e)}")
                continue

        return False
    
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