from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain
from astrbot import logger
from astrbot.core.platform.manager import PlatformManager

import asyncio
from typing import Optional

# 导入平台适配器
from .minecraft_adapter import MinecraftPlatformAdapter

@register("mcqq", "kterna", "连接Minecraft服务器与QQ群聊的插件，通过鹊桥模组实现消息互通", "1.3.0", "https://github.com/kterna/astrbot_plugin_mcqq")
class MCQQPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 获取平台管理器
        self.platform_manager = None
        self.minecraft_adapter = None

        # 初始化平台适配器
        asyncio.create_task(self.initialize_adapter())

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
            # 创建一个新的任务来启动WebSocket客户端
            asyncio.create_task(adapter.start_websocket_client())
            # 等待一段时间，让连接有机会建立
            await asyncio.sleep(2)

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
        success = await adapter.send_mc_message(message, sender_name)
        if success:
            yield event.plain_result("✅ 消息已发送到Minecraft服务器")
        else:
            yield event.plain_result("❌ 消息发送失败")

    @filter.command("mc帮助")
    async def mc_help_command(self, event: AstrMessageEvent):
        """显示Minecraft相关命令的帮助信息"""
        # 阻止触发LLM
        event.should_call_llm(True)

        help_msg = """
        Minecraft相关命令:
        /mcbind - 绑定当前群聊与Minecraft服务器
        /mcunbind - 解除当前群聊与Minecraft服务器的绑定
        /mcstatus - 显示当前Minecraft服务器连接状态和绑定信息
        /mcsay - 向Minecraft服务器发送消息
        """
        yield event.plain_result(help_msg)
