import asyncio
import json
import os
import uuid
import websockets
from typing import Dict, List, Any, Awaitable
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

from ..events.minecraft_event import MinecraftMessageEvent
from ..config.server_types import Vanilla, Spigot, Fabric, Forge, Neoforge
from ..managers.group_binding_manager import GroupBindingManager
from ..utils.bot_filter import BotFilter
from ..managers.process_manager import ProcessManager
from ..handlers.message_handler import MessageHandler

@register_platform_adapter("minecraft", "Minecraft服务器适配器", default_config_tmpl={
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
})
class MinecraftPlatformAdapter(Platform):
    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue) -> None:
        super().__init__(event_queue)
        self.config = platform_config
        self.settings = platform_settings

        # 上下文引用，用于发送消息
        self.context = None

        # 从配置中获取WebSocket连接信息
        self.ws_url = self.config.get("ws_url", "ws://127.0.0.1:8080/minecraft/ws")
        self.server_name = self.config.get("server_name", "Server")
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
        self.process_manager = ProcessManager()
        self.message_handler = MessageHandler(
            server_name=self.server_name,
            qq_message_prefix=self.qq_message_prefix,
            enable_join_quit=self.enable_join_quit,
            bot_filter=self.bot_filter,
            process_manager=self.process_manager
        )

        # 加载绑定关系
        self.binding_manager.load_bindings()

        # WebSocket连接头信息
        self.headers = {
            "x-self-name": self.server_name,
            "x-client-origin": "astrbot",
            "Authorization": f"Bearer {self.Authorization}" if self.Authorization else ""  # 添加Bearer前缀
        }

        # 连接状态和重连参数
        self.connected = False
        self.websocket = None
        self.should_reconnect = True  # 是否应该继续尝试重连
        self.total_retries = 0  # 总重试次数

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="minecraft",
            description="Minecraft服务器适配器",
            id=self.config.get("id")
        )

    async def run(self) -> Awaitable[Any]:
        """启动WebSocket客户端，维持与鹊桥模组的连接"""
        # 创建一个新的任务来启动WebSocket客户端，这样run方法可以立即返回
        task = asyncio.create_task(self.start_websocket_client())
        # 返回任务，但不等待它完成
        return task

    async def start_websocket_client(self):
        """启动WebSocket客户端，维持与鹊桥模组的连接"""
        retry_count = 0
        max_retries = self.max_retries

        while self.should_reconnect:
            try:
                if not self.connected:
                    logger.info(f"正在连接到鹊桥模组WebSocket服务器: {self.ws_url}")
                    
                    # 记录token使用情况
                    if not self.Authorization:
                        logger.warning("未配置Authorization，连接可能不安全")

                    # 尝试建立连接
                    self.websocket = await websockets.connect(
                        self.ws_url,
                        additional_headers=self.headers,
                        ping_interval=30,  # 保持心跳
                        ping_timeout=10
                    )

                    self.connected = True
                    retry_count = 0  # 重置重试计数
                    self.total_retries = 0  # 重置总重试次数
                    logger.info("成功连接到鹊桥模组WebSocket服务器")

                    # 持续接收消息
                    while True:
                        try:
                            message = await self.websocket.recv()
                            logger.debug(f"原始WebSocket消息: {message}")
                            await self.handle_mc_message(message)
                        except websockets.exceptions.ConnectionClosed as e:
                            logger.warning(f"WebSocket连接已关闭，代码: {e.code}, 原因: {e.reason}")
                            self.connected = False
                            self.websocket = None
                            
                            # 检查是否是认证错误或其他永久性错误
                            if e.code == 1008:  # 策略违反（可能是认证失败）
                                logger.error(f"WebSocket连接因策略违反而关闭，可能是Authorization错误: {e.reason}")
                                self.should_reconnect = False
                                break
                            elif e.code == 1003:  # 不支持的数据
                                logger.error(f"WebSocket连接因不支持的数据而关闭: {e.reason}")
                                self.should_reconnect = False
                                break
                            elif e.code == 1010:  # 必需的扩展
                                logger.error(f"WebSocket连接因扩展问题而关闭: {e.reason}")
                                self.should_reconnect = False
                                break
                            
                            break

            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    ConnectionRefusedError,
                    asyncio.TimeoutError) as e:
                self.connected = False
                self.websocket = None
                
                # 检查是否是可能无法恢复的错误
                if isinstance(e, websockets.exceptions.InvalidStatusCode):
                    if e.status_code == 401:  # 未授权，可能是token错误
                        logger.error(f"WebSocket连接未授权(401)，请检查Authorization是否正确。停止重试。")
                        self.should_reconnect = False
                        break
                    elif e.status_code == 403:  # 禁止访问
                        logger.error(f"WebSocket连接被拒绝(403)，服务器拒绝访问。停止重试。")
                        self.should_reconnect = False
                        break
                    elif e.status_code == 404:  # 路径不存在
                        logger.error(f"WebSocket连接失败(404)，请检查ws_url是否正确。停止重试。")
                        self.should_reconnect = False
                        break

                retry_count += 1
                self.total_retries += 1
                wait_time = min(self.reconnect_interval * retry_count, 60)  # 指数退避，最大60秒

                if self.total_retries >= self.max_retries:
                    logger.error(f"WebSocket连接失败次数已达到最大限制({self.max_retries}次)，停止重试")
                    self.should_reconnect = False
                    break
                elif retry_count > max_retries:
                    logger.error(f"WebSocket连接失败次数过多({retry_count}次)，将在60秒后重试")
                    await asyncio.sleep(60)
                    retry_count = 0
                else:
                    logger.error(f"WebSocket连接错误: {e}, 将在{wait_time}秒后尝试重新连接...(第{retry_count}次，总计{self.total_retries}次)")
                    await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"WebSocket处理未知错误: {e}")
                await asyncio.sleep(self.reconnect_interval)

    async def handle_mc_message(self, message: str):
        """处理从Minecraft服务器接收到的消息"""
        try:
            data = json.loads(message)
            logger.debug(f"收到Minecraft消息: {data}")

            # 获取事件名称和服务器名称
            server_type = data.get("server_type", "vanilla")
            event_name = data.get("event_name", "")
            server_name = data.get("server_name", self.server_name)

            # 根据server_type获取对应的服务器类型对象
            server_class = self.message_handler.get_server_class(server_type)

            # 获取关联的群聊列表
            bound_groups = self.binding_manager.get_bound_groups(server_name)
            if not bound_groups:
                logger.warning(f"服务器 {server_name} 没有关联的群聊，消息将不会被转发")
                return

            # 处理玩家聊天消息
            if event_name == server_class.chat:
                handled = await self.message_handler.handle_chat_message(
                    data=data,
                    server_class=server_class,
                    bound_groups=bound_groups,
                    send_to_groups_callback=self.send_to_bound_groups,
                    send_mc_message_callback=self.send_mc_message,
                    commit_event_callback=self.commit_event,
                    platform_meta=self.meta()
                )
                
                # 设置adapter引用
                if hasattr(self.message_handler, '_last_event'):
                    self.message_handler._last_event.adapter = self

            # 处理玩家加入/退出消息
            await self.message_handler.handle_player_join_quit(
                data=data,
                event_name=event_name,
                server_class=server_class,
                bound_groups=bound_groups,
                send_to_groups_callback=self.send_to_bound_groups
            )

            # 处理玩家死亡消息
            await self.message_handler.handle_player_death(
                data=data,
                event_name=event_name,
                server_class=server_class,
                bound_groups=bound_groups,
                send_to_groups_callback=self.send_to_bound_groups
            )

        except json.JSONDecodeError:
            logger.error(f"无法解析JSON消息: {message}")
        except Exception as e:
            logger.error(f"处理Minecraft消息时出错: {str(e)}")

    async def send_to_bound_groups(self, group_ids: List[str], message: str):
        """发送消息到绑定的QQ群"""
        from astrbot.core.message.message_event_result import MessageChain
        from astrbot.core.platform.astr_message_event import MessageSesion

        for group_id in group_ids:
            try:

                # 如果有context引用，使用context.send_message方法发送消息
                if hasattr(self, 'context') and self.context:
                    # 创建会话对象
                    session = f"aiocqhttp:GroupMessage:{group_id}"

                    # 创建消息链
                    message_chain = MessageChain().message(message)

                    # 发送消息
                    try:
                        await self.context.send_message(session, message_chain)
                        continue  # 发送成功，继续处理下一个群
                    except Exception as e:
                        logger.warning(f"通过context.send_message发送消息失败: {str(e)}，尝试使用事件系统")

                # 创建AstrBotMessage对象
                abm = AstrBotMessage()
                abm.type = MessageType.GROUP_MESSAGE
                abm.group_id = group_id
                abm.message_str = message
                abm.sender = MessageMember(
                    user_id=f"minecraft_{self.server_name}",
                    nickname=self.server_name
                )
                abm.message = [Plain(text=message)]
                abm.raw_message = {"content": message}
                abm.self_id = f"minecraft_{self.server_name}"
                abm.session_id = group_id
                abm.message_id = str(uuid.uuid4())

                # 创建消息事件并提交
                message_event = MinecraftMessageEvent(
                    message_str=message,
                    message_obj=abm,
                    platform_meta=self.meta(),
                    session_id=group_id,
                    adapter=self
                )

                # 使用事件系统发送消息到QQ群
                self.commit_event(message_event)
            except Exception as e:
                logger.error(f"发送消息到群 {group_id} 时出错: {str(e)}")

    async def send_by_session(self, session: MessageSesion, message_chain: MessageChain):
        """通过会话发送消息到Minecraft服务器"""
        try:
            # 提取消息文本
            message_text = ""
            for item in message_chain.chain:
                if isinstance(item, Plain):
                    message_text += item.text

            # 获取发送者信息
            sender_name = session.session_id.split(":")[-1] if ":" in session.session_id else "QQ用户"

            # 发送消息到Minecraft
            await self.send_mc_message(message_text, sender_name)

            # 调用父类方法
            await super().send_by_session(session, message_chain)
        except Exception as e:
            logger.error(f"发送消息到Minecraft时出错: {str(e)}")

    async def send_mc_message(self, message: str, sender: str = None):
        """发送消息到Minecraft服务器"""
        if not self.connected or not self.websocket:
            logger.error("无法发送消息：WebSocket未连接")
            return False

        try:
            # 构建发送到Minecraft的消息
            if sender:
                mc_message = f"{sender}: {message}"
            else:
                mc_message = f"{message}"

            broadcast_msg = {
                "api": "broadcast",
                "data": {
                    "message": [
                        {
                            "type": "text",
                            "data": {
                                "text": mc_message
                            }
                        }
                    ]
                }
            }

            # 打印要发送的JSON消息，便于调试
            logger.debug(f"发送的WebSocket消息: {json.dumps(broadcast_msg)}")

            # 发送消息
            await self.websocket.send(json.dumps(broadcast_msg))
            return True

        except Exception as e:
            logger.error(f"发送消息到Minecraft时出错: {str(e)}")
            return False

    async def terminate(self):
        """终止平台适配器"""
        self.should_reconnect = False
        if self.websocket:
            await self.websocket.close()
        logger.info("Minecraft平台适配器已被优雅地关闭")

    # 绑定和解绑群聊的方法（委托给GroupBindingManager）
    async def bind_group(self, group_id: str, server_name: str = None) -> bool:
        """绑定群聊与Minecraft服务器"""
        if server_name is None:
            server_name = self.server_name
        return self.binding_manager.bind_group(group_id, server_name)

    async def unbind_group(self, group_id: str, server_name: str = None) -> bool:
        """解除群聊与Minecraft服务器的绑定"""
        if server_name is None:
            server_name = self.server_name
        return self.binding_manager.unbind_group(group_id, server_name)

    def is_group_bound(self, group_id: str, server_name: str = None) -> bool:
        """检查群聊是否与Minecraft服务器绑定"""
        if server_name is None:
            server_name = self.server_name
        return self.binding_manager.is_group_bound(group_id, server_name)

    def is_bot_player(self, player_name: str) -> bool:
        """检查玩家是否为假人（委托给BotFilter）"""
        return self.bot_filter.is_bot_player(player_name)
