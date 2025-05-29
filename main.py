from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain
from astrbot import logger
from astrbot.core.platform.manager import PlatformManager
from astrbot.core.star.star_tools import StarTools

import asyncio
from typing import Optional

# 导入平台适配器
from .core.adapters.minecraft_adapter import MinecraftPlatformAdapter
# 导入管理器
from .core.managers.rcon_manager import RconManager
from .core.managers.broadcast_manager import BroadcastManager
# 导入命令处理器
from .core.handlers.command_handler import CommandHandler
# 导入路由管理器
from .core.routing.adapter_router import AdapterRouter

@register("mcqq", "kterna", "通过鹊桥模组实现Minecraft平台适配器，以及mcqq互联的插件", "1.6.0", "https://github.com/kterna/astrbot_plugin_mcqq")
class MCQQPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 获取平台管理器
        self.platform_manager = None
        self.minecraft_adapter = None

        # 获取数据目录
        self.data_dir = StarTools.get_data_dir("mcqq")

        # 初始化管理器
        self.rcon_manager = RconManager()
        self.broadcast_manager = BroadcastManager(str(self.data_dir))
        
        # 初始化路由管理器
        self.adapter_router = AdapterRouter(str(self.data_dir))
        
        # 初始化命令处理器
        self.command_handler = CommandHandler(self)

        # 初始化平台适配器
        asyncio.create_task(self.initialize_adapter())
        # 初始化RCON连接 (将从适配器配置读取设置)
        asyncio.create_task(self.initialize_rcon())
        # 启动整点广播任务
        asyncio.create_task(self.start_hourly_broadcast())

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

        # 查找所有Minecraft平台适配器
        minecraft_adapters = []
        for platform in self.platform_manager.platform_insts:
            if isinstance(platform, MinecraftPlatformAdapter):
                minecraft_adapters.append(platform)
                logger.info(f"找到Minecraft平台适配器: {platform.adapter_id} ({platform.server_name})")

                # 设置上下文引用，以便适配器可以使用context.send_message方法
                platform.context = self.context
                # 设置插件实例引用
                platform.plugin_instance = self
                # 设置路由器引用
                platform.router = self.adapter_router
                logger.debug(f"为适配器 {platform.adapter_id} 设置路由器引用")
                
                # 注册到路由管理器
                self.adapter_router.register_adapter(platform)
                logger.debug(f"适配器 {platform.adapter_id} 已注册到路由管理器")
                
        logger.info(f"总共找到 {len(minecraft_adapters)} 个Minecraft适配器")
        logger.info(f"路由管理器中注册的适配器: {list(self.adapter_router.adapters.keys())}")
                
        if minecraft_adapters:
            # 默认使用第一个适配器作为主适配器
            self.minecraft_adapter = minecraft_adapters[0]
            logger.info(f"已设置主适配器: {self.minecraft_adapter.adapter_id}")
        else:
            logger.warning("未找到任何Minecraft平台适配器，请确保适配器已正确注册并启用")

    async def initialize_rcon(self):
        """初始化RCON客户端并尝试连接"""
        # 等待适配器初始化完成
        await asyncio.sleep(2)

        adapter = await self.get_minecraft_adapter()
        if adapter:
            await self.rcon_manager.initialize(adapter)

    async def start_hourly_broadcast(self):
        """启动整点广播任务"""
        await asyncio.sleep(3)  # 等待适配器初始化
        await self.broadcast_manager.start_hourly_broadcast(self._broadcast_callback)

    async def _broadcast_callback(self, components):
        """广播回调函数"""
        adapter = await self.get_minecraft_adapter()
        if adapter:
            return await self.broadcast_manager.send_rich_broadcast(adapter, components)
        return False

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
        event.should_call_llm(True)
        result = await self.command_handler.handle_bind_command(event)
        yield event.plain_result(result)

    @filter.command("mcunbind")
    async def mc_unbind_command(self, event: AstrMessageEvent):
        """解除群聊与Minecraft服务器的绑定命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_unbind_command(event)
        yield event.plain_result(result)

    @filter.command("mcstatus")
    async def mc_status_command(self, event: AstrMessageEvent):
        """显示Minecraft服务器连接状态和绑定信息的命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_status_command(event)
        yield event.plain_result(result)

    @filter.command("mcsay")
    async def mc_say_command(self, event: AstrMessageEvent):
        """向Minecraft服务器发送消息的命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_say_command(event)
        yield event.plain_result(result)

    @filter.command("mc帮助")
    async def mc_help_command(self, event: AstrMessageEvent):
        """显示Minecraft相关命令的帮助信息"""
        event.should_call_llm(True)
        result = self.command_handler.handle_help_command(event)
        yield event.plain_result(result)

    @filter.command("rcon")
    async def rcon_command(self, event: AstrMessageEvent):
        """通过RCON执行Minecraft服务器指令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_rcon_command(event)
        yield event.plain_result(result)

    @filter.command("mc广播设置")
    async def mc_broadcast_config_command(self, event: AstrMessageEvent):
        """配置整点广播内容的命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_broadcast_config_command(event)
        yield event.plain_result(result)

    @filter.command("mc广播开关")
    async def mc_broadcast_toggle_command(self, event: AstrMessageEvent):
        """开启或关闭整点广播的命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_broadcast_toggle_command(event)
        yield event.plain_result(result)

    @filter.command("mc广播清除")
    async def mc_broadcast_clear_command(self, event: AstrMessageEvent):
        """清除自定义广播内容的命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_broadcast_clear_command(event)
        yield event.plain_result(result)

    @filter.command("mc广播测试")
    async def mc_broadcast_test_command(self, event: AstrMessageEvent):
        """测试整点广播的命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_broadcast_test_command(event)
        yield event.plain_result(result)

    @filter.command("mc自定义广播")
    async def mc_custom_broadcast_command(self, event: AstrMessageEvent):
        """发送自定义富文本广播的命令"""
        event.should_call_llm(True)
        result = await self.command_handler.handle_custom_broadcast_command(event)
        yield event.plain_result(result)

    async def terminate(self):
        """插件终止时调用"""
        logger.info("插件终止")
        # 保存路由器配置
        await self.adapter_router.save_config()
        # 关闭所有适配器
        await self.adapter_router.close_all_adapters()
        # 保存广播配置
        self.broadcast_manager.save_config()
        # 关闭RCON连接
        await self.rcon_manager.close()
        # 取消整点广播任务
        if self.broadcast_manager.hourly_broadcast_task is not None:
            task = self.broadcast_manager.hourly_broadcast_task
            if not task.done():
                task.cancel()
                logger.info("已取消整点广播任务")