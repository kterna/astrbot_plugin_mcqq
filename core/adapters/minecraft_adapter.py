import asyncio
import json
import os
import uuid
from typing import Dict, List, Any, Awaitable, Optional
from pathlib import Path
import subprocess
import psutil

from astrbot.api.platform import Platform, AstrBotMessage, MessageMember, PlatformMetadata, MessageType
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain, Image
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.core.platform.register import register_platform_adapter
from astrbot.core.star.star_tools import StarTools
from astrbot import logger
from astrbot.core.message.message_event_result import MessageChain

from .base_adapter import BaseMinecraftAdapter
from ..events.minecraft_event import MinecraftMessageEvent
from ..config.server_types import Vanilla, Spigot, Fabric, Forge, Neoforge
from ..managers.group_binding_manager import GroupBindingManager
from ..managers.websocket_manager import WebSocketManager
from ..managers.message_sender import MessageSender
from ..utils.bot_filter import BotFilter
from ..handlers.message_handler import MessageHandler

@register_platform_adapter(
    "minecraft", 
    "Minecraft服务器适配器", 
    # logo_path="minecraft.png",  # 新增：指定logo文件路径
    default_config_tmpl={
        "adapter_id": "minecraft_server_1",  # 添加适配器ID配置
        "ws_url": "ws://127.0.0.1:8080/minecraft/ws",
        "server_name": "Server",
        "Authorization": "",
        "enable_join_quit_messages": True,
        "qq_message_prefix": "[MC]",
        "max_reconnect_retries": 5,
        "reconnect_interval": 3,
        "filter_bots": True,
        "bot_prefix": ["bot_", "Bot_"],
        "bot_suffix": [],
        "rcon_enabled": False,
        "rcon_host": "localhost",
        "rcon_port": 25575,
        "rcon_password": ""
    }
)
class MinecraftPlatformAdapter(BaseMinecraftAdapter):
    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue) -> None:
        super().__init__(platform_config, platform_settings, event_queue)
        
        # 上下文引用，用于发送消息
        self.context = None
        
        # 插件实例引用，用于访问广播管理器和路由器
        self.plugin_instance = None
        
        # 路由器引用
        self.router = None

        # 从配置中获取WebSocket连接信息
        self.ws_url = self.config.get("ws_url", "ws://127.0.0.1:8080/minecraft/ws")
        self._server_name = self.config.get("server_name", "Server")
        self.Authorization = self.config.get("Authorization", "")
        self.enable_join_quit = self.config.get("enable_join_quit_messages", True)
        self.qq_message_prefix = self.config.get("qq_message_prefix", "[MC]")
        
        # 从配置中获取重连参数
        self.reconnect_interval = self.config.get("reconnect_interval", 3)  # 重连间隔(秒)
        self.max_retries = self.config.get("max_reconnect_retries", 5)  # 最大重试次数
        
        # 初始化数据目录
        self.data_dir = str(StarTools.get_data_dir("mcqq"))

        # 初始化各个管理器
        self.binding_manager = GroupBindingManager(self.data_dir)
        self.bot_filter = BotFilter(
            filter_enabled=self.config.get("filter_bots", True),
            prefix_list=self.config.get("bot_prefix", ["bot_", "Bot_"]),
            suffix_list=self.config.get("bot_suffix", [])
        )
        self.message_handler = MessageHandler(
            server_name=self._server_name,
            qq_message_prefix=self.qq_message_prefix,
            enable_join_quit=self.enable_join_quit,
            bot_filter=self.bot_filter,
        )

        # 加载绑定关系
        self.binding_manager.load_bindings()

        # WebSocket连接头信息
        self.headers = {
            "x-self-name": self._server_name,
            "x-client-origin": "astrbot",
            "Authorization": f"Bearer {self.Authorization}" if self.Authorization else ""  # 添加Bearer前缀
        }

        # 初始化WebSocket管理器和消息发送器
        self.websocket_manager = WebSocketManager(
            ws_url=self.ws_url,
            headers=self.headers,
            reconnect_interval=self.reconnect_interval,
            max_retries=self.max_retries
        )
        self.message_sender = MessageSender(self.websocket_manager)
        
        # 设置消息处理回调
        self.websocket_manager.set_message_handler(self.handle_mc_message)
        
    @property
    def server_name(self) -> str:
        """获取服务器名称"""
        return self._server_name

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="minecraft",
            description="Minecraft服务器适配器",
            id=self.config.get("id")
        )

    async def run(self) -> Awaitable[Any]:
        """启动WebSocket客户端，维持与鹊桥模组的连接"""
        # 直接运行并等待 WebSocket 循环，由 PlatformManager 统一托管任务
        await self.websocket_manager.start()

    async def handle_mc_message(self, message: str):
        """处理从Minecraft服务器接收到的消息"""
        try:
            data = json.loads(message)
            logger.debug(f"收到Minecraft消息: {data}")

            # 获取事件名称和服务器名称
            server_type = data.get("server_type", "vanilla")
            event_name = data.get("event_name", "")
            server_name = data.get("server_name", self._server_name)

            # 根据server_type获取对应的服务器类型对象
            server_class = self.message_handler.get_server_class(server_type)

            # 获取关联的群聊列表
            bound_groups = self.binding_manager.get_bound_groups(server_name)
            
            # 使用映射表简化事件处理
            event_handlers = {
                server_class.chat: self._handle_chat_event,
                server_class.join: self._handle_join_event,
                server_class.quit: self._handle_quit_event,
            }
            
            # 添加死亡事件处理（如果服务器类型支持）
            if hasattr(server_class, 'death'):
                event_handlers[server_class.death] = self._handle_death_event
            
            # 查找并执行对应的处理器
            handler = event_handlers.get(event_name)
            if handler:
                await handler(data, server_class, bound_groups)
            else:
                # 对于其他未识别的事件，记录日志但不进行处理
                logger.debug(f"[{self.adapter_id}] 收到未识别的事件: {event_name}，跳过处理")

        except json.JSONDecodeError:
            logger.error(f"无法解析JSON消息: {message}")
        except Exception as e:
            logger.error(f"处理Minecraft消息时出错: {str(e)}")

    async def _handle_chat_event(self, data, server_class, bound_groups):
        """处理聊天消息事件"""
        player_data = data.get("player", "")
        player_name = player_data.get("display_name", "")
        message_content = data.get("message", "")
        
        logger.debug(f"[{self.adapter_id}] 收到聊天消息: 玩家={player_name}, 消息={message_content}")
        
        # 路由消息到其他适配器（排除假人消息）
        if self.router and message_content and player_name and not self.bot_filter.is_bot_player(player_name):
            logger.debug(f"[{self.adapter_id}] 开始路由聊天消息到其他适配器")
            await self.router.route_chat_message(self.adapter_id, message_content, player_name)
        elif not self.router:
            logger.warning(f"[{self.adapter_id}] 路由器未设置，无法转发消息")
        elif self.bot_filter.is_bot_player(player_name):
            logger.debug(f"[{self.adapter_id}] 跳过假人消息: {player_name}")
        
        # 原有的消息处理逻辑
        await self.message_handler.handle_chat_message(
            data=data,
            server_class=server_class,
            bound_groups=bound_groups,
            send_to_groups_callback=self.send_to_bound_groups,
            send_mc_message_callback=self.send_mc_message,
            commit_event_callback=self.commit_event,
            platform_meta=self.meta(),
            adapter=self
        )
        
        # 设置adapter引用
        if hasattr(self.message_handler, '_last_event'):
            self.message_handler._last_event.adapter = self

    async def _handle_join_event(self, data, server_class, bound_groups):
        """处理玩家加入事件"""
        player_data = data.get("player", "")
        player_name = player_data.get("display_name", "")
            
        logger.debug(f"[{self.adapter_id}] 收到玩家加入: {player_name}")
        
        # 路由加入消息到其他适配器（排除假人）
        if self.router and player_name and not self.bot_filter.is_bot_player(player_name):
            logger.debug(f"[{self.adapter_id}] 开始路由加入消息到其他适配器")
            await self.router.route_player_join(self.adapter_id, player_name)
        elif not self.router:
            logger.warning(f"[{self.adapter_id}] 路由器未设置，无法转发加入消息")
        elif self.bot_filter.is_bot_player(player_name):
            logger.debug(f"[{self.adapter_id}] 跳过假人加入消息: {player_name}")
            
        # 原有的处理逻辑
        await self.message_handler.handle_player_join_quit(
            data=data,
            event_name=server_class.join,
            server_class=server_class,
            bound_groups=bound_groups,
            send_to_groups_callback=self.send_to_bound_groups
        )

    async def _handle_quit_event(self, data, server_class, bound_groups):
        """处理玩家退出事件"""
        player_data = data.get("player", "")
        player_name = player_data.get("display_name", "")

        logger.debug(f"[{self.adapter_id}] 收到玩家退出: {player_name}")
            
        # 路由退出消息到其他适配器（排除假人）
        if self.router and player_name and not self.bot_filter.is_bot_player(player_name):
            logger.debug(f"[{self.adapter_id}] 开始路由退出消息到其他适配器")
            await self.router.route_player_quit(self.adapter_id, player_name)
        elif not self.router:
            logger.warning(f"[{self.adapter_id}] 路由器未设置，无法转发退出消息")
        elif self.bot_filter.is_bot_player(player_name):
            logger.debug(f"[{self.adapter_id}] 跳过假人退出消息: {player_name}")
            
        # 原有的处理逻辑
        await self.message_handler.handle_player_join_quit(
            data=data,
            event_name=server_class.quit,
            server_class=server_class,
            bound_groups=bound_groups,
            send_to_groups_callback=self.send_to_bound_groups
        )

    async def _handle_death_event(self, data, server_class, bound_groups):
        """处理玩家死亡事件"""
        death_message = data.get("message", "")
        # 路由死亡消息到其他适配器
        if self.router and death_message:
            await self.router.route_player_death(self.adapter_id, death_message)
            
        # 原有的处理逻辑
        await self.message_handler.handle_player_death(
            data=data,
            event_name=server_class.death,
            server_class=server_class,
            bound_groups=bound_groups,
            send_to_groups_callback=self.send_to_bound_groups
        )

    async def send_to_bound_groups(self, group_ids: List[str], message: str):
        """发送消息到绑定的QQ群"""
        # 动态获取 QQ(aioCQHTTP) 适配器的实例 ID，用于构造 session
        qq_adapter_id = None
        if hasattr(self, 'context') and self.context and hasattr(self.context, 'platform_manager'):
            try:
                for p in self.context.platform_manager.get_insts():
                    try:
                        meta = p.meta()
                        if meta and meta.name == "aiocqhttp":
                            qq_adapter_id = meta.id
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"获取 QQ 适配器实例 ID 失败: {str(e)}")

        if not qq_adapter_id:
            logger.warning("未找到 aiocqhttp 适配器实例或其 ID，无法向QQ群发送消息。请确认已启用 QQ 个人号(aiocqhttp) 并查看其平台 ID。")
            return

        for group_id in group_ids:
            try:
                if hasattr(self, 'context') and self.context:
                    session = f"{qq_adapter_id}:GroupMessage:{group_id}"
                    message_chain = MessageChain().message(message)
                    try:
                        await self.context.send_message(session, message_chain)
                        logger.info(f"已发送消息到群 {group_id}（平台ID={qq_adapter_id}）")
                    except Exception as e:
                        logger.warning(f"发送消息到群 {group_id} 失败: {str(e)}")
                else:
                    logger.warning(f"context 未设置，无法发送消息到群 {group_id}")
            except Exception as e:
                logger.error(f"发送消息到群 {group_id} 时出错: {str(e)}")

    async def is_connected(self) -> bool:
        """实现基类的连接状态检查方法"""
        return self.websocket_manager.connected

    async def send_mc_message(self, message: str, sender: str = None):
        """发送消息到Minecraft服务器"""
        return await self.message_sender.send_broadcast_message(message, sender)

    async def send_rich_message(self, text: str, click_url: str="", hover_text: str="", color: str = "#E6E6FA"):
        """发送富文本消息到Minecraft服务器"""
        return await self.message_sender.send_rich_message(text, click_url, hover_text, color)

    async def send_private_message(self, uuid: str, components: List[Dict[str, Any]]):
        """发送私聊消息到指定玩家"""
        return await self.message_sender.send_private_message(uuid, components)

    async def terminate(self):
        """终止平台适配器"""
        # 关闭 websocket 连接
        await self.websocket_manager.close()
        
        # 清理平台适配器注册信息
        try:
            from astrbot.core.platform.register import platform_cls_map, platform_registry
            logger.debug(f"清理前 platform_cls_map: {list(platform_cls_map.keys())}")
            logger.debug(f"清理前 platform_registry: {[p.name for p in platform_registry]}")
            
            if "minecraft" in platform_cls_map:
                del platform_cls_map["minecraft"]
            # 从注册表中移除
            for i, platform_metadata in enumerate(platform_registry):
                if platform_metadata.name == "minecraft":
                    del platform_registry[i]
                    break
                    
            logger.debug(f"清理后 platform_cls_map: {list(platform_cls_map.keys())}")
            logger.debug(f"清理后 platform_registry: {[p.name for p in platform_registry]}")
        except Exception as e:
            logger.error(f"清理 Minecraft 平台适配器注册信息失败: {str(e)}")
            
        logger.info("Minecraft平台适配器已被优雅地关闭")

    # 绑定和解绑群聊的方法（委托给GroupBindingManager）
    async def bind_group(self, group_id: str, server_name: str = None) -> bool:
        """绑定群聊与Minecraft服务器"""
        if server_name is None:
            server_name = self._server_name
        return self.binding_manager.bind_group(group_id, server_name)

    async def unbind_group(self, group_id: str, server_name: str = None) -> bool:
        """解除群聊与Minecraft服务器的绑定"""
        if server_name is None:
            server_name = self._server_name
        return self.binding_manager.unbind_group(group_id, server_name)

    def is_group_bound(self, group_id: str, server_name: str = None) -> bool:
        """检查群聊是否与Minecraft服务器绑定"""
        if server_name is None:
            server_name = self._server_name
        return self.binding_manager.is_group_bound(group_id, server_name)

    def is_bot_player(self, player_name: str) -> bool:
        """检查玩家是否为假人（委托给BotFilter）"""
        return self.bot_filter.is_bot_player(player_name)

    
