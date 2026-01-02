import asyncio
from typing import Optional, List

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api.message_components import Plain
from astrbot import logger
from astrbot.core.platform.manager import PlatformManager
from astrbot.core.star.star_tools import StarTools
from astrbot.core.star.register.star_handler import register_on_platform_loaded

# 常量定义
PLUGIN_DATA_DIR = "mcqq"

# 导入平台适配器
from .core.adapters.minecraft_adapter import MinecraftPlatformAdapter
# 导入管理器
from .core.managers.rcon_manager import RconManager
from .core.managers.broadcast_config import BroadcastConfigManager
from .core.managers.broadcast_sender import BroadcastSender
from .core.managers.broadcast_scheduler import BroadcastScheduler
# 导入命令处理器
from .core.handlers.command_handler import CommandHandler
# 导入路由管理器
from .core.routing.adapter_router import AdapterRouter

@register("mcqq", "kterna", "通过鹊桥模组实现Minecraft平台适配器，以及mcqq互联的插件", "1.8.4", "https://github.com/kterna/astrbot_plugin_mcqq")
class MCQQPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 获取平台管理器
        self.platform_manager = None
        self.minecraft_adapter = None

        # 获取数据目录
        self.data_dir = StarTools.get_data_dir(PLUGIN_DATA_DIR)

        # 初始化管理器
        self.rcon_manager = RconManager()
        self.broadcast_config_manager = BroadcastConfigManager(str(self.data_dir))
        self.broadcast_sender = BroadcastSender()
        self.broadcast_scheduler = BroadcastScheduler(self, self.broadcast_config_manager, self._broadcast_callback)
        
        # 初始化路由管理器
        self.adapter_router = AdapterRouter(str(self.data_dir))
        
        # 初始化命令处理器
        self.command_handler = CommandHandler(self)

        # 初始化RCON连接 (将从适配器配置读取设置)
        asyncio.create_task(self.initialize_rcon())
        # 启动整点广播任务
        asyncio.create_task(self.start_hourly_broadcast())

    @register_on_platform_loaded()
    async def initialize_adapter(self):
        """初始化Minecraft平台适配器 - 监听平台加载完成钩子"""
        logger.info("检测到平台加载完成事件，开始初始化Minecraft适配器...")

        # 从上下文中直接获取平台管理器
        self.platform_manager = getattr(self.context, 'platform_manager', None)
        if not self.platform_manager:
            logger.error("无法获取平台管理器，Minecraft平台适配器将无法正常工作")
            return

        # 查找所有Minecraft平台适配器并设置路由器引用
        minecraft_adapters = []
        for platform in self.platform_manager.platform_insts:
            if isinstance(platform, MinecraftPlatformAdapter):
                minecraft_adapters.append(platform)
                logger.info(f"找到Minecraft平台适配器: {platform.adapter_id} ({platform.server_name})")

                # 设置路由器引用（用于适配器间消息转发）
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
            self.minecraft_adapter = None
            logger.warning("未找到任何Minecraft平台适配器，请确保适配器已正确注册并启用")

    async def initialize_rcon(self):
        """初始化RCON客户端并尝试连接"""
        # 等待适配器初始化完成
        await asyncio.sleep(2)

        await self.rcon_manager.initialize(self.minecraft_adapter)

    async def start_hourly_broadcast(self):
        """启动整点广播任务"""
        await asyncio.sleep(3)  # 等待适配器初始化
        self.broadcast_scheduler.start()

    async def _broadcast_callback(self, adapters, components):
        """广播回调函数"""
        if adapters:
            return await self.broadcast_sender.send_rich_broadcast(adapters, components)
        return False

    async def get_all_minecraft_adapter(self) -> List[MinecraftPlatformAdapter]:
        """获取所有Minecraft平台适配器"""
        minecraft_adapters = []

        if self.platform_manager:
            for platform in self.platform_manager.platform_insts:
                if isinstance(platform, MinecraftPlatformAdapter):
                    minecraft_adapters.append(platform)
                    logger.debug(f"找到Minecraft平台适配器: {platform.adapter_id}")

        if not minecraft_adapters:
            logger.warning("未找到任何Minecraft平台适配器，请确保适配器已正确注册并启用")

        return minecraft_adapters

    async def _handle_command(self, event: AstrMessageEvent, handler_method, is_async=True):
        """统一的命令处理方法，减少重复代码"""
        event.should_call_llm(True)
        result = await handler_method(event) if is_async else handler_method(event)
        yield event.plain_result(result)

    @filter.command("mcbind")
    async def mc_bind_command(self, event: AstrMessageEvent):
        """绑定群聊与Minecraft服务器的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_bind_command):
            yield result

    @filter.command("mcunbind")
    async def mc_unbind_command(self, event: AstrMessageEvent):
        """解除群聊与Minecraft服务器的绑定命令"""
        async for result in self._handle_command(event, self.command_handler.handle_unbind_command):
            yield result

    @filter.command("mcstatus")
    async def mc_status_command(self, event: AstrMessageEvent):
        """显示Minecraft服务器连接状态和绑定信息的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_status_command):
            yield result

    @filter.command("mcsay")
    async def mc_say_command(self, event: AstrMessageEvent):
        """向Minecraft服务器发送消息的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_say_command):
            yield result

    @filter.command("mc帮助")
    async def mc_help_command(self, event: AstrMessageEvent):
        """显示Minecraft相关命令的帮助信息"""
        async for result in self._handle_command(event, self.command_handler.handle_help_command, False):
            yield result

    @filter.command("rcon")
    async def rcon_command(self, event: AstrMessageEvent):
        """通过RCON执行Minecraft服务器指令"""
        async for result in self._handle_command(event, self.command_handler.handle_rcon_command):
            yield result

    @filter.command("mc广播设置")
    async def mc_broadcast_config_command(self, event: AstrMessageEvent):
        """配置整点广播内容的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_broadcast_config_command):
            yield result

    @filter.command("mc广播开关")
    async def mc_broadcast_toggle_command(self, event: AstrMessageEvent):
        """开启或关闭整点广播的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_broadcast_toggle_command):
            yield result

    @filter.command("mc广播清除")
    async def mc_broadcast_clear_command(self, event: AstrMessageEvent):
        """清除自定义广播内容的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_broadcast_clear_command):
            yield result

    @filter.command("mc广播测试")
    async def mc_broadcast_test_command(self, event: AstrMessageEvent):
        """测试整点广播的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_broadcast_test_command):
            yield result

    @filter.command("mc自定义广播")
    async def mc_custom_broadcast_command(self, event: AstrMessageEvent):
        """发送自定义富文本广播的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_custom_broadcast_command):
            yield result

    @filter.command("mc玩家列表")
    async def mc_player_list_command(self, event: AstrMessageEvent):
        """获取Minecraft服务器玩家列表的命令"""
        async for result in self._handle_command(event, self.command_handler.handle_player_list_command):
            yield result

    async def terminate(self):
        """插件终止时的清理工作"""
        logger.info("插件终止")
        
        # 保存路由器配置
        await self.adapter_router.save_config()
        
        # 关闭所有适配器
        await self.adapter_router.close_all_adapters()
        
        # 保存广播配置
        self.broadcast_config_manager.save_config()
        
        # 关闭RCON连接
        await self.rcon_manager.close()
        
        # 取消整点广播任务
        self.broadcast_scheduler.stop()
        
        # 清理平台适配器注册信息
        try:
            from astrbot.core.platform.register import platform_cls_map, platform_registry
            logger.debug(f"清理前 platform_cls_map: {list(platform_cls_map.keys())}")
            logger.debug(f"清理前 platform_registry: {[p.name for p in platform_registry]}")
            
            if "minecraft" in platform_cls_map:
                del platform_cls_map["minecraft"]
            for i, platform_metadata in enumerate(platform_registry):
                if platform_metadata.name == "minecraft":
                    del platform_registry[i]
                    break
                    
            logger.debug(f"清理后 platform_cls_map: {list(platform_cls_map.keys())}")
            logger.debug(f"清理后 platform_registry: {[p.name for p in platform_registry]}")
        except Exception as e:
            logger.error(f"清理 Minecraft 平台适配器注册信息失败: {str(e)}")

    async def get_minecraft_adapter(self, server_name: Optional[str] = None) -> Optional[MinecraftPlatformAdapter]:
        """获取指定的Minecraft平台适配器，如果未指定则获取主适配器"""
        if server_name:
            for adapter in self.adapter_router.get_all_adapters():
                if adapter.server_name == server_name or adapter.adapter_id == server_name:
                    return adapter
            return None
        return self.minecraft_adapter