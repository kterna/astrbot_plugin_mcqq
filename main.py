from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api.message_components import Plain, Image
from astrbot.core import AstrBotConfig
from astrbot import logger
from astrbot.core.platform.message_type import MessageType
from astrbot.core.message.message_event_result import MessageChain

import json
import asyncio
import websockets
import os
from typing import Dict, List, Optional

@register("mcqq", "kterna", "连接Minecraft服务器与QQ群聊的插件，通过鹊桥模组实现消息互通", "1.1.0", "https://github.com/kterna/astrbot_plugin_mcqq")
class MCQQPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        # 从配置中获取WebSocket连接信息
        self.ws_url = config.get("WEBSOCKET_URL", "ws://127.0.0.1:8080/minecraft/ws")
        self.server_name = config.get("SERVER_NAME", "Server")
        self.access_token = config.get("ACCESS_TOKEN", "")
        self.qq_message_prefix = config.get("QQ_MESSAGE_PREFIX", "[MC]")
        self.enable_join_quit = config.get("ENABLE_JOIN_QUIT_MESSAGES", True)
        
        # 配置文件路径
        self.data_dir = StarTools.get_data_dir("mcqq")
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
        
        # 启动WebSocket客户端
        asyncio.create_task(self.start_websocket_client())
    
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
    
    async def start_websocket_client(self):
        """启动WebSocket客户端，维持与鹊桥模组的连接"""
        retry_count = 0
        max_retries = 5
        
        while self.should_reconnect:
            try:
                if not self.connected:
                    logger.info(f"正在连接到鹊桥模组WebSocket服务器: {self.ws_url}")
                    logger.info(f"连接头信息: {self.headers}")
                    
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
                    logger.error(f"WebSocket连接失败次数过多({retry_count}次)，已停止自动重连。使用 /mcstatus 命令手动触发重连")
                    self.should_reconnect = False  # 停止重连尝试
                    break  # 退出循环
                else:
                    logger.error(f"WebSocket连接错误: {e}, 将在{wait_time}秒后尝试重新连接...(第{retry_count}次)")
                    await asyncio.sleep(wait_time)
            
            except Exception as e:
                logger.error(f"WebSocket处理未知错误: {e}")
                await asyncio.sleep(self.reconnect_interval)
                
        logger.info("WebSocket连接循环已退出，等待手动触发重连")
    
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
                
                if message_text.startswith("qq"):
                    message_text = message_text[2:]
                    # 构建转发到QQ的消息
                    qq_message = f"{self.qq_message_prefix} {player_name}: {message_text}"
                    
                    # 转发到关联的群聊
                    await self.send_to_bound_groups(bound_groups, qq_message)
                    logger.info(f"已转发玩家消息到关联群聊: {qq_message}")
            
            # 处理玩家加入/退出消息
            if self.enable_join_quit and event_name:
                if event_name == server_class.join:
                    player_data = data.get("player", {})
                    player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
                    join_message = f"{self.qq_message_prefix} 玩家 {player_name} 加入了服务器"
                    
                    # 转发到关联的群聊
                    await self.send_to_bound_groups(bound_groups, join_message)
                    logger.info(f"已转发玩家加入消息: {join_message}")
                
                elif event_name == server_class.quit:
                    player_data = data.get("player", {})
                    player_name = player_data.get("nickname", player_data.get("display_name", "未知玩家"))
                    quit_message = f"{self.qq_message_prefix} 玩家 {player_name} 离开了服务器"
                    
                    # 转发到关联的群聊
                    await self.send_to_bound_groups(bound_groups, quit_message)
                    logger.info(f"已转发玩家离开消息: {quit_message}")
            
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
                logger.info(f"已转发玩家死亡消息: {death_message}")
            
        except json.JSONDecodeError:
            logger.error(f"无法解析JSON消息: {message}")
        except Exception as e:
            logger.error(f"处理Minecraft消息时出错: {str(e)}")
    
    async def send_to_bound_groups(self, group_ids: List[str], message: str):
        """发送消息到绑定的QQ群"""
        for group_id in group_ids:
            try:
                # 正确构建MessageChain对象
                message_chain = MessageChain().message(message)
                
                # 创建统一消息源字符串，格式为"platform_name:message_type:session_id"
                # 这里使用aiocqhttp作为默认平台适配器，如需其他平台可根据需要修改
                session = f"aiocqhttp:GroupMessage:{group_id}"
                
                await self.context.send_message(session, message_chain)
                logger.debug(f"已发送消息到群 {group_id}: {message}")
            except Exception as e:
                logger.error(f"发送消息到群 {group_id} 时出错: {str(e)}")
    
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
            logger.info(f"已发送消息到Minecraft: {mc_message}")
            return True
            
        except Exception as e:
            logger.error(f"发送消息到Minecraft时出错: {str(e)}")
            return False
    
    @filter.command("mcbind")
    async def mc_bind_command(self, event: AstrMessageEvent):
        """绑定群聊与Minecraft服务器的命令"""
        # 阻止触发LLM
        event.should_call_llm(False)
        
        # 仅管理员可以使用此命令
        if not event.is_admin():
            yield event.plain_result("⛔ 只有管理员才能使用此命令")
            return
        
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("❌ 此命令只能在群聊中使用")
            return
        

        server_name = self.server_name
        
        # 更新绑定关系
        if server_name not in self.group_bindings:
            self.group_bindings[server_name] = []
        
        if group_id in self.group_bindings[server_name]:
            yield event.plain_result("ℹ️ 此群已经与Minecraft服务器绑定")
        else:
            self.group_bindings[server_name].append(group_id)
            # 保存绑定关系
            self.save_bindings()
            yield event.plain_result("✅ 成功将本群与Minecraft服务器绑定")
        
        logger.info(f"群聊 {group_id} 与服务器 {server_name} 绑定")
    
    @filter.command("mcunbind")
    async def mc_unbind_command(self, event: AstrMessageEvent):
        """解除群聊与Minecraft服务器的绑定命令"""
        # 阻止触发LLM
        event.should_call_llm(False)
        
        # 仅管理员可以使用此命令
        if not event.is_admin():
            yield event.plain_result("⛔ 只有管理员才能使用此命令")
            return
        
        group_id = event.get_group_id()
        
        if not group_id:
            yield event.plain_result("❌ 此命令只能在群聊中使用")
            return
        

        server_name = self.server_name
        
        # 更新绑定关系
        if server_name in self.group_bindings and group_id in self.group_bindings[server_name]:
            self.group_bindings[server_name].remove(group_id)
            # 保存绑定关系
            self.save_bindings()
            yield event.plain_result("✅ 成功解除本群与Minecraft服务器的绑定")
        else:
            yield event.plain_result("ℹ️ 此群未与Minecraft服务器绑定")
        
        logger.info(f"解除群聊 {group_id} 与服务器 {server_name} 的绑定")
    
    @filter.command("mcstatus")
    async def mc_status_command(self, event: AstrMessageEvent):
        """显示Minecraft服务器连接状态和绑定信息的命令"""
        # 阻止触发LLM
        event.should_call_llm(False)
        
        group_id = event.get_group_id()
        
        # 如果连接失败且不在重连状态，则手动触发重连
        if not self.connected and not self.should_reconnect:
            self.should_reconnect = True
            asyncio.create_task(self.start_websocket_client())
            yield event.plain_result("未连接到服务器，正在尝试重新连接...")
            return
        
        # 生成状态消息
        status_msg = f"🔌 Minecraft服务器连接状态: {'已连接' if self.connected else '未连接'}\n"
        status_msg += f"🌐 WebSocket地址: {self.ws_url}\n"
        
        # 添加绑定信息
        server_name = self.server_name
        is_bound = server_name in self.group_bindings and group_id in self.group_bindings[server_name]
        
        if is_bound:
            status_msg += "🔗 本群已绑定Minecraft服务器"
        else:
            status_msg += "🔗 本群未绑定Minecraft服务器"
        
        yield event.plain_result(status_msg)
    
    @filter.command("mcsay")
    async def mc_say_command(self, event: AstrMessageEvent):
        """向Minecraft服务器发送消息的命令"""
        # 阻止触发LLM
        event.should_call_llm(True)
        
        message = event.message_str
        message = message.replace("mcsay", "", 1).strip()
        if not message:
            yield event.plain_result("❓ 请提供要发送的消息内容，例如：/mcsay 大家好")
            return
        
        if not self.connected:
            yield event.plain_result("❌ 未连接到Minecraft服务器，请检查连接")
            return
        
        # 获取发送者信息
        sender_name = event.get_sender_name()
        
        # 发送消息到Minecraft
        await self.send_mc_message(message, sender_name)

    @filter.command("mc帮助")
    async def mc_help_command(self, event: AstrMessageEvent):
        """显示Minecraft相关命令的帮助信息"""
        
        help_msg = """
        Minecraft相关命令:
        /mcbind - 绑定当前群聊与Minecraft服务器
        /mcunbind - 解除当前群聊与Minecraft服务器的绑定
        /mcstatus - 显示当前Minecraft服务器连接状态和绑定信息
        /mcsay - 向Minecraft服务器发送消息
        """
        yield event.plain_result(help_msg)


