import asyncio
import json
import os
import uuid
import websockets
from typing import Dict, List, Any, Awaitable

from astrbot.api.platform import Platform, AstrBotMessage, MessageMember, PlatformMetadata, MessageType
from astrbot.api.event import MessageChain
from astrbot.api.message_components import Plain, Image
from astrbot.core.platform.astr_message_event import MessageSesion
from astrbot.core.platform.register import register_platform_adapter
from astrbot import logger

from .minecraft_event import MinecraftMessageEvent
from .server_types import Vanilla, Spigot, Fabric, Forge, Neoforge

@register_platform_adapter("minecraft", "Minecraft服务器适配器", default_config_tmpl={
    "ws_url": "ws://127.0.0.1:8080/minecraft/ws",
    "server_name": "Server",
    "access_token": "",
    "enable_join_quit_messages": True,
    "qq_message_prefix": "[MC]"
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
        self.access_token = self.config.get("access_token", "")
        self.enable_join_quit = self.config.get("enable_join_quit_messages", True)
        self.qq_message_prefix = self.config.get("qq_message_prefix", "[MC]")

        # 配置文件路径
        self.data_dir = os.path.join("data", "minecraft")
        self.bindings_file = os.path.join(self.data_dir, "group_bindings.json")

        # 确保数据目录存在
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        # 群聊与服务器关联配置
        self.group_bindings = self.load_bindings()

        # WebSocket连接头信息
        self.headers = {
            "x-self-name": self.server_name,
            "x-client-origin": "astrbot"
        }

        # 连接状态和重连参数
        self.connected = False
        self.reconnect_interval = 3  # 重连间隔(秒)
        self.websocket = None
        self.should_reconnect = True  # 是否应该继续尝试重连

    def load_bindings(self) -> Dict[str, List[str]]:
        """从文件加载群聊与服务器的绑定关系"""
        try:
            if os.path.exists(self.bindings_file):
                with open(self.bindings_file, 'r', encoding='utf-8') as f:
                    bindings = json.load(f)
                logger.info(f"已从 {self.bindings_file} 加载群聊绑定配置")
                return bindings
            else:
                logger.info("绑定配置文件不存在，将创建新的配置")
                return {}
        except Exception as e:
            logger.error(f"加载群聊绑定配置时出错: {str(e)}")
            return {}

    def save_bindings(self):
        """保存群聊与服务器的绑定关系到文件"""
        try:
            with open(self.bindings_file, 'w', encoding='utf-8') as f:
                json.dump(self.group_bindings, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存群聊绑定配置到 {self.bindings_file}")
        except Exception as e:
            logger.error(f"保存群聊绑定配置时出错: {str(e)}")

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
        max_retries = 5

        while self.should_reconnect:
            try:
                if not self.connected:
                    logger.info(f"正在连接到鹊桥模组WebSocket服务器: {self.ws_url}")

                    # 尝试建立连接
                    self.websocket = await websockets.connect(
                        self.ws_url,
                        additional_headers=self.headers,
                        ping_interval=30,  # 保持心跳
                        ping_timeout=10
                    )

                    self.connected = True
                    retry_count = 0  # 重置重试计数
                    logger.info("成功连接到鹊桥模组WebSocket服务器")

                    # 持续接收消息
                    while True:
                        try:
                            message = await self.websocket.recv()
                            logger.debug(f"原始WebSocket消息: {message}")
                            await self.handle_mc_message(message)
                        except websockets.exceptions.ConnectionClosed:
                            logger.warning("WebSocket连接已关闭，准备重新连接")
                            self.connected = False
                            self.websocket = None
                            break

            except (websockets.exceptions.ConnectionClosed,
                    websockets.exceptions.WebSocketException,
                    ConnectionRefusedError) as e:
                self.connected = False
                self.websocket = None

                retry_count += 1
                wait_time = min(self.reconnect_interval * retry_count, 60)  # 指数退避，最大60秒

                if retry_count > max_retries:
                    logger.error(f"WebSocket连接失败次数过多({retry_count}次)，将在60秒后重试")
                    await asyncio.sleep(60)
                    retry_count = 0
                else:
                    logger.error(f"WebSocket连接错误: {e}, 将在{wait_time}秒后尝试重新连接...(第{retry_count}次)")
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
            server_class = None
            if server_type == "vanilla":
                server_class = Vanilla()
            elif server_type == "spigot":
                server_class = Spigot()
            elif server_type == "fabric":
                server_class = Fabric()
            elif server_type == "forge":
                server_class = Forge()
            elif server_type == "neoforge":
                server_class = Neoforge()
            else:
                server_class = Vanilla()  # 默认使用vanilla类型

            # 获取关联的群聊列表
            bound_groups = self.group_bindings.get(server_name, [])
            if not bound_groups:
                logger.warning(f"服务器 {server_name} 没有关联的群聊，消息将不会被转发")
                return

            # 处理玩家聊天消息
            if event_name == server_class.chat and data.get("post_type") == "message" and data.get("sub_type") == "chat":
                player_data = data.get("player", {})
                player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
                message_text = data.get("message", "")

                # 处理以"#qq"开头的消息，转发到QQ群
                if message_text.startswith("#qq"):
                    message_text = message_text[3:].strip()
                    # 构建转发到QQ的消息
                    qq_message = f"{self.qq_message_prefix} {player_name}: {message_text}"

                    # 转发到关联的群聊
                    if bound_groups:
                        await self.send_to_bound_groups(bound_groups, qq_message)
                    else:
                        logger.warning(f"没有找到绑定的群聊，无法转发消息: {qq_message}")
                        await self.send_mc_message("没有找到绑定的群聊，无法转发消息。请先使用/mcbind命令绑定群聊。")

                # 处理以"#astr"开头的消息，作为AstrBot指令处理
                elif message_text.startswith("#astr"):
                    command_text = message_text[5:].strip()  # 去掉"#astr"前缀
                    if not command_text:
                        # 如果没有指令内容，发送帮助信息
                        help_message = "请输入要执行的AstrBot指令，例如：#astr help"
                        await self.send_mc_message(help_message)
                        return

                    try:
                        # 创建一个虚拟的消息事件，用于执行指令
                        abm = AstrBotMessage()
                        abm.type = MessageType.FRIEND_MESSAGE  # 使用私聊类型，避免群聊权限问题
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
                            platform_meta=self.meta(),
                            session_id=f"minecraft_{player_name}",
                            adapter=self
                        )

                        # 设置回调函数，将AstrBot的响应发送回Minecraft
                        async def on_response(response_message):
                            await self.send_mc_message(response_message)

                        message_event.on_response = on_response

                        # 提交事件到AstrBot处理
                        self.commit_event(message_event)
                    except Exception as e:
                        logger.error(f"执行AstrBot指令时出错: {str(e)}")
                        await self.send_mc_message(f"执行指令时出错: {str(e)}")

            # 处理玩家加入/退出消息
            if self.enable_join_quit and event_name:
                if event_name == server_class.join:
                    player_data = data.get("player", {})
                    player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
                    join_message = f"{self.qq_message_prefix} 玩家 {player_name} 加入了服务器"

                    # 转发到关联的群聊
                    await self.send_to_bound_groups(bound_groups, join_message)

                elif event_name == server_class.quit:
                    player_data = data.get("player", {})
                    player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
                    quit_message = f"{self.qq_message_prefix} 玩家 {player_name} 离开了服务器"

                    # 转发到关联的群聊
                    await self.send_to_bound_groups(bound_groups, quit_message)

            # 处理玩家死亡消息
            if hasattr(server_class, 'death') and event_name == server_class.death:
                player_data = data.get("player", {})
                player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
                death_reason = data.get("message", "未知原因")

                # 构建死亡位置信息（如果服务器类型支持位置信息）
                death_location = ""
                if "block_x" in server_class.player and "block_y" in server_class.player and "block_z" in server_class.player:
                    death_location = f"位置：x:{player_data.get('block_x')},y:{player_data.get('block_y')},z:{player_data.get('block_z')}"

                death_message = f"{self.qq_message_prefix} 玩家 {player_name} 死亡了，原因：{death_reason}"
                if death_location:
                    death_message += f"，{death_location}"

                # 转发到关联的群聊
                await self.send_to_bound_groups(bound_groups, death_message)

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

    # 绑定和解绑群聊的方法
    async def bind_group(self, group_id: str, server_name: str = None) -> bool:
        """绑定群聊与Minecraft服务器"""
        if server_name is None:
            server_name = self.server_name

        if server_name not in self.group_bindings:
            self.group_bindings[server_name] = []

        if group_id in self.group_bindings[server_name]:
            return False  # 已经绑定

        self.group_bindings[server_name].append(group_id)
        self.save_bindings()
        return True

    async def unbind_group(self, group_id: str, server_name: str = None) -> bool:
        """解除群聊与Minecraft服务器的绑定"""
        if server_name is None:
            server_name = self.server_name

        if server_name in self.group_bindings and group_id in self.group_bindings[server_name]:
            self.group_bindings[server_name].remove(group_id)
            self.save_bindings()
            return True
        return False

    def is_group_bound(self, group_id: str, server_name: str = None) -> bool:
        """检查群聊是否与Minecraft服务器绑定"""
        if server_name is None:
            server_name = self.server_name

        return server_name in self.group_bindings and group_id in self.group_bindings[server_name]
