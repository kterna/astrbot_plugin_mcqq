from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain
from astrbot import logger
from astrbot.core.platform.manager import PlatformManager

import asyncio
from typing import Optional

# 导入平台适配器
from .minecraft_adapter import MinecraftPlatformAdapter
import aiomcrcon

@register("mcqq", "kterna", "通过鹊桥模组实现Minecraft平台适配器，以及mcqq互联的插件", "1.4.0", "https://github.com/kterna/astrbot_plugin_mcqq")
class MCQQPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 获取平台管理器
        self.platform_manager = None
        self.minecraft_adapter = None

        # RCON 相关属性 - 初始化为默认值，实际值将从适配器配置中加载
        self.rcon_client: Optional[aiomcrcon.Client] = None
        self.rcon_enabled: bool = False
        self.rcon_host: Optional[str] = None
        self.rcon_port: Optional[int] = None
        self.rcon_password: Optional[str] = None
        self.rcon_connected: bool = False

        # 初始化平台适配器
        asyncio.create_task(self.initialize_adapter())
        # 初始化RCON连接 (将从适配器配置读取设置)
        asyncio.create_task(self.initialize_rcon())

    async def initialize_adapter(self):
        """初始化Minecraft平台适配器"""
        # 等待平台管理器初始化完成
        await asyncio.sleep(2)

        # 获取平台管理器
        for attr_name in dir(self.context):
            attr = getattr(self.context, attr_name)
            if isinstance(attr, PlatformManager):
                self.platform_manager = attr
                break

        if not self.platform_manager:
            logger.error("无法获取平台管理器，Minecraft平台适配器将无法正常工作")
            return

        # 查找Minecraft平台适配器
        for platform in self.platform_manager.platform_insts:
            if isinstance(platform, MinecraftPlatformAdapter):
                self.minecraft_adapter = platform
                logger.info("已找到Minecraft平台适配器")

                # 设置上下文引用，以便适配器可以使用context.send_message方法
                self.minecraft_adapter.context = self.context
                break

        if not self.minecraft_adapter:
            logger.warning("未找到Minecraft平台适配器，请确保适配器已正确注册并启用")

    async def initialize_rcon(self):
        """初始化RCON客户端并尝试连接 (从适配器配置中获取设置)"""
        # 等待适配器初始化完成，确保 self.minecraft_adapter 可用
        await asyncio.sleep(3)

        adapter = await self.get_minecraft_adapter()
        if not adapter:
            logger.warning("RCON初始化推迟：等待Minecraft平台适配器可用...")
            return

        # 从适配器的配置中获取RCON设置
        self.rcon_enabled = adapter.config.get("rcon_enabled", False)
        self.rcon_host = adapter.config.get("rcon_host", "localhost")
        self.rcon_port = adapter.config.get("rcon_port", 25575)
        self.rcon_password = adapter.config.get("rcon_password", "")

        if not self.rcon_enabled:
            logger.info("RCON功能未在适配器配置中启用，跳过RCON初始化。")
            return

        if not self.rcon_password:
            logger.error("RCON密码未在适配器配置中配置，无法初始化RCON连接。")
            return
        
        if not self.rcon_host:
            logger.error("RCON主机未在适配器配置中配置，无法初始化RCON连接。")
            return

        self.rcon_client = aiomcrcon.Client(self.rcon_host, self.rcon_port, self.rcon_password)
        logger.info(f"RCON: 正在尝试连接到服务器 {self.rcon_host}:{self.rcon_port}...")
        try:
            await self.rcon_client.connect()
            self.rcon_connected = True
            logger.info(f"RCON: 成功连接到服务器 {self.rcon_host}:{self.rcon_port}")
        except aiomcrcon.IncorrectPasswordError:
            logger.error(f"RCON连接失败：密码不正确。主机: {self.rcon_host}:{self.rcon_port}")
            self.rcon_client = None # 在认证失败时清除客户端
        except aiomcrcon.RCONConnectionError as e:
            logger.error(f"RCON连接错误：无法连接到服务器 {self.rcon_host}:{self.rcon_port}。错误: {e}")
            self.rcon_client = None # 在连接失败时清除客户端
        except Exception as e:
            logger.error(f"初始化RCON时发生未知错误: {e}")
            self.rcon_client = None # 清除客户端

    async def close_rcon(self):
        """关闭RCON连接"""
        if self.rcon_client and self.rcon_connected:
            logger.info(f"RCON: 正在关闭与服务器 {self.rcon_host}:{self.rcon_port} 的连接...")
            try:
                await self.rcon_client.close()
                logger.info(f"RCON: 连接已成功关闭 ({self.rcon_host}:{self.rcon_port})")
            except Exception as e:
                logger.error(f"关闭RCON连接时发生错误: {e}")
            finally:
                self.rcon_connected = False
                self.rcon_client = None # 确保在关闭尝试后客户端为None

    async def get_minecraft_adapter(self) -> Optional[MinecraftPlatformAdapter]:
        """获取Minecraft平台适配器"""
        if self.minecraft_adapter:
            return self.minecraft_adapter

        # 如果还没有找到适配器，再次尝试查找
        if self.platform_manager:
            for platform in self.platform_manager.platform_insts:
                if isinstance(platform, MinecraftPlatformAdapter):
                    self.minecraft_adapter = platform
                    logger.info("已找到Minecraft平台适配器")
                    return self.minecraft_adapter

        logger.warning("未找到Minecraft平台适配器，请确保适配器已正确注册并启用")
        return None

    @filter.command("mcbind")
    async def mc_bind_command(self, event: AstrMessageEvent):
        """绑定群聊与Minecraft服务器的命令"""
        # 阻止触发LLM
        event.should_call_llm(True)

        # 仅管理员可以使用此命令
        if not event.is_admin():
            yield event.plain_result("⛔ 只有管理员才能使用此命令")
            return

        group_id = event.get_group_id()

        if not group_id:
            yield event.plain_result("❌ 此命令只能在群聊中使用")
            return

        # 获取Minecraft适配器
        adapter = await self.get_minecraft_adapter()
        if not adapter:
            yield event.plain_result("❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用")
            return

        # 绑定群聊
        success = await adapter.bind_group(group_id)

        if success:
            yield event.plain_result("✅ 成功将本群与Minecraft服务器绑定")
        else:
            yield event.plain_result("ℹ️ 此群已经与Minecraft服务器绑定")

        logger.info(f"群聊 {group_id} 与服务器 {adapter.server_name} 绑定")

    @filter.command("mcunbind")
    async def mc_unbind_command(self, event: AstrMessageEvent):
        """解除群聊与Minecraft服务器的绑定命令"""
        # 阻止触发LLM
        event.should_call_llm(True)

        # 仅管理员可以使用此命令
        if not event.is_admin():
            yield event.plain_result("⛔ 只有管理员才能使用此命令")
            return

        group_id = event.get_group_id()

        if not group_id:
            yield event.plain_result("❌ 此命令只能在群聊中使用")
            return

        # 获取Minecraft适配器
        adapter = await self.get_minecraft_adapter()
        if not adapter:
            yield event.plain_result("❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用")
            return

        # 解除绑定
        success = await adapter.unbind_group(group_id)

        if success:
            yield event.plain_result("✅ 成功解除本群与Minecraft服务器的绑定")
        else:
            yield event.plain_result("ℹ️ 此群未与Minecraft服务器绑定")

        logger.info(f"解除群聊 {group_id} 与服务器 {adapter.server_name} 的绑定")

    @filter.command("mcstatus")
    async def mc_status_command(self, event: AstrMessageEvent):
        """显示Minecraft服务器连接状态和绑定信息的命令"""
        # 阻止触发LLM
        event.should_call_llm(True)

        group_id = event.get_group_id()

        # 获取Minecraft适配器
        adapter = await self.get_minecraft_adapter()
        if not adapter:
            yield event.plain_result("❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用")
            return

        # 如果未连接，尝试手动启动连接
        if not adapter.connected:
            yield event.plain_result("⏳ Minecraft服务器未连接，正在尝试连接...")
            
            # 强制重置连接状态
            adapter.connected = False
            adapter.websocket = None
            adapter.should_reconnect = True
            adapter.total_retries = 0
            
            # 启动新的重连任务并等待结果
            asyncio.create_task(adapter.start_websocket_client())
        else:
            # 生成状态消息
            status_msg = f"🔌 Minecraft服务器连接状态: {'已连接' if adapter.connected else '未连接'}\n"

            # 添加绑定信息
            is_bound = adapter.is_group_bound(group_id)

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

        # 获取Minecraft适配器
        adapter = await self.get_minecraft_adapter()
        if not adapter:
            yield event.plain_result("❌ 未找到Minecraft平台适配器，请确保适配器已正确注册并启用")
            return

        if not adapter.connected:
            yield event.plain_result("❌ 未连接到Minecraft服务器，请检查连接")
            return

        # 获取发送者信息
        sender_name = event.get_sender_name()

        # 发送消息到Minecraft
        await adapter.send_mc_message(message, sender_name)

    @filter.command("mc帮助")
    async def mc_help_command(self, event: AstrMessageEvent):
        """显示Minecraft相关命令的帮助信息"""
        # 阻止触发LLM
        event.should_call_llm(True)

        help_msg = """
Minecraft相关指令菜单:
qq群:
    '/'或@机器人可发起ai对话
    /mcbind - 绑定当前群聊与Minecraft服务器
    /mcunbind - 解除当前群聊与Minecraft服务器的绑定
    /mcstatus - 显示当前Minecraft服务器连接状态和绑定信息
    /mcsay - 向Minecraft服务器发送消息
    /rcon <指令> - 通过RCON执行Minecraft服务器指令 (仅管理员)
    /投影 - 获取投影菜单帮助(依赖插件astrbot_plugin_litematic)
mc:
    #astr - 发起ai对话
    #qq - 向qq群发送消息
"""
        yield event.plain_result(help_msg)

    @filter.command("rcon")
    async def rcon_command(self, event: AstrMessageEvent):
        """通过RCON执行Minecraft服务器指令"""
        event.should_call_llm(True)

        if not event.is_admin():
            yield event.plain_result("⛔ 只有管理员才能使用此命令。")
            return

        # 首先检查 RCON 是否在配置中启用
        if not self.rcon_enabled:
            logger.info(f"RCON: 用户 {event.get_sender_id()} 尝试执行rcon指令，但RCON功能未启用。")
            yield event.plain_result("❌ RCON 功能当前未启用。请联系管理员在插件配置中启用。")
            return

        command_to_execute = event.message_str.replace("rcon", "", 1).strip()
        if not command_to_execute:
            yield event.plain_result("❓ 请提供要执行的RCON指令，例如：/rcon whitelist add 玩家名")
            return

        if not self.rcon_client or not self.rcon_connected:
            logger.warning(f"RCON: 用户 {event.get_sender_id()} 尝试执行指令 '{command_to_execute}' 但RCON未连接。")
            yield event.plain_result("❌ RCON未连接到Minecraft服务器。正在尝试连接...")
            asyncio.create_task(self.initialize_rcon()) # 尝试重新初始化RCON连接
            return

        logger.info(f"RCON: 管理员 {event.get_sender_id()} 正在执行指令: '{command_to_execute}'")
        try:
            response = await self.rcon_client.send_cmd(command_to_execute)
            if response :
                actual_response = response[0]
            else:
                actual_response = "指令执行失败"

            yield event.plain_result(f"{actual_response}")
            logger.info(f"RCON: 指令 '{command_to_execute}' 响应: {actual_response}")

        except aiomcrcon.ClientNotConnectedError:
            logger.error("RCON: 在发送指令时发现客户端未连接。")
            self.rcon_connected = False # 更新连接状态
            yield event.plain_result("❌ RCON客户端未连接。请重试或检查连接。")
        except Exception as e:
            logger.error(f"RCON: 执行指令 '{command_to_execute}' 时发生错误: {e}")
            yield event.plain_result(f"❌ 执行RCON指令时发生错误: {e}")