class Vanilla():
    def __init__(self):
        self.server_type="vanilla"
        self.chat="MinecraftPlayerChatEvent"
        self.join="MinecraftPlayerJoinEvent"
        self.quit="MinecraftPlayerQuitEvent"

        self.player={
            "nickname": "nickname",
        }

class Spigot():
    def __init__(self):
        self.server_type="spigot"
        self.chat="AsyncPlayerChatEvent"
        self.join="PlayerJoinEvent"
        self.quit="PlayerQuitEvent"
        self.death="PlayerDeathEvent"
        self.player_command="PlayerCommandPreprocessEvent"

        self.player={
            "nickname": "nickname",
        }

class Fabric():
    def __init__(self):
        self.server_type="fabric"
        self.chat="ServerMessageEvent"
        self.join="ServerPlayConnectionJoinEvent"
        self.quit="ServerPlayConnectionDisconnectEvent"
        self.death="ServerLivingEntityAfterDeathEvent"
        self.player_command="ServerCommandMessageEvent"

        self.player={
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }

class Forge():    
    def __init__(self):
        self.server_type="forge"
        self.chat="ServerChatEvent"
        self.join="PlayerLoggedInEvent"
        self.quit="PlayerLoggedOutEvent"

        self.player={
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }
    
class Neoforge():
    def __init__(self):
        self.server_type="neoforge"
        self.chat="NeoServerChatEvent"
        self.join="NeoPlayerLoggedInEvent"
        self.quit="NeoPlayerLoggedOutEvent"
        self.player_command="NeoCommandEventb"

        self.player={
            "nickname": "nickname",
            "block_x": "block_x",
            "block_y": "block_y",
            "block_z": "block_z",
        }
